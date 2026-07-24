import datetime
import math
import re
from io import BytesIO
from xml.etree import ElementTree
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


_INVALID_XML_CHARACTERS = re.compile(
    "[\x00-\x08\x0b\x0c\x0e-\x1f\u007f-\u0084\u0086-\u009f]"
)


def _column_name(number):
    name = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _safe_text(value):
    value = _INVALID_XML_CHARACTERS.sub("", str(value))
    return value[:32767]


def _excel_date(value):
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        value = datetime.datetime.combine(value, datetime.time())
    if value.tzinfo is not None:
        value = value.replace(tzinfo=None)
    return (value - datetime.datetime(1899, 12, 30)).total_seconds() / 86400


def _cell(reference, value, header=False):
    cell = ElementTree.Element("c", {"r": reference})
    if header:
        cell.set("s", "1")

    if value is None:
        cell.set("t", "inlineStr")
        inline = ElementTree.SubElement(cell, "is")
        ElementTree.SubElement(inline, "t")
    elif isinstance(value, bool):
        cell.set("t", "b")
        ElementTree.SubElement(cell, "v").text = "1" if value else "0"
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        cell.set("t", "n")
        number = value if math.isfinite(value) else 0
        ElementTree.SubElement(cell, "v").text = str(number)
    elif isinstance(value, (datetime.datetime, datetime.date)):
        cell.set("s", "2")
        cell.set("t", "n")
        ElementTree.SubElement(cell, "v").text = str(_excel_date(value))
    else:
        cell.set("t", "inlineStr")
        inline = ElementTree.SubElement(cell, "is")
        text = ElementTree.SubElement(inline, "t")
        text.text = _safe_text(value)
        if text.text and (text.text.startswith(" ") or text.text.endswith(" ")):
            text.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return cell


def _xml_bytes(element):
    return ElementTree.tostring(
        element, encoding="utf-8", xml_declaration=True, short_empty_elements=True
    )


def build_xlsx(headers, rows, sheet_name="Users"):
    """Build a simple, styled XLSX workbook without an external dependency."""
    namespace = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    ElementTree.register_namespace("", namespace)

    worksheet = ElementTree.Element("worksheet", {"xmlns": namespace})
    last_column = _column_name(max(len(headers), 1))
    last_row = max(len(rows) + 1, 1)
    ElementTree.SubElement(
        worksheet, "dimension", {"ref": "A1:{}{}".format(last_column, last_row)}
    )

    sheet_views = ElementTree.SubElement(worksheet, "sheetViews")
    sheet_view = ElementTree.SubElement(
        sheet_views, "sheetView", {"workbookViewId": "0"}
    )
    ElementTree.SubElement(
        sheet_view,
        "pane",
        {
            "ySplit": "1",
            "topLeftCell": "A2",
            "activePane": "bottomLeft",
            "state": "frozen",
        },
    )

    columns = ElementTree.SubElement(worksheet, "cols")
    for index, header in enumerate(headers, start=1):
        values = [header]
        values.extend(row[index - 1] for row in rows if len(row) >= index)
        width = min(max(max(len(str(value or "")) for value in values) + 2, 12), 32)
        ElementTree.SubElement(
            columns,
            "col",
            {
                "min": str(index),
                "max": str(index),
                "width": str(width),
                "customWidth": "1",
            },
        )

    sheet_data = ElementTree.SubElement(worksheet, "sheetData")
    header_row = ElementTree.SubElement(sheet_data, "row", {"r": "1"})
    for index, header in enumerate(headers, start=1):
        header_row.append(_cell("{}1".format(_column_name(index)), header, header=True))

    for row_number, values in enumerate(rows, start=2):
        row = ElementTree.SubElement(sheet_data, "row", {"r": str(row_number)})
        for column_number, value in enumerate(values, start=1):
            row.append(
                _cell(
                    "{}{}".format(_column_name(column_number), row_number),
                    value,
                )
            )

    ElementTree.SubElement(
        worksheet,
        "autoFilter",
        {"ref": "A1:{}{}".format(last_column, last_row)},
    )

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="{sheet_name}" sheetId="1" r:id="rId1"/></sheets>
</workbook>""".format(sheet_name=escape(_safe_text(sheet_name), {'"': "&quot;"}))
    workbook_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy-mm-dd hh:mm"/></numFmts>
  <fonts count="2">
    <font><sz val="11"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/><family val="2"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF343A40"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="3">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"><alignment vertical="center"/></xf>
    <xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""

    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/styles.xml", styles)
        archive.writestr("xl/worksheets/sheet1.xml", _xml_bytes(worksheet))
    output.seek(0)
    return output

"""
Beautiful, customizable HTML email templates used by the admin Bulk Email page.

Each template is a full HTML document with inline, email-client-friendly CSS.
Templates use double-brace placeholders that are substituted at send time (and
in the preview):

    {{ctf_name}} - the name of the CTF (from config)
    {{subject}}  - the email subject
    {{message}}  - the body the admin typed (plain text; newlines become <br>)
    {{name}}     - the recipient's username (per recipient; "there" in preview)
    {{email}}    - the recipient's email address
    {{year}}     - the current year

Admins can select a template to load its HTML into the editor and then freely
customize the markup before previewing/sending.
"""

import datetime
from html import escape


def _message_to_html(message):
    """Escape a plain-text message and turn blank lines into paragraphs."""
    if not message:
        return ""
    blocks = [b.strip() for b in message.replace("\r\n", "\n").split("\n\n")]
    html_blocks = []
    for block in blocks:
        if not block:
            continue
        html_blocks.append("<p>" + escape(block).replace("\n", "<br>") + "</p>")
    return "\n".join(html_blocks)


def render_email_html(
    html,
    ctf_name="",
    subject="",
    message="",
    name="",
    email="",
    escape_message=True,
    extra=None,
):
    """Substitute the template placeholders and return the final HTML.

    ``extra`` is an optional dict of admin-defined custom placeholders
    ({"discord_link": "https://..."} becomes ``{{discord_link}}``). Built-in
    placeholders always win over custom ones with the same name.
    """
    rendered_message = _message_to_html(message) if escape_message else (message or "")
    replacements = {}
    if extra:
        for key, value in extra.items():
            replacements["{{" + str(key) + "}}"] = escape(str(value))
    # Built-ins are applied last into the dict so they override any custom
    # placeholder that tries to reuse a reserved name.
    replacements.update(
        {
            "{{ctf_name}}": escape(ctf_name or ""),
            "{{subject}}": escape(subject or ""),
            "{{message}}": rendered_message,
            "{{name}}": escape(name or ""),
            "{{email}}": escape(email or ""),
            "{{year}}": str(datetime.datetime.utcnow().year),
        }
    )
    for token, value in replacements.items():
        html = html.replace(token, value)
    return html


# --- Templates ---------------------------------------------------------------

_ANNOUNCEMENT = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f2f4f8;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f2f4f8;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <tr><td style="background:#1f2937;padding:28px 32px;">
          <h1 style="margin:0;color:#ffffff;font-size:22px;letter-spacing:0.5px;">{{ctf_name}}</h1>
        </td></tr>
        <tr><td style="padding:32px;color:#374151;font-size:16px;line-height:1.6;">
          <p style="margin-top:0;font-size:18px;color:#111827;"><strong>Hi {{name}},</strong></p>
          {{message}}
        </td></tr>
        <tr><td style="padding:20px 32px;background:#f9fafb;border-top:1px solid #eef0f3;color:#9ca3af;font-size:12px;text-align:center;">
          You are receiving this email because you registered for {{ctf_name}}.<br>
          &copy; {{year}} {{ctf_name}}. All rights reserved.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

_EVENT = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0b1020;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0b1020;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#111634;border-radius:16px;overflow:hidden;">
        <tr><td style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:44px 32px;text-align:center;">
          <p style="margin:0 0 8px;color:#e0e7ff;font-size:13px;letter-spacing:2px;text-transform:uppercase;">You're invited</p>
          <h1 style="margin:0;color:#ffffff;font-size:28px;">{{subject}}</h1>
        </td></tr>
        <tr><td style="padding:32px;color:#c7cbe0;font-size:16px;line-height:1.7;">
          <p style="margin-top:0;color:#ffffff;font-size:18px;"><strong>Hey {{name}}!</strong></p>
          {{message}}
          <div style="text-align:center;margin:32px 0 8px;">
            <a href="#" style="display:inline-block;background:#6366f1;color:#ffffff;text-decoration:none;padding:14px 36px;border-radius:999px;font-weight:bold;font-size:16px;">Register / Join Now</a>
          </div>
        </td></tr>
        <tr><td style="padding:20px 32px;color:#6b7280;font-size:12px;text-align:center;border-top:1px solid #23294d;">
          &copy; {{year}} {{ctf_name}}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

_MINIMAL = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#ffffff;font-family:Georgia,'Times New Roman',serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:40px 0;">
    <tr><td align="center">
      <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">
        <tr><td style="border-bottom:2px solid #111827;padding-bottom:16px;">
          <h1 style="margin:0;color:#111827;font-size:24px;">{{ctf_name}}</h1>
        </td></tr>
        <tr><td style="padding:28px 0;color:#374151;font-size:17px;line-height:1.7;">
          <p style="margin-top:0;">Dear {{name}},</p>
          {{message}}
          <p style="margin-bottom:0;">&mdash; The {{ctf_name}} Team</p>
        </td></tr>
        <tr><td style="padding-top:16px;border-top:1px solid #e5e7eb;color:#9ca3af;font-size:12px;">
          &copy; {{year}} {{ctf_name}}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

_DARK = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0d1117;font-family:Consolas,Menlo,Monaco,monospace;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0d1117;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#161b22;border:1px solid #30363d;border-radius:10px;overflow:hidden;">
        <tr><td style="padding:24px 28px;border-bottom:1px solid #30363d;">
          <span style="color:#3fb950;font-size:14px;">&gt;_</span>
          <span style="color:#e6edf3;font-size:18px;font-weight:bold;margin-left:8px;">{{ctf_name}}</span>
        </td></tr>
        <tr><td style="padding:28px;color:#c9d1d9;font-size:15px;line-height:1.7;">
          <p style="margin-top:0;color:#58a6ff;">// Hello {{name}},</p>
          {{message}}
        </td></tr>
        <tr><td style="padding:18px 28px;border-top:1px solid #30363d;color:#8b949e;font-size:12px;">
          {{ctf_name}} &bull; {{year}}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


_TOMCTF_MENACE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#050303;font-family:Consolas,Menlo,Monaco,monospace;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#050303;padding:32px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#0a0505;border:1px solid #8b0000;border-radius:12px;overflow:hidden;box-shadow:0 0 40px rgba(236,19,19,0.35);">
        <tr><td style="background:#050303;padding:6px 0;">
          <div style="height:3px;background:linear-gradient(90deg,#050303,#ec1313,#8b0000,#ec1313,#050303);"></div>
        </td></tr>
        <tr><td style="padding:36px 32px 20px;text-align:center;">
          <p style="margin:0 0 10px;color:#8b0000;font-size:11px;letter-spacing:6px;text-transform:uppercase;">// transmission incoming //</p>
          <h1 style="margin:0;color:#ec1313;font-size:30px;letter-spacing:3px;text-transform:uppercase;text-shadow:0 0 18px rgba(236,19,19,0.8);">{{ctf_name}}</h1>
          <p style="margin:14px 0 0;color:#ff4444;font-size:14px;letter-spacing:1px;">{{subject}}</p>
        </td></tr>
        <tr><td style="padding:8px 32px;">
          <div style="border-top:1px dashed #8b0000;"></div>
        </td></tr>
        <tr><td style="padding:24px 32px;color:#d4d4d4;font-size:15px;line-height:1.8;">
          <p style="margin-top:0;color:#ec1313;"><strong>&gt; TARGET IDENTIFIED: {{name}}</strong></p>
          {{message}}
        </td></tr>
        <tr><td style="padding:8px 32px 28px;text-align:center;">
          <div style="display:inline-block;border:1px solid #ec1313;color:#ec1313;padding:12px 34px;font-size:13px;letter-spacing:3px;text-transform:uppercase;border-radius:4px;box-shadow:0 0 20px rgba(236,19,19,0.3),inset 0 0 12px rgba(236,19,19,0.12);">
            The clock is ticking
          </div>
        </td></tr>
        <tr><td style="padding:18px 32px;background:#050303;border-top:1px solid #1a0a0a;text-align:center;">
          <p style="margin:0;color:#8E8E93;font-size:11px;letter-spacing:1px;">
            {{ctf_name}} &bull; {{year}} &bull; <span style="color:#8b0000;">we are watching</span>
          </p>
        </td></tr>
        <tr><td style="background:#050303;padding:0 0 6px;">
          <div style="height:3px;background:linear-gradient(90deg,#050303,#8b0000,#ec1313,#8b0000,#050303);"></div>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# Ordered mapping of template id -> metadata + HTML
EMAIL_TEMPLATES = {
    "tomctf": {
        "name": "TomCTF Menace",
        "description": "Menacing dark-red cyberpunk look matching the TomCTF site theme.",
        "html": _TOMCTF_MENACE,
    },
    "announcement": {
        "name": "Announcement",
        "description": "Clean branded header with a light body. Great for updates.",
        "html": _ANNOUNCEMENT,
    },
    "event": {
        "name": "Event Invitation",
        "description": "Bold gradient hero with a call-to-action button.",
        "html": _EVENT,
    },
    "minimal": {
        "name": "Minimal",
        "description": "Simple, elegant, serif typography. Letter-style.",
        "html": _MINIMAL,
    },
    "dark": {
        "name": "Dark / Terminal",
        "description": "Dark hacker-style theme with monospace font.",
        "html": _DARK,
    },
}


def get_template_html(template_id):
    template = EMAIL_TEMPLATES.get(template_id)
    return template["html"] if template else None

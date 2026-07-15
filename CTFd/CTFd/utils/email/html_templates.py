"""
Cyber-themed HTML email templates used by the admin Bulk Email page.

Each template is a full HTML document with inline, email-client-friendly CSS.
Templates use double-brace placeholders that are substituted at send time (and
in the preview):

    {{ctf_name}}        - the name of the CTF (configurable on the compose form)
    {{subject}}         - the email subject
    {{message}}         - the body the admin typed (plain text; newlines become <br>)
    {{name}}            - the recipient's username (per recipient)
    {{email}}           - the recipient's email address (per recipient)
    {{register_number}} - the recipient's register number (per recipient)
    {{date}}            - configurable date (defaults to today)
    {{year}}            - the current year

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

_RED_VS_BLUE = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#07070d;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#07070d;padding:32px 0;">
    <tr><td align="center">
      <table role="presentation" width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;background:#0d0d16;border-radius:14px;overflow:hidden;box-shadow:0 10px 50px rgba(0,0,0,0.7);">
        <!-- Split header: red vs blue -->
        <tr>
          <td style="padding:0;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="50%" style="background:linear-gradient(135deg,#3b0000,#b91c1c);padding:26px 10px;text-align:center;">
                  <p style="margin:0;color:#fecaca;font-size:11px;letter-spacing:4px;">OFFENSE</p>
                  <h2 style="margin:6px 0 0;color:#ffffff;font-size:22px;letter-spacing:2px;text-shadow:0 0 12px rgba(255,60,60,0.9);">RED TEAM</h2>
                </td>
                <td width="50%" style="background:linear-gradient(225deg,#001a3b,#1d4ed8);padding:26px 10px;text-align:center;">
                  <p style="margin:0;color:#bfdbfe;font-size:11px;letter-spacing:4px;">DEFENSE</p>
                  <h2 style="margin:6px 0 0;color:#ffffff;font-size:22px;letter-spacing:2px;text-shadow:0 0 12px rgba(60,130,255,0.9);">BLUE TEAM</h2>
                </td>
              </tr>
            </table>
            <div style="height:4px;background:linear-gradient(90deg,#b91c1c 0%,#b91c1c 48%,#ffffff 50%,#1d4ed8 52%,#1d4ed8 100%);"></div>
          </td>
        </tr>
        <tr><td style="padding:30px 34px 6px;text-align:center;">
          <p style="margin:0;color:#71717a;font-size:12px;letter-spacing:5px;text-transform:uppercase;">{{ctf_name}} presents</p>
          <h1 style="margin:10px 0 0;color:#f4f4f5;font-size:26px;letter-spacing:1px;">{{subject}}</h1>
        </td></tr>
        <tr><td style="padding:22px 34px;color:#d4d4d8;font-size:15px;line-height:1.75;">
          <p style="margin-top:0;"><strong style="color:#f87171;">Operative {{name}}</strong> <span style="color:#71717a;">// pick your side.</span></p>
          {{message}}
        </td></tr>
        <tr><td style="padding:4px 34px 30px;text-align:center;">
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
            <tr>
              <td style="padding:0 8px;">
                <div style="border:1px solid #b91c1c;background:rgba(185,28,28,0.12);color:#f87171;padding:11px 26px;font-size:12px;letter-spacing:3px;border-radius:6px;font-weight:bold;">ATTACK</div>
              </td>
              <td style="color:#52525b;font-size:14px;font-weight:bold;">VS</td>
              <td style="padding:0 8px;">
                <div style="border:1px solid #1d4ed8;background:rgba(29,78,216,0.12);color:#60a5fa;padding:11px 26px;font-size:12px;letter-spacing:3px;border-radius:6px;font-weight:bold;">DEFEND</div>
              </td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="padding:16px 34px;background:#08080f;border-top:1px solid #1c1c2a;text-align:center;">
          <p style="margin:0;color:#52525b;font-size:11px;letter-spacing:1px;">{{ctf_name}} &bull; {{date}} &bull; {{year}}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

_BREACH = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#000000;font-family:Consolas,Menlo,Monaco,'Courier New',monospace;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#000000;padding:32px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#020a02;border:1px solid #00ff41;border-radius:8px;overflow:hidden;box-shadow:0 0 35px rgba(0,255,65,0.25);">
        <!-- Terminal title bar -->
        <tr><td style="background:#0a1a0a;padding:10px 16px;border-bottom:1px solid #00ff41;">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ff5f56;margin-right:5px;"></span>
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#ffbd2e;margin-right:5px;"></span>
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#27c93f;"></span>
          <span style="color:#00ff41;font-size:12px;margin-left:12px;">root@{{ctf_name}}:~#</span>
        </td></tr>
        <tr><td style="padding:26px 28px 10px;">
          <p style="margin:0;color:#00ff41;font-size:13px;line-height:1.9;">
            <span style="color:#008f11;">$</span> ./initiate_breach.sh --target {{name}}<br>
            <span style="color:#008f11;">[*]</span> scanning target............ <span style="color:#00ff41;">DONE</span><br>
            <span style="color:#008f11;">[*]</span> bypassing perimeter........ <span style="color:#00ff41;">DONE</span><br>
            <span style="color:#008f11;">[!]</span> <span style="color:#39ff14;font-weight:bold;">ACCESS GRANTED</span>
          </p>
        </td></tr>
        <tr><td style="padding:8px 28px 4px;text-align:center;">
          <h1 style="margin:0;color:#39ff14;font-size:26px;letter-spacing:4px;text-transform:uppercase;text-shadow:0 0 14px rgba(57,255,20,0.8);">SYSTEM BREACHED</h1>
          <p style="margin:8px 0 0;color:#008f11;font-size:13px;letter-spacing:2px;">{{subject}}</p>
        </td></tr>
        <tr><td style="padding:20px 28px;color:#b7ffc9;font-size:14px;line-height:1.8;">
          <p style="margin-top:0;color:#00ff41;">&gt; incoming payload for <span style="text-decoration:underline;">{{name}}</span>:</p>
          {{message}}
          <p style="margin-bottom:0;color:#008f11;">&gt; transmission ends. leave no trace. <span style="color:#39ff14;">_</span></p>
        </td></tr>
        <tr><td style="padding:14px 28px;background:#010401;border-top:1px dashed #008f11;text-align:center;">
          <p style="margin:0;color:#008f11;font-size:11px;letter-spacing:2px;">{{ctf_name}} // {{date}} // uid={{email}}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

_CLASSIFIED = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#181512;font-family:'Courier New',Courier,monospace;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#181512;padding:32px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#f0e9d8;border-radius:4px;overflow:hidden;box-shadow:0 14px 40px rgba(0,0,0,0.8);">
        <tr><td style="background:#1c1a17;padding:14px 26px;">
          <table role="presentation" width="100%"><tr>
            <td style="color:#c8b98a;font-size:12px;letter-spacing:3px;">FILE #{{year}}-{{register_number}}</td>
            <td align="right" style="color:#c8b98a;font-size:12px;letter-spacing:3px;">{{date}}</td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:30px 34px 8px;text-align:center;">
          <div style="display:inline-block;border:4px double #a11212;color:#a11212;padding:8px 30px;font-size:24px;font-weight:bold;letter-spacing:8px;transform:rotate(-3deg);">TOP&nbsp;SECRET</div>
          <p style="margin:18px 0 0;color:#57534e;font-size:12px;letter-spacing:4px;">EYES ONLY &mdash; OPERATION: {{ctf_name}}</p>
        </td></tr>
        <tr><td style="padding:20px 34px 6px;">
          <table role="presentation" width="100%" style="border:1px solid #a8a29e;border-collapse:collapse;">
            <tr>
              <td style="border:1px solid #a8a29e;padding:8px 12px;color:#44403c;font-size:12px;width:40%;"><strong>AGENT:</strong> {{name}}</td>
              <td style="border:1px solid #a8a29e;padding:8px 12px;color:#44403c;font-size:12px;"><strong>CONTACT:</strong> {{email}}</td>
            </tr>
            <tr>
              <td style="border:1px solid #a8a29e;padding:8px 12px;color:#44403c;font-size:12px;"><strong>ID:</strong> {{register_number}}</td>
              <td style="border:1px solid #a8a29e;padding:8px 12px;color:#44403c;font-size:12px;"><strong>RE:</strong> {{subject}}</td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="padding:20px 34px;color:#292524;font-size:14px;line-height:1.8;">
          <p style="margin-top:0;"><strong>BRIEFING FOLLOWS:</strong></p>
          {{message}}
          <p style="margin-bottom:0;color:#78716c;font-size:12px;">This document will self-destruct after the event. Unauthorized disclosure is punishable by challenge flags.</p>
        </td></tr>
        <tr><td style="padding:14px 34px;background:#1c1a17;text-align:center;">
          <p style="margin:0;color:#a8956a;font-size:11px;letter-spacing:3px;">CLASSIFIED &bull; {{ctf_name}} COMMAND &bull; {{year}}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

_NEON_GRID = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#0a0118;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#0a0118;padding:32px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#120826;border:1px solid #7c3aed;border-radius:16px;overflow:hidden;box-shadow:0 0 45px rgba(124,58,237,0.4);">
        <tr><td style="background:linear-gradient(180deg,#2e1065 0%,#120826 100%);padding:40px 32px 30px;text-align:center;">
          <p style="margin:0 0 12px;color:#22d3ee;font-size:12px;letter-spacing:6px;text-transform:uppercase;text-shadow:0 0 10px rgba(34,211,238,0.9);">&#9650; enter the grid &#9650;</p>
          <h1 style="margin:0;font-size:32px;letter-spacing:2px;text-transform:uppercase;color:#f0abfc;text-shadow:0 0 20px rgba(240,171,252,0.8),0 0 40px rgba(124,58,237,0.6);">{{ctf_name}}</h1>
          <div style="margin:18px auto 0;width:180px;height:2px;background:linear-gradient(90deg,transparent,#22d3ee,transparent);"></div>
        </td></tr>
        <tr><td style="padding:10px 32px 0;text-align:center;">
          <p style="margin:0;color:#a78bfa;font-size:16px;letter-spacing:1px;">{{subject}}</p>
        </td></tr>
        <tr><td style="padding:22px 32px;color:#ddd6fe;font-size:15px;line-height:1.75;">
          <p style="margin-top:0;"><span style="color:#22d3ee;font-weight:bold;">{{name}}</span><span style="color:#7c3aed;"> :: connection established</span></p>
          {{message}}
        </td></tr>
        <tr><td style="padding:4px 32px 30px;text-align:center;">
          <div style="display:inline-block;background:linear-gradient(90deg,#7c3aed,#d946ef);color:#ffffff;padding:13px 40px;border-radius:999px;font-size:14px;font-weight:bold;letter-spacing:2px;box-shadow:0 0 22px rgba(217,70,239,0.6);">JACK IN</div>
        </td></tr>
        <tr><td style="padding:16px 32px;background:#0d051c;border-top:1px solid #2e1065;text-align:center;">
          <p style="margin:0;color:#6d28d9;font-size:11px;letter-spacing:2px;">{{ctf_name}} &loz; {{date}} &loz; {{year}}</p>
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
    "redvsblue": {
        "name": "Red vs Blue",
        "description": "Split red team / blue team battle design. Attack vs defend.",
        "html": _RED_VS_BLUE,
    },
    "breach": {
        "name": "System Breach",
        "description": "Green-on-black hacker terminal with a breach log intro.",
        "html": _BREACH,
    },
    "classified": {
        "name": "Classified Dossier",
        "description": "Top-secret file with agent details table and stamp.",
        "html": _CLASSIFIED,
    },
    "neon": {
        "name": "Neon Grid",
        "description": "Synthwave purple/cyan cyber grid with glowing CTA.",
        "html": _NEON_GRID,
    },
}


def get_template_html(template_id):
    template = EMAIL_TEMPLATES.get(template_id)
    return template["html"] if template else None

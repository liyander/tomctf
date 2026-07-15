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
import re
from html import escape


_PLACEHOLDER_RE = re.compile(r"{{([A-Za-z0-9_]+)}}")


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
    date="",
    register_number="",
    escape_message=True,
    extra=None,
):
    """Substitute the template placeholders and return the final HTML.

    ``extra`` is an optional dict of admin-defined custom placeholders
    ({"discord_link": "https://..."} becomes ``{{discord_link}}``). Built-in
    placeholders always win over custom ones with the same name.
    """
    rendered_message = _message_to_html(message) if escape_message else (message or "")
    today = datetime.date.today().strftime("%d %B %Y")
    custom = {str(key): escape(str(value)) for key, value in (extra or {}).items()}

    # Keep compatibility with the bulk-mail sender, which historically passed
    # these two values through ``extra``.
    date = date or custom.pop("date", "") or today
    register_number = register_number or custom.pop("register_number", "")
    replacements = custom
    replacements.update(
        {
            "ctf_name": escape(ctf_name or ""),
            "subject": escape(subject or ""),
            "message": rendered_message,
            "name": escape(name or ""),
            "email": escape(email or ""),
            "date": escape(str(date)),
            "register_number": escape(str(register_number)),
            "year": str(datetime.datetime.now(datetime.timezone.utc).year),
        }
    )

    # One regex pass prevents values containing placeholder-like text from
    # being substituted a second time. Unknown placeholders remain editable.
    return _PLACEHOLDER_RE.sub(
        lambda match: replacements.get(match.group(1), match.group(0)), html
    )


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
        <!-- Split header: red vs blue over the green network -->
        <tr>
          <td style="padding:0;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td width="37%" style="background:linear-gradient(135deg,#3b0000,#b91c1c);padding:26px 8px;text-align:center;">
                  <p style="margin:0;color:#fecaca;font-size:11px;letter-spacing:4px;">OFFENSE</p>
                  <h2 style="margin:6px 0 0;color:#ffffff;font-size:21px;letter-spacing:2px;text-shadow:0 0 12px rgba(255,60,60,0.9);">RED TEAM</h2>
                </td>
                <td width="26%" style="background:linear-gradient(180deg,#02180a,#065f46);padding:26px 6px;text-align:center;border-left:1px solid rgba(16,185,129,0.5);border-right:1px solid rgba(16,185,129,0.5);">
                  <p style="margin:0;color:#a7f3d0;font-size:11px;letter-spacing:4px;">THE FIELD</p>
                  <h2 style="margin:6px 0 0;color:#34d399;font-size:18px;letter-spacing:2px;text-shadow:0 0 14px rgba(52,211,153,0.9);">NETWORK</h2>
                </td>
                <td width="37%" style="background:linear-gradient(225deg,#001a3b,#1d4ed8);padding:26px 8px;text-align:center;">
                  <p style="margin:0;color:#bfdbfe;font-size:11px;letter-spacing:4px;">DEFENSE</p>
                  <h2 style="margin:6px 0 0;color:#ffffff;font-size:21px;letter-spacing:2px;text-shadow:0 0 12px rgba(60,130,255,0.9);">BLUE TEAM</h2>
                </td>
              </tr>
            </table>
            <div style="height:4px;background:linear-gradient(90deg,#b91c1c 0%,#b91c1c 34%,#10b981 50%,#1d4ed8 66%,#1d4ed8 100%);"></div>
          </td>
        </tr>
        <tr><td style="padding:30px 34px 6px;text-align:center;">
          <p style="margin:0;color:#71717a;font-size:12px;letter-spacing:5px;text-transform:uppercase;">{{ctf_name}} presents</p>
          <h1 style="margin:10px 0 0;color:#f4f4f5;font-size:26px;letter-spacing:1px;">{{subject}}</h1>
        </td></tr>
        <tr><td style="padding:22px 34px;color:#d4d4d8;font-size:15px;line-height:1.75;">
          <p style="margin-top:0;"><strong style="color:#f87171;">Operative {{name}}</strong> <span style="color:#71717a;">// pick your side. the</span> <span style="color:#34d399;">network</span> <span style="color:#71717a;">is the battlefield.</span></p>
          {{message}}
        </td></tr>
        <tr><td style="padding:4px 34px 30px;text-align:center;">
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
            <tr>
              <td style="padding:0 8px;">
                <div style="border:1px solid #b91c1c;background:rgba(185,28,28,0.12);color:#f87171;padding:11px 26px;font-size:12px;letter-spacing:3px;border-radius:6px;font-weight:bold;">ATTACK</div>
              </td>
              <td style="padding:0 8px;">
                <div style="border:1px solid #10b981;background:rgba(16,185,129,0.12);color:#34d399;padding:11px 26px;font-size:12px;letter-spacing:3px;border-radius:6px;font-weight:bold;box-shadow:0 0 14px rgba(16,185,129,0.35);">NETWORK</div>
              </td>
              <td style="padding:0 8px;">
                <div style="border:1px solid #1d4ed8;background:rgba(29,78,216,0.12);color:#60a5fa;padding:11px 26px;font-size:12px;letter-spacing:3px;border-radius:6px;font-weight:bold;">DEFEND</div>
              </td>
            </tr>
          </table>
        </td></tr>
        <tr><td style="padding:16px 34px;background:#08080f;border-top:1px solid #1c1c2a;text-align:center;">
          <p style="margin:0;color:#52525b;font-size:11px;letter-spacing:1px;">{{ctf_name}} <span style="color:#10b981;">&bull;</span> {{date}} <span style="color:#10b981;">&bull;</span> {{year}}</p>
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

_ZERO_DAY = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#05070b;font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;color:#05070b;">Priority zero-day intelligence from {{ctf_name}}.</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#05070b;padding:32px 10px;">
    <tr><td align="center">
      <table role="presentation" width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;background:#0b1018;border:1px solid #293241;border-radius:10px;overflow:hidden;">
        <tr><td style="background:#f97316;padding:9px 28px;color:#160800;font-size:11px;font-weight:bold;letter-spacing:4px;text-align:center;">CRITICAL // ZERO-DAY ADVISORY // PRIORITY 0</td></tr>
        <tr><td style="padding:30px 32px 18px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            <td>
              <p style="margin:0 0 7px;color:#64748b;font:12px Consolas,monospace;letter-spacing:2px;">CVE-{{year}}-0CTF</p>
              <h1 style="margin:0;color:#f8fafc;font-size:28px;line-height:1.2;">{{subject}}</h1>
            </td>
            <td width="92" align="right"><div style="border:2px solid #f97316;color:#fb923c;padding:9px 6px;text-align:center;font:bold 22px Consolas,monospace;border-radius:5px;">10.0<div style="font-size:8px;letter-spacing:2px;margin-top:4px;">SEVERITY</div></div></td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:0 32px;"><div style="height:1px;background:#293241;"></div></td></tr>
        <tr><td style="padding:22px 32px;color:#cbd5e1;font-size:15px;line-height:1.75;">
          <p style="margin-top:0;color:#94a3b8;">Researcher <strong style="color:#fb923c;">{{name}}</strong>, a high-impact condition has been detected in the challenge infrastructure.</p>
          {{message}}
        </td></tr>
        <tr><td style="padding:0 32px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#111827;border-left:3px solid #f97316;"><tr><td style="padding:13px 16px;color:#94a3b8;font:12px Consolas,monospace;line-height:1.7;">
            VECTOR&nbsp;&nbsp; NETWORK / USER INTERACTION<br>
            STATUS&nbsp;&nbsp; <span style="color:#fb923c;">UNPATCHED &mdash; EXPLOIT RESPONSIBLY</span><br>
            DISCLOSED {{date}}
          </td></tr></table>
        </td></tr>
        <tr><td style="padding:16px 32px;background:#070b11;text-align:center;color:#475569;font-size:10px;letter-spacing:2px;">{{ctf_name}} VULNERABILITY RESEARCH // {{year}}</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

_SOC_COMMAND = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#06111a;font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;color:#06111a;">Security operations dispatch for {{name}}.</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#06111a;padding:32px 10px;">
    <tr><td align="center">
      <table role="presentation" width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;background:#091923;border:1px solid #164e63;border-radius:12px;overflow:hidden;box-shadow:0 0 35px rgba(6,182,212,.15);">
        <tr><td style="padding:24px 30px;background:#07141d;border-bottom:1px solid #164e63;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            <td><p style="margin:0;color:#22d3ee;font-size:11px;font-weight:bold;letter-spacing:4px;">&#9678; SECURITY OPERATIONS CENTER</p><h1 style="margin:7px 0 0;color:#ecfeff;font-size:22px;">{{ctf_name}}</h1></td>
            <td align="right"><span style="display:inline-block;background:#083344;border:1px solid #06b6d4;color:#67e8f9;padding:7px 10px;border-radius:4px;font:10px Consolas,monospace;letter-spacing:2px;">STATUS: ACTIVE</span></td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:24px 30px 10px;">
          <p style="margin:0;color:#64748b;font:11px Consolas,monospace;letter-spacing:2px;">INCIDENT / {{register_number}} &nbsp;&bull;&nbsp; {{date}}</p>
          <h2 style="margin:9px 0 0;color:#f8fafc;font-size:25px;">{{subject}}</h2>
        </td></tr>
        <tr><td style="padding:15px 30px 22px;color:#cbd5e1;font-size:15px;line-height:1.75;">
          <p style="margin-top:0;">Analyst <strong style="color:#67e8f9;">{{name}}</strong>, this secure dispatch requires your attention.</p>
          {{message}}
        </td></tr>
        <tr><td style="padding:0 30px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
            <td width="31%" style="background:#0c2430;border-top:2px solid #22d3ee;padding:12px;text-align:center;color:#64748b;font-size:9px;letter-spacing:2px;">DETECT<div style="color:#67e8f9;font-size:13px;font-weight:bold;margin-top:6px;">SIGNAL</div></td>
            <td width="3%"></td>
            <td width="32%" style="background:#0c2430;border-top:2px solid #a78bfa;padding:12px;text-align:center;color:#64748b;font-size:9px;letter-spacing:2px;">ANALYZE<div style="color:#c4b5fd;font-size:13px;font-weight:bold;margin-top:6px;">THREAT</div></td>
            <td width="3%"></td>
            <td width="31%" style="background:#0c2430;border-top:2px solid #34d399;padding:12px;text-align:center;color:#64748b;font-size:9px;letter-spacing:2px;">RESPOND<div style="color:#6ee7b7;font-size:13px;font-weight:bold;margin-top:6px;">CONTAIN</div></td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:15px 30px;background:#061018;border-top:1px solid #12303d;color:#45606d;font:10px Consolas,monospace;text-align:center;letter-spacing:2px;">AUTHORIZED RECIPIENT: {{email}} // SOC-{{year}}</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

_MISSION_BRIEF = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#07100a;font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;color:#07100a;">Your next operation has been assigned.</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#07100a;padding:32px 10px;">
    <tr><td align="center">
      <table role="presentation" width="620" cellpadding="0" cellspacing="0" style="max-width:620px;width:100%;background:#101810;border:1px solid #3f6212;border-radius:4px;overflow:hidden;">
        <tr><td style="padding:12px 28px;background:#365314;color:#ecfccb;font:10px Consolas,monospace;letter-spacing:3px;">
          <table role="presentation" width="100%"><tr><td>FIELD OPERATIONS // {{ctf_name}}</td><td align="right">{{date}}</td></tr></table>
        </td></tr>
        <tr><td style="padding:32px 32px 16px;text-align:center;">
          <div style="display:inline-block;border:1px solid #65a30d;border-radius:50%;width:66px;height:66px;line-height:66px;color:#bef264;font:bold 26px Consolas,monospace;box-shadow:inset 0 0 0 5px #17230f;">M-{{register_number}}</div>
          <p style="margin:16px 0 7px;color:#84a45c;font-size:10px;letter-spacing:5px;">NEW OBJECTIVE UNLOCKED</p>
          <h1 style="margin:0;color:#f7fee7;font-size:27px;text-transform:uppercase;letter-spacing:1px;">{{subject}}</h1>
        </td></tr>
        <tr><td style="padding:16px 32px;color:#d9f99d;font-size:15px;line-height:1.8;">
          <p style="margin-top:0;color:#a3b58c;">Operator <strong style="color:#bef264;">{{name}}</strong>, command has issued the following mission parameters:</p>
          {{message}}
        </td></tr>
        <tr><td style="padding:0 32px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px dashed #4d7c0f;"><tr><td style="padding:14px 18px;color:#78905d;font:11px Consolas,monospace;line-height:1.8;">
            RULE 01 &nbsp;<span style="color:#bef264;">ENUMERATE EVERYTHING</span><br>
            RULE 02 &nbsp;<span style="color:#bef264;">TRUST NO INPUT</span><br>
            RULE 03 &nbsp;<span style="color:#bef264;">CAPTURE THE FLAG</span>
          </td></tr></table>
        </td></tr>
        <tr><td style="padding:15px 32px;background:#090f08;text-align:center;color:#536445;font-size:10px;letter-spacing:3px;">PLAN // EXPLOIT // DOCUMENT // EXFILTRATE</td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

_FLAG_CAPTURED = """<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#080510;font-family:Arial,Helvetica,sans-serif;">
  <div style="display:none;max-height:0;overflow:hidden;color:#080510;">Achievement unlocked in {{ctf_name}}.</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#080510;padding:32px 10px;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#120c20;border:1px solid #f59e0b;border-radius:14px;overflow:hidden;box-shadow:0 0 42px rgba(245,158,11,.22);">
        <tr><td style="height:5px;background:#f59e0b;font-size:0;">&nbsp;</td></tr>
        <tr><td style="padding:38px 32px 18px;text-align:center;">
          <div style="font-size:52px;line-height:1;color:#fbbf24;text-shadow:0 0 22px rgba(251,191,36,.65);">&#9873;</div>
          <p style="margin:13px 0 7px;color:#c084fc;font-size:11px;font-weight:bold;letter-spacing:5px;">ACHIEVEMENT UNLOCKED</p>
          <h1 style="margin:0;color:#fef3c7;font-size:30px;letter-spacing:2px;">FLAG CAPTURED</h1>
          <p style="margin:10px 0 0;color:#f59e0b;font-size:15px;">{{subject}}</p>
        </td></tr>
        <tr><td style="padding:15px 34px 20px;color:#e9d5ff;font-size:15px;line-height:1.75;text-align:left;">
          <p style="margin-top:0;text-align:center;color:#a78bfa;">Outstanding work, <strong style="color:#fbbf24;">{{name}}</strong>.</p>
          {{message}}
        </td></tr>
        <tr><td style="padding:0 34px 30px;text-align:center;">
          <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;background:#1d1430;border:1px solid #6d28d9;border-radius:8px;"><tr>
            <td style="padding:14px 22px;border-right:1px solid #6d28d9;"><div style="color:#7c6a96;font-size:9px;letter-spacing:2px;">PLAYER</div><div style="color:#f5d0fe;font-size:13px;margin-top:5px;">{{name}}</div></td>
            <td style="padding:14px 22px;"><div style="color:#7c6a96;font-size:9px;letter-spacing:2px;">OPERATION</div><div style="color:#f5d0fe;font-size:13px;margin-top:5px;">{{ctf_name}}</div></td>
          </tr></table>
        </td></tr>
        <tr><td style="padding:16px 32px;background:#0c0815;text-align:center;color:#5b4b72;font-size:10px;letter-spacing:2px;">KEEP HACKING // KEEP LEARNING // {{year}}</td></tr>
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
    "zeroday": {
        "name": "Zero-Day Advisory",
        "description": "Critical vulnerability bulletin styled like a CVE intelligence alert.",
        "html": _ZERO_DAY,
    },
    "soc": {
        "name": "SOC Command Center",
        "description": "Polished security-operations dispatch with incident status panels.",
        "html": _SOC_COMMAND,
    },
    "mission": {
        "name": "Mission Brief",
        "description": "Tactical field-operations briefing for challenges and event missions.",
        "html": _MISSION_BRIEF,
    },
    "captured": {
        "name": "Flag Captured",
        "description": "Gold and ultraviolet achievement email for winners and milestones.",
        "html": _FLAG_CAPTURED,
    },
}


def get_template_html(template_id):
    template = EMAIL_TEMPLATES.get(template_id)
    return template["html"] if template else None

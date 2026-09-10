"""Dark-mode-safe colors for HTML email previews."""

from __future__ import annotations

THEME = {
    "bg": "#0f172a",
    "card": "#1e293b",
    "text": "#e2e8f0",
    "muted": "#94a3b8",
    "accent": "#818cf8",
    "border": "#334155",
}


def render_html(body_text: str, *, name: str = "Message") -> str:
    escaped = (
        body_text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="color-scheme" content="light dark"/>
  <title>{name}</title>
</head>
<body style="margin:0;background:{THEME['bg']};color:{THEME['text']};font-family:Georgia,serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{THEME['bg']};">
    <tr>
      <td align="center" style="padding:24px;">
        <table role="presentation" width="560" cellpadding="0" cellspacing="0" style="background:{THEME['card']};border:1px solid {THEME['border']};border-radius:12px;">
          <tr>
            <td style="padding:28px 32px;color:{THEME['text']};font-size:16px;line-height:1.5;">
              <p style="margin:0 0 12px;color:{THEME['accent']};font-size:13px;letter-spacing:0.04em;">{name}</p>
              <div>{escaped}</div>
              <p style="margin:24px 0 0;color:{THEME['muted']};font-size:12px;">Sent with AJAS. Colors stay readable in dark inboxes.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

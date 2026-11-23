"""General-purpose branded email sending for the site itself (as opposed to
anusport_sync.py's membership renewal/welcome emails, which are specific to
that feature) -- currently just the forgot-password email."""

import smtplib
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

import config

LOGO_PATH = Path(__file__).resolve().parent / "static" / "site" / "nucc-logo.png"
LOGO_CID = "nucc_logo"

_HTML_TEMPLATE = """\
<!doctype html>
<html>
<body style="margin:0; padding:24px; background:#e9ebee; font-family: -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:480px; margin:0 auto; background:#ffffff; border-radius:10px; overflow:hidden; border:1px solid #dddfe2;">
    <tr>
      <td style="background:#ffffff; padding:28px 24px; text-align:center; border-bottom:3px solid #1877f2;">
        <img src="cid:{logo_cid}" width="110" alt="NUCC" style="display:block; margin:0 auto;">
      </td>
    </tr>
    <tr>
      <td style="padding:32px 28px 8px;">
        <h1 style="margin:0 0 4px; font-size:20px; color:#1c1e21;">Reset your password</h1>
        <p style="margin:0; color:#65676b; font-size:14px;">National University Caving Club</p>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 28px 0; font-size:15px; line-height:1.5; color:#1c1e21;">
        <p>Someone (hopefully you) asked to reset the password for this email address.
        Click below to choose a new one -- this link works once, and expires in an hour.</p>
      </td>
    </tr>
    <tr>
      <td style="padding:16px 28px 32px; text-align:center;">
        <a href="{reset_url}" style="display:inline-block; background:#1877f2; color:#ffffff; text-decoration:none; padding:10px 20px; border-radius:6px; font-weight:600;">Choose a new password</a>
      </td>
    </tr>
    <tr>
      <td style="padding:0 28px 32px; font-size:13px; line-height:1.5; color:#65676b;">
        <p>If you didn't request this, you can safely ignore this email -- your password hasn't been changed.</p>
      </td>
    </tr>
    <tr>
      <td style="padding:20px 28px; background:#f7f8fa; border-top:1px solid #e4e6eb; text-align:center;">
        <p style="margin:0; font-size:12px; color:#8a8d91;">National University Caving Club &middot; nucc.anumc.org.au</p>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """Sends the branded reset-password email via SMTP if config.SMTP_HOST
    is set; otherwise prints the link to stdout. Returns whether an actual
    SMTP send was attempted. Callers must not use this return value to
    decide what to tell the user -- always show the same "if that email
    exists..." message regardless, so an outside observer can't use the
    response to probe which emails have accounts."""
    if not config.SMTP_HOST:
        print(f"[email_notify] SMTP not configured -- password reset link for {to_email}: {reset_url}")
        return False

    msg = MIMEMultipart("related")
    msg["Subject"] = "Reset your NUCC password"
    msg["From"] = formataddr(("NUCC", config.SMTP_SENDER))
    msg["To"] = to_email

    alternative = MIMEMultipart("alternative")
    alternative.attach(MIMEText(f"Reset your password: {reset_url}\n\nIf you didn't request this, ignore this email.", "plain"))
    alternative.attach(MIMEText(_HTML_TEMPLATE.format(logo_cid=LOGO_CID, reset_url=reset_url), "html"))
    msg.attach(alternative)

    try:
        logo_bytes = LOGO_PATH.read_bytes()
        logo_part = MIMEImage(logo_bytes, _subtype="png", name="nucc-logo.png")
        logo_part["Content-ID"] = f"<{LOGO_CID}>"
        logo_part["Content-Disposition"] = "inline; filename=nucc-logo.png"
        msg.attach(logo_part)
    except OSError as exc:
        print(f"[email_notify] Couldn't read logo at {LOGO_PATH}, sending without it: {exc}")

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            server.starttls()
            if config.SMTP_USERNAME:
                server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_SENDER, [to_email], msg.as_string())
        return True
    except Exception:
        return False

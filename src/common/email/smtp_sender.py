import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from common.const.settings import settings


def send_email_html(*, to: str, subject: str, html: str, text_fallback: str) -> None:
    if not (settings.SMTP_HOST and settings.SMTP_PORT and settings.SMTP_USER and settings.SMTP_PASSWORD):
        print(f"[MAIL-DEBUG]\nTO: {to}\nSUBJECT: {subject}\n{text_fallback}\n")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_SENDER
    msg["To"] = to
    msg.attach(MIMEText(text_fallback, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL(settings.SMTP_HOST, int(settings.SMTP_PORT)) as s:
        s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        s.sendmail(settings.SMTP_SENDER, [to], msg.as_string())

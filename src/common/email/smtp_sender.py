# src/common/email/smtp_sender.py
"""공용 SMTP 이메일 발송 유틸리티."""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from common.const.settings import settings


def send_email_html(*, to: str, subject: str, html: str, text_fallback: str) -> None:
    """SMTP 설정이 없으면 콘솔로 프리뷰 출력, 있으면 실제 발송."""
    if not (settings.SMTP_HOST and settings.SMTP_PORT and settings.SMTP_USER and settings.SMTP_PASSWORD):
        print(f"[MAIL-DEBUG]\nTO: {to}\nSUBJECT: {subject}\n{text_fallback}\n\n--- HTML (preview) ---\n{html[:400]}...\n")
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

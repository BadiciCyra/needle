"""E-posta gönderimi (şifre sıfırlama).

SMTP ayarları (.env: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_FROM) verilmemişse e-posta
gönderilmez, mesaj sunucu loguna yazılır: yerel geliştirmede sıfırlama bağlantısı `docker compose logs api`
ile görülür. Yayında SMTP ayarlanmalı (ör. Resend, Brevo, Gmail uygulama şifresi).
"""

import logging
import smtplib
from email.message import EmailMessage

from app.config import Settings

log = logging.getLogger("needle.mailer")


def send_mail(settings: Settings, to: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        log.warning("SMTP ayarlı değil, e-posta gönderilmedi. Alıcı: %s | Konu: %s\n%s", to, subject, body)
        return
    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = to
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)

import os
import smtplib
from email.message import EmailMessage


def send_report(subject, body):
    keys = ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"]
    if not all(os.getenv(k) for k in keys):
        return False
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = subject, os.environ["EMAIL_FROM"], os.environ["EMAIL_TO"]
    message.set_content(body)
    with smtplib.SMTP(os.environ["SMTP_HOST"], int(os.environ["SMTP_PORT"]), timeout=30) as smtp:
        smtp.starttls()
        smtp.login(os.environ["SMTP_USERNAME"], os.environ["SMTP_PASSWORD"])
        smtp.send_message(message)
    return True

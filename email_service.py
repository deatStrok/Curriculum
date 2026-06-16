from __future__ import annotations

import base64
from typing import Optional

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (
    Attachment,
    Disposition,
    FileContent,
    FileName,
    FileType,
    Mail,
    ReplyTo,
)

from settings import SENDGRID_API_KEY


def send_email_sendgrid(
    from_email: str,
    from_name: str,
    to_email: str,
    subject: str,
    html_body: str,
    reply_to_email: Optional[str] = None,
    attachment_bytes: Optional[bytes] = None,
    attachment_filename: Optional[str] = None,
) -> dict:
    if not SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY não configurada.")

    message = Mail(
        from_email=(from_email, from_name),
        to_emails=to_email,
        subject=subject,
        html_content=html_body,
    )

    if reply_to_email:
        message.reply_to = ReplyTo(reply_to_email)

    if attachment_bytes and attachment_filename:
        encoded = base64.b64encode(attachment_bytes).decode()
        attachment = Attachment(
            FileContent(encoded),
            FileName(attachment_filename),
            FileType("application/pdf"),
            Disposition("attachment"),
        )
        message.attachment = attachment

    sg = SendGridAPIClient(SENDGRID_API_KEY)
    response = sg.send(message)
    return {
        "status_code": response.status_code,
        "body": str(response.body),
        "headers": dict(response.headers),
    }

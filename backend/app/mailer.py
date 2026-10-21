"""Email transport (SMTP and IMAP) with strict invariants (SEC-19, SEC-21, SEC-22, SEC-23)."""

import email
import imaplib
import logging
import os
import smtplib
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.config import settings
from app.guard import check_send_guard
from app.models import Brochure, Contact, Message, Target

logger = logging.getLogger(__name__)


class ParsedEmail(BaseModel):
    message_id_header: str | None = None
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    sender: str
    recipient: str | None = None
    subject: str = ""
    body: str = ""
    headers: dict[str, str] = Field(default_factory=dict)


def parse_email_message(msg: Any) -> ParsedEmail:
    """Extract headers, threading references, and body from an email Message."""
    headers: dict[str, str] = {}
    for k, v in msg.items():
        headers[k.lower()] = str(v)

    subject = str(msg.get("Subject", ""))
    sender = str(msg.get("From", ""))
    recipient = str(msg.get("To", ""))
    msg_id = str(msg.get("Message-ID", ""))
    in_reply_to = str(msg.get("In-Reply-To", ""))
    references_str = str(msg.get("References", ""))
    references = [r.strip() for r in references_str.split() if r.strip()]

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            cdispo = str(part.get("Content-Disposition"))
            if ctype == "text/plain" and "attachment" not in cdispo:
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")
                break
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body = payload.decode(charset, errors="replace")

    return ParsedEmail(
        message_id_header=msg_id.strip() if msg_id else None,
        in_reply_to=in_reply_to.strip() if in_reply_to else None,
        references=references,
        sender=sender.strip(),
        recipient=recipient.strip() if recipient else None,
        subject=subject.strip(),
        body=body.strip(),
        headers=headers,
    )


def fetch_unseen_emails(imap_client: Any | None = None) -> list[ParsedEmail]:
    """Fetch unseen emails via IMAP client (or test seam) with TLS (SEC-23)."""
    if imap_client is not None:
        messages = imap_client.fetch_unseen()
        parsed_list: list[ParsedEmail] = []
        for m in messages:
            if isinstance(m, ParsedEmail):
                parsed_list.append(m)
            else:
                parsed_list.append(parse_email_message(m))
        return parsed_list

    if not settings.imap_user or not settings.imap_password:
        return []

    context = ssl.create_default_context()  # SEC-23: strict certificate verification
    results: list[ParsedEmail] = []

    try:
        with imaplib.IMAP4_SSL(
            settings.imap_host, settings.imap_port, ssl_context=context
        ) as client:
            client.login(settings.imap_user, settings.imap_password)
            client.select("INBOX")
            status, data = client.search(None, "UNSEEN")
            if status != "OK" or not data or not data[0]:
                return []

            for num in data[0].split():
                res, msg_data = client.fetch(num, "(RFC822)")
                if res != "OK":
                    continue
                for part in msg_data:
                    if isinstance(part, tuple):
                        email_obj = email.message_from_bytes(part[1])
                        results.append(parse_email_message(email_obj))
    except Exception as exc:
        logger.error("IMAP poll failed: %s", type(exc).__name__)

    return results


def mask_email(email_addr: str) -> str:
    """Mask email address for audit logging, e.g. a***@domain (SEC-29)."""
    if "@" not in email_addr:
        return "***"
    local, domain = email_addr.split("@", 1)
    if not local:
        return f"***@{domain}"
    return f"{local[0]}***@{domain}"


def send_message(
    db: Session,
    message_id: int,
    transport: Any | None = None,
    now: datetime | None = None,
) -> bool:
    """Send an approved message after passing all guard checks (SEC-19).

    This is the single function responsible for sending email in the application.
    """
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    # 1. Evaluate guard invariants first in one transaction (SEC-19)
    guard_result = check_send_guard(db, message_id, now=current_time)
    if not guard_result.allowed:
        logger.warning("Send guard refused message %s: %s", message_id, guard_result.reason)
        return False

    message = db.get(Message, message_id)
    if not message or not message.contact_id:
        logger.error("Message %s or associated contact not found", message_id)
        return False

    contact = db.get(Contact, message.contact_id)
    if not contact or not contact.email:
        logger.error("Contact for message %s has no valid email", message_id)
        return False

    target = db.get(Target, message.target_id)
    if not target:
        logger.error("Target for message %s not found", message_id)
        return False

    recipient = contact.email.strip().lower()

    # 2. Prevent header injection: reject CR/LF in recipient or subject (SEC-21)
    if "\r" in recipient or "\n" in recipient:
        raise ValueError("Header injection detected: CR/LF in recipient address")
    if "\r" in message.subject or "\n" in message.subject:
        raise ValueError("Header injection detected: CR/LF in subject line")

    # 3. Construct plain-text email with EmailMessage (SEC-21, SEC-22)
    email_msg = EmailMessage()
    email_msg["From"] = settings.smtp_from
    email_msg["To"] = recipient
    email_msg["Subject"] = message.subject
    msg_id = make_msgid(domain=settings.smtp_from.split("@")[-1])
    email_msg["Message-ID"] = msg_id
    email_msg["Date"] = formatdate(current_time.timestamp(), localtime=False)
    email_msg.set_content(message.body)

    # Attach brochure if present (Phase 8, G5)
    if message.attachment_id:
        brochure = db.get(Brochure, message.attachment_id)
        if brochure:
            brochure_path = os.path.join(settings.brochures_upload_dir, brochure.stored_name)
            if os.path.exists(brochure_path):
                with open(brochure_path, "rb") as bf:
                    file_data = bf.read()
                email_msg.add_attachment(
                    file_data,
                    maintype="application",
                    subtype="pdf",
                    filename=brochure.filename,
                )

    # 4. Transmit via transport (fake seam for tests or live SMTP with TLS)
    try:
        if transport is not None:
            transport.send_message(email_msg)
        else:
            context = ssl.create_default_context()  # SEC-23: strict certificate verification
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                if settings.smtp_starttls:
                    server.starttls(context=context)
                if settings.smtp_user and settings.smtp_password:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(email_msg)
    except Exception as exc:
        message.status = "failed"
        db.commit()
        # SEC-29: do not log email body, recipient address, or password
        logger.error("Failed transmitting message %s: %s", message_id, type(exc).__name__)
        return False

    # 5. Update state on successful send
    message.status = "sent"
    message.sent_at = current_time
    message.message_id_header = msg_id

    if target.status == "not_contacted":
        target.status = "contacted"
    target.last_contacted_at = current_time

    log_audit(
        db,
        message.approved_by,
        "send_message",
        "messages",
        str(message.id),
        f"Sent message to {mask_email(recipient)}",
    )
    db.commit()

    # Invoke Graph B: handle_event (sent) per ARCHITECTURE.md line 117
    from app.graph import handle_graph_b_event

    handle_graph_b_event("sent", target.id, message_id=message.id, now=current_time)

    logger.info("Message %s successfully sent to %s", message_id, mask_email(recipient))
    return True

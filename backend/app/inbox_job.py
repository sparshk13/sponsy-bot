"""IMAP reply polling, header matching, and suppression (R6, SEC-22, SEC-26)."""

import logging
from email.utils import parseaddr
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.classifier import classify_reply
from app.mailer import ParsedEmail, fetch_unseen_emails, mask_email
from app.models import Contact, Message, Suppression, Target, utc_now

logger = logging.getLogger(__name__)


def extract_email_address(raw_sender: str) -> str:
    """Extract bare email address from 'Name <email@domain>' string."""
    _, addr = parseaddr(raw_sender)
    return addr.strip().lower() if addr else raw_sender.strip().lower()


def match_reply_to_target(
    db: Session, email_item: ParsedEmail
) -> tuple[Target | None, Contact | None, Message | None]:
    """Match an incoming reply to a target via In-Reply-To, References, or sender email."""
    # 1. Match via In-Reply-To
    if email_item.in_reply_to:
        matched_msg = db.scalar(
            select(Message).where(
                Message.message_id_header == email_item.in_reply_to,
                Message.direction == "out",
            )
        )
        if matched_msg:
            contact = db.get(Contact, matched_msg.contact_id) if matched_msg.contact_id else None
            return matched_msg.target, contact, matched_msg

    # 2. Match via References
    for ref in email_item.references:
        matched_msg = db.scalar(
            select(Message).where(
                Message.message_id_header == ref,
                Message.direction == "out",
            )
        )
        if matched_msg:
            contact = db.get(Contact, matched_msg.contact_id) if matched_msg.contact_id else None
            return matched_msg.target, contact, matched_msg

    # 3. Fallback: match by sender address matching a contact of a contacted target
    sender_addr = extract_email_address(email_item.sender)
    if sender_addr:
        contact = db.scalar(select(Contact).where(func.lower(Contact.email) == sender_addr))
        if contact:
            target = db.scalar(
                select(Target)
                .where(
                    Target.company_id == contact.company_id,
                    Target.status.in_(["contacted", "follow_up", "interested", "meeting_booked"]),
                )
                .order_by(Target.last_contacted_at.desc())
            )
            if target:
                return target, contact, None

    return None, None, None


def _apply_suppression_for_decline(db: Session, target: Target, contact: Contact | None) -> None:
    """Add contact email and company domain to suppression list on decline (SEC-22, SEC-26)."""
    if contact and contact.email:
        email_clean = contact.email.strip().lower()
        existing_email_supp = db.scalar(select(Suppression).where(Suppression.value == email_clean))
        if not existing_email_supp:
            db.add(
                Suppression(
                    kind="email",
                    value=email_clean,
                    reason=f"Contact declined sponsorship outreach for {target.company.name}",
                    created_at=utc_now(),
                )
            )
            log_audit(
                db,
                None,
                "auto_suppress_decline",
                "suppression",
                None,
                f"Suppressed email {mask_email(email_clean)} after decline",
            )

    domain_clean = target.company.domain.strip().lower()
    existing_domain_supp = db.scalar(select(Suppression).where(Suppression.value == domain_clean))
    if not existing_domain_supp:
        db.add(
            Suppression(
                kind="domain",
                value=domain_clean,
                reason=f"Company declined sponsorship outreach ({target.company.name})",
                created_at=utc_now(),
            )
        )
        log_audit(
            db,
            None,
            "auto_suppress_decline",
            "suppression",
            None,
            f"Suppressed domain {domain_clean} after decline",
        )


def process_incoming_email(db: Session, email_item: ParsedEmail) -> Message | None:
    """Process one incoming email: match, classify, update target state, and store message."""
    # Check duplicate ingestion
    if email_item.message_id_header:
        existing = db.scalar(
            select(Message).where(
                Message.message_id_header == email_item.message_id_header,
                Message.direction == "in",
            )
        )
        if existing:
            return existing

    target, contact, _sent_msg = match_reply_to_target(db, email_item)
    if not target:
        sender_clean = extract_email_address(email_item.sender)
        logger.info("Incoming email could not be matched to target: %s", mask_email(sender_clean))
        return None

    campaign_info = {
        "name": target.campaign.name,
        "calendar_link": target.campaign.calendar_link or "",
        "sender_name": "Outreach Team",
    }

    result = classify_reply(
        headers=email_item.headers,
        sender=email_item.sender,
        subject=email_item.subject,
        body=email_item.body,
        company_name=target.company.name,
        campaign_info=campaign_info,
    )

    msg = Message(
        target_id=target.id,
        contact_id=contact.id if contact else None,
        direction="in",
        kind="reply",
        subject=email_item.subject,
        body=email_item.body,
        status="received",
        classification=result.classification,
        summary=result.summary,
        suggested_reply=result.suggested_reply if result.suggested_reply else None,
        classified_by_human=False,
        message_id_header=email_item.message_id_header,
        in_reply_to=email_item.in_reply_to,
        created_at=utc_now(),
    )
    db.add(msg)
    db.flush()

    # State transitions based on classification
    if result.classification == "bounce":
        if contact:
            contact.is_valid = False
            log_audit(
                db,
                None,
                "email_bounced",
                "contacts",
                str(contact.id),
                f"Contact marked invalid due to bounce for {mask_email(contact.email or '')}",
            )
    elif result.classification == "declined":
        target.status = "declined"
        _apply_suppression_for_decline(db, target, contact)
        log_audit(
            db,
            None,
            "reply_declined",
            "targets",
            str(target.id),
            f"Target {target.id} marked declined from incoming reply",
        )
    elif result.classification == "interested":
        target.status = "interested"
        log_audit(
            db,
            None,
            "reply_interested",
            "targets",
            str(target.id),
            f"Target {target.id} marked interested from incoming reply",
        )
    elif result.classification == "auto_reply":
        # Target status remains unchanged (ARCHITECTURE.md line 124)
        log_audit(
            db,
            None,
            "reply_auto_reply",
            "targets",
            str(target.id),
            f"Auto-reply recorded for target {target.id}",
        )
    else:
        log_audit(
            db,
            None,
            "reply_received",
            "targets",
            str(target.id),
            f"Reply recorded with class '{result.classification}' for target {target.id}",
        )

    db.commit()
    db.refresh(msg)

    # Invoke Graph B: handle_event (reply_received) per ARCHITECTURE.md line 108
    from app.graph import handle_graph_b_event

    handle_graph_b_event(
        "reply_received",
        target.id,
        message_id=msg.id,
        classification=result.classification,
    )

    return msg


def poll_inbox(db: Session, imap_client: Any | None = None) -> list[Message]:
    """Poll IMAP for unseen messages, ingest them, and return newly created messages."""
    unseen_emails = fetch_unseen_emails(imap_client=imap_client)
    created_messages: list[Message] = []
    for email_item in unseen_emails:
        msg = process_incoming_email(db, email_item)
        if msg:
            created_messages.append(msg)
    return created_messages

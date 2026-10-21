"""Messages and approval queue routes enforcing SEC-09, SEC-19, SEC-20, and PRD R5."""

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user, verify_csrf
from app.db import get_db
from app.drafting import compute_approved_hash
from app.models import AuditLog, Contact, Message, Target, User, utc_now

router = APIRouter(prefix="/api/messages", tags=["messages"])
queue_router = APIRouter(prefix="/api/queue", tags=["queue"])


class MessageUpdateRequest(BaseModel):
    subject: str = Field(..., max_length=255)
    body: str = Field(..., max_length=10000)


class ClassOverrideRequest(BaseModel):
    classification: Literal["interested", "declined", "question", "auto_reply", "bounce", "other"]


class ConvertSuggestedReplyRequest(BaseModel):
    subject: str | None = None
    body: str | None = None


class MessageResponse(BaseModel):
    id: int
    target_id: int
    contact_id: int | None
    direction: str
    kind: str
    subject: str | None
    body: str | None
    status: str
    facts_used: Any | None
    approved_by: int | None
    approved_at: datetime | None
    approved_hash: str | None
    classification: str | None = None
    summary: str | None = None
    suggested_reply: str | None = None
    classified_by_human: bool = False
    in_reply_to: str | None = None
    message_id_header: str | None = None
    attachment_id: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class QueueItemResponse(BaseModel):
    id: int
    target_id: int
    company_id: int
    company_name: str
    company_domain: str
    campaign_id: int
    campaign_name: str
    tier: str | None
    contact_id: int | None
    contact_name: str | None
    contact_role: str | None
    contact_email: str | None
    subject: str | None
    body: str | None
    status: str
    kind: str = "first"
    attachment_id: int | None = None
    facts_used: Any | None
    approved_by: int | None
    approved_at: datetime | None
    created_at: datetime
    is_owner: bool


def _log_audit(
    db: Session,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    detail: str | None = None,
) -> None:
    # SEC-30: append-only audit log
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        detail=detail,
    )
    db.add(entry)


def _verify_message_ownership(message: Message, user: User) -> None:
    # SEC-09: Re-load object server-side and check role and ownership
    target = message.target
    if user.role != "admin" and (not target or target.owner_id != user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this target.",
        )


@queue_router.get("", response_model=list[QueueItemResponse])
def list_queue(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QueueItemResponse]:
    """List drafts waiting for approval (own drafts for organizers, all for admins)."""
    stmt = (
        select(Message)
        .join(Target, Message.target_id == Target.id)
        .where(
            Message.direction == "out",
            Message.status.in_(["draft", "approved"]),
        )
    )

    if user.role != "admin":
        stmt = stmt.where(Target.owner_id == user.id)

    stmt = stmt.order_by(Message.created_at.desc())
    messages = db.scalars(stmt).all()

    items: list[QueueItemResponse] = []
    for msg in messages:
        target = msg.target
        contact = msg.contact_id and db.get(Contact, msg.contact_id)
        items.append(
            QueueItemResponse(
                id=msg.id,
                target_id=msg.target_id,
                company_id=target.company_id,
                company_name=target.company.name,
                company_domain=target.company.domain,
                campaign_id=target.campaign_id,
                campaign_name=target.campaign.name,
                tier=target.tier,
                contact_id=msg.contact_id,
                contact_name=contact.name if contact else None,
                contact_role=contact.role if contact else None,
                contact_email=contact.email if contact else None,
                subject=msg.subject,
                body=msg.body,
                status=msg.status,
                kind=msg.kind,
                attachment_id=msg.attachment_id,
                facts_used=msg.facts_used if isinstance(msg.facts_used, list) else None,
                approved_by=msg.approved_by,
                approved_at=msg.approved_at,
                created_at=msg.created_at,
                is_owner=(target.owner_id == user.id or user.role == "admin"),
            )
        )
    return items


@router.put("/{message_id}", response_model=MessageResponse, dependencies=[Depends(verify_csrf)])
def update_message(
    message_id: int,
    req: MessageUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Save an edit to a draft. If approved, voids approval and resets status to draft (SEC-19)."""
    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    _verify_message_ownership(message, user)

    was_approved = message.status == "approved"
    message.subject = req.subject.strip()
    message.body = req.body.strip()

    if was_approved:
        # SEC-19, SEC-30: Any edit after approval voids approval
        message.status = "draft"
        message.approved_by = None
        message.approved_at = None
        message.approved_hash = None
        _log_audit(
            db,
            user.id,
            "edit_after_approve",
            "messages",
            str(message.id),
            f"Edited draft after approval for target {message.target_id}; approval voided.",
        )
    else:
        _log_audit(
            db,
            user.id,
            "edit_draft",
            "messages",
            str(message.id),
            f"Edited draft message for target {message.target_id}.",
        )

    db.commit()
    db.refresh(message)
    return MessageResponse.model_validate(message)


@router.post(
    "/{message_id}/approve", response_model=MessageResponse, dependencies=[Depends(verify_csrf)]
)
def approve_message(
    message_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """SEC-20: Exactly one route approves a message, recording user, time, and hash."""
    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    _verify_message_ownership(message, user)

    if not message.subject or not message.subject.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Subject cannot be empty."
        )
    if not message.body or not message.body.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email body cannot be empty."
        )

    # Resolve recipient address from contact or target company contact
    recipient_email: str | None = None
    if message.contact_id:
        contact = db.get(Contact, message.contact_id)
        if contact and contact.email:
            recipient_email = contact.email
    if not recipient_email:
        # Look for company contact
        contact = db.scalar(
            select(Contact).where(
                Contact.company_id == message.target.company_id,
                Contact.email.isnot(None),
                Contact.is_valid.is_(True),
            )
        )
        if contact and contact.email:
            recipient_email = contact.email
            message.contact_id = contact.id

    if not recipient_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve message without a valid contact email address.",
        )

    # Compute sha256(to + subject + body) per SEC-19
    approved_hash = compute_approved_hash(recipient_email, message.subject, message.body)

    # SEC-20: Only this authenticated human POST sets status = 'approved'
    message.status = "approved"
    message.approved_by = user.id
    message.approved_at = utc_now()
    message.approved_hash = approved_hash

    _log_audit(
        db,
        user.id,
        "approve_message",
        "messages",
        str(message.id),
        f"Approved message for target {message.target_id} to {recipient_email}.",
    )

    db.commit()
    db.refresh(message)
    return MessageResponse.model_validate(message)


@router.post(
    "/{message_id}/discard", response_model=MessageResponse, dependencies=[Depends(verify_csrf)]
)
def discard_message(
    message_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Discard a draft message."""
    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    _verify_message_ownership(message, user)

    message.status = "discarded"
    _log_audit(
        db,
        user.id,
        "discard_message",
        "messages",
        str(message.id),
        f"Discarded draft for target {message.target_id}.",
    )

    db.commit()
    db.refresh(message)
    return MessageResponse.model_validate(message)


@router.put(
    "/{message_id}/class",
    response_model=MessageResponse,
    dependencies=[Depends(verify_csrf)],
)
def override_classification(
    message_id: int,
    req: ClassOverrideRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Human override of message classification (SEC-09, R6)."""
    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    _verify_message_ownership(message, user)

    if message.direction != "in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only incoming replies can have their classification overridden.",
        )

    old_class = message.classification
    new_class = req.classification
    message.classification = new_class
    message.classified_by_human = True

    target = message.target
    if target:
        if new_class == "declined":
            target.status = "declined"
            contact = db.get(Contact, message.contact_id) if message.contact_id else None
            from app.inbox_job import _apply_suppression_for_decline

            _apply_suppression_for_decline(db, target, contact)
        elif new_class == "interested":
            target.status = "interested"

    _log_audit(
        db,
        user.id,
        "override_classification",
        "messages",
        str(message.id),
        f"Overrode classification from '{old_class}' to '{new_class}' on message {message.id}.",
    )

    db.commit()
    db.refresh(message)
    return MessageResponse.model_validate(message)


@router.post(
    "/{message_id}/suggested-reply",
    response_model=MessageResponse,
    dependencies=[Depends(verify_csrf)],
)
def convert_suggested_reply(
    message_id: int,
    req: ConvertSuggestedReplyRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageResponse:
    """Convert a suggested reply into a draft in the queue (SEC-09, R6)."""
    incoming = db.get(Message, message_id)
    if not incoming:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")

    _verify_message_ownership(incoming, user)

    if incoming.direction != "in":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only convert suggested replies from incoming messages.",
        )

    body_to_use = req.body or incoming.suggested_reply
    if not body_to_use or not body_to_use.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No suggested reply body available.",
        )

    subject_to_use = req.subject or (
        f"Re: {incoming.subject}" if incoming.subject else "Sponsorship discussion"
    )

    draft = Message(
        target_id=incoming.target_id,
        contact_id=incoming.contact_id,
        direction="out",
        kind="reply",
        subject=subject_to_use.strip(),
        body=body_to_use.strip(),
        status="draft",
        in_reply_to=incoming.message_id_header,
        created_by=user.id,
        created_at=utc_now(),
    )
    db.add(draft)
    db.flush()

    _log_audit(
        db,
        user.id,
        "create_draft_from_suggested_reply",
        "messages",
        str(draft.id),
        f"Created draft response to message {incoming.id} for target {incoming.target_id}.",
    )

    db.commit()
    db.refresh(draft)
    return MessageResponse.model_validate(draft)

"""Inbox routes for received email replies (PRD R6, G8, G9, ROUTES.md)."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Contact, Message, Target, User

router = APIRouter(prefix="/api/inbox", tags=["inbox"])


class InboxItemResponse(BaseModel):
    id: int
    target_id: int
    company_id: int
    company_name: str
    company_domain: str
    campaign_id: int
    campaign_name: str
    contact_id: int | None
    contact_name: str | None
    contact_email: str | None
    subject: str | None
    body: str | None
    summary: str | None
    classification: str | None
    classified_by_human: bool
    suggested_reply: str | None
    created_at: datetime
    is_owner: bool


@router.get("", response_model=list[InboxItemResponse])
def list_inbox(
    classification: str | None = Query(None),
    own_only: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InboxItemResponse]:
    """List incoming email replies newest first (PRD R6, G8)."""
    stmt = (
        select(Message)
        .join(Target, Message.target_id == Target.id)
        .where(Message.direction == "in")
    )

    if own_only and user.role != "admin":
        stmt = stmt.where(Target.owner_id == user.id)

    if classification:
        stmt = stmt.where(Message.classification == classification)

    stmt = stmt.order_by(Message.created_at.desc())
    messages = db.scalars(stmt).all()

    items: list[InboxItemResponse] = []
    for msg in messages:
        target = msg.target
        contact = msg.contact_id and db.get(Contact, msg.contact_id)
        items.append(
            InboxItemResponse(
                id=msg.id,
                target_id=msg.target_id,
                company_id=target.company_id,
                company_name=target.company.name,
                company_domain=target.company.domain,
                campaign_id=target.campaign_id,
                campaign_name=target.campaign.name,
                contact_id=msg.contact_id,
                contact_name=contact.name if contact else None,
                contact_email=contact.email if contact else None,
                subject=msg.subject,
                body=msg.body,
                summary=msg.summary,
                classification=msg.classification,
                classified_by_human=msg.classified_by_human,
                suggested_reply=msg.suggested_reply,
                created_at=msg.created_at,
                is_owner=(target.owner_id == user.id or user.role == "admin"),
            )
        )
    return items

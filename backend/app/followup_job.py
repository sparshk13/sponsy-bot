"""Scheduled job for due follow-ups and auto-closing (PRD R7)."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.graph import handle_graph_b_event
from app.models import Target

logger = logging.getLogger(__name__)


def process_due_followups(db: Session, now: datetime | None = None) -> list[int]:
    """Find targets whose next_followup_at is due and process via Graph B.

    Returns the list of target IDs processed.
    """
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    stmt = (
        select(Target.id)
        .where(
            Target.status.in_(["contacted", "follow_up"]),
            Target.next_followup_at.isnot(None),
            Target.next_followup_at <= current_time,
        )
        .order_by(Target.next_followup_at.asc())
    )

    due_target_ids = list(db.scalars(stmt).all())
    processed_ids: list[int] = []

    for target_id in due_target_ids:
        try:
            handle_graph_b_event("followup_due", target_id=target_id, now=current_time)
            processed_ids.append(target_id)
        except Exception as exc:
            logger.error("Failed processing due follow-up for target %s: %s", target_id, exc)

    return processed_ids

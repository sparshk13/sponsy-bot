"""Background queue worker for paced email sending (SEC-19, BUD-08)."""

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.mailer import send_message
from app.models import Message

logger = logging.getLogger(__name__)


def process_send_queue(
    db: Session,
    transport: Any | None = None,
    now: datetime | None = None,
    jitter_fn: Callable[[], int] | None = None,
) -> int:
    """Process the next approved message in the queue with row locking and pacing.

    Uses SELECT FOR UPDATE SKIP LOCKED to guarantee safe concurrent execution.
    Returns 1 if a message was successfully sent, 0 otherwise.
    """
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    # 1. Pacing check: ensure minimum gap + random jitter since last send (BUD-08)
    last_sent_at = db.scalar(
        select(func.max(Message.sent_at)).where(
            Message.direction == "out",
            Message.status == "sent",
        )
    )

    if last_sent_at is not None:
        if last_sent_at.tzinfo is None:
            last_sent_at = last_sent_at.replace(tzinfo=timezone.utc)
        elapsed = (current_time - last_sent_at).total_seconds()
        jitter = (
            jitter_fn() if jitter_fn else secrets.randbelow(settings.send_jitter_max_seconds + 1)
        )
        required_gap = settings.send_min_gap_seconds + jitter
        if elapsed < required_gap:
            logger.info("Send paced: %.1fs elapsed, required gap %.1fs", elapsed, required_gap)
            return 0

    # 2. Select oldest approved message with row lock (SEC-37, ARCHITECTURE 6)
    stmt = (
        select(Message)
        .where(Message.direction == "out", Message.status == "approved")
        .order_by(Message.approved_at.asc(), Message.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    message = db.scalars(stmt).first()
    if not message:
        return 0

    message_id = message.id
    success = send_message(db, message_id, transport=transport, now=current_time)
    return 1 if success else 0

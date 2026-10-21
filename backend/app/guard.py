"""Email safety guard checking all 8 invariant conditions before sending (SEC-19)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.drafting import compute_approved_hash
from app.models import Contact, Message, SettingsState, Suppression, Target


@dataclass
class GuardResult:
    allowed: bool
    reason: str | None = None


def check_send_guard(db: Session, message_id: int, now: datetime | None = None) -> GuardResult:
    """Evaluate all eight SEC-19 invariants in one transaction. Any failure blocks send."""
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    # 1. Global pause is off (h)
    pause_state = db.scalar(select(SettingsState.value).where(SettingsState.key == "paused"))
    if pause_state and pause_state.strip().lower() in ("true", "1", "yes"):
        return GuardResult(allowed=False, reason="Global sending pause is enabled")

    # 2. Inside the send window (g)
    tz = ZoneInfo(settings.timezone)
    local_dt = current_time.astimezone(tz)
    if settings.weekdays_only and local_dt.weekday() >= 5:
        return GuardResult(allowed=False, reason="Outside send window: weekend")
    if not (settings.send_window_start_hour <= local_dt.hour < settings.send_window_end_hour):
        return GuardResult(
            allowed=False,
            reason=(
                f"Outside send window hours ({settings.send_window_start_hour}:00 - "
                f"{settings.send_window_end_hour}:00 {settings.timezone})"
            ),
        )

    # Load message and target
    message = db.get(Message, message_id)
    if not message:
        return GuardResult(allowed=False, reason="Message not found")

    # 3. Status is approved (a)
    if message.status != "approved":
        return GuardResult(
            allowed=False,
            reason=f"Message status is '{message.status}', expected 'approved'",
        )

    # 4. Hash verification (b)
    contact = db.get(Contact, message.contact_id) if message.contact_id else None
    if not contact or not contact.email:
        return GuardResult(allowed=False, reason="Message has no valid contact email")

    recipient = contact.email.strip().lower()
    expected_hash = compute_approved_hash(recipient, message.subject, message.body)
    if not message.approved_hash or message.approved_hash != expected_hash:
        return GuardResult(
            allowed=False,
            reason="Message content does not match approved hash (approval voided)",
        )

    # 5. Target is not declined or closed (d)
    target = db.get(Target, message.target_id)
    if not target:
        return GuardResult(allowed=False, reason="Target not found")
    if target.status in ("declined", "closed_no_reply"):
        return GuardResult(
            allowed=False,
            reason=f"Target is closed with status '{target.status}'",
        )

    # 6. Follow-up count within limit (e)
    if target.followup_count > settings.max_followups:
        return GuardResult(
            allowed=False,
            reason=(
                f"Target followup count ({target.followup_count}) exceeds "
                f"maximum limit ({settings.max_followups})"
            ),
        )

    # 7. Recipient and domain not suppressed (c)
    recipient_domain = recipient.split("@")[-1] if "@" in recipient else ""
    target_domain = target.company.domain.strip().lower() if target.company else ""

    suppressed = db.scalars(
        select(Suppression).where(
            (Suppression.kind == "email") & (Suppression.value == recipient)
            | (Suppression.kind == "domain")
            & (Suppression.value.in_([recipient_domain, target_domain]))
        )
    ).first()
    if suppressed:
        return GuardResult(
            allowed=False,
            reason=f"Recipient or domain is suppressed ({suppressed.kind}: {suppressed.value})",
        )

    # 8. Today's sent count below daily cap (f)
    local_midnight = local_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    utc_midnight = local_midnight.astimezone(timezone.utc)

    sent_today = (
        db.scalar(
            select(func.count(Message.id)).where(
                Message.direction == "out",
                Message.status == "sent",
                Message.sent_at >= utc_midnight,
            )
        )
        or 0
    )

    if sent_today >= settings.daily_send_cap:
        return GuardResult(
            allowed=False,
            reason=f"Daily send cap ({settings.daily_send_cap}) reached for today",
        )

    return GuardResult(allowed=True, reason=None)

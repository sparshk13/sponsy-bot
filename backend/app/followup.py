"""Follow-up scheduling math and business day calculation (PRD R7, G2)."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings


def get_followup_delay_days(followup_index: int) -> int:
    """Return number of business days to wait for the given follow-up index (0-indexed)."""
    try:
        delays = [int(x.strip()) for x in settings.followup_days.split(",") if x.strip()]
    except Exception:
        delays = [4, 5]
    if not delays:
        delays = [4, 5]
    if followup_index < len(delays):
        return delays[followup_index]
    return delays[-1]


def compute_next_followup_at(
    base_time: datetime,
    days_offset: int,
    tz_name: str = "Asia/Kolkata",
    start_hour: int = 9,
    start_minute: int = 30,
    end_hour: int = 17,
    end_minute: int = 30,
) -> datetime:
    """Calculate next follow-up timestamp in UTC, advancing by weekdays and ensuring send window."""
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)

    local_tz = ZoneInfo(tz_name)
    local_dt = base_time.astimezone(local_tz)

    advanced = 0
    curr = local_dt
    while advanced < days_offset:
        curr += timedelta(days=1)
        if curr.weekday() < 5:
            advanced += 1

    window_start = curr.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)
    window_end = curr.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)

    if curr < window_start:
        curr = window_start
    elif curr > window_end:
        curr += timedelta(days=1)
        while curr.weekday() >= 5:
            curr += timedelta(days=1)
        curr = curr.replace(hour=start_hour, minute=start_minute, second=0, microsecond=0)

    return curr.astimezone(timezone.utc)

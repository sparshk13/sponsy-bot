"""Free-tier budget tracking, counted wrappers, and rate limiting (BUD rules)."""

import time
from collections import deque
from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import ApiUsage, utc_today

T = TypeVar("T")


class BudgetExhausted(Exception):
    """Raised when an external API budget cap has been reached (BUD-02)."""

    def __init__(self, provider: str, limit: int, period: str):
        self.provider = provider
        self.limit = limit
        self.period = period
        super().__init__(
            f"{provider.capitalize()} {period} budget cap of {limit} units has been reached."
        )


class GeminiRateLimiter:
    """In-process rate limiter enforcing GEMINI_RPM (BUD-03)."""

    def __init__(self, rpm: int):
        self.rpm = rpm
        self.timestamps: deque[float] = deque()

    def acquire(self) -> None:
        now = time.monotonic()
        while self.timestamps and now - self.timestamps[0] >= 60.0:
            self.timestamps.popleft()

        if len(self.timestamps) >= self.rpm:
            sleep_needed = 60.0 - (now - self.timestamps[0])
            if sleep_needed > 0:
                time.sleep(sleep_needed)
            now = time.monotonic()
            while self.timestamps and now - self.timestamps[0] >= 60.0:
                self.timestamps.popleft()

        self.timestamps.append(time.monotonic())


_gemini_limiter = GeminiRateLimiter(settings.gemini_rpm)


def get_current_usage(db: Session, provider: str) -> int:
    today = utc_today()
    if provider == "gemini":
        row = db.scalar(
            select(ApiUsage.units).where(ApiUsage.day == today, ApiUsage.provider == provider)
        )
        return row or 0

    first_of_month = date(today.year, today.month, 1)
    total = db.scalar(
        select(func.coalesce(func.sum(ApiUsage.units), 0)).where(
            ApiUsage.provider == provider,
            ApiUsage.day >= first_of_month,
        )
    )
    return int(total or 0)


def get_cap_and_period(provider: str) -> tuple[int, str]:
    if provider == "gemini":
        return settings.gemini_daily_call_cap, "daily"
    if provider == "tavily":
        return settings.tavily_monthly_credit_cap, "monthly"
    if provider == "hunter":
        return settings.hunter_monthly_credit_cap, "monthly"
    return 0, "daily"


def check_budget(db: Session, provider: str, units: int = 1) -> None:
    cap, period = get_cap_and_period(provider)
    if cap <= 0:
        return

    used = get_current_usage(db, provider)
    if used + units > cap:
        raise BudgetExhausted(provider, cap, period)


def increment_usage(db: Session, provider: str, units: int = 1) -> None:
    today = utc_today()
    stmt = (
        select(ApiUsage)
        .where(ApiUsage.day == today, ApiUsage.provider == provider)
        .with_for_update()
    )
    row = db.scalar(stmt)
    if row:
        row.units += units
    else:
        row = ApiUsage(day=today, provider=provider, units=units)
        db.add(row)
    db.commit()


def run_with_budget(
    db: Session,
    provider: str,
    fn: Callable[..., T],
    units: int = 1,
    *args: Any,
    **kwargs: Any,
) -> T:
    """Execute fn with pre-call budget check and post-call counted increment (BUD-02)."""
    check_budget(db, provider, units)

    if provider == "gemini":
        _gemini_limiter.acquire()

    result = fn(*args, **kwargs)
    increment_usage(db, provider, units)
    return result


def get_usage_overview(db: Session) -> list[dict[str, Any]]:
    providers = ["gemini", "tavily", "hunter"]
    items: list[dict[str, Any]] = []

    for p in providers:
        cap, period = get_cap_and_period(p)
        used = get_current_usage(db, p)
        pct = min(100, int((used / cap) * 100)) if cap > 0 else 0
        items.append(
            {
                "provider": p,
                "used": used,
                "cap": cap,
                "period": period,
                "percent": pct,
                "is_exhausted": used >= cap,
                "is_warning": pct >= 80,
            }
        )
    return items

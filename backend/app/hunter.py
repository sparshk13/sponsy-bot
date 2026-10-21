"""Hunter.io domain search integration with budget guard (BUD-01, BUD-07, G1)."""

import logging
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.budget import BudgetExhausted, check_budget, increment_usage
from app.config import settings

logger = logging.getLogger(__name__)

HUNTER_API_URL = "https://api.hunter.io/v2/domain-search"


class HunterError(Exception):
    """Raised when Hunter API fails or is not configured."""


def search_hunter_domain(
    domain: str,
    db: Session,
    client: httpx.Client | None = None,
) -> dict[str, Any] | None:
    """Find a contact for a domain using Hunter.io with strict budget checks."""
    if not settings.hunter_api_key:
        raise HunterError("Hunter API key is not configured.")

    # BUD-02, BUD-07: check monthly credit budget before making external call
    check_budget(db, "hunter", units=1)

    params = {
        "domain": domain,
        "api_key": settings.hunter_api_key,
    }

    try:
        if client is not None:
            response = client.get(HUNTER_API_URL, params=params, timeout=10.0)
        else:
            with httpx.Client(timeout=10.0) as http_client:  # SEC-18: 10s timeout
                response = http_client.get(HUNTER_API_URL, params=params)

        if response.status_code == 429:
            raise BudgetExhausted("hunter", settings.hunter_monthly_credit_cap, "monthly")

        if response.status_code != 200:
            logger.warning(
                "Hunter API returned status %s for domain %s", response.status_code, domain
            )
            return None

        data = response.json().get("data", {})
        emails = data.get("emails", [])
        if not emails:
            # Increment usage since credit was consumed by Hunter
            increment_usage(db, "hunter", units=1)
            return None

        # Prefer contacts in marketing, partnerships, sponsorship, or executive positions
        chosen = emails[0]
        for em in emails:
            pos = (em.get("position") or "").lower()
            dept = (em.get("department") or "").lower()
            if any(k in pos or k in dept for k in ["sponsor", "partner", "market", "growth"]):
                chosen = em
                break

        first_name = (chosen.get("first_name") or "").strip()
        last_name = (chosen.get("last_name") or "").strip()
        full_name = f"{first_name} {last_name}".strip() or None
        position = chosen.get("position") or None
        email_addr = (chosen.get("value") or "").strip().lower()

        if not email_addr:
            increment_usage(db, "hunter", units=1)
            return None

        # Increment usage after successful call
        increment_usage(db, "hunter", units=1)

        return {
            "name": full_name,
            "role": position,
            "email": email_addr,
            "source": "hunter",
        }
    except BudgetExhausted:
        raise
    except Exception as exc:
        logger.error("Hunter domain search failed for %s: %s", domain, type(exc).__name__)
        raise HunterError(f"Hunter search failed: {exc}") from exc

"""Draft validation, fact citations, number whitelisting, and approval hashing (R4, R5, R12)."""

import difflib
import hashlib
import re
from typing import Any

from pydantic import BaseModel


class ValidationResult(BaseModel):
    is_valid: bool
    errors: list[str]


def compute_approved_hash(recipient: str, subject: str, body: str) -> str:
    """SEC-19: approved_hash = sha256(to + subject + body)."""
    payload = f"{recipient.strip().lower()}{subject.strip()}{body.strip()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _extract_numbers(text: str | None) -> set[str]:
    if not text:
        return set()
    raw = re.findall(r"\d+", text)
    return set(raw)


def validate_draft(
    subject: str,
    body: str,
    facts_used: list[int],
    campaign_data: dict[str, Any],
    company_name: str,
    verified_facts: list[dict[str, Any]],
    other_draft_bodies: list[str] | None = None,
    kind: str = "first",
) -> ValidationResult:
    """Validate draft against PRD R4, R5, R12, and EMAIL_GUIDE rules."""
    errors: list[str] = []

    # 1. Fact citation check (R12): all facts_used must be verified and belong to target
    verified_fact_map = {f["id"]: f for f in verified_facts if f.get("status") == "verified"}
    for fid in facts_used:
        if fid not in verified_fact_map:
            errors.append(f"Fact ID {fid} is not a verified fact for this company.")

    # 2. Placeholders check
    if "[" in subject or "]" in subject or "[" in body or "]" in body:
        errors.append("Draft contains placeholder brackets ('[' or ']').")

    # 3. Plain text check (no HTML, no Markdown bold/bullets/headings)
    if re.search(r"<[^>]+>", body):
        errors.append("Draft contains HTML tags. Plain text only is allowed.")
    if "**" in body:
        errors.append("Draft contains Markdown bold ('**').")
    if re.search(r"^\s*#+\s+", body, re.MULTILINE):
        errors.append("Draft contains Markdown headings.")
    if re.search(r"^\s*[-*]\s+", body, re.MULTILINE):
        errors.append("Draft contains bullet lists.")

    # 4. Opt-out sentence check (SEC-22, EMAIL_GUIDE)
    opt_out_pattern = re.compile(
        r"(not write again|opt-out|opt out|tell me and I will not|if this is not for you)",
        re.IGNORECASE,
    )
    if not opt_out_pattern.search(body):
        errors.append("Draft must include a plain one-line opt-out sentence.")

    # 5. Length bounds (80 to 160 words for first outreach; 40 to 100 for follow-up)
    min_words, max_words = (40, 100) if kind in ("followup", "follow_up") else (80, 160)
    words = body.strip().split()
    word_count = len(words)
    if word_count < min_words or word_count > max_words:
        errors.append(
            f"Word count {word_count} is outside the allowed {min_words}-{max_words} range."
        )

    # 6. Whitelist numbers, years, and amounts (R12)
    allowed_numbers: set[str] = set()
    for field in [
        "name",
        "event_summary",
        "event_date",
        "audience_note",
        "cash_target_inr",
        "goodies_note",
        "credits_note",
        "calendar_link",
    ]:
        val = campaign_data.get(field)
        if val is not None:
            allowed_numbers.update(_extract_numbers(str(val)))

    # Add numbers from used verified facts
    for fid in facts_used:
        fact = verified_fact_map.get(fid)
        if fact:
            allowed_numbers.update(_extract_numbers(fact.get("claim")))
            allowed_numbers.update(_extract_numbers(fact.get("evidence_quote")))

    body_numbers = _extract_numbers(body)
    # Filter out empty strings
    unwhitelisted = {n for n in body_numbers if n not in allowed_numbers}
    if unwhitelisted:
        numbers_str = ", ".join(sorted(unwhitelisted))
        errors.append(f"Draft contains unverified/invented numbers or years: {numbers_str}.")

    # 7. Cross-campaign similarity bound < 0.8 (R4)
    if other_draft_bodies:
        # Mask company name to compare structural template similarity
        masked_candidate = re.sub(re.escape(company_name), "[COMPANY]", body, flags=re.IGNORECASE)
        for idx, other_body in enumerate(other_draft_bodies):
            if not other_body or not other_body.strip():
                continue
            masked_other = re.sub(
                re.escape(company_name), "[COMPANY]", other_body, flags=re.IGNORECASE
            )
            similarity = difflib.SequenceMatcher(None, masked_candidate, masked_other).ratio()
            if similarity >= 0.8:
                errors.append(
                    f"Draft is too similar ({similarity:.2f} >= 0.80) to draft #{idx + 1}."
                )
                break

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)

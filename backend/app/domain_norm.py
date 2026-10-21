"""Domain normalisation and fuzzy match detection for company deduplication (PRD R9)."""

import re
from difflib import SequenceMatcher
from urllib.parse import urlparse

DOMAIN_PATTERN = r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$"
DOMAIN_REGEX = re.compile(DOMAIN_PATTERN)


def normalize_domain(raw: str) -> str:
    """Normalize a URL or domain string to a clean, lowercase domain name without www."""
    cleaned = raw.strip().lower()
    if not cleaned:
        return ""

    if not cleaned.startswith(("http://", "https://")):
        cleaned = "https://" + cleaned

    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return ""

    hostname = parsed.hostname
    if not hostname:
        return ""

    if hostname.startswith("www."):
        hostname = hostname[4:]

    hostname = hostname.split(":")[0].strip("/")
    if not DOMAIN_REGEX.match(hostname):
        return ""

    return hostname


def find_near_matches(name: str, existing_names: list[str], threshold: float = 0.7) -> list[str]:
    """Find near matches to company name in existing companies using difflib."""
    target = name.strip().lower()
    if len(target) < 3:
        return []

    matches: list[str] = []
    for candidate in existing_names:
        cand_lower = candidate.strip().lower()
        if cand_lower == target:
            continue

        ratio = SequenceMatcher(None, target, cand_lower).ratio()
        is_sub = (len(cand_lower) >= 4 and cand_lower in target) or (
            len(target) >= 4 and target in cand_lower
        )

        if ratio >= threshold or is_sub:
            matches.append(candidate)
    return matches

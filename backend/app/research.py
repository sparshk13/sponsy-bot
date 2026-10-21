"""Research pipeline, fact extraction, verification, and scoring (R2, R3, R10, R12)."""

import re
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.budget import run_with_budget
from app.llm import llm_client
from app.models import Company, CompanyFact, Contact, Target, utc_now
from app.search import search_client

CACHE_WINDOW = timedelta(days=30)
FUNDING_SIGNALS = (
    "employee",
    "funding",
    "revenue",
    "raised",
    "billion",
    "million",
    "series",
    "ipo",
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def compute_priority(
    verified_facts: list[CompanyFact],
    has_category: bool,
    has_contact: bool,
) -> tuple[str, int]:
    """Calculate deterministic priority score per ARCHITECTURE.md section 5."""
    score = 0

    has_past_sponsorship = any(f.kind == "past_sponsorship" for f in verified_facts)
    if has_past_sponsorship:
        score += 3

    if has_category:
        score += 2

    has_funding = any(
        any(sig in f.claim.lower() for sig in FUNDING_SIGNALS) for f in verified_facts
    )
    if has_funding:
        score += 1

    if has_contact:
        score += 1

    priority = "A" if score >= 4 else "B" if score >= 2 else "C"
    return priority, score


def run_research(db: Session, target: Target, force_refresh: bool = False) -> None:
    """Execute research, fact extraction, quote verification, and recommendation."""
    company: Company = target.company
    now = utc_now()

    is_cached = (
        not force_refresh
        and target.researched_at is not None
        and (now - target.researched_at) < CACHE_WINDOW
    )

    if not is_cached:
        # BUD-05: at most 2 Tavily searches
        q1 = f"{company.name} company profile overview about"
        q2 = f"{company.name} sponsor student hackathon university grant tech event"

        res1 = run_with_budget(db, "tavily", search_client.search, 1, q1, 3)
        res2 = run_with_budget(db, "tavily", search_client.search, 1, q2, 3)

        combined_results = res1 + res2
        source_dict: dict[int, dict[str, str]] = {}
        source_list_for_llm: list[dict[str, str]] = []

        for idx, item in enumerate(combined_results, start=1):
            source_dict[idx] = {
                "id": str(idx),
                "url": item.url,
                "content": item.content,
            }
            source_list_for_llm.append(source_dict[idx])

        # BUD-06: 1 call to extract facts
        fact_batch = run_with_budget(
            db,
            "gemini",
            llm_client.extract_facts,
            1,
            company.name,
            company.domain,
            source_list_for_llm,
        )

        # PRD R12: verify quotes against retrieved sources
        new_facts: list[CompanyFact] = []
        for ef in fact_batch.facts:
            source = source_dict.get(ef.source_id)
            if not source or not source["url"]:
                status = "unverified"
                source_url = ""
            else:
                source_url = source["url"]
                norm_quote = normalize_text(ef.evidence_quote)
                norm_source = normalize_text(source["content"])
                status = "verified" if (norm_quote and norm_quote in norm_source) else "unverified"

            fact_row = CompanyFact(
                company_id=company.id,
                kind=ef.kind,
                claim=ef.claim.strip(),
                source_url=source_url,
                evidence_quote=ef.evidence_quote.strip(),
                status=status,
                retrieved_at=now,
            )
            db.add(fact_row)
            new_facts.append(fact_row)

        db.commit()

    all_facts = list(
        db.scalars(
            select(CompanyFact)
            .where(CompanyFact.company_id == company.id)
            .order_by(CompanyFact.id.asc())
        ).all()
    )
    verified_facts = [f for f in all_facts if f.status == "verified"]

    has_contact = (
        db.scalar(
            select(Contact.id)
            .where(Contact.company_id == company.id, Contact.is_valid.is_(True))
            .limit(1)
        )
        is not None
    )

    priority, score = compute_priority(
        verified_facts=verified_facts,
        has_category=bool(company.category),
        has_contact=has_contact,
    )

    campaign = target.campaign
    campaign_info = {
        "event_summary": campaign.event_summary,
        "event_date": str(campaign.event_date) if campaign.event_date else "",
        "cash_target": str(campaign.cash_target_inr) if campaign.cash_target_inr else "",
        "goodies_note": campaign.goodies_note or "",
        "credits_note": campaign.credits_note or "",
    }

    verified_facts_payload = [
        {"id": f.id, "kind": f.kind, "claim": f.claim} for f in verified_facts
    ]

    # BUD-06: 1 call to recommend tier and ask
    rec = run_with_budget(
        db,
        "gemini",
        llm_client.recommend_ask,
        1,
        company.name,
        company.category,
        campaign_info,
        verified_facts_payload,
    )

    verified_ids_set = {f.id for f in verified_facts}
    valid_reasoning_ids = [fid for fid in rec.reasoning_fact_ids if fid in verified_ids_set]

    if not verified_facts or not valid_reasoning_ids:
        target.ask_basis = "assumption"
        target.ask_summary = rec.ask_summary or f"Sponsorship request for {company.name}"
        target.ask_reasoning = (
            "No sponsorship history found in the sources searched. This ask is an assumption."
        )
        target.ask_fact_ids = []
    else:
        target.ask_basis = "evidence"
        target.ask_summary = rec.ask_summary
        target.ask_reasoning = rec.ask_reasoning
        target.ask_fact_ids = valid_reasoning_ids

    target.tier = rec.tier
    target.priority = priority
    target.priority_score = score
    target.researched_at = now

    db.commit()
    db.refresh(target)

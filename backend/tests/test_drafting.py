"""Tests for draft validator, fact citations, number whitelisting, and similarity bound."""

from app.drafting import compute_approved_hash, validate_draft

SAMPLE_CAMPAIGN = {
    "name": "HackFest 2026",
    "event_summary": "A 24-hour student hackathon",
    "event_date": "2026-10-24",
    "audience_note": "150 engineering students",
    "cash_target_inr": 150000,
    "goodies_note": "Stickers and swag",
    "credits_note": "Cloud compute credits",
    "calendar_link": "https://cal.com/hackfest",
}

VERIFIED_FACTS = [
    {
        "id": 101,
        "kind": "past_sponsorship",
        "claim": "Sponsored PyCon India in 2024 with 50000 INR",
        "evidence_quote": "We contributed 50000 INR to PyCon India 2024.",
        "status": "verified",
    },
    {
        "id": 102,
        "kind": "profile",
        "claim": "Developer platform for cloud deployments",
        "evidence_quote": "A developer platform for fast cloud deployments.",
        "status": "verified",
    },
    {
        "id": 103,
        "kind": "other",
        "claim": "Offered student internships in 2025",
        "evidence_quote": "Hired 5 student interns in 2025.",
        "status": "unverified",
    },
]


def _build_valid_body(company_name: str = "Acme Corp") -> str:
    # 80 to 160 words, contains opt-out, allowed numbers (24, 2026, 150, 50000, 2024)
    return (
        f"Hello,\n\n"
        f"I organize HackFest 2026 at our college, a 24-hour hackathon on 2026-10-24 "
        f"for about 150 student engineers. We are bringing together motivated students "
        f"to build technical projects over a single weekend.\n\n"
        f"I noticed that {company_name} sponsored PyCon India in 2024 with 50000 INR to help "
        f"the tech community. Your developer tools are popular among our participants, and "
        f"support from your team would make a genuine difference for our event.\n\n"
        f"Could {company_name} consider sponsoring our hackathon? In return, we would feature "
        f"your developer tools directly to participants. "
        f"If a short call is easier, please let me know.\n\n"
        f"Sparsh, Organizer, Student Tech Club\n"
        f"If this is not for you, tell me and I will not write again."
    )


def test_draft_validator_accepts_valid_draft():
    body = _build_valid_body("Acme Corp")
    result = validate_draft(
        subject="Credits for student hackathon",
        body=body,
        facts_used=[101],
        campaign_data=SAMPLE_CAMPAIGN,
        company_name="Acme Corp",
        verified_facts=VERIFIED_FACTS,
    )
    assert result.is_valid is True
    assert result.errors == []


def test_draft_validator_rejects_unverified_fact_id():
    body = _build_valid_body("Acme Corp")
    # Fact 103 is unverified in VERIFIED_FACTS
    result = validate_draft(
        subject="Credits for student hackathon",
        body=body,
        facts_used=[103],
        campaign_data=SAMPLE_CAMPAIGN,
        company_name="Acme Corp",
        verified_facts=VERIFIED_FACTS,
    )
    assert result.is_valid is False
    assert any("not a verified fact" in err for err in result.errors)


def test_draft_validator_rejects_invented_number():
    body = _build_valid_body("Acme Corp").replace("50000 INR", "99999 INR")
    result = validate_draft(
        subject="Credits for student hackathon",
        body=body,
        facts_used=[101],
        campaign_data=SAMPLE_CAMPAIGN,
        company_name="Acme Corp",
        verified_facts=VERIFIED_FACTS,
    )
    assert result.is_valid is False
    assert any("invented numbers or years: 99999" in err for err in result.errors)


def test_draft_validator_rejects_placeholder_brackets():
    body = _build_valid_body("Acme Corp").replace("Hello,", "Hello [Name],")
    result = validate_draft(
        subject="Credits for student hackathon",
        body=body,
        facts_used=[101],
        campaign_data=SAMPLE_CAMPAIGN,
        company_name="Acme Corp",
        verified_facts=VERIFIED_FACTS,
    )
    assert result.is_valid is False
    assert any("placeholder brackets" in err for err in result.errors)


def test_draft_validator_rejects_html_and_markdown():
    # Test HTML
    body_html = _build_valid_body("Acme Corp") + "<p>Extra line</p>"
    result_html = validate_draft(
        subject="Credits for student hackathon",
        body=body_html,
        facts_used=[101],
        campaign_data=SAMPLE_CAMPAIGN,
        company_name="Acme Corp",
        verified_facts=VERIFIED_FACTS,
    )
    assert result_html.is_valid is False
    assert any("HTML tags" in err for err in result_html.errors)

    # Test Markdown bold
    body_md = _build_valid_body("Acme Corp").replace("HackFest 2026", "**HackFest 2026**")
    result_md = validate_draft(
        subject="Credits for student hackathon",
        body=body_md,
        facts_used=[101],
        campaign_data=SAMPLE_CAMPAIGN,
        company_name="Acme Corp",
        verified_facts=VERIFIED_FACTS,
    )
    assert result_md.is_valid is False
    assert any("Markdown bold" in err for err in result_md.errors)


def test_draft_validator_rejects_missing_opt_out():
    body_no_opt = _build_valid_body("Acme Corp").replace(
        "If this is not for you, tell me and I will not write again.",
        "Thank you for your time.",
    )
    result = validate_draft(
        subject="Credits for student hackathon",
        body=body_no_opt,
        facts_used=[101],
        campaign_data=SAMPLE_CAMPAIGN,
        company_name="Acme Corp",
        verified_facts=VERIFIED_FACTS,
    )
    assert result.is_valid is False
    assert any("opt-out sentence" in err for err in result.errors)


def test_draft_validator_rejects_short_word_count():
    body_short = (
        "Hello. We are organizing a student event. We need your sponsorship. "
        "If this is not for you, tell me and I will not write again."
    )
    result = validate_draft(
        subject="Credits for student hackathon",
        body=body_short,
        facts_used=[],
        campaign_data=SAMPLE_CAMPAIGN,
        company_name="Acme Corp",
        verified_facts=[],
    )
    assert result.is_valid is False
    assert any("outside the allowed 80-160 range" in err for err in result.errors)


def test_draft_validator_similarity_bound():
    body1 = _build_valid_body("Alpha Corp")
    # An almost identical body with just company name changed should trigger similarity bound >= 0.8
    body2 = _build_valid_body("Beta Corp")

    result = validate_draft(
        subject="Credits for student hackathon",
        body=body2,
        facts_used=[101],
        campaign_data=SAMPLE_CAMPAIGN,
        company_name="Beta Corp",
        verified_facts=VERIFIED_FACTS,
        other_draft_bodies=[body1],
    )
    assert result.is_valid is False
    assert any("too similar" in err for err in result.errors)


def test_compute_approved_hash():
    h1 = compute_approved_hash("contact@acme.com", "Sponsorship", "Email body text")
    h2 = compute_approved_hash("CONTACT@acme.com ", "Sponsorship", "Email body text")
    assert h1 == h2
    assert len(h1) == 64

    # Any change in body voids/changes hash
    h3 = compute_approved_hash("contact@acme.com", "Sponsorship", "Email body text.")
    assert h1 != h3

"""Tests for research, quote verification, caching, and scoring (R2, R3, R10, R12)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, create_session
from app.models import Campaign, Company, Target, User
from tests.fixtures.search_data import (
    FAKE_INJECTION_CONTENT,
    FakeLLMClient,
    FakeSearchClient,
    SearchResult,
)


def auth_client(client: TestClient, db: Session, user: User) -> tuple[TestClient, str]:
    raw_token, csrf_token = create_session(db, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    return client, csrf_token


def test_quote_verification_verifies_real_and_flags_fabricated(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session, monkeypatch
) -> None:
    company = Company(name="Stripe", domain="stripe.com", category="Fintech")
    db.add(company)
    db.commit()

    target = Target(campaign_id=test_campaign.id, company_id=company.id, owner_id=organizer_user.id)
    db.add(target)
    db.commit()

    fake_search = FakeSearchClient()
    fake_llm = FakeLLMClient()

    monkeypatch.setattr("app.research.search_client", fake_search)
    monkeypatch.setattr("app.research.llm_client", fake_llm)

    _, csrf = auth_client(client, db, organizer_user)
    resp = client.post(f"/api/targets/{target.id}/prepare", headers={"X-CSRF-Token": csrf})

    assert resp.status_code == 200
    data = resp.json()

    assert data["ask_basis"] == "evidence"
    assert len(data["facts"]) == 3

    facts_by_claim = {f["claim"]: f for f in data["facts"]}
    verified_claim = "Stripe sponsored HackMIT in 2025 with $10,000 in cash"
    unverified_claim = "Stripe sponsored CollegeCon with $50,000 in 2024"

    assert facts_by_claim[verified_claim]["status"] == "verified"
    assert facts_by_claim[unverified_claim]["status"] == "unverified"


def test_unverified_facts_are_never_used_in_ask_reasoning(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session, monkeypatch
) -> None:
    company = Company(name="Acme", domain="acme.com", category="Software")
    db.add(company)
    db.commit()

    target = Target(campaign_id=test_campaign.id, company_id=company.id, owner_id=organizer_user.id)
    db.add(target)
    db.commit()

    fake_search = FakeSearchClient()
    fake_llm = FakeLLMClient()

    monkeypatch.setattr("app.research.search_client", fake_search)
    monkeypatch.setattr("app.research.llm_client", fake_llm)

    _, csrf = auth_client(client, db, organizer_user)
    resp = client.post(f"/api/targets/{target.id}/prepare", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200
    data = resp.json()

    # Fact ids in reasoning must belong only to verified facts
    verified_fact_ids = {f["id"] for f in data["facts"] if f["status"] == "verified"}
    unverified_fact_ids = {f["id"] for f in data["facts"] if f["status"] == "unverified"}

    assert data["ask_fact_ids"] is not None
    for fid in data["ask_fact_ids"]:
        assert fid in verified_fact_ids
        assert fid not in unverified_fact_ids


def test_company_with_no_search_results_shows_no_evidence_and_assumption_basis(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session, monkeypatch
) -> None:
    company = Company(name="Obscure Startup", domain="obscure.com")
    db.add(company)
    db.commit()

    target = Target(campaign_id=test_campaign.id, company_id=company.id, owner_id=organizer_user.id)
    db.add(target)
    db.commit()

    # Fake search returning 0 results and fake LLM returning 0 facts
    fake_search = FakeSearchClient(results=[])
    from app.llm import FactBatch

    fake_llm = FakeLLMClient(fact_batch=FactBatch(facts=[]))

    monkeypatch.setattr("app.research.search_client", fake_search)
    monkeypatch.setattr("app.research.llm_client", fake_llm)

    _, csrf = auth_client(client, db, organizer_user)
    resp = client.post(f"/api/targets/{target.id}/prepare", headers={"X-CSRF-Token": csrf})

    assert resp.status_code == 200
    data = resp.json()

    assert data["ask_basis"] == "assumption"
    assert "No sponsorship history found in the sources searched" in data["ask_reasoning"]
    assert data["ask_fact_ids"] == []


def test_30_day_cache_prevents_repeat_search_and_extraction(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session, monkeypatch
) -> None:
    company = Company(name="Cached Corp", domain="cached.com")
    db.add(company)
    db.commit()

    target = Target(campaign_id=test_campaign.id, company_id=company.id, owner_id=organizer_user.id)
    db.add(target)
    db.commit()

    fake_search = FakeSearchClient()
    fake_llm = FakeLLMClient()

    monkeypatch.setattr("app.research.search_client", fake_search)
    monkeypatch.setattr("app.research.llm_client", fake_llm)

    _, csrf = auth_client(client, db, organizer_user)

    # First run executes search
    resp1 = client.post(f"/api/targets/{target.id}/prepare", headers={"X-CSRF-Token": csrf})
    assert resp1.status_code == 200
    assert fake_search.call_count == 2
    assert fake_llm.extract_call_count == 1

    # Second run within 30 days makes 0 new search or extraction calls (BUD-04)
    resp2 = client.post(f"/api/targets/{target.id}/prepare", headers={"X-CSRF-Token": csrf})
    assert resp2.status_code == 200
    assert fake_search.call_count == 2
    assert fake_llm.extract_call_count == 1

    # Refresh research forces repeat search
    resp3 = client.post(
        f"/api/targets/{target.id}/refresh-research", headers={"X-CSRF-Token": csrf}
    )
    assert resp3.status_code == 200
    assert fake_search.call_count == 4
    assert fake_llm.extract_call_count == 2


def test_non_owner_cannot_prepare_target(
    client: TestClient, admin_user: User, organizer_user: User, test_campaign: Campaign, db: Session
) -> None:
    company = Company(name="Restricted Corp", domain="restricted.com")
    db.add(company)
    db.commit()

    target = Target(campaign_id=test_campaign.id, company_id=company.id, owner_id=admin_user.id)
    db.add(target)
    db.commit()

    # Organizer is not the owner
    _, csrf = auth_client(client, db, organizer_user)
    resp = client.post(f"/api/targets/{target.id}/prepare", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 403
    assert "You do not own this target" in resp.json()["detail"]


def test_prompt_injection_in_search_result_treated_as_data(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session, monkeypatch
) -> None:
    company = Company(name="Untrusted Site", domain="untrusted.com")
    db.add(company)
    db.commit()

    target = Target(campaign_id=test_campaign.id, company_id=company.id, owner_id=organizer_user.id)
    db.add(target)
    db.commit()

    fake_search = FakeSearchClient(
        results=[
            SearchResult(
                url="https://evil.com",
                title="Hacked Page",
                content=FAKE_INJECTION_CONTENT,
            )
        ]
    )
    fake_llm = FakeLLMClient()

    monkeypatch.setattr("app.research.search_client", fake_search)
    monkeypatch.setattr("app.research.llm_client", fake_llm)

    _, csrf = auth_client(client, db, organizer_user)
    resp = client.post(f"/api/targets/{target.id}/prepare", headers={"X-CSRF-Token": csrf})
    assert resp.status_code == 200

    # Ensure status remained 'not_contacted' and was NOT set to secured or approved (SEC-24)
    db.refresh(target)
    assert target.status == "not_contacted"

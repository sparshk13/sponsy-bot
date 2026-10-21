"""Tests for budget tracking, counted wrappers, and usage endpoints (BUD-01 to BUD-03, BUD-09)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, create_session
from app.budget import BudgetExhausted, check_budget, increment_usage, run_with_budget
from app.config import settings
from app.models import Campaign, Company, Target, User
from tests.fixtures.search_data import FakeLLMClient, FakeSearchClient


def auth_client(client: TestClient, db: Session, user: User) -> tuple[TestClient, str]:
    raw_token, csrf_token = create_session(db, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    return client, csrf_token


def test_budget_exhaustion_blocks_calls(db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "gemini_daily_call_cap", 5)

    # Increment usage up to the cap
    increment_usage(db, "gemini", 5)

    # Calling check_budget must raise BudgetExhausted
    try:
        check_budget(db, "gemini", 1)
        assert False, "Expected BudgetExhausted exception"
    except BudgetExhausted as e:
        assert "Gemini daily budget cap of 5 units" in str(e)

    # run_with_budget must refuse and execute 0 times
    called = False

    def dummy() -> None:
        nonlocal called
        called = True

    try:
        run_with_budget(db, "gemini", dummy, 1)
        assert False, "Expected BudgetExhausted exception"
    except BudgetExhausted:
        pass

    assert not called


def test_prepare_target_returns_429_when_budget_exhausted(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session, monkeypatch
) -> None:
    company = Company(name="Exhausted Corp", domain="exhausted.com")
    db.add(company)
    db.commit()

    target = Target(campaign_id=test_campaign.id, company_id=company.id, owner_id=organizer_user.id)
    db.add(target)
    db.commit()

    # Exhaust Tavily budget
    monkeypatch.setattr(settings, "tavily_monthly_credit_cap", 10)
    increment_usage(db, "tavily", 10)

    monkeypatch.setattr("app.research.search_client", FakeSearchClient())
    monkeypatch.setattr("app.research.llm_client", FakeLLMClient())

    _, csrf = auth_client(client, db, organizer_user)
    resp = client.post(f"/api/targets/{target.id}/prepare", headers={"X-CSRF-Token": csrf})

    assert resp.status_code == 429
    assert "budget cap" in resp.json()["detail"].lower()


def test_usage_overview_reports_stats_and_warnings(
    client: TestClient, organizer_user: User, db: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "gemini_daily_call_cap", 100)
    # Set 85 units to trigger 80% warning
    increment_usage(db, "gemini", 85)

    _, csrf = auth_client(client, db, organizer_user)
    resp = client.get("/api/usage")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 3

    gemini_item = next(item for item in data if item["provider"] == "gemini")
    assert gemini_item["used"] == 85
    assert gemini_item["cap"] == 100
    assert gemini_item["percent"] == 85
    assert gemini_item["is_warning"] is True
    assert gemini_item["is_exhausted"] is False

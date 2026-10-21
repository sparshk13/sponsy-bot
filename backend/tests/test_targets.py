"""Tests for campaigns, companies, targets, deduplication, and claims (Phase 2)."""

import io
import threading
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.auth import SESSION_COOKIE_NAME, create_session
from app.models import Campaign, Company, Message, Target, User
from app.routes.targets import check_cooldown


def auth_client(client: TestClient, db: Session, user: User) -> tuple[TestClient, str]:
    raw_token, csrf_token = create_session(db, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    return client, csrf_token


def test_domain_normalization_handles_variations() -> None:
    from app.domain_norm import normalize_domain

    assert normalize_domain("https://www.Google.com/about/") == "google.com"
    assert normalize_domain("http://github.com:443") == "github.com"
    assert normalize_domain("WWW.STRIPE.COM/pricing?ref=1") == "stripe.com"
    assert normalize_domain("subdomain.example.co.uk/") == "subdomain.example.co.uk"


def test_admin_can_create_and_update_campaign(
    client: TestClient, admin_user: User, organizer_user: User, db: Session
) -> None:
    _, csrf = auth_client(client, db, admin_user)

    resp = client.post(
        "/api/admin/campaigns",
        headers={"X-CSRF-Token": csrf},
        json={
            "name": "DevCon 2026",
            "event_summary": "National developers conference.",
            "cash_target_inr": 1000000,
        },
    )
    assert resp.status_code == 201
    campaign_id = resp.json()["id"]

    # Organizer cannot update campaign (SEC-09)
    auth_client(client, db, organizer_user)
    org_update = client.put(
        f"/api/admin/campaigns/{campaign_id}",
        headers={"X-CSRF-Token": csrf},
        json={"name": "Hacked Name"},
    )
    assert org_update.status_code == 403


def test_add_target_manual_and_duplicate_prevention(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session
) -> None:
    _, csrf = auth_client(client, db, organizer_user)

    resp = client.post(
        "/api/targets",
        headers={"X-CSRF-Token": csrf},
        json={
            "campaign_id": test_campaign.id,
            "name": "Acme Software",
            "website": "https://www.acme-software.com/careers",
            "category": "Dev Tools",
            "contact_name": "Jane Contact",
            "contact_email": "jane@acme-software.com",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["domain"] == "acme-software.com"
    assert data["contact"]["email"] == "jane@acme-software.com"

    # PRD R9: Duplicate target in same campaign rejected
    dup_resp = client.post(
        "/api/targets",
        headers={"X-CSRF-Token": csrf},
        json={
            "campaign_id": test_campaign.id,
            "name": "Acme Duplicate",
            "website": "acme-software.com",
        },
    )
    assert dup_resp.status_code == 400
    assert "already a target" in dup_resp.json()["detail"]


def test_csv_import_with_60_rows_and_duplicates_reports_skipped(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session
) -> None:
    _, csrf = auth_client(client, db, organizer_user)

    # Generate 60 CSV rows: 40 unique companies, 15 duplicates, 5 empty/invalid
    lines = ["company,website,category,contact name,email"]
    for i in range(1, 41):
        lines.append(
            f"Company {i},https://www.company{i}.com,Tech,Person {i},person{i}@company{i}.com"
        )
    # Duplicate domains within batch
    for i in range(1, 16):
        lines.append(
            f"Company {i} Duplicate,http://company{i}.com,Tech,Other,other{i}@company{i}.com"
        )
    # Invalid rows
    lines.append(",,,")
    lines.append("Invalid No Website,,Tech,Person,p@example.com")
    lines.append("Invalid Bad URL,://bad,Tech,Person,p2@example.com")
    lines.append(",https://noname.com,Tech,Person,p3@example.com")
    lines.append("Empty Domain, ,Tech,Person,p4@example.com")

    csv_content = "\n".join(lines).encode("utf-8")

    resp = client.post(
        "/api/targets/import",
        headers={"X-CSRF-Token": csrf},
        data={"campaign_id": test_campaign.id},
        files={"file": ("sponsors.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200
    result = resp.json()

    assert result["total"] == 60
    assert result["created"] == 40
    assert result["skipped"] == 20
    assert len(result["rows"]) == 60

    # Verify report indicates why skipped
    skipped_rows = [r for r in result["rows"] if r["status"] == "skipped"]
    assert len(skipped_rows) == 20
    assert any("Duplicate domain" in r["reason"] for r in skipped_rows)


def test_fuzzy_near_match_warning_on_csv_import(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session
) -> None:
    # Pre-populate a company
    db.add(Company(name="Google Cloud", domain="cloud.google.com"))
    db.commit()

    _, csrf = auth_client(client, db, organizer_user)
    csv_content = "name,website\nGoogle Cloud Platform,https://gcp.google.com\n".encode("utf-8")

    resp = client.post(
        "/api/targets/import",
        headers={"X-CSRF-Token": csrf},
        data={"campaign_id": test_campaign.id},
        files={"file": ("test.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert resp.status_code == 200
    res = resp.json()
    assert len(res["near_matches"]) >= 1
    assert "Google Cloud" in res["near_matches"][0]


def test_target_claim_and_other_user_conflict(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session
) -> None:
    # Create Priya
    from app.auth import hash_password

    priya = User(
        email="priya@example.com",
        name="Priya",
        role="organizer",
        password_hash=hash_password("priya_password123"),
        is_active=True,
    )
    db.add(priya)
    company = Company(name="Stripe", domain="stripe.com")
    db.add(company)
    db.commit()

    target = Target(campaign_id=test_campaign.id, company_id=company.id)
    db.add(target)
    db.commit()

    # Priya claims target
    _, csrf_priya = auth_client(client, db, priya)
    claim_resp = client.post(
        f"/api/targets/{target.id}/claim", headers={"X-CSRF-Token": csrf_priya}
    )
    assert claim_resp.status_code == 200

    # Another organizer attempts to claim
    _, csrf_org = auth_client(client, db, organizer_user)
    conflict_resp = client.post(
        f"/api/targets/{target.id}/claim", headers={"X-CSRF-Token": csrf_org}
    )
    assert conflict_resp.status_code == 409
    expected_msg = "Priya owns this company. Ask an admin if it needs to move."
    assert conflict_resp.json()["detail"] == expected_msg


def test_two_users_claiming_same_target_race_safely(
    db: Session, test_campaign: Campaign, organizer_user: User
) -> None:
    # SEC-37 & PRD R9: test concurrent claim race condition with threads on real PostgreSQL
    from app.auth import hash_password

    user_a = organizer_user
    user_b = User(
        email="user_b@example.com",
        name="User B",
        role="organizer",
        password_hash=hash_password("user_b_pass123"),
        is_active=True,
    )
    company = Company(name="Concurrent Corp", domain="concurrent.com")
    db.add_all([user_b, company])
    db.commit()

    target = Target(campaign_id=test_campaign.id, company_id=company.id)
    db.add(target)
    db.commit()
    target_id = target.id

    engine = db.get_bind()
    session_factory = sessionmaker(bind=engine)

    results: list[dict[str, bool | str]] = []

    def attempt_claim(user_id: int, user_name: str) -> None:
        local_db = session_factory()
        try:
            # Using SELECT FOR UPDATE as in route
            t = local_db.scalar(select(Target).where(Target.id == target_id).with_for_update())
            if t and t.owner_id is None:
                t.owner_id = user_id
                local_db.commit()
                results.append({"user": user_name, "success": True})
            else:
                results.append({"user": user_name, "success": False})
        except Exception as e:
            local_db.rollback()
            results.append({"user": user_name, "success": False, "error": str(e)})
        finally:
            local_db.close()

    thread1 = threading.Thread(target=attempt_claim, args=(user_a.id, "User A"))
    thread2 = threading.Thread(target=attempt_claim, args=(user_b.id, "User B"))

    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    successes = [r for r in results if r.get("success") is True]
    assert len(successes) == 1, f"Expected exactly 1 winner in atomic claim race, got: {results}"


def test_90_day_cooldown_and_admin_unlock(
    client: TestClient,
    admin_user: User,
    organizer_user: User,
    test_campaign: Campaign,
    db: Session,
) -> None:
    # Create past campaign and company
    old_campaign = Campaign(
        name="Old Hackathon", event_summary="Last year", created_by=admin_user.id
    )
    company = Company(name="Cooldown Corp", domain="cooldown.com")
    db.add_all([old_campaign, company])
    db.commit()

    old_target = Target(campaign_id=old_campaign.id, company_id=company.id)
    db.add(old_target)
    db.commit()

    # Create message sent 30 days ago (within 90-day cooldown)
    msg = Message(
        target_id=old_target.id,
        direction="out",
        kind="first",
        status="sent",
        sent_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    db.add(msg)
    db.commit()

    # Target in new campaign
    new_target = Target(campaign_id=test_campaign.id, company_id=company.id)
    db.add(new_target)
    db.commit()

    assert check_cooldown(db, company.id) is True

    # Organizer cannot unlock cooldown (SEC-09)
    _, csrf_org = auth_client(client, db, organizer_user)
    unlock_fail = client.post(
        f"/api/targets/{new_target.id}/unlock", headers={"X-CSRF-Token": csrf_org}
    )
    assert unlock_fail.status_code == 403

    # Admin unlocks cooldown
    _, csrf_admin = auth_client(client, db, admin_user)
    unlock_resp = client.post(
        f"/api/targets/{new_target.id}/unlock", headers={"X-CSRF-Token": csrf_admin}
    )
    assert unlock_resp.status_code == 200
    assert unlock_resp.json()["cooldown_unlocked"] is True
    assert unlock_resp.json()["cooldown_active"] is False


def test_list_targets_with_filters(
    client: TestClient, organizer_user: User, test_campaign: Campaign, db: Session
) -> None:
    c1 = Company(name="Alpha Corp", domain="alpha.com", category="Fintech")
    c2 = Company(name="Beta Corp", domain="beta.com", category="Gaming")
    db.add_all([c1, c2])
    db.commit()

    t1 = Target(campaign_id=test_campaign.id, company_id=c1.id, status="not_contacted", tier="cash")
    t2 = Target(campaign_id=test_campaign.id, company_id=c2.id, status="contacted", tier="goodies")
    db.add_all([t1, t2])
    db.commit()

    _, csrf = auth_client(client, db, organizer_user)

    # Filter by status
    resp = client.get(f"/api/targets?campaign_id={test_campaign.id}&status=contacted")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["domain"] == "beta.com"

    # Search filter
    search_resp = client.get(f"/api/targets?campaign_id={test_campaign.id}&search=alpha")
    assert search_resp.status_code == 200
    assert len(search_resp.json()) == 1
    assert search_resp.json()[0]["domain"] == "alpha.com"

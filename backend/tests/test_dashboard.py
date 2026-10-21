"""Tests for Phase 9: Dashboard, Institutional Memory, and CSV Export (G3, G10, SEC-30)."""

import csv
import io

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, create_session, hash_password
from app.models import AuditLog, Campaign, Company, Contact, Outcome, Target, User


def _login(client: TestClient, user: User, db: Session) -> dict[str, str]:
    token, csrf_token = create_session(db, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, token)
    return {"X-CSRF-Token": csrf_token}


def test_dashboard_stats_match_db(client: TestClient, db: Session):
    """Test dashboard stats reflect database state across all stages (G3)."""
    admin = User(
        email="dashadmin@test.org",
        name="Dashboard Admin",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    organizer = User(
        email="dashorg@test.org",
        name="Dashboard Organizer",
        role="organizer",
        password_hash=hash_password("orgpass123456"),
    )
    db.add_all([admin, organizer])
    db.commit()

    campaign = Campaign(
        name="Hackathon 2026",
        event_summary="Premier annual hackathon",
        created_by=admin.id,
    )
    db.add(campaign)
    db.commit()

    stages = [
        "not_contacted",
        "not_contacted",
        "contacted",
        "follow_up",
        "interested",
        "meeting_booked",
        "secured",
        "declined",
        "closed_no_reply",
    ]

    targets = []
    for idx, stage in enumerate(stages):
        company = Company(name=f"Company {idx}", domain=f"company{idx}.com")
        db.add(company)
        db.commit()

        target = Target(
            campaign_id=campaign.id,
            company_id=company.id,
            owner_id=organizer.id if idx % 2 == 0 else admin.id,
            status=stage,
            tier="cash" if idx % 2 == 0 else "credits",
            priority="A" if idx % 2 == 0 else "B",
            ask_summary="Support student hackathon",
        )
        db.add(target)
        db.commit()
        targets.append(target)

    # Add outcomes
    secured_target = next(t for t in targets if t.status == "secured")
    cash_outcome = Outcome(
        target_id=secured_target.id,
        kind="cash",
        amount_inr=150000,
        description="Gold tier cash support",
        confirmed_by=admin.id,
    )
    goodies_outcome = Outcome(
        target_id=secured_target.id,
        kind="goodies",
        amount_inr=None,
        description="50 T-shirts and stickers",
        confirmed_by=admin.id,
    )
    db.add_all([cash_outcome, goodies_outcome])
    db.commit()

    headers = _login(client, organizer, db)
    resp = client.get("/api/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_targets"] == 9
    assert data["contacted_count"] == 7
    # Stages count check
    pipeline_dict = {item["stage"]: item["count"] for item in data["pipeline"]}
    assert pipeline_dict["not_contacted"] == 2
    assert pipeline_dict["contacted"] == 1
    assert pipeline_dict["follow_up"] == 1
    assert pipeline_dict["interested"] == 1
    assert pipeline_dict["meeting_booked"] == 1
    assert pipeline_dict["secured"] == 1
    assert pipeline_dict["declined"] == 1
    assert pipeline_dict["closed_no_reply"] == 1

    # Interested count: interested (1) + meeting_booked (1) + secured (1) = 3
    assert data["interested_count"] == 3
    assert data["declined_count"] == 1
    assert data["secured_count"] == 1

    # Rates: 3 / 7 = 42.9%
    assert data["interest_rate"] == 42.9

    # Cash and non-cash totals
    assert data["total_cash_inr"] == 150000
    assert len(data["non_cash_outcomes"]) == 1
    assert data["non_cash_outcomes"][0]["kind"] == "goodies"
    assert data["non_cash_outcomes"][0]["description"] == "50 T-shirts and stickers"


def test_dashboard_organizer_stats(client: TestClient, db: Session):
    """Test per-organizer dashboard breakdown (G3)."""
    admin = User(
        email="lead@test.org",
        name="Team Lead",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    member = User(
        email="member@test.org",
        name="Team Member",
        role="organizer",
        password_hash=hash_password("memberpass123"),
    )
    db.add_all([admin, member])
    db.commit()

    campaign = Campaign(
        name="CodeFest 2026",
        event_summary="Annual coding festival",
        created_by=admin.id,
    )
    db.add(campaign)
    db.commit()

    # Assign 2 targets to member (1 contacted, 1 secured)
    c1 = Company(name="Cloud Corp", domain="cloudcorp.io")
    c2 = Company(name="Dev Inc", domain="devinc.org")
    db.add_all([c1, c2])
    db.commit()

    t1 = Target(
        campaign_id=campaign.id,
        company_id=c1.id,
        owner_id=member.id,
        status="contacted",
    )
    t2 = Target(
        campaign_id=campaign.id,
        company_id=c2.id,
        owner_id=member.id,
        status="secured",
    )
    db.add_all([t1, t2])
    db.commit()

    outcome = Outcome(
        target_id=t2.id,
        kind="cash",
        amount_inr=200000,
        confirmed_by=member.id,
    )
    db.add(outcome)
    db.commit()

    headers = _login(client, admin, db)
    resp = client.get("/api/dashboard", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    member_stat = next(o for o in data["organizers"] if o["user_id"] == member.id)
    assert member_stat["assigned_count"] == 2
    assert member_stat["contacted_count"] == 2
    assert member_stat["secured_count"] == 1
    assert member_stat["secured_cash_inr"] == 200000


def test_memory_endpoint_returns_past_sponsors(client: TestClient, db: Session):
    """Test institutional memory across campaigns (G10)."""
    admin = User(
        email="memadmin@test.org",
        name="Mem Admin",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    db.add(admin)
    db.commit()

    camp1 = Campaign(name="Hack 2025", event_summary="2025 event", created_by=admin.id)
    camp2 = Campaign(name="Hack 2026", event_summary="2026 event", created_by=admin.id)
    db.add_all([camp1, camp2])
    db.commit()

    c1 = Company(name="Alpha Soft", domain="alphasoft.com")
    c2 = Company(name="Beta Labs", domain="betalabs.io")
    db.add_all([c1, c2])
    db.commit()

    t1 = Target(
        campaign_id=camp1.id,
        company_id=c1.id,
        owner_id=admin.id,
        status="secured",
        tier="cash",
        ask_summary="₹1,00,000 cash tier for dev track",
    )
    t2 = Target(
        campaign_id=camp2.id,
        company_id=c2.id,
        owner_id=admin.id,
        status="secured",
        tier="credits",
        ask_summary="Cloud credits for participants",
    )
    db.add_all([t1, t2])
    db.commit()

    o1 = Outcome(
        target_id=t1.id,
        kind="cash",
        amount_inr=100000,
        description="Title sponsor cash",
        confirmed_by=admin.id,
    )
    o2 = Outcome(
        target_id=t2.id,
        kind="credits",
        amount_inr=None,
        description="$5000 AWS credits",
        confirmed_by=admin.id,
    )
    db.add_all([o1, o2])
    db.commit()

    headers = _login(client, admin, db)
    resp = client.get("/api/memory", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_cash_inr"] == 100000
    assert data["total_sponsors"] == 2
    assert len(data["entries"]) == 2

    # Check entries contain past sponsor details and the ask that worked
    alpha_entry = next(e for e in data["entries"] if e["company_name"] == "Alpha Soft")
    assert alpha_entry["company_domain"] == "alphasoft.com"
    assert alpha_entry["campaign_name"] == "Hack 2025"
    assert alpha_entry["kind"] == "cash"
    assert alpha_entry["amount_inr"] == 100000
    assert alpha_entry["ask_worked"] == "₹1,00,000 cash tier for dev track"
    assert alpha_entry["tier"] == "cash"

    beta_entry = next(e for e in data["entries"] if e["company_name"] == "Beta Labs")
    assert beta_entry["company_domain"] == "betalabs.io"
    assert beta_entry["campaign_name"] == "Hack 2026"
    assert beta_entry["kind"] == "credits"
    assert beta_entry["description"] == "$5000 AWS credits"


def test_export_tracker_csv_forbidden_for_organizer(client: TestClient, db: Session):
    """Test non-admin cannot export tracker CSV (SEC-09)."""
    organizer = User(
        email="orgexport@test.org",
        name="Org User",
        role="organizer",
        password_hash=hash_password("orgpass123456"),
    )
    db.add(organizer)
    db.commit()

    headers = _login(client, organizer, db)
    resp = client.get("/api/export/tracker.csv", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Admin access required to export tracker."


def test_export_tracker_csv_admin_success_and_audit(client: TestClient, db: Session):
    """Test admin exports tracker CSV and audit log entry is recorded (SEC-30)."""
    admin = User(
        email="adminexport@test.org",
        name="Admin Exporter",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    db.add(admin)
    db.commit()

    campaign = Campaign(name="ExportFest", event_summary="Event", created_by=admin.id)
    db.add(campaign)
    db.commit()

    company = Company(name="Export Co", domain="exportco.com")
    db.add(company)
    db.commit()

    contact = Contact(
        company_id=company.id,
        name="Alex Smith",
        email="alex@exportco.com",
        role="Partner Director",
    )
    db.add(contact)

    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=admin.id,
        status="secured",
        tier="cash",
        priority="A",
    )
    db.add(target)
    db.commit()

    outcome = Outcome(
        target_id=target.id,
        kind="cash",
        amount_inr=300000,
        description="Gold sponsorship confirmed",
        confirmed_by=admin.id,
    )
    db.add(outcome)
    db.commit()

    headers = _login(client, admin, db)
    resp = client.get("/api/export/tracker.csv", headers=headers)
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert 'attachment; filename="tracker.csv"' in resp.headers["content-disposition"]

    # Parse CSV content
    reader = csv.reader(io.StringIO(resp.text))
    rows = list(reader)
    assert len(rows) >= 2  # Header + at least 1 data row
    header = rows[0]
    assert "company_name" in header
    assert "domain" in header
    assert "outcome_amount_inr" in header

    data_row = next(r for r in rows[1:] if r[0] == "Export Co")
    assert data_row[1] == "exportco.com"
    assert data_row[2] == "ExportFest"
    assert data_row[5] == "secured"
    assert data_row[7] == "Alex Smith"
    assert data_row[8] == "alex@exportco.com"
    assert data_row[13] == "300000"

    # Verify audit log (SEC-30)
    audit = db.scalar(
        select(AuditLog).where(
            AuditLog.user_id == admin.id,
            AuditLog.action == "export_tracker",
        )
    )
    assert audit is not None
    assert audit.entity == "targets"

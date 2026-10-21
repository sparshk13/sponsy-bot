"""Tests for approval queue, edit voids approval, IDOR, and approval invariants."""

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, create_session
from app.graph import build_graph_a
from app.models import AuditLog, Campaign, Company, Contact, Message, Target, User
from app.routes.messages import compute_approved_hash


def auth_client(client: TestClient, db: Session, user: User) -> tuple[TestClient, str]:
    raw_token, csrf_token = create_session(db, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    return client, csrf_token


def _setup_target_with_message(
    db: Session, owner: User, company_name: str = "Test Co", has_contact: bool = True
) -> tuple[Target, Message]:
    campaign = Campaign(
        name="Tech Drive 2026",
        event_summary="Hackathon",
        cash_target_inr=100000,
        created_by=owner.id,
    )
    db.add(campaign)
    db.flush()

    domain = f"{company_name.lower().replace(' ', '')}.com"
    company = Company(name=company_name, domain=domain)
    db.add(company)
    db.flush()

    contact = None
    if has_contact:
        contact = Contact(
            company_id=company.id,
            name="Alice Lead",
            role="Director",
            email=f"alice@{domain}",
        )
        db.add(contact)
        db.flush()

    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=owner.id,
        tier="cash",
    )
    db.add(target)
    db.flush()

    msg = Message(
        target_id=target.id,
        contact_id=contact.id if contact else None,
        direction="out",
        kind="first",
        subject=f"Sponsorship inquiry for {company_name}",
        body="Hello, we would love your support for Tech Drive 2026. "
        "If this is not for you, tell me and I will not write again.",
        status="draft",
        created_by=owner.id,
    )
    db.add(msg)
    db.commit()
    db.refresh(target)
    db.refresh(msg)
    return target, msg


def test_queue_lists_only_own_drafts_for_organizer(client: TestClient, db: Session):
    user_a = User(email="org_a@test.com", name="Org A", password_hash="x", role="organizer")
    user_b = User(email="org_b@test.com", name="Org B", password_hash="x", role="organizer")
    admin = User(email="admin_q@test.com", name="Admin Q", password_hash="x", role="admin")
    db.add_all([user_a, user_b, admin])
    db.commit()

    _setup_target_with_message(db, user_a, "Alpha Corp")
    _setup_target_with_message(db, user_b, "Beta Corp")

    # Login as User A -> sees only Alpha Corp
    auth_client(client, db, user_a)
    res_a = client.get("/api/queue")
    assert res_a.status_code == 200
    items_a = res_a.json()
    assert len(items_a) == 1
    assert items_a[0]["company_name"] == "Alpha Corp"

    # Login as Admin -> sees both
    auth_client(client, db, admin)
    res_adm = client.get("/api/queue")
    assert res_adm.status_code == 200
    items_adm = res_adm.json()
    assert len(items_adm) == 2


def test_update_message_edits_draft(client: TestClient, db: Session):
    owner = User(
        email="editor_org@test.com", name="Editor Org", password_hash="x", role="organizer"
    )
    db.add(owner)
    db.commit()
    target, msg = _setup_target_with_message(db, owner, "Delta Inc")

    _, csrf = auth_client(client, db, owner)
    res = client.put(
        f"/api/messages/{msg.id}",
        json={"subject": "Updated subject line", "body": "Updated body text."},
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["subject"] == "Updated subject line"
    assert data["body"] == "Updated body text."
    assert data["status"] == "draft"


def test_edit_after_approval_voids_approval(client: TestClient, db: Session):
    owner = User(email="approver@test.com", name="Approver", password_hash="x", role="organizer")
    db.add(owner)
    db.commit()
    target, msg = _setup_target_with_message(db, owner, "Epsilon Ltd")

    _, csrf = auth_client(client, db, owner)

    # 1. Approve message
    app_res = client.post(f"/api/messages/{msg.id}/approve", headers={"X-CSRF-Token": csrf})
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["status"] == "approved"
    assert app_data["approved_hash"] is not None
    assert app_data["approved_by"] == owner.id

    # 2. Edit message after approval -> must reset status to draft and clear approval hash (SEC-19)
    edit_res = client.put(
        f"/api/messages/{msg.id}",
        json={"subject": "Slight change", "body": "Changed body after approval."},
        headers={"X-CSRF-Token": csrf},
    )
    assert edit_res.status_code == 200
    edit_data = edit_res.json()
    assert edit_data["status"] == "draft"
    assert edit_data["approved_hash"] is None
    assert edit_data["approved_by"] is None

    # Check audit log contains edit_after_approve (SEC-30)
    audit = db.query(AuditLog).filter(AuditLog.action == "edit_after_approve").first()
    assert audit is not None
    assert audit.user_id == owner.id


def test_approve_route_records_hash_user_and_timestamp(client: TestClient, db: Session):
    owner = User(email="owner_rec@test.com", name="Owner Rec", password_hash="x", role="organizer")
    db.add(owner)
    db.commit()
    target, msg = _setup_target_with_message(db, owner, "Gamma Corp")

    _, csrf = auth_client(client, db, owner)
    res = client.post(f"/api/messages/{msg.id}/approve", headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "approved"
    assert data["approved_by"] == owner.id
    assert data["approved_at"] is not None

    contact = target.company.contacts[0]
    expected_hash = compute_approved_hash(contact.email, msg.subject, msg.body)
    assert data["approved_hash"] == expected_hash


def test_approve_route_refuses_without_contact_email(client: TestClient, db: Session):
    owner = User(email="owner_noc@test.com", name="Owner NoC", password_hash="x", role="organizer")
    db.add(owner)
    db.commit()
    target, msg = _setup_target_with_message(db, owner, "NoContact Co", has_contact=False)

    _, csrf = auth_client(client, db, owner)
    res = client.post(f"/api/messages/{msg.id}/approve", headers={"X-CSRF-Token": csrf})
    assert res.status_code == 400
    assert "valid contact email" in res.json()["detail"]


def test_discard_route_sets_discarded(client: TestClient, db: Session):
    owner = User(
        email="owner_disc@test.com", name="Owner Disc", password_hash="x", role="organizer"
    )
    db.add(owner)
    db.commit()
    target, msg = _setup_target_with_message(db, owner, "Discard Co")

    _, csrf = auth_client(client, db, owner)
    res = client.post(f"/api/messages/{msg.id}/discard", headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200
    assert res.json()["status"] == "discarded"


def test_idor_organizer_cannot_edit_or_approve_other_organizers_draft(
    client: TestClient, db: Session
):
    owner_a = User(email="owner_a@test.com", name="Owner A", password_hash="x", role="organizer")
    owner_b = User(email="owner_b@test.com", name="Owner B", password_hash="x", role="organizer")
    db.add_all([owner_a, owner_b])
    db.commit()

    target_a, msg_a = _setup_target_with_message(db, owner_a, "Target A")

    _, csrf_b = auth_client(client, db, owner_b)

    # User B tries to update User A's draft -> 403 (SEC-09)
    res_put = client.put(
        f"/api/messages/{msg_a.id}",
        json={"subject": "Hacked", "body": "Hacked body"},
        headers={"X-CSRF-Token": csrf_b},
    )
    assert res_put.status_code == 403

    # User B tries to approve User A's draft -> 403 (SEC-09)
    res_app = client.post(f"/api/messages/{msg_a.id}/approve", headers={"X-CSRF-Token": csrf_b})
    assert res_app.status_code == 403


def test_graph_a_stops_at_await_approval_and_does_not_approve(client: TestClient, db: Session):
    """PRD R5, SEC-20: Graph A must stop at await_approval and never set status = 'approved'."""
    owner = User(email="graph_u@test.com", name="Graph User", password_hash="x", role="organizer")
    db.add(owner)
    db.commit()
    target, _ = _setup_target_with_message(db, owner, "GraphTarget Co")

    graph = build_graph_a()
    config = {"configurable": {"thread_id": f"test_thread_{target.id}"}}
    graph.invoke({"target_id": target.id, "user_id": owner.id}, config=config)

    # Check database: message must exist and its status must be 'draft'
    msg = db.scalar(
        select(Message).where(Message.target_id == target.id, Message.direction == "out")
    )
    assert msg is not None
    assert msg.status == "draft"
    assert msg.approved_by is None
    assert msg.approved_hash is None


def test_codebase_grep_only_approve_route_sets_status_approved():
    """SEC-20: assert no code outside approve_message sets status = 'approved'."""
    app_dir = Path(__file__).resolve().parent.parent / "app"
    approved_assignments: list[str] = []

    for py_file in app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Look for status assignments to 'approved' or "approved"
            if (
                '.status = "approved"' in stripped
                or ".status = 'approved'" in stripped
                or 'status="approved"' in stripped
                or "status='approved'" in stripped
            ):
                rel_path = py_file.relative_to(app_dir)
                approved_assignments.append(f"{rel_path}:{i}: {stripped}")

    # Exactly one occurrence is permitted: in app/routes/messages.py
    assert len(approved_assignments) == 1, (
        f"Found multiple assignments setting status to 'approved': {approved_assignments}"
    )
    assert "routes/messages.py" in approved_assignments[0]

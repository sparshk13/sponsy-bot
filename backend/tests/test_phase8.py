"""Tests for Phase 8: Contacts, Templates, and Brochures (G1, G5, G6, SEC-17)."""

import io
from email.message import EmailMessage

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, create_session, hash_password
from app.config import settings
from app.drafting import compute_approved_hash
from app.graph import build_graph_a
from app.hunter import search_hunter_domain
from app.mailer import send_message
from app.models import (
    ApiUsage,
    Brochure,
    Campaign,
    Company,
    CompanyFact,
    Contact,
    Message,
    Target,
    Template,
    User,
    utc_now,
)


def _login(client: TestClient, user: User, db: Session) -> dict[str, str]:
    token, csrf_token = create_session(db, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, token)
    return {"X-CSRF-Token": csrf_token}


def test_hunter_domain_search_success(client: TestClient, db: Session, monkeypatch):
    """Test Hunter search extracts contact and increments counted usage (G1, BUD-07)."""
    admin = User(
        email="admin@test.org",
        name="Admin",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    db.add(admin)
    db.commit()

    company = Company(name="Acme Corp", domain="acme.com")
    campaign = Campaign(name="Hack 2026", event_summary="Student hackathon", created_by=admin.id)
    db.add_all([company, campaign])
    db.commit()

    target = Target(campaign_id=campaign.id, company_id=company.id, owner_id=admin.id)
    db.add(target)
    db.commit()

    monkeypatch.setattr(settings, "hunter_api_key", "test_hunter_key")

    mock_response_data = {
        "data": {
            "domain": "acme.com",
            "emails": [
                {
                    "value": "alice@acme.com",
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "position": "Head of Sponsorship",
                    "department": "marketing",
                }
            ],
        }
    }

    def mock_get(url, params=None, timeout=None):
        req = httpx.Request("GET", url)
        return httpx.Response(200, json=mock_response_data, request=req)

    transport = httpx.MockTransport(lambda req: mock_get(str(req.url)))
    mock_http_client = httpx.Client(transport=transport)

    # Call search_hunter_domain directly with seam
    res = search_hunter_domain("acme.com", db, client=mock_http_client)
    assert res is not None
    assert res["name"] == "Alice Smith"
    assert res["email"] == "alice@acme.com"
    assert res["role"] == "Head of Sponsorship"

    # Verify usage was incremented
    usage = db.scalar(select(ApiUsage.units).where(ApiUsage.provider == "hunter"))
    assert usage == 1

    # Now test endpoint POST /api/targets/{id}/find-contact
    monkeypatch.setattr(
        "app.routes.targets.search_hunter_domain",
        lambda domain, db: {
            "name": "Alice Smith",
            "role": "Head of Sponsorship",
            "email": "alice@acme.com",
            "source": "hunter",
        },
    )

    headers = _login(client, admin, db)
    resp = client.post(f"/api/targets/{target.id}/find-contact", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is True
    assert data["contact"]["email"] == "alice@acme.com"

    # Contact should now be in database
    contact = db.scalar(select(Contact).where(Contact.company_id == company.id))
    assert contact is not None
    assert contact.name == "Alice Smith"
    assert contact.source == "hunter"


def test_hunter_domain_search_exhausted(client: TestClient, db: Session, monkeypatch):
    """Hunter search refused with 429 when budget cap reached (BUD-02, BUD-07)."""
    admin = User(
        email="admin2@test.org",
        name="Admin",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    db.add(admin)
    db.commit()

    company = Company(name="Beta Corp", domain="beta.com")
    campaign = Campaign(name="Hack 2026", event_summary="Student hackathon", created_by=admin.id)
    db.add_all([company, campaign])
    db.commit()

    target = Target(campaign_id=campaign.id, company_id=company.id, owner_id=admin.id)
    db.add(target)
    db.commit()

    monkeypatch.setattr(settings, "hunter_api_key", "test_hunter_key")
    monkeypatch.setattr(settings, "hunter_monthly_credit_cap", 10)

    # Pre-fill usage to cap
    usage = ApiUsage(day=utc_now().date(), provider="hunter", units=10)
    db.add(usage)
    db.commit()

    headers = _login(client, admin, db)
    resp = client.post(f"/api/targets/{target.id}/find-contact", headers=headers)
    assert resp.status_code == 429
    assert "budget exhausted" in resp.json()["detail"].lower()


def test_update_contact_manual(client: TestClient, db: Session):
    """PUT /api/targets/{id}/contact allows updating contact details manually (PRD R1)."""
    organizer = User(
        email="org@test.org",
        name="Organizer",
        role="organizer",
        password_hash=hash_password("orgpass123456"),
    )
    db.add(organizer)
    db.commit()

    company = Company(name="Gamma Inc", domain="gamma.com")
    campaign = Campaign(
        name="Hack 2026", event_summary="Student hackathon", created_by=organizer.id
    )
    db.add_all([company, campaign])
    db.commit()

    target = Target(campaign_id=campaign.id, company_id=company.id, owner_id=organizer.id)
    db.add(target)
    db.commit()

    headers = _login(client, organizer, db)
    payload = {
        "name": "Bob Vance",
        "role": "Refrigeration Director",
        "email": "bob@gamma.com",
    }
    resp = client.put(f"/api/targets/{target.id}/contact", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Bob Vance"
    assert data["role"] == "Refrigeration Director"
    assert data["email"] == "bob@gamma.com"
    assert data["source"] == "manual"


def test_brochure_upload_admin_only(client: TestClient, db: Session):
    """Organizers cannot upload brochures (SEC-09, SEC-17)."""
    organizer = User(
        email="org2@test.org",
        name="Org",
        role="organizer",
        password_hash=hash_password("orgpass123456"),
    )
    db.add(organizer)
    db.commit()

    headers = _login(client, organizer, db)
    pdf_content = b"%PDF-1.4 sample content"
    files = {"file": ("brochure.pdf", io.BytesIO(pdf_content), "application/pdf")}
    data = {"tier": "cash"}
    resp = client.post("/api/admin/brochures", files=files, data=data, headers=headers)
    assert resp.status_code == 403


def test_brochure_upload_rejects_non_pdf(client: TestClient, db: Session):
    """Uploads must start with %PDF magic bytes (SEC-17)."""
    admin = User(
        email="admin3@test.org",
        name="Admin",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    db.add(admin)
    db.commit()

    headers = _login(client, admin, db)
    # File disguised as PDF but with executable or text content
    fake_content = b"<html><script>alert(1)</script></html>"
    files = {"file": ("malicious.pdf", io.BytesIO(fake_content), "application/pdf")}
    data = {"tier": "cash"}
    resp = client.post("/api/admin/brochures", files=files, data=data, headers=headers)
    assert resp.status_code == 400
    assert "magic bytes" in resp.json()["detail"].lower()


def test_brochure_upload_rejects_oversize(client: TestClient, db: Session):
    """Brochure upload rejects files over 5 MB (SEC-17)."""
    admin = User(
        email="admin4@test.org",
        name="Admin",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    db.add(admin)
    db.commit()

    headers = _login(client, admin, db)
    oversize_content = b"%PDF" + (b"0" * (5 * 1024 * 1024 + 10))
    files = {"file": ("huge.pdf", io.BytesIO(oversize_content), "application/pdf")}
    data = {"tier": "cash"}
    resp = client.post("/api/admin/brochures", files=files, data=data, headers=headers)
    assert resp.status_code == 400
    assert "5 mb" in resp.json()["detail"].lower()


def test_brochure_upload_and_download(client: TestClient, db: Session, tmp_path, monkeypatch):
    """PDF uploads successfully and is served via authenticated attachment route (SEC-17, G5)."""
    upload_dir = str(tmp_path / "brochures")
    monkeypatch.setattr(settings, "brochures_upload_dir", upload_dir)

    admin = User(
        email="admin5@test.org",
        name="Admin",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    db.add(admin)
    db.commit()

    headers = _login(client, admin, db)
    pdf_content = b"%PDF-1.4 test brochure content"
    files = {"file": ("cash_tier_brochure.pdf", io.BytesIO(pdf_content), "application/pdf")}
    data = {"tier": "cash"}
    resp = client.post("/api/admin/brochures", files=files, data=data, headers=headers)
    assert resp.status_code == 201
    brochure_data = resp.json()
    assert brochure_data["tier"] == "cash"
    assert brochure_data["filename"] == "cash_tier_brochure.pdf"
    brochure_id = brochure_data["id"]

    # Test download via GET /api/brochures/{id}
    dl_resp = client.get(f"/api/brochures/{brochure_id}")
    assert dl_resp.status_code == 200
    assert dl_resp.content == pdf_content
    # Content-Disposition header check (SEC-17)
    assert "attachment" in dl_resp.headers.get("content-disposition", "")
    assert "cash_tier_brochure.pdf" in dl_resp.headers.get("content-disposition", "")


def test_template_crud_admin_only(client: TestClient, db: Session):
    """Admin can list, create, update, and delete templates (G6)."""
    admin = User(
        email="admin6@test.org",
        name="Admin",
        role="admin",
        password_hash=hash_password("adminpass1234"),
    )
    organizer = User(
        email="org3@test.org",
        name="Org",
        role="organizer",
        password_hash=hash_password("orgpass123456"),
    )
    db.add_all([admin, organizer])
    db.commit()

    # Organizer denied
    org_headers = _login(client, organizer, db)
    resp = client.post(
        "/api/admin/templates",
        json={"kind": "first", "name": "First Contact", "body": "Hello {company}"},
        headers=org_headers,
    )
    assert resp.status_code == 403

    # Admin allowed
    admin_headers = _login(client, admin, db)
    create_resp = client.post(
        "/api/admin/templates",
        json={"kind": "first", "name": "First Contact", "body": "Hello {company}"},
        headers=admin_headers,
    )
    assert create_resp.status_code == 201
    tpl_id = create_resp.json()["id"]

    # List
    list_resp = client.get("/api/admin/templates", headers=admin_headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Update
    update_resp = client.put(
        f"/api/admin/templates/{tpl_id}",
        json={"body": "Updated template text"},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["body"] == "Updated template text"

    # Delete
    del_resp = client.delete(f"/api/admin/templates/{tpl_id}", headers=admin_headers)
    assert del_resp.status_code == 204

    assert db.scalar(select(Template).where(Template.id == tpl_id)) is None


def test_first_email_draft_attaches_tier_brochure(db: Session, tmp_path, monkeypatch):
    """Graph A drafting attaches matching tier brochure to draft message (G5)."""
    upload_dir = str(tmp_path / "brochures")
    monkeypatch.setattr(settings, "brochures_upload_dir", upload_dir)

    user = User(
        email="dev@test.org",
        name="Developer",
        role="organizer",
        password_hash=hash_password("devpass123456"),
    )
    db.add(user)
    db.commit()

    campaign = Campaign(name="Hack 2026", event_summary="Student hackathon", created_by=user.id)
    company = Company(name="Delta Labs", domain="delta.com")
    db.add_all([campaign, company])
    db.commit()

    # Create brochure for cash tier
    brochure = Brochure(
        tier="cash",
        filename="cash_brochure.pdf",
        stored_name="test_cash.pdf",
        uploaded_by=user.id,
    )
    db.add(brochure)

    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=user.id,
        tier="cash",
        status="not_contacted",
    )
    db.add(target)

    fact = CompanyFact(
        company_id=company.id,
        kind="profile",
        claim="Delta Labs develops high-performance developer tools.",
        source_url="https://delta.com/about",
        evidence_quote="Delta Labs develops high-performance developer tools.",
        status="verified",
    )
    contact = Contact(
        company_id=company.id,
        name="Jane Doe",
        email="jane@delta.com",
        source="manual",
    )
    db.add_all([fact, contact])
    db.commit()

    # Build and run Graph A
    graph_a = build_graph_a()
    state = graph_a.invoke(
        {"target_id": target.id, "user_id": user.id},
        config={"configurable": {"thread_id": f"target-{target.id}"}},
    )

    # Verify message was drafted with brochure attachment linked
    msg_id = state.get("message_id")
    assert msg_id is not None
    msg = db.get(Message, msg_id)
    assert msg is not None
    assert msg.attachment_id == brochure.id


def test_mailer_attaches_brochure_pdf(db: Session, tmp_path, monkeypatch):
    """Mailer attaches brochure PDF to outbound email message (G5)."""
    upload_dir = tmp_path / "brochures"
    upload_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "brochures_upload_dir", str(upload_dir))

    pdf_file = upload_dir / "sample_brochure.pdf"
    pdf_content = b"%PDF-1.4 Real brochure payload for testing attachment"
    pdf_file.write_bytes(pdf_content)

    user = User(
        email="mailer_tester@test.org",
        name="Tester",
        role="organizer",
        password_hash=hash_password("testpass12345"),
    )
    db.add(user)
    db.commit()

    campaign = Campaign(name="Hack 2026", event_summary="Student hackathon", created_by=user.id)
    company = Company(name="Epsilon Inc", domain="epsilon.com")
    db.add_all([campaign, company])
    db.commit()

    brochure = Brochure(
        tier="cash",
        filename="epsilon_brochure.pdf",
        stored_name="sample_brochure.pdf",
        uploaded_by=user.id,
    )
    db.add(brochure)
    db.flush()

    contact = Contact(
        company_id=company.id,
        name="Mark",
        email="mark@epsilon.com",
        source="manual",
    )
    db.add(contact)
    db.flush()

    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=user.id,
        tier="cash",
        status="not_contacted",
    )
    db.add(target)
    db.flush()

    body_text = (
        "Hello Mark,\n\nWe would love your support for Hack 2026.\n\n"
        "Outreach Team\nIf this is not for you, tell me and I will not write again."
    )
    subject_text = "Hackathon sponsorship"
    recipient = "mark@epsilon.com"
    app_hash = compute_approved_hash(recipient, subject_text, body_text)

    msg = Message(
        target_id=target.id,
        contact_id=contact.id,
        attachment_id=brochure.id,
        direction="out",
        kind="first",
        subject=subject_text,
        body=body_text,
        status="approved",
        approved_by=user.id,
        approved_at=utc_now(),
        approved_hash=app_hash,
    )
    db.add(msg)
    db.commit()

    # Send with fake transport seam
    class FakeTransport:
        def __init__(self):
            self.sent_messages: list[EmailMessage] = []

        def send_message(self, msg: EmailMessage):
            self.sent_messages.append(msg)

    transport = FakeTransport()
    # Force within send window
    from datetime import datetime, timezone

    send_time = datetime(2026, 10, 20, 11, 0, 0, tzinfo=timezone.utc)

    success = send_message(db, msg.id, transport=transport, now=send_time)
    assert success is True
    assert len(transport.sent_messages) == 1

    sent_msg = transport.sent_messages[0]
    # Verify email has attachments
    attachments = list(sent_msg.iter_attachments())
    assert len(attachments) == 1
    att = attachments[0]
    assert att.get_filename() == "epsilon_brochure.pdf"
    assert att.get_content_type() == "application/pdf"
    assert att.get_payload(decode=True) == pdf_content

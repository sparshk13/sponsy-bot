"""Tests for mailer, guard checks, pacing, and send safety (SEC-19 to SEC-23, BUD-08)."""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import SESSION_COOKIE_NAME, create_session
from app.config import settings
from app.drafting import compute_approved_hash
from app.guard import check_send_guard
from app.mailer import mask_email, send_message
from app.models import (
    AuditLog,
    Campaign,
    Company,
    Contact,
    Message,
    SettingsState,
    Suppression,
    Target,
    User,
)
from app.send_job import process_send_queue


class FakeTransport:
    """In-memory test seam for mail transport."""

    def __init__(self) -> None:
        self.sent: list[object] = []

    def send_message(self, msg: object) -> None:
        self.sent.append(msg)


def _make_in_window_time(hour: int = 11, weekday: int = 1) -> datetime:
    """Return a controllable datetime inside the IST send window (weekday Tuesday by default)."""
    # 2026-10-20 is a Tuesday (weekday 1)
    return datetime(2026, 10, 20, hour, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))


def _setup_target_and_message(
    db: Session,
    owner: User,
    company_name: str = "Trishul Cloud",
    contact_email: str = "sponsor@trishul.in",
    status: str = "approved",
) -> tuple[Target, Message]:
    campaign = Campaign(
        name="HackTech 2026",
        event_summary="Student hackathon",
        cash_target_inr=150000,
        created_by=owner.id,
    )
    db.add(campaign)
    db.flush()

    domain = contact_email.split("@")[-1]
    company = Company(name=company_name, domain=domain)
    db.add(company)
    db.flush()

    contact = Contact(
        company_id=company.id,
        name="Priya Lead",
        role="Director",
        email=contact_email,
    )
    db.add(contact)
    db.flush()

    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=owner.id,
        tier="cash",
        status="not_contacted",
    )
    db.add(target)
    db.flush()

    subject = f"HackTech 2026 partnership with {company_name}"
    body = (
        "Hello Priya,\n\n"
        "We are organizing HackTech 2026 for 150 student engineers. "
        "We would love to partner with your team.\n\n"
        "Sparsh, Organizer, Student Tech Club\n"
        "If this is not for you, tell me and I will not write again."
    )
    approved_hash = (
        compute_approved_hash(contact_email, subject, body) if status == "approved" else None
    )

    msg = Message(
        target_id=target.id,
        contact_id=contact.id,
        direction="out",
        kind="first",
        subject=subject,
        body=body,
        status=status,
        approved_by=owner.id if status == "approved" else None,
        approved_at=datetime.now(ZoneInfo("UTC")) if status == "approved" else None,
        approved_hash=approved_hash,
    )
    db.add(msg)
    db.commit()
    db.refresh(target)
    db.refresh(msg)
    return target, msg


def test_guard_refuses_when_not_approved(db: Session, organizer_user: User):
    _, msg = _setup_target_and_message(db, organizer_user, company_name="Corp A", status="draft")
    now = _make_in_window_time()
    result = check_send_guard(db, msg.id, now=now)

    assert result.allowed is False
    assert "status is 'draft'" in (result.reason or "")


def test_guard_refuses_when_hash_mismatch(db: Session, organizer_user: User):
    _, msg = _setup_target_and_message(db, organizer_user, company_name="Corp B", status="approved")
    # Tamper with the body without updating hash
    msg.body = msg.body + "\nExtra text"
    db.commit()

    now = _make_in_window_time()
    result = check_send_guard(db, msg.id, now=now)

    assert result.allowed is False
    assert "does not match approved hash" in (result.reason or "")


def test_guard_refuses_when_recipient_or_domain_suppressed(db: Session, organizer_user: User):
    _, msg = _setup_target_and_message(
        db,
        organizer_user,
        company_name="Corp C",
        contact_email="blocked@domain.in",
        status="approved",
    )

    # 1. Suppress email directly
    sup_email = Suppression(kind="email", value="blocked@domain.in", reason="User opted out")
    db.add(sup_email)
    db.commit()

    now = _make_in_window_time()
    result = check_send_guard(db, msg.id, now=now)
    assert result.allowed is False
    assert "suppressed (email" in (result.reason or "")

    # 2. Remove email suppression, suppress domain
    db.delete(sup_email)
    sup_domain = Suppression(kind="domain", value="domain.in", reason="Company unsubscribed")
    db.add(sup_domain)
    db.commit()

    result2 = check_send_guard(db, msg.id, now=now)
    assert result2.allowed is False
    assert "suppressed (domain" in (result2.reason or "")


def test_guard_refuses_when_target_declined_or_closed(db: Session, organizer_user: User):
    target, msg = _setup_target_and_message(
        db, organizer_user, company_name="Corp D", status="approved"
    )

    target.status = "declined"
    db.commit()
    now = _make_in_window_time()

    result = check_send_guard(db, msg.id, now=now)
    assert result.allowed is False
    assert "status 'declined'" in (result.reason or "")

    target.status = "closed_no_reply"
    db.commit()

    result2 = check_send_guard(db, msg.id, now=now)
    assert result2.allowed is False
    assert "status 'closed_no_reply'" in (result2.reason or "")


def test_guard_refuses_when_followup_limit_exceeded(db: Session, organizer_user: User):
    target, msg = _setup_target_and_message(
        db, organizer_user, company_name="Corp E", status="approved"
    )
    target.followup_count = settings.max_followups + 1
    db.commit()

    now = _make_in_window_time()
    result = check_send_guard(db, msg.id, now=now)
    assert result.allowed is False
    assert "exceeds maximum limit" in (result.reason or "")


def test_guard_refuses_when_outside_send_window(db: Session, organizer_user: User):
    _, msg = _setup_target_and_message(db, organizer_user, company_name="Corp F", status="approved")

    # Before start hour (8:00 AM IST)
    before_time = _make_in_window_time(hour=8)
    result = check_send_guard(db, msg.id, now=before_time)
    assert result.allowed is False
    assert "Outside send window hours" in (result.reason or "")

    # After end hour (18:30 IST)
    after_time = _make_in_window_time(hour=19)
    result2 = check_send_guard(db, msg.id, now=after_time)
    assert result2.allowed is False
    assert "Outside send window hours" in (result2.reason or "")

    # Weekend (Sunday: 2026-10-25)
    weekend_time = datetime(2026, 10, 25, 12, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    result3 = check_send_guard(db, msg.id, now=weekend_time)
    assert result3.allowed is False
    assert "weekend" in (result3.reason or "")


def test_guard_refuses_when_global_pause_active(db: Session, organizer_user: User):
    _, msg = _setup_target_and_message(db, organizer_user, company_name="Corp G", status="approved")
    state = db.get(SettingsState, "paused")
    if not state:
        state = SettingsState(key="paused", value="true")
        db.add(state)
    else:
        state.value = "true"
    db.commit()

    now = _make_in_window_time()
    result = check_send_guard(db, msg.id, now=now)
    assert result.allowed is False
    assert "Global sending pause is enabled" in (result.reason or "")

    db.delete(state)
    db.commit()


def test_send_message_rejects_header_injection_cr_lf(db: Session, organizer_user: User):
    _, msg = _setup_target_and_message(db, organizer_user, company_name="Corp H", status="approved")

    # Injected recipient
    contact = db.get(Contact, msg.contact_id)
    contact.email = "spoofed@domain.com\r\nBcc: evil@domain.com"
    msg.approved_hash = compute_approved_hash(contact.email, msg.subject, msg.body)
    db.commit()

    now = _make_in_window_time()
    with pytest.raises(ValueError, match="Header injection detected: CR/LF in recipient"):
        send_message(db, msg.id, transport=FakeTransport(), now=now)

    # Injected subject
    contact.email = "valid@domain.com"
    msg.subject = "Legit Subject\nBcc: evil@domain.com"
    msg.approved_hash = compute_approved_hash(contact.email, msg.subject, msg.body)
    db.commit()

    with pytest.raises(ValueError, match="Header injection detected: CR/LF in subject"):
        send_message(db, msg.id, transport=FakeTransport(), now=now)


def test_send_message_success_and_audit(db: Session, organizer_user: User):
    target, msg = _setup_target_and_message(
        db,
        organizer_user,
        company_name="Corp I",
        contact_email="priya@corp-i.in",
        status="approved",
    )

    transport = FakeTransport()
    now = _make_in_window_time()
    success = send_message(db, msg.id, transport=transport, now=now)

    assert success is True
    assert len(transport.sent) == 1
    sent_msg = transport.sent[0]
    assert sent_msg["To"] == "priya@corp-i.in"
    assert sent_msg["Subject"] == msg.subject
    assert sent_msg["Message-ID"] is not None

    db.refresh(msg)
    db.refresh(target)
    assert msg.status == "sent"
    assert msg.sent_at is not None
    assert msg.message_id_header == sent_msg["Message-ID"]
    assert target.status == "contacted"
    assert target.last_contacted_at is not None

    audit_entry = db.scalar(
        select(AuditLog).where(
            AuditLog.action == "send_message",
            AuditLog.entity_id == str(msg.id),
        )
    )
    assert audit_entry is not None
    assert "p***@corp-i.in" in audit_entry.detail


def test_send_job_pacing_and_daily_cap_simulation(
    db: Session, organizer_user: User, monkeypatch: pytest.MonkeyPatch
):
    """BUD-11: Simulate 40 approved messages in a day spaced and in-window, capped at 40."""
    monkeypatch.setattr(settings, "daily_send_cap", 40)
    transport = FakeTransport()
    base_time = _make_in_window_time(hour=9)  # 9:00 AM IST

    # Create 41 approved targets and messages
    msg_ids = []
    for i in range(41):
        _, m = _setup_target_and_message(
            db,
            organizer_user,
            company_name=f"Partner {i}",
            contact_email=f"contact{i}@partner{i}.in",
            status="approved",
        )
        msg_ids.append(m.id)

    # Process all messages spacing them by 65 seconds
    current_time = base_time
    sent_count = 0

    for i in range(40):
        # Pass jitter_fn returning 0 for deterministic test pacing
        result = process_send_queue(db, transport=transport, now=current_time, jitter_fn=lambda: 0)
        assert result == 1, f"Expected message {i} to send successfully"
        sent_count += 1
        # Advance time by 65 seconds (> send_min_gap_seconds 60)
        current_time = current_time + timedelta(seconds=65)

    assert sent_count == 40
    assert len(transport.sent) == 40

    # 41st message attempt: cap reached
    result_41 = process_send_queue(db, transport=transport, now=current_time, jitter_fn=lambda: 0)
    assert result_41 == 0

    # Verify guard explicitly reports cap reached
    cap_check = check_send_guard(db, msg_ids[40], now=current_time)
    assert cap_check.allowed is False
    assert "Daily send cap" in (cap_check.reason or "")


def test_daily_send_cap_validation_rejects_above_40():
    """BUD-08 / PRD R11: Cap cannot be configured above 40."""
    from app.config import Settings

    with pytest.raises(ValueError, match="daily_send_cap cannot exceed 40"):
        Settings(daily_send_cap=41)


def test_admin_pause_endpoint_and_immediate_stop(client: TestClient, db: Session, admin_user: User):
    raw_token, csrf_token = create_session(db, admin_user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)

    # 1. Turn pause on
    resp = client.put(
        "/api/admin/pause",
        json={"paused": True},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp.status_code == 200
    assert resp.json()["paused"] is True

    # Check GET /api/admin/pause
    get_resp = client.get("/api/admin/pause")
    assert get_resp.status_code == 200
    assert get_resp.json()["paused"] is True

    # 2. Sending must stop immediately
    _, msg = _setup_target_and_message(
        db, admin_user, company_name="Paused Corp", status="approved"
    )
    now = _make_in_window_time()
    guard_result = check_send_guard(db, msg.id, now=now)
    assert guard_result.allowed is False
    assert "Global sending pause is enabled" in (guard_result.reason or "")

    # 3. Turn pause off
    resp_off = client.put(
        "/api/admin/pause",
        json={"paused": False},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert resp_off.status_code == 200
    assert resp_off.json()["paused"] is False

    guard_result_off = check_send_guard(db, msg.id, now=now)
    assert guard_result_off.allowed is True


def test_logs_do_not_contain_bodies_or_unmasked_emails(
    db: Session, organizer_user: User, caplog: pytest.LogCaptureFixture
):
    """SEC-29: logs never contain bodies, passwords, or full email addresses."""
    secret_body_marker = "SUPER_SECRET_BODY_CONTENT_12345"
    unmasked_address = "secret_director@confidential.com"

    target, msg = _setup_target_and_message(
        db,
        organizer_user,
        company_name="Secret Corp",
        contact_email=unmasked_address,
        status="approved",
    )
    msg.body = (
        f"Hello,\n\n{secret_body_marker}\n\n"
        f"Sparsh\nIf this is not for you, tell me and I will not write again."
    )
    msg.approved_hash = compute_approved_hash(unmasked_address, msg.subject, msg.body)
    db.commit()

    transport = FakeTransport()
    now = _make_in_window_time()

    with caplog.at_level(logging.DEBUG):
        send_message(db, msg.id, transport=transport, now=now)

    full_log_text = caplog.text
    assert secret_body_marker not in full_log_text
    assert unmasked_address not in full_log_text
    assert mask_email(unmasked_address) in full_log_text

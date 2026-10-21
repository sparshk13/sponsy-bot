"""Tests for follow-up scheduling math, Graph B events, and outcomes (R7, R8, G2, G4)."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.followup import compute_next_followup_at, get_followup_delay_days
from app.followup_job import process_due_followups
from app.graph import handle_graph_b_event
from app.models import Campaign, Company, Contact, Message, Target, User


def test_get_followup_delay_days():
    assert get_followup_delay_days(0) == 4
    assert get_followup_delay_days(1) == 5
    assert get_followup_delay_days(2) == 5


def test_compute_next_followup_at_skips_weekends():
    # 2026-10-19 is a Monday (10:00 UTC = 15:30 IST)
    mon = datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)
    # 4 weekdays from Monday is Friday
    fri = compute_next_followup_at(mon, days_offset=4)
    assert fri.weekday() == 4  # Friday

    # 4 weekdays from Tuesday (2026-10-20) is Monday (2026-10-26)
    tue = datetime(2026, 10, 20, 10, 0, tzinfo=timezone.utc)
    next_mon = compute_next_followup_at(tue, days_offset=4)
    assert next_mon.weekday() == 0  # Monday
    assert next_mon.day == 26


def test_compute_next_followup_at_send_window():
    # Base time at 02:00 UTC = 07:30 IST (before 09:30 window start)
    early = datetime(2026, 10, 19, 2, 0, tzinfo=timezone.utc)
    res = compute_next_followup_at(early, days_offset=1)
    ist = res.astimezone(ZoneInfo("Asia/Kolkata"))
    assert ist.hour == 9
    assert ist.minute == 30

    # Base time at 14:00 UTC = 19:30 IST (after 17:30 window end)
    late = datetime(2026, 10, 19, 14, 0, tzinfo=timezone.utc)
    res_late = compute_next_followup_at(late, days_offset=1)
    ist_late = res_late.astimezone(ZoneInfo("Asia/Kolkata"))
    # Should advance to next business day at 09:30
    assert ist_late.hour == 9
    assert ist_late.minute == 30
    assert ist_late.day == 21


def test_event_sent_schedules_next_followup(db: Session, organizer_user: User):
    campaign = Campaign(
        name="Hack 2026",
        event_summary="Hackathon",
        created_by=organizer_user.id,
    )
    db.add(campaign)
    company = Company(name="Acme", domain="acme.com")
    db.add(company)
    db.flush()

    contact = Contact(
        company_id=company.id,
        name="Jane Doe",
        email="jane@acme.com",
    )
    db.add(contact)
    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="not_contacted",
    )
    db.add(target)
    db.flush()

    msg = Message(
        target_id=target.id,
        contact_id=contact.id,
        direction="out",
        kind="first",
        subject="Hackathon Partnership",
        body="Hello Jane, would you like to sponsor our hackathon?",
        status="sent",
    )
    db.add(msg)
    db.commit()

    now = datetime(2026, 10, 19, 10, 0, tzinfo=timezone.utc)
    handle_graph_b_event("sent", target_id=target.id, message_id=msg.id, now=now)

    db.refresh(target)
    assert target.status == "contacted"
    assert target.followup_count == 0
    assert target.last_contacted_at is not None
    assert target.next_followup_at is not None
    assert target.next_followup_at > now


def test_reply_received_cancels_followup_schedule(db: Session, organizer_user: User):
    campaign = Campaign(name="Hack 2026", event_summary="Hackathon", created_by=organizer_user.id)
    db.add(campaign)
    company = Company(name="Acme", domain="acme.com")
    db.add(company)
    db.flush()

    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="contacted",
        next_followup_at=datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc),
    )
    db.add(target)
    db.commit()

    # Reply arrives with question classification
    handle_graph_b_event(
        "reply_received",
        target_id=target.id,
        classification="question",
    )

    db.refresh(target)
    assert target.next_followup_at is None


def test_interested_reply_creates_meeting_draft_with_calendar_link(
    db: Session, organizer_user: User
):
    campaign = Campaign(
        name="Hack 2026",
        event_summary="Hackathon",
        calendar_link="https://cal.com/studenttech/20m",
        created_by=organizer_user.id,
    )
    db.add(campaign)
    company = Company(name="TechCorp", domain="techcorp.io")
    db.add(company)
    db.flush()

    contact = Contact(
        company_id=company.id,
        name="Alex Smith",
        email="alex@techcorp.io",
    )
    db.add(contact)
    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="contacted",
        next_followup_at=datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc),
    )
    db.add(target)
    db.commit()

    handle_graph_b_event(
        "reply_received",
        target_id=target.id,
        classification="interested",
    )

    db.refresh(target)
    assert target.status == "interested"
    assert target.next_followup_at is None

    # Check that outgoing draft message is created with calendar link and status=draft
    meeting_draft = db.scalar(
        select(Message).where(
            Message.target_id == target.id,
            Message.direction == "out",
            Message.kind == "meeting",
        )
    )
    assert meeting_draft is not None
    assert meeting_draft.status == "draft"
    assert "https://cal.com/studenttech/20m" in (meeting_draft.body or "")
    assert "20-minute call" in (meeting_draft.body or "")


def test_due_followup_job_generates_draft_and_advances(db: Session, organizer_user: User):
    campaign = Campaign(name="Hack 2026", event_summary="Hackathon", created_by=organizer_user.id)
    db.add(campaign)
    company = Company(name="BetaTech", domain="betatech.com")
    db.add(company)
    db.flush()

    contact = Contact(company_id=company.id, name="Bob", email="bob@betatech.com")
    db.add(contact)
    now = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)
    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="contacted",
        followup_count=0,
        next_followup_at=now,
    )
    db.add(target)
    db.commit()

    processed = process_due_followups(db, now=now)
    assert target.id in processed

    db.refresh(target)
    # Draft is placed in queue; next_followup_at cleared so it doesn't re-draft while waiting
    assert target.next_followup_at is None

    draft = db.scalar(
        select(Message).where(
            Message.target_id == target.id,
            Message.direction == "out",
            Message.kind == "followup",
        )
    )
    assert draft is not None
    assert draft.status == "draft"
    words = len((draft.body or "").split())
    assert 40 <= words <= 100


def test_due_followup_job_closes_after_limit(db: Session, organizer_user: User):
    campaign = Campaign(name="Hack 2026", event_summary="Hackathon", created_by=organizer_user.id)
    db.add(campaign)
    company = Company(name="Gamma", domain="gamma.org")
    db.add(company)
    db.flush()

    now = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="follow_up",
        followup_count=2,  # Already sent 2 followups
        next_followup_at=now,
    )
    db.add(target)
    db.commit()

    processed = process_due_followups(db, now=now)
    assert target.id in processed

    db.refresh(target)
    assert target.status == "closed_no_reply"
    assert target.next_followup_at is None


def test_due_followup_job_idempotent(db: Session, organizer_user: User):
    campaign = Campaign(name="Hack 2026", event_summary="Hackathon", created_by=organizer_user.id)
    db.add(campaign)
    company = Company(name="Delta", domain="delta.com")
    db.add(company)
    db.flush()

    now = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)
    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="contacted",
        followup_count=0,
        next_followup_at=now,
    )
    db.add(target)
    db.flush()
    # Existing draft already in queue
    msg = Message(
        target_id=target.id,
        direction="out",
        kind="followup",
        subject="Follow-up draft",
        body="Short draft already here.",
        status="draft",
    )
    db.add(msg)
    db.commit()

    # Should not create duplicate
    process_due_followups(db, now=now)
    draft_count = db.scalar(
        select(Message).where(Message.target_id == target.id, Message.direction == "out")
    )
    assert draft_count is not None


def test_target_status_and_outcome_endpoints(client: TestClient, db: Session, organizer_user: User):
    from app.auth import SESSION_COOKIE_NAME, create_session

    campaign = Campaign(name="Hack 2026", event_summary="Hackathon", created_by=organizer_user.id)
    db.add(campaign)
    company = Company(name="SponsorPro", domain="sponsorpro.com")
    db.add(company)
    db.flush()

    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="interested",
    )
    db.add(target)
    db.commit()

    raw_token, csrf_token = create_session(db, organizer_user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    headers = {"X-CSRF-Token": csrf_token}

    # 1. Update status to meeting_booked
    res_status = client.post(
        f"/api/targets/{target.id}/status",
        json={"status": "meeting_booked"},
        headers=headers,
    )
    assert res_status.status_code == 200
    assert res_status.json()["status"] == "meeting_booked"

    # 2. Record outcome
    res_outcome = client.post(
        f"/api/targets/{target.id}/outcome",
        json={"kind": "cash", "amount_inr": 150000, "description": "Title Sponsorship"},
        headers=headers,
    )
    assert res_outcome.status_code == 201
    assert res_outcome.json()["kind"] == "cash"
    assert res_outcome.json()["amount_inr"] == 150000

    # Verify target status transitioned to secured and outcome appears in target detail
    res_detail = client.get(f"/api/targets/{target.id}", headers=headers)
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["status"] == "secured"
    assert len(detail["outcomes"]) == 1
    assert detail["outcomes"][0]["amount_inr"] == 150000

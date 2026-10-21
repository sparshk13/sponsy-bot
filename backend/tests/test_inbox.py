"""Tests for reply tracking, IMAP matching, classification, and inbox (R6, G8, G9)."""

from datetime import datetime, timezone

from sqlalchemy import select

from app.classifier import is_auto_reply, is_bounce, strip_quoted_text
from app.inbox_job import match_reply_to_target, process_incoming_email
from app.llm import ReplyAnalysis, strip_pii
from app.mailer import ParsedEmail
from app.models import Company, Contact, Message, Suppression, Target


def test_strip_pii_removes_emails_and_phone_numbers():
    text = (
        "Hello, contact me at sponsor@bigcorp.com or john.doe+deals@work.org. "
        "Call me at +91 98765 43210 or 555-234-5678. Our budget for 2026 is 150000."
    )
    cleaned = strip_pii(text)
    assert "sponsor@bigcorp.com" not in cleaned
    assert "john.doe+deals@work.org" not in cleaned
    assert "+91 98765 43210" not in cleaned
    assert "555-234-5678" not in cleaned
    assert "[email]" in cleaned
    assert "[phone]" in cleaned
    # Ensure ordinary numbers like years and budgets are not erased
    assert "2026" in cleaned


def test_is_bounce_detection():
    assert is_bounce({}, "mailer-daemon@googlemail.com", "Delivery Status Notification")
    assert is_bounce({}, "postmaster@corp.com", "Failure notice")
    assert is_bounce(
        {"content-type": "multipart/report; report-type=delivery-status"},
        "admin@corp.com",
        "Mail failed",
    )
    assert is_bounce({"x-failed-recipients": "someone@corp.com"}, "admin@corp.com", "Undelivered")
    assert not is_bounce({}, "alice@company.com", "Re: Sponsorship inquiry")


def test_is_auto_reply_detection():
    assert is_auto_reply({"auto-submitted": "auto-replied"}, "Re: Tech event")
    assert is_auto_reply({"x-autoreply": "yes"}, "Re: Tech event")
    assert is_auto_reply({"precedence": "auto_reply"}, "Re: Tech event")
    assert is_auto_reply({}, "Out of Office: vacation until Monday")
    assert is_auto_reply({}, "Automatic reply: Re: Tech event")
    assert not is_auto_reply({}, "Re: Student Tech Event")


def test_strip_quoted_text():
    raw_email = (
        "We are happy to sponsor this event.\n\n"
        "On Mon, Oct 19, 2026 at 10:00 AM outreach@studenttechclub.org wrote:\n"
        "> Hello,\n"
        "> Would you like to sponsor our event?"
    )
    cleaned = strip_quoted_text(raw_email)
    assert cleaned.strip() == "We are happy to sponsor this event."


def auth_client(client, db, user):
    from app.auth import SESSION_COOKIE_NAME, create_session

    raw_token, csrf_token = create_session(db, user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    return client, csrf_token


def test_match_reply_by_in_reply_to_and_references(db, organizer_user, test_campaign):
    company = Company(name="Acme Tech", domain="acmetech.com")
    db.add(company)
    db.flush()

    contact = Contact(company_id=company.id, name="Sarah", email="sarah@acmetech.com")
    target = Target(
        campaign_id=test_campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="contacted",
    )
    db.add_all([contact, target])
    db.flush()

    sent_msg = Message(
        target_id=target.id,
        contact_id=contact.id,
        direction="out",
        kind="initial",
        status="sent",
        subject="Hack 2026 Sponsorship",
        body="Hello Sarah...",
        message_id_header="<msg-12345@studenttechclub.org>",
        sent_at=datetime.now(timezone.utc),
    )
    db.add(sent_msg)
    db.commit()

    # 1. Match by in_reply_to
    reply_email_1 = ParsedEmail(
        message_id_header="<reply-001@acmetech.com>",
        in_reply_to="<msg-12345@studenttechclub.org>",
        sender="sarah@acmetech.com",
        subject="Re: Hack 2026 Sponsorship",
        body="We would love to sponsor!",
    )
    matched_target, matched_contact, matched_sent = match_reply_to_target(db, reply_email_1)
    assert matched_target.id == target.id
    assert matched_contact.id == contact.id
    assert matched_sent.id == sent_msg.id

    # 2. Match by references
    reply_email_2 = ParsedEmail(
        message_id_header="<reply-002@acmetech.com>",
        references=["<msg-12345@studenttechclub.org>"],
        sender="sarah@acmetech.com",
        subject="Re: Hack 2026 Sponsorship",
        body="Following up on this.",
    )
    matched_target, _, _ = match_reply_to_target(db, reply_email_2)
    assert matched_target.id == target.id

    # 3. Match by sender email fallback
    reply_email_3 = ParsedEmail(
        message_id_header="<reply-003@acmetech.com>",
        sender="Sarah Connor <sarah@acmetech.com>",
        subject="Separate email thread",
        body="Regarding the sponsorship.",
    )
    matched_target, _, _ = match_reply_to_target(db, reply_email_3)
    assert matched_target.id == target.id


def test_process_incoming_bounce_marks_contact_invalid(db, organizer_user, test_campaign):
    company = Company(name="Bounce Corp", domain="bouncecorp.com")
    db.add(company)
    db.flush()

    contact = Contact(company_id=company.id, name="Bob", email="bob@bouncecorp.com")
    target = Target(
        campaign_id=test_campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="contacted",
    )
    db.add_all([contact, target])
    db.flush()

    sent_msg = Message(
        target_id=target.id,
        contact_id=contact.id,
        direction="out",
        kind="initial",
        status="sent",
        subject="Sponsorship",
        message_id_header="<bounce-test-1@club.org>",
    )
    db.add(sent_msg)
    db.commit()

    bounce_email = ParsedEmail(
        message_id_header="<daemon-123@mailer.org>",
        in_reply_to="<bounce-test-1@club.org>",
        sender="mailer-daemon@googlemail.com",
        subject="Delivery Status Notification (Failure)",
        body="Recipient address rejected: user unknown",
        headers={"content-type": "multipart/report; report-type=delivery-status"},
    )

    msg = process_incoming_email(db, bounce_email)
    assert msg is not None
    assert msg.classification == "bounce"
    assert msg.status == "received"

    db.refresh(contact)
    assert contact.is_valid is False
    db.refresh(target)
    assert target.status == "contacted"


def test_process_incoming_auto_reply_does_not_change_target_status(
    db, organizer_user, test_campaign
):
    company = Company(name="Vacation Corp", domain="vacation.com")
    db.add(company)
    db.flush()

    contact = Contact(company_id=company.id, name="Dan", email="dan@vacation.com")
    target = Target(
        campaign_id=test_campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="contacted",
    )
    db.add_all([contact, target])
    db.flush()

    sent_msg = Message(
        target_id=target.id,
        contact_id=contact.id,
        direction="out",
        kind="initial",
        status="sent",
        subject="Sponsorship",
        message_id_header="<vacation-1@club.org>",
    )
    db.add(sent_msg)
    db.commit()

    auto_email = ParsedEmail(
        message_id_header="<auto-123@vacation.com>",
        in_reply_to="<vacation-1@club.org>",
        sender="dan@vacation.com",
        subject="Automatic reply: Out of office",
        body="I am out of the office until next week.",
        headers={"auto-submitted": "auto-replied"},
    )

    msg = process_incoming_email(db, auto_email)
    assert msg is not None
    assert msg.classification == "auto_reply"

    db.refresh(target)
    assert target.status == "contacted"


def test_process_incoming_decline_suppresses_contact_and_domain(
    db, organizer_user, test_campaign, monkeypatch
):
    company = Company(name="Decline Inc", domain="declineinc.com")
    db.add(company)
    db.flush()

    contact = Contact(company_id=company.id, name="Dave", email="dave@declineinc.com")
    target = Target(
        campaign_id=test_campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="contacted",
    )
    db.add_all([contact, target])
    db.flush()

    sent_msg = Message(
        target_id=target.id,
        contact_id=contact.id,
        direction="out",
        kind="initial",
        status="sent",
        subject="Sponsorship",
        message_id_header="<decline-test@club.org>",
    )
    db.add(sent_msg)
    db.commit()

    # Mock classify_reply to return declined
    monkeypatch.setattr(
        "app.inbox_job.classify_reply",
        lambda **kwargs: ReplyAnalysis(
            classification="declined",
            summary="Declined: budget exhausted.",
            suggested_reply="",
        ),
    )

    decline_email = ParsedEmail(
        message_id_header="<decline-msg-1@declineinc.com>",
        in_reply_to="<decline-test@club.org>",
        sender="dave@declineinc.com",
        subject="Re: Sponsorship",
        body="Sorry, we have no budget left for sponsorships this year. Please remove us.",
    )

    msg = process_incoming_email(db, decline_email)
    assert msg is not None
    assert msg.classification == "declined"

    db.refresh(target)
    assert target.status == "declined"

    email_supp = db.scalar(select(Suppression).where(Suppression.value == "dave@declineinc.com"))
    assert email_supp is not None
    assert email_supp.kind == "email"

    dom_supp = db.scalar(select(Suppression).where(Suppression.value == "declineinc.com"))
    assert dom_supp is not None
    assert dom_supp.kind == "domain"


def test_inbox_api_and_human_override(client, db, organizer_user, test_campaign):
    _, csrf_token = auth_client(client, db, organizer_user)

    company = Company(name="Test Corp", domain="testcorp.com")
    db.add(company)
    db.flush()

    contact = Contact(company_id=company.id, name="Emma", email="emma@testcorp.com")
    target = Target(
        campaign_id=test_campaign.id,
        company_id=company.id,
        owner_id=organizer_user.id,
        status="contacted",
    )
    db.add_all([contact, target])
    db.flush()

    incoming_msg = Message(
        target_id=target.id,
        contact_id=contact.id,
        direction="in",
        kind="reply",
        status="received",
        classification="question",
        summary="Asking for details about attendee numbers.",
        suggested_reply="Hi Emma, we expect about 150 attendees. Let me know if that works.",
        subject="Re: Hack 2026",
        body="How many students usually attend?",
        message_id_header="<incoming-100@testcorp.com>",
    )
    db.add(incoming_msg)
    db.commit()

    # 1. GET /api/inbox
    res = client.get("/api/inbox")
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1
    found = next((i for i in items if i["id"] == incoming_msg.id), None)
    assert found is not None
    assert found["company_name"] == "Test Corp"
    assert found["classification"] == "question"
    assert found["suggested_reply"] is not None

    # 2. PUT /api/messages/{id}/class - Human override to interested
    res_override = client.put(
        f"/api/messages/{incoming_msg.id}/class",
        json={"classification": "interested"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_override.status_code == 200
    data = res_override.json()
    assert data["classification"] == "interested"
    assert data["classified_by_human"] is True

    db.refresh(target)
    assert target.status == "interested"

    # 3. POST /api/messages/{id}/suggested-reply - Convert suggestion to draft
    res_convert = client.post(
        f"/api/messages/{incoming_msg.id}/suggested-reply",
        json={},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res_convert.status_code == 200
    draft_data = res_convert.json()
    assert draft_data["direction"] == "out"
    assert draft_data["status"] == "draft"
    assert draft_data["kind"] == "reply"
    assert "Hi Emma" in draft_data["body"]

    # 4. GET /api/today returns updated counts
    res_today = client.get("/api/today")
    assert res_today.status_code == 200
    today_data = res_today.json()
    assert "pending_approvals" in today_data
    assert "unread_replies" in today_data
    assert today_data["pending_approvals"] >= 1

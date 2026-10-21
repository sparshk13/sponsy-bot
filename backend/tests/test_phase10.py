"""Tests for Phase 10: Deployment pack, 2FA, SEC-39 to SEC-41, and admin telemetry."""

import hashlib

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import create_session, hash_password
from app.config import settings
from app.models import Contact, Message, Suppression, Target, User
from app.models import Session as SessionModel
from app.security import _IP_AUTH_REQUESTS


def test_two_factor_setup_and_confirmation(
    client: TestClient, admin_user: User, db: Session
) -> None:
    raw_token, csrf = create_session(db, admin_user.id)
    client.cookies.set("sponsy_session", raw_token)

    # 1. Initiate 2FA setup
    res = client.post("/api/account/2fa/setup", headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200
    data = res.json()
    assert "secret" in data
    assert "otpauth_url" in data
    secret = data["secret"]

    # In DB, secret is saved but enabled is False
    db.refresh(admin_user)
    assert admin_user.totp_secret == secret
    assert not admin_user.totp_enabled

    # 2. Confirm 2FA with valid TOTP code
    totp = pyotp.TOTP(secret)
    valid_code = totp.now()
    res_confirm = client.post(
        "/api/account/2fa/confirm",
        headers={"X-CSRF-Token": csrf},
        json={"code": valid_code},
    )
    assert res_confirm.status_code == 200
    confirm_data = res_confirm.json()
    recovery_codes = confirm_data["recovery_codes"]
    assert len(recovery_codes) == 10

    # In DB, enabled is True and recovery codes are hashed
    db.refresh(admin_user)
    assert admin_user.totp_enabled is True
    assert len(admin_user.recovery_codes) == 10
    first_hashed = hashlib.sha256(
        recovery_codes[0].replace("-", "").lower().encode("utf-8")
    ).hexdigest()
    assert first_hashed in admin_user.recovery_codes


def test_two_factor_login_flow(client: TestClient, db: Session) -> None:
    # Create user with 2FA enabled
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    user = User(
        email="totp_user@example.com",
        name="TOTP User",
        role="organizer",
        password_hash=hash_password("secure_pass1234"),
        is_active=True,
        totp_secret=secret,
        totp_enabled=True,
    )
    db.add(user)
    db.commit()

    # Step 1: Login with email + password -> requires 2FA
    res_login = client.post(
        "/api/login",
        json={"email": "totp_user@example.com", "password": "secure_pass1234"},
    )
    assert res_login.status_code == 200
    login_data = res_login.json()
    assert login_data["requires_2fa"] is True
    assert "pending_token" in login_data
    # No session cookie issued yet (SEC-40)
    assert "sponsy_session" not in res_login.cookies

    pending_token = login_data["pending_token"]

    # Step 2: Try invalid code -> 401
    res_bad = client.post(
        "/api/login/code",
        json={"pending_token": pending_token, "code": "000000"},
    )
    assert res_bad.status_code == 401
    assert "sponsy_session" not in res_bad.cookies

    # Step 3: Try valid code -> 200 and session cookie issued
    res_valid = client.post(
        "/api/login/code",
        json={"pending_token": pending_token, "code": totp.now()},
    )
    assert res_valid.status_code == 200
    assert "sponsy_session" in res_valid.cookies


def test_two_factor_login_with_recovery_code(client: TestClient, db: Session) -> None:
    plain_recovery_code = "a1b2-c3d4"
    hashed_code = hashlib.sha256(
        plain_recovery_code.replace("-", "").lower().encode("utf-8")
    ).hexdigest()

    user = User(
        email="recovery_user@example.com",
        name="Recovery User",
        role="organizer",
        password_hash=hash_password("secure_pass1234"),
        is_active=True,
        totp_secret=pyotp.random_base32(),
        totp_enabled=True,
        recovery_codes=[hashed_code],
    )
    db.add(user)
    db.commit()

    # Step 1: Login
    res_login = client.post(
        "/api/login",
        json={"email": "recovery_user@example.com", "password": "secure_pass1234"},
    )
    pending_token = res_login.json()["pending_token"]

    # Step 2: Use recovery code
    res_code = client.post(
        "/api/login/code",
        json={"pending_token": pending_token, "code": plain_recovery_code},
    )
    assert res_code.status_code == 200
    assert "sponsy_session" in res_code.cookies

    # Recovery code must be consumed (SEC-40 single-use)
    db.refresh(user)
    assert hashed_code not in (user.recovery_codes or [])

    # Using the same recovery code again must fail
    res_login2 = client.post(
        "/api/login",
        json={"email": "recovery_user@example.com", "password": "secure_pass1234"},
    )
    pending_token2 = res_login2.json()["pending_token"]
    res_code2 = client.post(
        "/api/login/code",
        json={"pending_token": pending_token2, "code": plain_recovery_code},
    )
    assert res_code2.status_code == 401


def test_admin_reset_user_two_factor(client: TestClient, admin_user: User, db: Session) -> None:
    user = User(
        email="reset_me@example.com",
        name="Reset Me",
        role="organizer",
        password_hash=hash_password("secure_pass1234"),
        is_active=True,
        totp_secret="JBSWY3DPEHPK3PXP",
        totp_enabled=True,
        recovery_codes=["hash1", "hash2"],
    )
    db.add(user)
    db.commit()

    raw_token, csrf = create_session(db, admin_user.id)
    client.cookies.set("sponsy_session", raw_token)

    res = client.post(
        f"/api/admin/users/{user.id}/reset-2fa",
        headers={"X-CSRF-Token": csrf},
    )
    assert res.status_code == 200

    db.refresh(user)
    assert user.totp_enabled is False
    assert user.totp_secret is None
    assert user.recovery_codes is None


def test_prod_login_without_2fa_rejected(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "prod")

    user = User(
        email="no_2fa_prod@example.com",
        name="No 2FA",
        role="organizer",
        password_hash=hash_password("secure_pass1234"),
        is_active=True,
        totp_enabled=False,
    )
    db.add(user)
    db.commit()

    res = client.post(
        "/api/login",
        json={"email": "no_2fa_prod@example.com", "password": "secure_pass1234"},
        headers={"Host": "localhost", "Origin": "http://localhost"},
    )
    assert res.status_code == 403
    assert "sponsy_session" not in res.cookies


def test_internet_facing_security_host_and_origin(
    client: TestClient, admin_user: User, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "public_url", "https://sponsy.example.com")

    # 1. Invalid Host header rejected with 400
    res_bad_host = client.get("/api/today", headers={"Host": "evil.com"})
    assert res_bad_host.status_code == 400
    assert "Invalid Host header" in res_bad_host.text

    # 2. State-changing request with invalid Origin rejected with 403
    raw_token, csrf = create_session(db, admin_user.id)
    client.cookies.set("sponsy_session", raw_token)

    res_bad_origin = client.post(
        "/api/admin/revoke-sessions",
        headers={
            "Host": "sponsy.example.com",
            "Origin": "https://evil.com",
            "X-CSRF-Token": csrf,
        },
    )
    assert res_bad_origin.status_code == 403
    assert "Invalid Origin or Referer" in res_bad_origin.text

    # 3. Request with valid Host and Origin accepted
    res_valid = client.post(
        "/api/admin/revoke-sessions",
        headers={
            "Host": "sponsy.example.com",
            "Origin": "https://sponsy.example.com",
            "X-CSRF-Token": csrf,
        },
    )
    assert res_valid.status_code == 200


def test_rate_limiting_per_ip(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "login_rate_limit_per_minute", 3)
    _IP_AUTH_REQUESTS.clear()

    # Send 3 login requests -> 401 (credentials check)
    for _ in range(3):
        res = client.post(
            "/api/login",
            json={"email": "fake@example.com", "password": "fake_pass1234"},
        )
        assert res.status_code in (401, 429)

    # 4th request must be rate limited with 429
    res_blocked = client.post(
        "/api/login",
        json={"email": "fake@example.com", "password": "fake_pass1234"},
    )
    assert res_blocked.status_code == 429
    assert "Rate limit exceeded" in res_blocked.text


def test_prod_security_headers_and_cookie(
    client: TestClient, admin_user: User, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "prod")
    monkeypatch.setattr(settings, "public_url", "https://sponsy.example.com")

    res = client.get("/api/healthz")
    assert res.status_code == 200
    assert "strict-transport-security" in res.headers
    assert "nosniff" in res.headers["x-content-type-options"]

    # Cookie secure flag check in prod
    res_login = client.post(
        "/api/login",
        json={"email": admin_user.email, "password": "admin_secure_pass123"},
        headers={"Host": "sponsy.example.com", "Origin": "https://sponsy.example.com"},
    )
    # Since admin_user has totp_enabled=False in test, in prod it returns 403
    assert res_login.status_code == 403

    # Enable 2FA on admin
    admin_user.totp_enabled = True
    admin_user.totp_secret = pyotp.random_base32()
    db.commit()

    res_login2 = client.post(
        "/api/login",
        json={"email": admin_user.email, "password": "admin_secure_pass123"},
        headers={"Host": "sponsy.example.com", "Origin": "https://sponsy.example.com"},
    )
    assert res_login2.status_code == 200
    pending_token = res_login2.json()["pending_token"]

    totp = pyotp.TOTP(admin_user.totp_secret)
    res_code = client.post(
        "/api/login/code",
        json={"pending_token": pending_token, "code": totp.now()},
        headers={"Host": "sponsy.example.com", "Origin": "https://sponsy.example.com"},
    )
    assert res_code.status_code == 200
    # Cookie has secure flag in prod
    set_cookie_header = res_code.headers.get("set-cookie", "")
    assert "Secure" in set_cookie_header or "secure" in set_cookie_header.lower()


def test_admin_system_status(client: TestClient, admin_user: User, db: Session) -> None:
    raw_token, _ = create_session(db, admin_user.id)
    client.cookies.set("sponsy_session", raw_token)

    res = client.get("/api/admin/system")
    assert res.status_code == 200
    data = res.json()
    assert "db_size_bytes" in data
    assert "disk_free_bytes" in data
    assert "last_mail_check" in data
    assert "last_send" in data
    assert "last_backup" in data


def test_admin_revoke_all_sessions(client: TestClient, admin_user: User, db: Session) -> None:
    raw_token, csrf = create_session(db, admin_user.id)
    create_session(db, admin_user.id)
    client.cookies.set("sponsy_session", raw_token)

    sessions_before = db.scalars(select(SessionModel)).all()
    assert len(sessions_before) >= 2

    res = client.post("/api/admin/revoke-sessions", headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200

    sessions_after = db.scalars(select(SessionModel)).all()
    assert len(sessions_after) == 0


def test_admin_erase_contact(
    client: TestClient, admin_user: User, test_campaign: Target, db: Session
) -> None:
    from app.models import Company

    company = Company(name="TargetCo", domain="targetco.com")
    db.add(company)
    db.flush()

    contact = Contact(
        company_id=company.id,
        name="Privacy User",
        email="privacy@targetco.com",
    )
    db.add(contact)
    db.flush()

    target = Target(
        campaign_id=test_campaign.id,
        company_id=company.id,
        status="contacted",
    )
    db.add(target)
    db.flush()

    msg = Message(
        target_id=target.id,
        contact_id=contact.id,
        direction="out",
        kind="pitch",
        subject="Confidential sponsorship proposal",
        body="Secret proposal body content for privacy user",
        status="sent",
    )
    db.add(msg)
    db.commit()

    raw_token, csrf = create_session(db, admin_user.id)
    client.cookies.set("sponsy_session", raw_token)

    # Erase contact
    res = client.post(f"/api/admin/contacts/{contact.id}/erase", headers={"X-CSRF-Token": csrf})
    assert res.status_code == 200

    # Contact is removed
    deleted_contact = db.get(Contact, contact.id)
    assert deleted_contact is None

    # Suppression entry is recorded
    suppression = db.scalar(
        select(Suppression).where(
            Suppression.kind == "email",
            Suppression.value == "privacy@targetco.com",
        )
    )
    assert suppression is not None
    assert suppression.reason == "contact_erased"

    # Message bodies and subjects are scrubbed (SEC-28)
    db.refresh(msg)
    assert msg.body == "[erased]"
    assert msg.subject == "[erased]"
    assert msg.contact_id is None

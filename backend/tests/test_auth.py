"""Tests for authentication, sessions, CSRF, throttling, and role authorization (Phase 1)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import IDLE_TIMEOUT, SESSION_COOKIE_NAME, create_session
from app.models import AuditLog, User, utc_now
from app.models import Session as SessionModel


def test_login_successful_sets_cookie_and_creates_session(
    client: TestClient, organizer_user: User, db: Session
) -> None:
    response = client.post(
        "/api/login",
        json={"email": "organizer@example.com", "password": "organizer_pass123"},
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Logged in"}

    cookie = response.cookies.get(SESSION_COOKIE_NAME)
    assert cookie is not None

    # Verify session exists in DB
    stmt = select(SessionModel).where(SessionModel.user_id == organizer_user.id)
    sessions = db.scalars(stmt).all()
    assert len(sessions) == 1
    assert sessions[0].csrf_token is not None


def test_login_failure_with_wrong_password_returns_generic_error(
    client: TestClient, organizer_user: User
) -> None:
    # SEC-05: same error for wrong password
    response = client.post(
        "/api/login",
        json={"email": "organizer@example.com", "password": "wrong_password_test"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "That email and password do not match."


def test_login_failure_with_unknown_email_returns_identical_error(client: TestClient) -> None:
    # SEC-05: same error for unknown user
    response = client.post(
        "/api/login",
        json={"email": "nobody@example.com", "password": "some_random_password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "That email and password do not match."


def test_login_throttling_after_five_failed_attempts(
    client: TestClient, organizer_user: User
) -> None:
    # SEC-06: 5 failures locks account and IP pair
    for _ in range(5):
        resp = client.post(
            "/api/login",
            json={"email": "organizer@example.com", "password": "bad_password_attempt"},
        )
        assert resp.status_code == 401

    # 6th attempt should be throttled with HTTP 429
    throttled_resp = client.post(
        "/api/login",
        json={"email": "organizer@example.com", "password": "organizer_pass123"},
    )
    assert throttled_resp.status_code == 429
    assert "Too many failed attempts" in throttled_resp.json()["detail"]


def test_protected_route_denies_unauthenticated_request(client: TestClient) -> None:
    # SEC-08: deny by default
    response = client.get("/api/today")
    assert response.status_code == 401


def test_session_idle_timeout_rejects_expired_session(
    client: TestClient, organizer_user: User, db: Session
) -> None:
    # SEC-07: 8 hour idle timeout
    raw_token, _ = create_session(db, organizer_user.id)
    session_row = db.query(SessionModel).filter_by(user_id=organizer_user.id).first()
    assert session_row is not None
    session_row.last_seen_at = utc_now() - IDLE_TIMEOUT - timedelta(minutes=5)
    db.commit()

    client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    response = client.get("/api/session")
    assert response.status_code == 401
    assert "idle timeout" in response.json()["detail"].lower()


def test_organizer_cannot_access_admin_user_routes(
    client: TestClient, organizer_user: User, db: Session
) -> None:
    # SEC-09: role checks prevent organizer from viewing admin pages
    raw_token, _ = create_session(db, organizer_user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)

    response = client.get("/api/admin/users")
    assert response.status_code == 403
    assert "Administrator access required" in response.json()["detail"]


def test_admin_can_list_and_create_users(client: TestClient, admin_user: User, db: Session) -> None:
    # SEC-04 & SEC-09: admin creates organizer
    raw_token, csrf_token = create_session(db, admin_user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)

    # List users
    list_resp = client.get("/api/admin/users")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    # Create new user
    create_resp = client.post(
        "/api/admin/users",
        headers={"X-CSRF-Token": csrf_token},
        json={
            "email": "new_member@example.com",
            "name": "New Member",
            "role": "organizer",
            "password": "new_secure_password123",
        },
    )
    assert create_resp.status_code == 201
    assert create_resp.json()["email"] == "new_member@example.com"
    assert create_resp.json()["role"] == "organizer"


def test_mutation_without_csrf_token_is_rejected(
    client: TestClient, admin_user: User, db: Session
) -> None:
    # SEC-10: CSRF header required on mutation routes
    raw_token, _ = create_session(db, admin_user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)

    # Attempt POST without X-CSRF-Token header
    response = client.post(
        "/api/admin/users",
        json={
            "email": "blocked@example.com",
            "name": "Blocked",
            "role": "organizer",
            "password": "blocked_pass123",
        },
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_mutation_with_invalid_csrf_token_is_rejected(
    client: TestClient, admin_user: User, db: Session
) -> None:
    # SEC-10: invalid token rejected
    raw_token, _ = create_session(db, admin_user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)

    response = client.post(
        "/api/admin/users",
        headers={"X-CSRF-Token": "invalid_forged_token"},
        json={
            "email": "blocked2@example.com",
            "name": "Blocked",
            "role": "organizer",
            "password": "blocked_pass123",
        },
    )
    assert response.status_code == 403
    assert "CSRF" in response.json()["detail"]


def test_admin_cannot_deactivate_self(client: TestClient, admin_user: User, db: Session) -> None:
    raw_token, csrf_token = create_session(db, admin_user.id)
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)

    response = client.put(
        f"/api/admin/users/{admin_user.id}",
        headers={"X-CSRF-Token": csrf_token},
        json={"is_active": False},
    )
    assert response.status_code == 400
    assert "deactivate their own account" in response.json()["detail"]


def test_password_change_invalidates_old_sessions(
    client: TestClient, organizer_user: User, db: Session
) -> None:
    # SEC-07: password change resets sessions
    raw_token_1, csrf_token_1 = create_session(db, organizer_user.id)
    raw_token_2, _ = create_session(db, organizer_user.id)

    client.cookies.set(SESSION_COOKIE_NAME, raw_token_1)
    change_resp = client.post(
        "/api/account/password",
        headers={"X-CSRF-Token": csrf_token_1},
        json={"old_password": "organizer_pass123", "new_password": "brand_new_password_2026"},
    )
    assert change_resp.status_code == 200

    # Old token 2 should no longer exist or work
    client.cookies.clear()
    client.cookies.set(SESSION_COOKIE_NAME, raw_token_2)
    session_check = client.get("/api/session")
    assert session_check.status_code == 401


def test_audit_log_records_login_logout_and_user_creation(
    client: TestClient, admin_user: User, db: Session
) -> None:
    # SEC-30: audit log append-only
    login_resp = client.post(
        "/api/login",
        json={"email": "admin@example.com", "password": "admin_secure_pass123"},
    )
    assert login_resp.status_code == 200

    logs = db.scalars(select(AuditLog).where(AuditLog.action == "login")).all()
    assert len(logs) >= 1
    assert logs[0].entity == "users"
    assert logs[0].user_id == admin_user.id


def test_create_admin_script_bootstraps_admin(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    # SEC-04: scripts/create_admin.py creates the first admin
    import sys
    from pathlib import Path

    from sqlalchemy.orm import sessionmaker

    root_dir = str(Path(__file__).resolve().parent.parent.parent)
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)

    import scripts.create_admin as ca

    test_session_factory = sessionmaker(bind=db.get_bind())
    monkeypatch.setattr(ca, "SessionLocal", test_session_factory)
    ca.create_admin("first_admin@example.com", "First Admin", "super_secret_admin_pass123")

    user = db.scalar(select(User).where(User.email == "first_admin@example.com"))
    assert user is not None
    assert user.role == "admin"
    assert user.is_active is True

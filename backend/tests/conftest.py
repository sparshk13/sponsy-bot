"""Pytest fixtures with real disposable PostgreSQL database (CODE-13)."""

import os
import subprocess
import time
from collections.abc import Generator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.auth import hash_password
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import (
    ApiUsage,
    AuditLog,
    Brochure,
    Campaign,
    Company,
    CompanyFact,
    Contact,
    LoginAttempt,
    Message,
    Outcome,
    Target,
    Template,
    User,
)
from app.models import Session as SessionModel

TEST_CONTAINER_NAME = "sponsy_pytest_pg"
DEFAULT_TEST_URL = "postgresql+psycopg://postgres:testpass@localhost:54333/sponsy_test"


@pytest.fixture(scope="session")
def postgres_service() -> Generator[str, None, None]:
    test_url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)

    raw_conn_url = test_url.replace("+psycopg", "")
    try:
        conn = psycopg.connect(raw_conn_url, connect_timeout=1)
        conn.close()
        yield test_url
        return
    except Exception:
        pass

    env = dict(os.environ)
    colima_sock = Path.home() / ".colima" / "default" / "docker.sock"
    if colima_sock.exists() and "DOCKER_HOST" not in env:
        env["DOCKER_HOST"] = f"unix://{colima_sock}"

    subprocess.run(["docker", "rm", "-f", TEST_CONTAINER_NAME], env=env, capture_output=True)

    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        TEST_CONTAINER_NAME,
        "-p",
        "54333:5432",
        "-e",
        "POSTGRES_PASSWORD=testpass",
        "-e",
        "POSTGRES_DB=sponsy_test",
        "postgres:17-alpine",
    ]
    subprocess.run(cmd, env=env, check=True, capture_output=True)

    connected = False
    for _ in range(15):
        try:
            conn = psycopg.connect(raw_conn_url, connect_timeout=1)
            conn.close()
            connected = True
            break
        except Exception:
            time.sleep(1)

    if not connected:
        subprocess.run(["docker", "rm", "-f", TEST_CONTAINER_NAME], env=env, capture_output=True)
        raise RuntimeError("Failed to connect to disposable PostgreSQL container")

    try:
        yield test_url
    finally:
        subprocess.run(["docker", "rm", "-f", TEST_CONTAINER_NAME], env=env, capture_output=True)


@pytest.fixture(scope="session")
def engine(postgres_service: str):
    eng = create_engine(postgres_service, pool_pre_ping=True)
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture
def db(engine) -> Generator[Session, None, None]:
    SessionTest = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionTest()

    session.query(Outcome).delete()
    session.query(Message).delete()
    session.query(Brochure).delete()
    session.query(Template).delete()
    session.query(Target).delete()
    session.query(CompanyFact).delete()
    session.query(Contact).delete()
    session.query(Company).delete()
    session.query(Campaign).delete()
    session.query(SessionModel).delete()
    session.query(AuditLog).delete()
    session.query(LoginAttempt).delete()
    session.query(ApiUsage).delete()
    session.query(User).delete()
    session.commit()

    def override_get_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session
    finally:
        app.dependency_overrides.pop(get_db, None)
        session.close()


@pytest.fixture
def client(db: Session, monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setattr(settings, "app_env", "dev")
    monkeypatch.setattr(settings, "gemini_rpm", 1000)
    from app.budget import _gemini_limiter

    _gemini_limiter.timestamps.clear()

    from app.security import _IP_API_REQUESTS, _IP_AUTH_REQUESTS

    _IP_API_REQUESTS.clear()
    _IP_AUTH_REQUESTS.clear()

    test_client = TestClient(app)
    try:
        yield test_client
    finally:
        _IP_API_REQUESTS.clear()
        _IP_AUTH_REQUESTS.clear()


@pytest.fixture
def admin_user(db: Session) -> User:
    admin = User(
        email="admin@example.com",
        name="Admin User",
        role="admin",
        password_hash=hash_password("admin_secure_pass123"),
        is_active=True,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def organizer_user(db: Session) -> User:
    organizer = User(
        email="organizer@example.com",
        name="Organizer User",
        role="organizer",
        password_hash=hash_password("organizer_pass123"),
        is_active=True,
    )
    db.add(organizer)
    db.commit()
    db.refresh(organizer)
    return organizer


@pytest.fixture
def test_campaign(db: Session, admin_user: User) -> Campaign:
    campaign = Campaign(
        name="Hackathon 2026",
        event_summary="Annual 36-hour student hackathon with 500 attendees.",
        cash_target_inr=500000,
        goodies_note="Swag bags and t-shirts",
        credits_note="Cloud credits for participants",
        created_by=admin_user.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign

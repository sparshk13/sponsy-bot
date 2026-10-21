"""Authentication, sessions, CSRF, and login throttling enforcing SEC-04 to SEC-10."""

import hashlib
import secrets
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import LoginAttempt, User, utc_now
from app.models import Session as SessionModel

SESSION_COOKIE_NAME = "sponsy_session"
IDLE_TIMEOUT = timedelta(hours=8)
ABSOLUTE_TIMEOUT = timedelta(days=7)
THROTTLE_WINDOW = timedelta(minutes=15)
MAX_LOGIN_FAILURES = 5

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    # SEC-05: minimum 12 characters, argon2id
    if len(password) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 12 characters long",
        )
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    # SEC-05: verify with argon2id
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "127.0.0.1"


def check_login_throttle(db: Session, email: str, ip: str) -> bool:
    # SEC-06: 5 failures per account and IP in 15 minutes locks that pair for 15 minutes
    cutoff = utc_now() - THROTTLE_WINDOW
    stmt = (
        select(func.count(LoginAttempt.id))
        .where(func.lower(LoginAttempt.email) == email.strip().lower())
        .where(LoginAttempt.ip == ip)
        .where(LoginAttempt.at >= cutoff)
    )
    failure_count = db.scalar(stmt) or 0
    return failure_count >= MAX_LOGIN_FAILURES


def record_login_failure(db: Session, email: str, ip: str) -> None:
    # SEC-06: recorded in DB so it survives restarts
    attempt = LoginAttempt(
        email=email.strip().lower(),
        ip=ip,
        at=utc_now(),
    )
    db.add(attempt)
    db.commit()


def create_session(db: Session, user_id: int) -> tuple[str, str]:
    # SEC-07: secrets.token_urlsafe(32), stored as sha256 hash
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    csrf_token = secrets.token_urlsafe(32)

    now = utc_now()
    session_row = SessionModel(
        token_hash=token_hash,
        user_id=user_id,
        csrf_token=csrf_token,
        created_at=now,
        last_seen_at=now,
    )
    db.add(session_row)
    db.commit()
    return raw_token, csrf_token


def set_session_cookie(response: Response, raw_token: str) -> None:
    # SEC-07: HttpOnly, Secure in prod, SameSite=Lax
    is_prod = settings.app_env == "prod"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=int(ABSOLUTE_TIMEOUT.total_seconds()),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    # SEC-07
    is_prod = settings.app_env == "prod"
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=is_prod,
        samesite="lax",
    )


def get_current_session(
    request: Request,
    db: Session = Depends(get_db),
) -> SessionModel:
    # SEC-07 & SEC-08: validate server-side session from HttpOnly cookie
    raw_token = request.cookies.get(SESSION_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or not found",
        )

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    session = db.get(SessionModel, token_hash)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or not found",
        )

    now = utc_now()
    # SEC-07: 8 hour idle timeout
    if now - session.last_seen_at > IDLE_TIMEOUT:
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session idle timeout expired",
        )

    # SEC-07: 7 day absolute timeout
    if now - session.created_at > ABSOLUTE_TIMEOUT:
        db.delete(session)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session absolute timeout expired",
        )

    session.last_seen_at = now
    db.commit()
    return session


def get_current_user(
    session: SessionModel = Depends(get_current_session),
) -> User:
    # SEC-08 & SEC-09: check user active status
    user = session.user
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated or unavailable",
        )
    return user


def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    # SEC-09: role authorization check
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return user


def verify_csrf(
    request: Request,
    session: SessionModel = Depends(get_current_session),
) -> None:
    # SEC-10: required in X-CSRF-Token header on every POST/PUT/PATCH/DELETE
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    csrf_header = request.headers.get("X-CSRF-Token")
    if not csrf_header or not secrets.compare_digest(csrf_header, session.csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing CSRF token",
        )

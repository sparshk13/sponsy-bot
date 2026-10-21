import hashlib
import secrets
import time

import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.audit import log_audit
from app.auth import (
    check_login_throttle,
    clear_session_cookie,
    create_session,
    get_client_ip,
    get_current_session,
    get_current_user,
    hash_password,
    record_login_failure,
    set_session_cookie,
    verify_csrf,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.models import Session as SessionModel
from app.models import User
from app.schemas import (
    ChangePasswordRequest,
    LoginCodeRequest,
    LoginRequest,
    LoginResponse,
    SessionResponse,
    TwoFactorConfirmRequest,
    TwoFactorConfirmResponse,
    TwoFactorSetupResponse,
    UserResponse,
)

router = APIRouter(prefix="/api", tags=["auth"])

# In-memory storage for pending 2FA authentication attempts: pending_token -> (user_id, timestamp)
PENDING_2FA_LOGINS: dict[str, tuple[int, float]] = {}


@router.post("/login", response_model=LoginResponse, response_model_exclude_none=True)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    ip = get_client_ip(request)
    normalized_email = req.email.strip().lower()

    # SEC-06: 5 failures in 15 minutes locks account and IP pair
    if check_login_throttle(db, normalized_email, ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    stmt = select(User).where(func.lower(User.email) == normalized_email)
    user = db.scalar(stmt)

    if not user or not user.is_active or not verify_password(req.password, user.password_hash):
        record_login_failure(db, normalized_email, ip)
        # SEC-05: same error for unknown user and wrong password
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That email and password do not match.",
        )

    # SEC-40: When 2FA is enabled or in production, enforce second step before issuing session
    if user.totp_enabled:
        pending_token = secrets.token_urlsafe(32)
        PENDING_2FA_LOGINS[pending_token] = (user.id, time.time())
        return LoginResponse(
            message="Two-factor authentication code required",
            requires_2fa=True,
            pending_token=pending_token,
        )

    if settings.app_env == "prod":
        # In prod, login without 2FA never creates a session (SEC-40)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Two-factor authentication is required in production.",
        )

    # SEC-07: new session token on login
    raw_token, _ = create_session(db, user.id)
    set_session_cookie(response, raw_token)
    log_audit(db, user.id, "login", "users", str(user.id), "User logged in")

    return LoginResponse(message="Logged in")


@router.post("/login/code")
def login_with_code(
    req: LoginCodeRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    ip = get_client_ip(request)
    entry = PENDING_2FA_LOGINS.get(req.pending_token)
    if not entry or (time.time() - entry[1]) > 300:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session expired. Please log in again.",
        )

    user_id = entry[0]
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated or unavailable.",
        )

    if check_login_throttle(db, user.email, ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again in 15 minutes.",
        )

    code_clean = req.code.strip().replace(" ", "").replace("-", "")
    valid = False
    used_recovery = False

    if user.totp_secret:
        totp = pyotp.TOTP(user.totp_secret)
        valid = totp.verify(code_clean, valid_window=1)

    if not valid and user.recovery_codes:
        code_hash = hashlib.sha256(code_clean.lower().encode("utf-8")).hexdigest()
        if code_hash in user.recovery_codes:
            valid = True
            used_recovery = True
            # Consume recovery code
            user.recovery_codes = [c for c in user.recovery_codes if c != code_hash]
            flag_modified(user, "recovery_codes")
            db.commit()

    if not valid:
        record_login_failure(db, user.email, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication code or recovery code.",
        )

    PENDING_2FA_LOGINS.pop(req.pending_token, None)
    raw_token, _ = create_session(db, user.id)
    set_session_cookie(response, raw_token)
    action_note = (
        "User logged in with recovery code" if used_recovery else "User logged in with 2FA"
    )
    log_audit(db, user.id, "login_2fa", "users", str(user.id), action_note)
    return {"message": "Logged in"}


@router.post(
    "/account/2fa/setup",
    response_model=TwoFactorSetupResponse,
    dependencies=[Depends(verify_csrf)],
)
def setup_two_factor(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TwoFactorSetupResponse:
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    otpauth_url = totp.provisioning_uri(name=user.email, issuer_name="Sponsy Bot")

    user.totp_secret = secret
    db.commit()
    return TwoFactorSetupResponse(secret=secret, otpauth_url=otpauth_url)


@router.post(
    "/account/2fa/confirm",
    response_model=TwoFactorConfirmResponse,
    dependencies=[Depends(verify_csrf)],
)
def confirm_two_factor(
    req: TwoFactorConfirmRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TwoFactorConfirmResponse:
    if not user.totp_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Two-factor setup has not been initiated.",
        )

    code_clean = req.code.strip().replace(" ", "").replace("-", "")
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(code_clean, valid_window=1):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code.",
        )

    # SEC-40: Generate 10 single-use recovery codes, stored hashed
    plain_codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(10)]
    hashed_codes = [
        hashlib.sha256(c.replace("-", "").lower().encode("utf-8")).hexdigest() for c in plain_codes
    ]

    user.recovery_codes = hashed_codes
    user.totp_enabled = True
    flag_modified(user, "recovery_codes")
    db.commit()

    log_audit(db, user.id, "enable_2fa", "users", str(user.id), "Two-factor authentication enabled")
    return TwoFactorConfirmResponse(recovery_codes=plain_codes)


@router.post("/logout", dependencies=[Depends(verify_csrf)])
def logout(
    response: Response,
    session: SessionModel = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    # SEC-07: delete session on logout
    db.delete(session)
    db.commit()
    clear_session_cookie(response)
    log_audit(db, user.id, "logout", "users", str(user.id), "User logged out")
    return {"message": "Logged out"}


@router.get("/session")
def get_session(
    session: SessionModel = Depends(get_current_session),
    user: User = Depends(get_current_user),
) -> SessionResponse:
    # SEC-10: CSRF token lives in memory from GET /api/session
    return SessionResponse(
        user=UserResponse.model_validate(user),
        csrf_token=session.csrf_token,
    )


@router.post("/account/password", dependencies=[Depends(verify_csrf)])
def change_password(
    req: ChangePasswordRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if not verify_password(req.old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    user.password_hash = hash_password(req.new_password)

    # SEC-07: invalidate all existing sessions on password change
    stmt = select(SessionModel).where(SessionModel.user_id == user.id)
    existing_sessions = db.scalars(stmt).all()
    for s in existing_sessions:
        db.delete(s)
    db.commit()

    raw_token, _ = create_session(db, user.id)
    set_session_cookie(response, raw_token)
    log_audit(db, user.id, "change_password", "users", str(user.id), "Password changed")

    return {"message": "Password updated"}

import os
import pathlib
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import hash_password, require_admin, verify_csrf
from app.config import settings
from app.db import get_db
from app.models import (
    AuditLog,
    Brochure,
    Contact,
    Message,
    SettingsState,
    Suppression,
    Template,
    User,
)
from app.models import Session as SessionModel
from app.schemas import (
    AuditLogResponse,
    BrochureResponse,
    CreateUserRequest,
    PauseRequest,
    PauseResponse,
    SuppressionCreateRequest,
    SuppressionResponse,
    SystemStatusResponse,
    TemplateCreate,
    TemplateResponse,
    TemplateUpdate,
    UpdateUserRequest,
    UserResponse,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])
MAX_BROCHURE_BYTES = 5 * 1024 * 1024  # SEC-17: 5 MB max


@router.get("/users", response_model=list[UserResponse])
def list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[User]:
    stmt = select(User).order_by(User.id.asc())
    return list(db.scalars(stmt).all())


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
def create_user(
    req: CreateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    normalized_email = req.email.strip().lower()
    existing = db.scalar(select(User).where(func.lower(User.email) == normalized_email))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # SEC-04 & SEC-05: admins create users with argon2id hashed passwords
    new_user = User(
        email=normalized_email,
        name=req.name.strip(),
        role=req.role,
        password_hash=hash_password(req.password),
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_audit(
        db,
        admin.id,
        "create_user",
        "users",
        str(new_user.id),
        f"Created {new_user.role} account",
    )
    return new_user


@router.put(
    "/users/{user_id}",
    response_model=UserResponse,
    dependencies=[Depends(verify_csrf)],
)
def update_user(
    user_id: int,
    req: UpdateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    # SEC-09: re-load object server-side and verify existence
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if req.is_active is not None:
        if not req.is_active and target_user.id == admin.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Administrators cannot deactivate their own account.",
            )
        target_user.is_active = req.is_active
        if not req.is_active:
            # Terminate active sessions for deactivated user
            sessions = db.scalars(
                select(SessionModel).where(SessionModel.user_id == target_user.id)
            ).all()
            for s in sessions:
                db.delete(s)

    if req.password is not None:
        target_user.password_hash = hash_password(req.password)
        # Terminate active sessions on password reset
        sessions = db.scalars(
            select(SessionModel).where(SessionModel.user_id == target_user.id)
        ).all()
        for s in sessions:
            db.delete(s)

    db.commit()
    db.refresh(target_user)

    log_audit(
        db,
        admin.id,
        "update_user",
        "users",
        str(target_user.id),
        "Updated user settings",
    )
    return target_user


@router.get("/audit", response_model=list[AuditLogResponse])
def get_audit_log(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[AuditLog]:
    # SEC-30: read-only audit log inspection
    stmt = select(AuditLog).order_by(AuditLog.at.desc()).limit(100)
    return list(db.scalars(stmt).all())


@router.get("/pause", response_model=PauseResponse)
def get_pause_state(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PauseResponse:
    val = db.scalar(select(SettingsState.value).where(SettingsState.key == "paused"))
    paused = bool(val and val.strip().lower() in ("true", "1", "yes"))
    return PauseResponse(paused=paused)


@router.put("/pause", response_model=PauseResponse, dependencies=[Depends(verify_csrf)])
def set_pause_state(
    req: PauseRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> PauseResponse:
    state = db.get(SettingsState, "paused")
    str_val = "true" if req.paused else "false"
    if state:
        state.value = str_val
    else:
        state = SettingsState(key="paused", value=str_val)
        db.add(state)

    log_audit(
        db,
        admin.id,
        "pause_toggle",
        "settings",
        "paused",
        f"Global sending pause set to {req.paused}",
    )
    db.commit()
    return PauseResponse(paused=req.paused)


# Suppression CRUD (R6, SEC-22, docs/ROUTES.md)
@router.get("/suppression", response_model=list[SuppressionResponse])
def list_suppression(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Suppression]:
    """List all suppression entries (Admin only)."""
    return list(db.scalars(select(Suppression).order_by(Suppression.created_at.desc())).all())


@router.post(
    "/suppression",
    response_model=SuppressionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
def add_suppression(
    req: SuppressionCreateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Suppression:
    """Add an email or domain to suppression (Admin only)."""
    clean_val = req.value.strip().lower()
    existing = db.scalar(select(Suppression).where(Suppression.value == clean_val))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Suppression entry for this value already exists.",
        )
    supp = Suppression(
        kind=req.kind,
        value=clean_val,
        reason=req.reason.strip() if req.reason else None,
    )
    db.add(supp)
    db.commit()
    db.refresh(supp)
    log_audit(
        db,
        admin.id,
        "add_suppression",
        "suppression",
        str(supp.id),
        f"Admin suppressed {supp.kind}: {supp.value}",
    )
    return supp


@router.delete(
    "/suppression/{suppression_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_csrf)],
)
def remove_suppression(
    suppression_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """Remove an email or domain from suppression (Admin only)."""
    supp = db.get(Suppression, suppression_id)
    if not supp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Suppression entry not found.",
        )
    val = supp.value
    db.delete(supp)
    db.commit()
    log_audit(
        db,
        admin.id,
        "remove_suppression",
        "suppression",
        str(suppression_id),
        f"Admin removed suppression for {val}",
    )


# Template CRUD (Phase 8, G6)
@router.get("/templates", response_model=list[TemplateResponse])
def list_templates(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Template]:
    """List all email outreach templates (Admin only)."""
    return list(db.scalars(select(Template).order_by(Template.id.asc())).all())


@router.post(
    "/templates",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
def create_template(
    req: TemplateCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Template:
    """Create a new email template (Admin only)."""
    template = Template(
        kind=req.kind,
        name=req.name.strip(),
        body=req.body.strip(),
    )
    db.add(template)
    db.flush()

    log_audit(
        db,
        admin.id,
        "create_template",
        "templates",
        str(template.id),
        f"Created template '{template.name}' ({template.kind})",
    )
    db.commit()
    db.refresh(template)
    return template


@router.put(
    "/templates/{template_id}",
    response_model=TemplateResponse,
    dependencies=[Depends(verify_csrf)],
)
def update_template(
    template_id: int,
    req: TemplateUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Template:
    """Update an existing template (Admin only)."""
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    if req.name is not None:
        template.name = req.name.strip()
    if req.body is not None:
        template.body = req.body.strip()

    log_audit(
        db,
        admin.id,
        "update_template",
        "templates",
        str(template.id),
        f"Updated template '{template.name}'",
    )
    db.commit()
    db.refresh(template)
    return template


@router.delete(
    "/templates/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(verify_csrf)],
)
def delete_template(
    template_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """Delete a template (Admin only)."""
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")

    log_audit(
        db,
        admin.id,
        "delete_template",
        "templates",
        str(template.id),
        f"Deleted template '{template.name}'",
    )
    db.delete(template)
    db.commit()


# Brochure Uploads (Phase 8, SEC-17, G5)
@router.get("/brochures", response_model=list[BrochureResponse])
def list_brochures(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[Brochure]:
    """List uploaded brochures for tiers (Admin only)."""
    return list(db.scalars(select(Brochure).order_by(Brochure.tier.asc())).all())


@router.post(
    "/brochures",
    response_model=BrochureResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
def upload_brochure(
    tier: str = Form(...),
    file: UploadFile = File(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Brochure:
    """Upload a tier brochure PDF with strict SEC-17 security checks."""
    if tier not in ("cash", "goodies", "credits"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tier must be one of: cash, goodies, credits.",
        )

    # SEC-17: read content and check 5 MB size limit
    content = file.file.read(MAX_BROCHURE_BYTES + 1)
    if len(content) > MAX_BROCHURE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Brochure exceeds maximum allowed size of 5 MB (SEC-17).",
        )

    # SEC-17: magic bytes must be %PDF
    if not content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is not a valid PDF document (magic bytes check failed).",
        )

    # SEC-17: sanitize original filename, generate random stored filename
    original_filename = pathlib.Path(file.filename or "brochure.pdf").name
    # Disallow path-like traversal in original name
    if "/" in original_filename or "\\" in original_filename or ".." in original_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    stored_name = f"{uuid.uuid4().hex}.pdf"
    storage_dir = settings.brochures_upload_dir
    os.makedirs(storage_dir, exist_ok=True)
    destination_path = os.path.join(storage_dir, stored_name)

    # Write file to disk outside static/
    with open(destination_path, "wb") as f:
        f.write(content)

    # Check if a brochure already exists for this tier
    existing = db.scalar(select(Brochure).where(Brochure.tier == tier))
    if existing:
        # Clean up old stored file if present
        old_path = os.path.join(storage_dir, existing.stored_name)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass
        existing.filename = original_filename
        existing.stored_name = stored_name
        existing.uploaded_by = admin.id
        existing.created_at = func.now()
        brochure = existing
    else:
        brochure = Brochure(
            tier=tier,
            filename=original_filename,
            stored_name=stored_name,
            uploaded_by=admin.id,
        )
        db.add(brochure)

    db.flush()
    log_audit(
        db,
        admin.id,
        "upload_brochure",
        "brochures",
        str(brochure.id),
        f"Uploaded brochure '{original_filename}' for tier {tier}",
    )
    db.commit()
    db.refresh(brochure)
    return brochure


@router.post(
    "/users/{user_id}/reset-2fa",
    dependencies=[Depends(verify_csrf)],
)
def reset_user_two_factor(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Reset 2FA credentials for a user (SEC-40)."""
    target_user = db.get(User, user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    target_user.totp_enabled = False
    target_user.totp_secret = None
    target_user.recovery_codes = None
    db.commit()

    log_audit(
        db,
        admin.id,
        "reset_2fa",
        "users",
        str(target_user.id),
        f"Reset 2FA for {target_user.email}",
    )
    return {"message": "Two-factor authentication reset"}


@router.get("/system", response_model=SystemStatusResponse)
def get_system_status(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SystemStatusResponse:
    """System health and operational telemetry (Acceptance 10.6)."""
    last_mail_check = db.scalar(
        select(func.max(Message.created_at)).where(Message.direction == "in")
    )
    last_send = db.scalar(
        select(func.max(Message.sent_at)).where(
            Message.direction == "out", Message.status == "sent"
        )
    )

    # Latest backup file from backups directory
    last_backup = None
    backups_dir = pathlib.Path("backups")
    if backups_dir.is_dir():
        files = sorted(backups_dir.glob("*.age"), key=os.path.getmtime, reverse=True)
        if files:
            last_backup = files[0].name

    # Database size
    try:
        db_size_bytes = db.scalar(text("SELECT pg_database_size(current_database())")) or 0
    except Exception:
        db_size_bytes = 0

    # Free disk space
    try:
        disk_free_bytes = shutil.disk_usage(os.getcwd()).free
    except Exception:
        disk_free_bytes = 0

    return SystemStatusResponse(
        last_mail_check=last_mail_check,
        last_send=last_send,
        last_backup=last_backup,
        db_size_bytes=db_size_bytes,
        disk_free_bytes=disk_free_bytes,
    )


@router.post(
    "/revoke-sessions",
    dependencies=[Depends(verify_csrf)],
)
def revoke_all_sessions(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Revoke all server-side sessions across all users (SEC-07, Acceptance 10.6)."""
    db.execute(delete(SessionModel))
    db.commit()

    log_audit(
        db,
        admin.id,
        "revoke_sessions",
        "sessions",
        "all",
        "All user sessions revoked",
    )
    return {"message": "All sessions revoked"}


@router.post(
    "/contacts/{contact_id}/erase",
    dependencies=[Depends(verify_csrf)],
)
def erase_contact(
    contact_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Erase a contact and message bodies while preserving suppression (SEC-28)."""
    contact = db.get(Contact, contact_id)
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found.")

    contact_email = contact.email.strip().lower() if contact.email else None

    # Preserve suppression entry
    if contact_email:
        existing_supp = db.scalar(
            select(Suppression).where(
                Suppression.kind == "email",
                Suppression.value == contact_email,
            )
        )
        if not existing_supp:
            suppression = Suppression(
                kind="email",
                value=contact_email,
                reason="contact_erased",
            )
            db.add(suppression)

    # Erase message bodies and metadata linked to this contact
    messages = db.scalars(select(Message).where(Message.contact_id == contact.id)).all()
    for msg in messages:
        msg.body = "[erased]"
        msg.subject = "[erased]"
        msg.summary = None
        msg.suggested_reply = None
        msg.contact_id = None

    db.delete(contact)
    db.commit()

    log_audit(
        db,
        admin.id,
        "erase_contact",
        "contacts",
        str(contact_id),
        f"Contact {contact_email or contact_id} erased and suppressed",
    )
    return {"message": "Contact erased"}

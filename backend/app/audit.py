"""Append-only audit logging module enforcing SEC-30."""

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_audit(
    db: Session,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    detail: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail=detail,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

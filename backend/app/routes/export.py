"""Data export endpoints (SEC-30)."""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.audit import log_audit
from app.auth import get_current_user
from app.db import get_db
from app.models import Target, User

router = APIRouter(prefix="/api/export", tags=["export"])


@router.get("/tracker.csv")
def export_tracker_csv(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required to export tracker.",
        )

    log_audit(db, user.id, "export_tracker", "targets", None, "Exported tracker CSV")

    stmt = (
        select(Target)
        .options(
            selectinload(Target.company),
            selectinload(Target.campaign),
            selectinload(Target.owner),
            selectinload(Target.outcomes),
        )
        .order_by(Target.id.asc())
    )
    targets = db.execute(stmt).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "company_name",
            "domain",
            "campaign_name",
            "tier",
            "priority",
            "status",
            "owner_name",
            "contact_name",
            "contact_email",
            "contact_role",
            "last_contacted_at",
            "followup_count",
            "outcome_kind",
            "outcome_amount_inr",
            "outcome_notes",
            "created_at",
        ]
    )

    for target in targets:
        contact = target.company.contacts[0] if target.company.contacts else None
        outcome = target.outcomes[-1] if target.outcomes else None

        writer.writerow(
            [
                target.company.name if target.company else "",
                target.company.domain if target.company else "",
                target.campaign.name if target.campaign else "",
                target.tier or "",
                target.priority or "",
                target.status,
                target.owner.name if target.owner else "",
                contact.name if contact and contact.name else "",
                contact.email if contact and contact.email else "",
                contact.role if contact and contact.role else "",
                target.last_contacted_at.isoformat() if target.last_contacted_at else "",
                target.followup_count,
                outcome.kind if outcome else "",
                outcome.amount_inr if outcome and outcome.amount_inr is not None else "",
                outcome.description if outcome and outcome.description else "",
                target.created_at.isoformat() if target.created_at else "",
            ]
        )

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="tracker.csv"'},
    )

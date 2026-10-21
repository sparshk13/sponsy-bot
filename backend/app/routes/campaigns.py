"""Admin campaign management routes enforcing SEC-09 and SEC-10."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import get_current_user, require_admin, verify_csrf
from app.db import get_db
from app.models import Campaign, User
from app.schemas import CampaignCreate, CampaignResponse, CampaignUpdate

router = APIRouter(prefix="/api/admin/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignResponse])
def list_campaigns(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Campaign]:
    stmt = select(Campaign).order_by(Campaign.id.desc())
    return list(db.scalars(stmt).all())


@router.post(
    "",
    response_model=CampaignResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
def create_campaign(
    req: CampaignCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Campaign:
    campaign = Campaign(
        name=req.name.strip(),
        event_summary=req.event_summary.strip(),
        event_date=req.event_date,
        audience_note=req.audience_note.strip() if req.audience_note else None,
        cash_target_inr=req.cash_target_inr,
        goodies_note=req.goodies_note.strip() if req.goodies_note else None,
        credits_note=req.credits_note.strip() if req.credits_note else None,
        calendar_link=req.calendar_link.strip() if req.calendar_link else None,
        created_by=admin.id,
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    log_audit(
        db,
        admin.id,
        "create_campaign",
        "campaigns",
        str(campaign.id),
        f"Created campaign {campaign.name}",
    )
    return campaign


@router.put(
    "/{campaign_id}",
    response_model=CampaignResponse,
    dependencies=[Depends(verify_csrf)],
)
def update_campaign(
    campaign_id: int,
    req: CampaignUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Campaign:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found.",
        )

    if req.name is not None:
        campaign.name = req.name.strip()
    if req.event_summary is not None:
        campaign.event_summary = req.event_summary.strip()
    if req.event_date is not None:
        campaign.event_date = req.event_date
    if req.audience_note is not None:
        campaign.audience_note = req.audience_note.strip() if req.audience_note else None
    if req.cash_target_inr is not None:
        campaign.cash_target_inr = req.cash_target_inr
    if req.goodies_note is not None:
        campaign.goodies_note = req.goodies_note.strip() if req.goodies_note else None
    if req.credits_note is not None:
        campaign.credits_note = req.credits_note.strip() if req.credits_note else None
    if req.calendar_link is not None:
        campaign.calendar_link = req.calendar_link.strip() if req.calendar_link else None

    db.commit()
    db.refresh(campaign)

    log_audit(
        db,
        admin.id,
        "update_campaign",
        "campaigns",
        str(campaign.id),
        f"Updated campaign {campaign.name}",
    )
    return campaign

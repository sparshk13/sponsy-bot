"""Dashboard and institutional memory routes (G3, G10)."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import Campaign, Company, Message, Outcome, Target, User
from app.schemas import (
    DashboardNonCashOutcome,
    DashboardOrganizerStat,
    DashboardPipelineStage,
    DashboardResponse,
    MemoryEntryResponse,
    MemoryResponse,
)

router = APIRouter(prefix="/api", tags=["dashboard"])

PIPELINE_STAGES: list[tuple[str, str]] = [
    ("not_contacted", "Not Contacted"),
    ("contacted", "Contacted"),
    ("follow_up", "Follow-up"),
    ("interested", "Interested"),
    ("meeting_booked", "Meeting Booked"),
    ("secured", "Secured"),
    ("declined", "Declined"),
    ("closed_no_reply", "Closed (No Reply)"),
]


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    status_counts = dict(
        db.execute(select(Target.status, func.count(Target.id)).group_by(Target.status)).all()
    )

    pipeline: list[DashboardPipelineStage] = [
        DashboardPipelineStage(
            stage=stage,
            label=label,
            count=status_counts.get(stage, 0),
        )
        for stage, label in PIPELINE_STAGES
    ]

    total_targets = sum(status_counts.values())
    contacted_count = total_targets - status_counts.get("not_contacted", 0)

    # Replied targets: either received inbound message or reached a response status
    replied_stmt = (
        select(func.count(func.distinct(Target.id)))
        .outerjoin(Message, Message.target_id == Target.id)
        .where(
            or_(
                Message.direction == "in",
                Target.status.in_(["interested", "meeting_booked", "secured", "declined"]),
            )
        )
    )
    replied_count = db.scalar(replied_stmt) or 0

    response_rate = (
        round((replied_count / contacted_count) * 100, 1) if contacted_count > 0 else 0.0
    )

    interested_count = (
        status_counts.get("interested", 0)
        + status_counts.get("meeting_booked", 0)
        + status_counts.get("secured", 0)
    )
    interest_rate = (
        round((interested_count / contacted_count) * 100, 1) if contacted_count > 0 else 0.0
    )

    declined_count = status_counts.get("declined", 0)
    secured_count = status_counts.get("secured", 0)

    total_cash_inr = (
        db.scalar(
            select(func.coalesce(func.sum(Outcome.amount_inr), 0)).where(Outcome.kind == "cash")
        )
        or 0
    )

    non_cash_rows = db.execute(
        select(Outcome, Company.name)
        .join(Target, Outcome.target_id == Target.id)
        .join(Company, Target.company_id == Company.id)
        .where(Outcome.kind.in_(["goodies", "credits"]))
        .order_by(Outcome.confirmed_at.desc())
    ).all()

    non_cash_outcomes = [
        DashboardNonCashOutcome(
            id=outcome.id,
            company_name=company_name,
            kind=outcome.kind,
            description=outcome.description,
            confirmed_at=outcome.confirmed_at,
        )
        for outcome, company_name in non_cash_rows
    ]

    users = db.execute(select(User).order_by(User.name)).scalars().all()
    organizers: list[DashboardOrganizerStat] = []
    for u in users:
        assigned = db.scalar(select(func.count(Target.id)).where(Target.owner_id == u.id)) or 0
        user_contacted = (
            db.scalar(
                select(func.count(Target.id)).where(
                    Target.owner_id == u.id, Target.status != "not_contacted"
                )
            )
            or 0
        )
        user_secured = (
            db.scalar(
                select(func.count(Target.id)).where(
                    Target.owner_id == u.id, Target.status == "secured"
                )
            )
            or 0
        )
        user_cash = (
            db.scalar(
                select(func.coalesce(func.sum(Outcome.amount_inr), 0))
                .join(Target, Outcome.target_id == Target.id)
                .where(Target.owner_id == u.id, Outcome.kind == "cash")
            )
            or 0
        )
        organizers.append(
            DashboardOrganizerStat(
                user_id=u.id,
                name=u.name,
                assigned_count=assigned,
                contacted_count=user_contacted,
                secured_count=user_secured,
                secured_cash_inr=user_cash,
            )
        )

    return DashboardResponse(
        total_targets=total_targets,
        pipeline=pipeline,
        contacted_count=contacted_count,
        replied_count=replied_count,
        response_rate=response_rate,
        interested_count=interested_count,
        interest_rate=interest_rate,
        declined_count=declined_count,
        secured_count=secured_count,
        total_cash_inr=total_cash_inr,
        non_cash_outcomes=non_cash_outcomes,
        organizers=organizers,
    )


@router.get("/memory", response_model=MemoryResponse)
def get_memory(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    outcomes_stmt = (
        select(Outcome, Target, Company, Campaign)
        .join(Target, Outcome.target_id == Target.id)
        .join(Company, Target.company_id == Company.id)
        .join(Campaign, Target.campaign_id == Campaign.id)
        .order_by(Outcome.confirmed_at.desc())
    )
    rows = db.execute(outcomes_stmt).all()

    entries: list[MemoryEntryResponse] = []
    unique_domains: set[str] = set()
    total_cash_inr = 0

    for outcome, target, company, campaign in rows:
        unique_domains.add(company.domain)
        if outcome.kind == "cash" and outcome.amount_inr:
            total_cash_inr += outcome.amount_inr

        entries.append(
            MemoryEntryResponse(
                id=outcome.id,
                company_name=company.name,
                company_domain=company.domain,
                campaign_name=campaign.name,
                kind=outcome.kind,
                amount_inr=outcome.amount_inr,
                description=outcome.description,
                confirmed_at=outcome.confirmed_at,
                ask_worked=target.ask_summary or target.ask_reasoning,
                tier=target.tier,
            )
        )

    return MemoryResponse(
        entries=entries,
        total_cash_inr=total_cash_inr,
        total_sponsors=len(unique_domains),
    )

"""Target tracking, claims, deduplication, and CSV import routes (PRD R1, R9)."""

import csv
import io
from datetime import timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import log_audit
from app.auth import get_current_user, require_admin, verify_csrf
from app.budget import BudgetExhausted
from app.db import get_db
from app.domain_norm import find_near_matches, normalize_domain
from app.graph import build_graph_a
from app.hunter import HunterError, search_hunter_domain
from app.models import (
    Campaign,
    Company,
    CompanyFact,
    Contact,
    Message,
    Outcome,
    Target,
    User,
    utc_now,
)
from app.research import run_research
from app.schemas import (
    ClaimResponse,
    CompanyFactResponse,
    ContactResponse,
    ContactUpdateRequest,
    CSVImportResponse,
    CSVImportRowReport,
    FindContactResponse,
    MessageResponse,
    OutcomeCreateRequest,
    OutcomeResponse,
    TargetCreateRequest,
    TargetDetailResponse,
    TargetReassignRequest,
    TargetResponse,
    TargetStatusUpdateRequest,
)

router = APIRouter(prefix="/api/targets", tags=["targets"])
COOLDOWN_WINDOW = timedelta(days=90)


def check_cooldown(db: Session, company_id: int) -> bool:
    """Check if company was contacted within the 90-day cooldown period (PRD R9)."""
    cutoff = utc_now() - COOLDOWN_WINDOW
    stmt = (
        select(Message.id)
        .join(Target, Message.target_id == Target.id)
        .where(
            Target.company_id == company_id,
            Message.direction == "out",
            Message.status == "sent",
            Message.sent_at >= cutoff,
        )
        .limit(1)
    )
    return db.scalar(stmt) is not None


def format_target_response(db: Session, target: Target) -> TargetResponse:
    company = target.company
    owner = target.owner
    contact = db.scalar(
        select(Contact)
        .where(Contact.company_id == company.id, Contact.is_valid.is_(True))
        .order_by(Contact.id.asc())
    )
    cooldown_active = check_cooldown(db, company.id)

    return TargetResponse(
        id=target.id,
        campaign_id=target.campaign_id,
        company_id=company.id,
        company_name=company.name,
        domain=company.domain,
        category=company.category,
        website=company.website,
        owner_id=target.owner_id,
        owner_name=owner.name if owner else None,
        status=target.status,
        tier=target.tier,
        priority=target.priority,
        priority_score=target.priority_score,
        contact=ContactResponse.model_validate(contact) if contact else None,
        followup_count=target.followup_count,
        last_contacted_at=target.last_contacted_at,
        next_followup_at=target.next_followup_at,
        cooldown_active=cooldown_active and not target.cooldown_unlocked,
        cooldown_unlocked=target.cooldown_unlocked,
        created_at=target.created_at,
    )


@router.get("", response_model=list[TargetResponse])
def list_targets(
    campaign_id: int | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    tier_filter: str | None = Query(None, alias="tier"),
    owner_id: int | None = Query(None),
    search: str | None = Query(None),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[TargetResponse]:
    stmt = select(Target).join(Company, Target.company_id == Company.id)

    if campaign_id is not None:
        stmt = stmt.where(Target.campaign_id == campaign_id)
    if status_filter:
        stmt = stmt.where(Target.status == status_filter)
    if tier_filter:
        stmt = stmt.where(Target.tier == tier_filter)
    if owner_id is not None:
        stmt = stmt.where(Target.owner_id == owner_id)
    if search:
        term = f"%{search.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Company.name).like(term),
                func.lower(Company.domain).like(term),
                func.lower(Company.category).like(term),
            )
        )

    stmt = stmt.order_by(Target.id.asc())
    targets = db.scalars(stmt).all()
    return [format_target_response(db, t) for t in targets]


@router.post(
    "",
    response_model=TargetResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
def add_target(
    req: TargetCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetResponse:
    campaign = db.get(Campaign, req.campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    domain = normalize_domain(req.website)
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid website or domain is required.",
        )

    company = db.scalar(select(Company).where(Company.domain == domain))
    if not company:
        company = Company(
            name=req.name.strip(),
            domain=domain,
            website=req.website.strip(),
            category=req.category.strip() if req.category else None,
        )
        db.add(company)
        db.commit()
        db.refresh(company)

    # SEC-37: check duplicate target in campaign
    existing_target = db.scalar(
        select(Target).where(
            Target.campaign_id == campaign.id,
            Target.company_id == company.id,
        )
    )
    if existing_target:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{company.name} is already a target in this campaign.",
        )

    if req.contact_email or req.contact_name:
        contact = Contact(
            company_id=company.id,
            name=req.contact_name.strip() if req.contact_name else None,
            role=req.contact_role.strip() if req.contact_role else None,
            email=req.contact_email.strip().lower() if req.contact_email else None,
            source="manual",
        )
        db.add(contact)

    target = Target(
        campaign_id=campaign.id,
        company_id=company.id,
        status="not_contacted",
    )
    db.add(target)
    db.commit()
    db.refresh(target)

    log_audit(db, user.id, "add_target", "targets", str(target.id), f"Added target {company.name}")
    return format_target_response(db, target)


@router.post("/import", response_model=CSVImportResponse, dependencies=[Depends(verify_csrf)])
def import_csv(
    campaign_id: int = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CSVImportResponse:
    campaign = db.get(Campaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    try:
        content = file.file.read().decode("utf-8-sig")
    except (UnicodeDecodeError, AttributeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read CSV file. Please upload a UTF-8 encoded text file.",
        )

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV file contains no headers.",
        )

    headers = {h.strip().lower(): h for h in reader.fieldnames if h}
    name_col = headers.get("name") or headers.get("company") or headers.get("company_name")
    website_col = headers.get("website") or headers.get("domain") or headers.get("url")
    category_col = headers.get("category")
    contact_name_col = (
        headers.get("contact_name") or headers.get("contact name") or headers.get("contact")
    )
    contact_role_col = headers.get("contact_role") or headers.get("role")
    contact_email_col = headers.get("contact_email") or headers.get("email")

    if not name_col or not website_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="CSV must contain 'name' and 'website' (or 'domain') columns.",
        )

    reports: list[CSVImportRowReport] = []
    seen_domains_in_batch: set[str] = set()
    created_count = 0
    skipped_count = 0
    imported_names: list[str] = []

    existing_companies = {c.name for c in db.scalars(select(Company)).all()}

    row_index = 0
    for row in reader:
        row_index += 1
        raw_name = (row.get(name_col) or "").strip()
        raw_website = (row.get(website_col) or "").strip()
        category = (row.get(category_col) or "").strip() if category_col else None
        c_name = (row.get(contact_name_col) or "").strip() if contact_name_col else None
        c_role = (row.get(contact_role_col) or "").strip() if contact_role_col else None
        c_email = (row.get(contact_email_col) or "").strip() if contact_email_col else None

        if not raw_name or not raw_website:
            skipped_count += 1
            reports.append(
                CSVImportRowReport(
                    row=row_index,
                    name=raw_name or "Unknown",
                    domain="",
                    status="skipped",
                    reason="Missing company name or website.",
                )
            )
            continue

        domain = normalize_domain(raw_website)
        if not domain:
            skipped_count += 1
            reports.append(
                CSVImportRowReport(
                    row=row_index,
                    name=raw_name,
                    domain="",
                    status="skipped",
                    reason="Invalid domain format.",
                )
            )
            continue

        if domain in seen_domains_in_batch:
            skipped_count += 1
            reports.append(
                CSVImportRowReport(
                    row=row_index,
                    name=raw_name,
                    domain=domain,
                    status="skipped",
                    reason="Duplicate domain in import batch.",
                )
            )
            continue
        seen_domains_in_batch.add(domain)

        company = db.scalar(select(Company).where(Company.domain == domain))
        if not company:
            company = Company(
                name=raw_name,
                domain=domain,
                website=raw_website,
                category=category or None,
            )
            db.add(company)
            db.commit()
            db.refresh(company)

        existing_target = db.scalar(
            select(Target).where(
                Target.campaign_id == campaign.id,
                Target.company_id == company.id,
            )
        )
        if existing_target:
            skipped_count += 1
            reports.append(
                CSVImportRowReport(
                    row=row_index,
                    name=raw_name,
                    domain=domain,
                    status="skipped",
                    reason="Company already exists in this campaign.",
                )
            )
            continue

        if c_email or c_name:
            contact = Contact(
                company_id=company.id,
                name=c_name or None,
                role=c_role or None,
                email=c_email.lower() if c_email else None,
                source="csv",
            )
            db.add(contact)

        target = Target(
            campaign_id=campaign.id,
            company_id=company.id,
            status="not_contacted",
        )
        db.add(target)
        db.commit()

        imported_names.append(raw_name)
        created_count += 1
        reports.append(
            CSVImportRowReport(
                row=row_index,
                name=raw_name,
                domain=domain,
                status="created",
            )
        )

    near_matches: list[str] = []
    for name in imported_names:
        matches = find_near_matches(name, list(existing_companies))
        for m in matches:
            msg = f"Imported '{name}' is similar to existing company '{m}'"
            if msg not in near_matches:
                near_matches.append(msg)

    log_audit(
        db,
        user.id,
        "import_targets",
        "targets",
        str(campaign.id),
        f"Imported {created_count} targets, skipped {skipped_count}",
    )

    return CSVImportResponse(
        total=row_index,
        created=created_count,
        skipped=skipped_count,
        rows=reports,
        near_matches=near_matches,
    )


def format_target_detail_response(db: Session, target: Target) -> TargetDetailResponse:
    base_resp = format_target_response(db, target)
    facts = list(
        db.scalars(
            select(CompanyFact)
            .where(CompanyFact.company_id == target.company_id)
            .order_by(CompanyFact.id.asc())
        ).all()
    )

    draft = db.scalar(
        select(Message)
        .where(
            Message.target_id == target.id,
            Message.direction == "out",
            Message.status.in_(["draft", "approved"]),
        )
        .order_by(Message.id.desc())
    )
    draft_resp = (
        MessageResponse(
            id=draft.id,
            target_id=draft.target_id,
            contact_id=draft.contact_id,
            direction=draft.direction,
            kind=draft.kind,
            subject=draft.subject,
            body=draft.body,
            status=draft.status,
            facts_used=draft.facts_used if isinstance(draft.facts_used, list) else None,
            approved_by=draft.approved_by,
            approved_at=draft.approved_at,
            approved_hash=draft.approved_hash,
            created_at=draft.created_at,
        )
        if draft
        else None
    )

    messages = list(
        db.scalars(
            select(Message).where(Message.target_id == target.id).order_by(Message.created_at.asc())
        ).all()
    )
    thread_resp = [
        MessageResponse(
            id=m.id,
            target_id=m.target_id,
            contact_id=m.contact_id,
            direction=m.direction,
            kind=m.kind,
            subject=m.subject,
            body=m.body,
            status=m.status,
            facts_used=m.facts_used if isinstance(m.facts_used, list) else None,
            approved_by=m.approved_by,
            approved_at=m.approved_at,
            approved_hash=m.approved_hash,
            created_at=m.created_at,
        )
        for m in messages
    ]

    outcomes_list = list(
        db.scalars(
            select(Outcome)
            .where(Outcome.target_id == target.id)
            .order_by(Outcome.confirmed_at.asc())
        ).all()
    )

    return TargetDetailResponse(
        **base_resp.model_dump(),
        campaign_name=target.campaign.name if target.campaign else None,
        ask_summary=target.ask_summary,
        ask_reasoning=target.ask_reasoning,
        ask_basis=target.ask_basis,
        ask_fact_ids=target.ask_fact_ids if isinstance(target.ask_fact_ids, list) else None,
        researched_at=target.researched_at,
        facts=[CompanyFactResponse.model_validate(f) for f in facts],
        draft=draft_resp,
        thread=thread_resp,
        outcomes=[OutcomeResponse.model_validate(o) for o in outcomes_list],
    )


def verify_target_ownership(target: Target, user: User) -> None:
    # SEC-09: Re-load object server-side and check role and ownership
    if user.role != "admin" and target.owner_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this target.",
        )


@router.get("/{target_id}", response_model=TargetDetailResponse)
def get_target(
    target_id: int,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetDetailResponse:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    return format_target_detail_response(db, target)


@router.post(
    "/{target_id}/prepare",
    response_model=TargetDetailResponse,
    dependencies=[Depends(verify_csrf)],
)
def prepare_target(
    target_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetDetailResponse:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    verify_target_ownership(target, user)

    try:
        # Run Graph A (load -> research -> recommend -> find_contact -> draft -> await_approval)
        graph = build_graph_a()
        config = {"configurable": {"thread_id": f"target_{target.id}"}}
        graph.invoke({"target_id": target.id, "user_id": user.id}, config=config)
    except BudgetExhausted as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    log_audit(
        db,
        user.id,
        "prepare_target",
        "targets",
        str(target.id),
        f"Prepared target {target.company.name}",
    )
    return format_target_detail_response(db, target)


@router.post(
    "/{target_id}/refresh-research",
    response_model=TargetDetailResponse,
    dependencies=[Depends(verify_csrf)],
)
def refresh_target_research(
    target_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetDetailResponse:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    verify_target_ownership(target, user)

    try:
        run_research(db, target, force_refresh=True)
    except BudgetExhausted as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    log_audit(
        db,
        user.id,
        "refresh_research",
        "targets",
        str(target.id),
        f"Refreshed research for target {target.company.name}",
    )
    return format_target_detail_response(db, target)


@router.post(
    "/{target_id}/claim",
    response_model=ClaimResponse,
    dependencies=[Depends(verify_csrf)],
)
def claim_target(
    target_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClaimResponse:
    # SEC-37 & PRD R9: Atomic ownership claim using SELECT FOR UPDATE
    target = db.scalar(select(Target).where(Target.id == target_id).with_for_update())
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    if target.owner_id is not None:
        if target.owner_id == user.id:
            return ClaimResponse(
                target_id=target.id,
                owner_id=user.id,
                owner_name=user.name,
                message="You already own this company.",
            )
        owner_name = target.owner.name if target.owner else "Another organizer"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{owner_name} owns this company. Ask an admin if it needs to move.",
        )

    target.owner_id = user.id
    db.commit()
    db.refresh(target)

    log_audit(
        db,
        user.id,
        "claim_target",
        "targets",
        str(target.id),
        f"Claimed target {target.company.name}",
    )
    return ClaimResponse(
        target_id=target.id,
        owner_id=user.id,
        owner_name=user.name,
        message="Target claimed successfully.",
    )


@router.post(
    "/{target_id}/unlock",
    response_model=TargetResponse,
    dependencies=[Depends(verify_csrf)],
)
def unlock_cooldown(
    target_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TargetResponse:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    target.cooldown_unlocked = True
    db.commit()
    db.refresh(target)

    log_audit(
        db,
        admin.id,
        "unlock_cooldown",
        "targets",
        str(target.id),
        f"Admin unlocked cooldown for {target.company.name}",
    )
    return format_target_response(db, target)


@router.post(
    "/{target_id}/reassign",
    response_model=TargetResponse,
    dependencies=[Depends(verify_csrf)],
)
def reassign_target(
    target_id: int,
    req: TargetReassignRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> TargetResponse:
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    new_owner = db.get(User, req.new_owner_id)
    if not new_owner or not new_owner.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target new owner does not exist or is inactive.",
        )

    old_owner_id = target.owner_id
    target.owner_id = new_owner.id
    db.commit()
    db.refresh(target)

    log_audit(
        db,
        admin.id,
        "reassign_target",
        "targets",
        str(target.id),
        f"Reassigned target from user {old_owner_id} to user {new_owner.id}",
    )
    return format_target_response(db, target)


@router.post(
    "/{target_id}/status",
    response_model=TargetResponse,
    dependencies=[Depends(verify_csrf)],
)
def update_target_status(
    target_id: int,
    req: TargetStatusUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TargetResponse:
    """Organizer updates target status (e.g. meeting_booked, secured, etc.) (PRD R7, R8)."""
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    verify_target_ownership(target, user)

    old_status = target.status
    target.status = req.status

    if req.status in ("closed_no_reply", "declined", "secured"):
        target.next_followup_at = None

    log_audit(
        db,
        user.id,
        "update_target_status",
        "targets",
        str(target.id),
        f"Changed status of target {target.id} from '{old_status}' to '{req.status}'",
    )
    db.commit()
    db.refresh(target)
    return format_target_response(db, target)


@router.post(
    "/{target_id}/outcome",
    response_model=OutcomeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_csrf)],
)
def record_outcome(
    target_id: int,
    req: OutcomeCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OutcomeResponse:
    """Record secured sponsorship outcome and mark target secured (PRD R8, G10)."""
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    verify_target_ownership(target, user)

    outcome = Outcome(
        target_id=target.id,
        kind=req.kind,
        amount_inr=req.amount_inr,
        description=req.description.strip() if req.description else None,
        confirmed_by=user.id,
        confirmed_at=utc_now(),
    )
    db.add(outcome)

    target.status = "secured"
    target.next_followup_at = None

    log_audit(
        db,
        user.id,
        "record_outcome",
        "outcomes",
        str(target.id),
        f"Recorded outcome ({req.kind}, amount={req.amount_inr}) for target {target.id}",
    )
    db.commit()
    db.refresh(outcome)
    return OutcomeResponse.model_validate(outcome)


@router.post(
    "/{target_id}/find-contact",
    response_model=FindContactResponse,
    dependencies=[Depends(verify_csrf)],
)
def find_contact(
    target_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FindContactResponse:
    """Find contact via Hunter.io on manual click (PRD G1, BUD-07)."""
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    verify_target_ownership(target, user)

    company = db.get(Company, target.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    try:
        result = search_hunter_domain(company.domain, db)
    except BudgetExhausted as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Hunter credit budget exhausted: {exc}",
        )
    except HunterError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if not result:
        return FindContactResponse(
            found=False,
            contact=None,
            message=f"No contact found for domain {company.domain}.",
        )

    # Check if contact already exists
    existing = db.scalar(
        select(Contact).where(
            Contact.company_id == company.id,
            Contact.email == result["email"],
        )
    )
    if existing:
        return FindContactResponse(
            found=True,
            contact=ContactResponse.model_validate(existing),
            message="Contact already on file.",
        )

    contact = Contact(
        company_id=company.id,
        name=result["name"],
        role=result["role"],
        email=result["email"],
        source="hunter",
        is_valid=True,
    )
    db.add(contact)
    db.flush()

    log_audit(
        db,
        user.id,
        "find_contact",
        "contacts",
        str(contact.id),
        f"Discovered contact {contact.email} for company {company.domain} via Hunter",
    )
    db.commit()
    db.refresh(contact)

    return FindContactResponse(
        found=True,
        contact=ContactResponse.model_validate(contact),
        message="Contact discovered via Hunter.",
    )


@router.put(
    "/{target_id}/contact",
    response_model=ContactResponse,
    dependencies=[Depends(verify_csrf)],
)
def update_contact(
    target_id: int,
    req: ContactUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ContactResponse:
    """Add or edit contact for target's company (PRD R1)."""
    target = db.get(Target, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found.")

    verify_target_ownership(target, user)

    company = db.get(Company, target.company_id)
    if not company:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found.")

    email_clean = req.email.strip().lower()
    if not email_clean or "@" not in email_clean:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Valid email address is required.",
        )

    # Look for existing contact for this company
    contact = db.scalar(
        select(Contact).where(Contact.company_id == company.id).order_by(Contact.id.desc())
    )

    if contact:
        contact.name = req.name.strip() if req.name else None
        contact.role = req.role.strip() if req.role else None
        contact.email = email_clean
        contact.source = "manual"
        contact.is_valid = True
    else:
        contact = Contact(
            company_id=company.id,
            name=req.name.strip() if req.name else None,
            role=req.role.strip() if req.role else None,
            email=email_clean,
            source="manual",
            is_valid=True,
        )
        db.add(contact)

    db.flush()
    log_audit(
        db,
        user.id,
        "update_contact",
        "contacts",
        str(contact.id),
        f"Updated contact {contact.email} for company {company.id}",
    )
    db.commit()
    db.refresh(contact)

    return ContactResponse.model_validate(contact)

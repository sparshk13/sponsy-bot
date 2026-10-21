"""Pydantic validation schemas for auth, users, audit, campaigns, and targets."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str
    role: str
    is_active: bool
    totp_enabled: bool = False
    created_at: datetime


class SessionResponse(BaseModel):
    user: UserResponse
    csrf_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., max_length=128)
    new_password: str = Field(..., min_length=12, max_length=128)


class CreateUserRequest(BaseModel):
    email: str = Field(..., max_length=255)
    name: str = Field(..., max_length=255)
    role: str = Field("organizer", pattern="^(admin|organizer)$")
    password: str = Field(..., min_length=12, max_length=128)


class UpdateUserRequest(BaseModel):
    is_active: bool | None = None
    password: str | None = Field(None, min_length=12, max_length=128)


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    at: datetime
    user_id: int | None
    action: str
    entity: str
    entity_id: str | None
    detail: str | None


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    event_summary: str = Field(..., min_length=1)
    event_date: date | None = None
    audience_note: str | None = None
    cash_target_inr: int | None = Field(None, ge=0)
    goodies_note: str | None = None
    credits_note: str | None = None
    calendar_link: str | None = None


class CampaignUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    event_summary: str | None = None
    event_date: date | None = None
    audience_note: str | None = None
    cash_target_inr: int | None = Field(None, ge=0)
    goodies_note: str | None = None
    credits_note: str | None = None
    calendar_link: str | None = None


class CampaignResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    event_summary: str
    event_date: date | None
    audience_note: str | None
    cash_target_inr: int | None
    goodies_note: str | None
    credits_note: str | None
    calendar_link: str | None
    created_by: int
    created_at: datetime


class ContactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str | None
    role: str | None
    email: str | None
    source: str
    is_valid: bool


class TargetCreateRequest(BaseModel):
    campaign_id: int
    name: str = Field(..., min_length=1, max_length=255)
    website: str = Field(..., min_length=1, max_length=512)
    category: str | None = Field(None, max_length=128)
    contact_name: str | None = Field(None, max_length=255)
    contact_role: str | None = Field(None, max_length=255)
    contact_email: str | None = Field(None, max_length=255)


class TargetResponse(BaseModel):
    id: int
    campaign_id: int
    company_id: int
    company_name: str
    domain: str
    category: str | None
    website: str | None
    owner_id: int | None
    owner_name: str | None
    status: str
    tier: str | None
    priority: str | None
    priority_score: int
    contact: ContactResponse | None
    followup_count: int
    last_contacted_at: datetime | None
    next_followup_at: datetime | None
    cooldown_active: bool
    cooldown_unlocked: bool
    created_at: datetime


class CompanyFactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    kind: str
    claim: str
    source_url: str
    evidence_quote: str
    status: str
    retrieved_at: datetime


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    contact_id: int | None
    direction: str
    kind: str
    subject: str | None
    body: str | None
    status: str
    facts_used: list[int] | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    approved_hash: str | None = None
    attachment_id: int | None = None
    created_at: datetime


class TargetStatusUpdateRequest(BaseModel):
    status: str = Field(
        ...,
        pattern="^(not_contacted|contacted|follow_up|interested|meeting_booked|secured|declined|closed_no_reply)$",
    )


class OutcomeCreateRequest(BaseModel):
    kind: str = Field(..., pattern="^(cash|goodies|credits)$")
    amount_inr: int | None = Field(None, ge=0)
    description: str | None = Field(None, max_length=2000)


class OutcomeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    target_id: int
    kind: str
    amount_inr: int | None
    description: str | None
    confirmed_by: int | None
    confirmed_at: datetime


class TargetDetailResponse(TargetResponse):
    campaign_name: str | None = None
    ask_summary: str | None
    ask_reasoning: str | None
    ask_basis: str | None
    ask_fact_ids: list[int] | None = None
    researched_at: datetime | None = None
    facts: list[CompanyFactResponse] = []
    draft: MessageResponse | None = None
    thread: list[MessageResponse] = []
    outcomes: list[OutcomeResponse] = []


class UsageItemResponse(BaseModel):
    provider: str
    used: int
    cap: int
    period: str
    percent: int
    is_exhausted: bool
    is_warning: bool


class CSVImportRowReport(BaseModel):
    row: int
    name: str
    domain: str
    status: str
    reason: str | None = None


class CSVImportResponse(BaseModel):
    total: int
    created: int
    skipped: int
    rows: list[CSVImportRowReport]
    near_matches: list[str]


class ClaimResponse(BaseModel):
    target_id: int
    owner_id: int
    owner_name: str
    message: str


class PauseRequest(BaseModel):
    paused: bool


class PauseResponse(BaseModel):
    paused: bool


class ContactUpdateRequest(BaseModel):
    name: str | None = Field(None, max_length=255)
    role: str | None = Field(None, max_length=255)
    email: str = Field(..., min_length=3, max_length=255)


class FindContactResponse(BaseModel):
    found: bool
    contact: ContactResponse | None = None
    message: str | None = None


class TemplateCreate(BaseModel):
    kind: str = Field(..., pattern="^(first|followup|meeting)$")
    name: str = Field(..., min_length=1, max_length=255)
    body: str = Field(..., min_length=1)


class TemplateUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    body: str | None = Field(None, min_length=1)


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    name: str
    body: str
    created_at: datetime
    updated_at: datetime


class BrochureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tier: str
    filename: str
    uploaded_by: int
    created_at: datetime


class DashboardPipelineStage(BaseModel):
    stage: str
    label: str
    count: int


class DashboardOrganizerStat(BaseModel):
    user_id: int
    name: str
    assigned_count: int
    contacted_count: int
    secured_count: int
    secured_cash_inr: int


class DashboardNonCashOutcome(BaseModel):
    id: int
    company_name: str
    kind: str
    description: str | None
    confirmed_at: datetime


class DashboardResponse(BaseModel):
    total_targets: int
    pipeline: list[DashboardPipelineStage]
    contacted_count: int
    replied_count: int
    response_rate: float
    interested_count: int
    interest_rate: float
    declined_count: int
    secured_count: int
    total_cash_inr: int
    non_cash_outcomes: list[DashboardNonCashOutcome]
    organizers: list[DashboardOrganizerStat]


class MemoryEntryResponse(BaseModel):
    id: int
    company_name: str
    company_domain: str
    campaign_name: str
    kind: str
    amount_inr: int | None
    description: str | None
    confirmed_at: datetime
    ask_worked: str | None
    tier: str | None


class MemoryResponse(BaseModel):
    entries: list[MemoryEntryResponse]
    total_cash_inr: int
    total_sponsors: int


class LoginResponse(BaseModel):
    message: str = "Logged in"
    requires_2fa: bool | None = None
    pending_token: str | None = None


class LoginCodeRequest(BaseModel):
    pending_token: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=6, max_length=32)


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_url: str


class TwoFactorConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=16)


class TwoFactorConfirmResponse(BaseModel):
    recovery_codes: list[str]


class SystemStatusResponse(BaseModel):
    last_mail_check: datetime | None = None
    last_send: datetime | None = None
    last_backup: str | None = None
    db_size_bytes: int = 0
    disk_free_bytes: int = 0


class TargetReassignRequest(BaseModel):
    new_owner_id: int


class SuppressionCreateRequest(BaseModel):
    kind: str = Field(..., pattern="^(email|domain)$")
    value: str = Field(..., min_length=1, max_length=255)
    reason: str | None = None


class SuppressionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    value: str
    reason: str | None
    created_at: datetime

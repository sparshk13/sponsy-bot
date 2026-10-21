"""FastAPI application initialization and core router wiring."""

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models import Message, Target, User, utc_now
from app.routes import (
    admin,
    auth,
    brochures,
    campaigns,
    dashboard,
    export,
    inbox,
    messages,
    targets,
    usage,
)
from app.security import SecurityHeadersMiddleware

is_dev = settings.app_env == "dev"

app = FastAPI(
    title="Sponsy Bot API",
    docs_url="/docs" if is_dev else None,
    redoc_url="/redoc" if is_dev else None,
    openapi_url="/openapi.json" if is_dev else None,
)

app.add_middleware(SecurityHeadersMiddleware)

# Wire API routes
app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(campaigns.router)
app.include_router(targets.router)
app.include_router(messages.router)
app.include_router(messages.queue_router)
app.include_router(inbox.router)
app.include_router(usage.router)
app.include_router(brochures.router)
app.include_router(dashboard.router)
app.include_router(export.router)


@app.get("/api/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/today")
def get_today(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    pending_stmt = select(func.count(Message.id)).where(
        Message.direction == "out",
        Message.status.in_(["draft", "approved"]),
    )
    if user.role != "admin":
        pending_stmt = pending_stmt.join(Target, Message.target_id == Target.id).where(
            Target.owner_id == user.id
        )
    pending_approvals = db.scalar(pending_stmt) or 0

    unread_stmt = select(func.count(Message.id)).where(
        Message.direction == "in",
        Message.classified_by_human.is_(False),
        Message.classification != "bounce",
    )
    if user.role != "admin":
        unread_stmt = unread_stmt.join(Target, Message.target_id == Target.id).where(
            Target.owner_id == user.id
        )
    unread_replies = db.scalar(unread_stmt) or 0

    due_stmt = select(func.count(Target.id)).where(
        Target.status == "contacted",
        Target.next_followup_at.isnot(None),
        Target.next_followup_at <= utc_now(),
    )
    if user.role != "admin":
        due_stmt = due_stmt.where(Target.owner_id == user.id)
    due_followups = db.scalar(due_stmt) or 0

    tz = ZoneInfo(settings.timezone)
    local_now = datetime.now(timezone.utc).astimezone(tz)
    local_midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    utc_midnight = local_midnight.astimezone(timezone.utc)

    sent_today = (
        db.scalar(
            select(func.count(Message.id)).where(
                Message.direction == "out",
                Message.status == "sent",
                Message.sent_at >= utc_midnight,
            )
        )
        or 0
    )

    return {
        "pending_approvals": pending_approvals,
        "unread_replies": unread_replies,
        "due_followups": due_followups,
        "sent_today": sent_today,
        "daily_cap": settings.daily_send_cap,
    }


dist_path = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if not dist_path.is_dir():
    dist_path = Path("/app/frontend/dist")

if dist_path.is_dir():
    assets_path = dist_path / "assets"
    if assets_path.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

    fonts_path = dist_path / "fonts"
    if fonts_path.is_dir():
        app.mount("/fonts", StaticFiles(directory=str(fonts_path)), name="fonts")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        file_target = dist_path / full_path
        if full_path and file_target.is_file():
            return FileResponse(file_target)
        return FileResponse(dist_path / "index.html")

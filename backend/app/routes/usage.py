"""Free-tier usage overview route (PRD R10, BUD-09)."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.budget import get_usage_overview
from app.db import get_db
from app.models import User
from app.schemas import UsageItemResponse

router = APIRouter(prefix="/api/usage", tags=["usage"])


@router.get("", response_model=list[UsageItemResponse])
def get_usage(
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    return get_usage_overview(db)

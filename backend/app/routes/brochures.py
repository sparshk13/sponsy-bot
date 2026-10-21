"""Authenticated brochure download route (SEC-17)."""

import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models import Brochure, User

router = APIRouter(prefix="/api/brochures", tags=["brochures"])


@router.get("/{brochure_id}")
def download_brochure(
    brochure_id: int,
    _user: User = Depends(get_current_user),  # SEC-08 & SEC-17: authenticated user only
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download a brochure PDF as an attachment with strict authentication."""
    brochure = db.get(Brochure, brochure_id)
    if not brochure:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brochure not found.",
        )

    filepath = os.path.join(settings.brochures_upload_dir, brochure.stored_name)
    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Brochure file missing on disk.",
        )

    # SEC-17: served with Content-Disposition: attachment
    return FileResponse(
        path=filepath,
        media_type="application/pdf",
        filename=brochure.filename,
        headers={"Content-Disposition": f'attachment; filename="{brochure.filename}"'},
    )

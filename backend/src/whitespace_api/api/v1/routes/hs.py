"""Find a product's HS code from a description or a photo."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession, get_current_user
from whitespace_api.schemas.hs import HsFinderOut
from whitespace_api.services import hs_finder as service
from whitespace_api.services.pipeline import LimitError

router = APIRouter(dependencies=[Depends(get_current_user)], tags=["markets"])


@router.post("/products/identify", response_model=HsFinderOut)
async def identify(
    db: DbSession,
    user: CurrentUser,
    settings: AppSettings,
    description: Annotated[str | None, Form(max_length=600)] = None,
    photo: Annotated[UploadFile | None, File(description="JPEG, PNG or WebP, up to 4 MB")] = None,
) -> HsFinderOut:
    """Up to three likely codes, each with how sure and why, plus questions that would
    decide between them. The photo isn't stored."""
    data = await photo.read(service.MAX_IMAGE_BYTES + 1) if photo is not None else None
    try:
        return await service.find(db, user, settings, description=description, photo=data)
    except service.FinderError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except LimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc

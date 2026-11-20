"""Check a buyer's purchase order or letter of credit against your quote."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession, get_current_user
from whitespace_api.schemas.documents import DocCheckOut
from whitespace_api.services import doc_check as service
from whitespace_api.services.pipeline import LimitError, NotFoundError

router = APIRouter(
    prefix="/documents", dependencies=[Depends(get_current_user)], tags=["documents"]
)


@router.post("/check", response_model=DocCheckOut)
async def check(
    db: DbSession,
    user: CurrentUser,
    settings: AppSettings,
    file: Annotated[UploadFile | None, File(description="The PO or credit, as a PDF")] = None,
    text: Annotated[str | None, Form(max_length=service.MAX_CHARS)] = None,
    quote_id: Annotated[uuid.UUID | None, Form()] = None,
) -> DocCheckOut:
    """Read the document (SWIFT MT700 text is read in code; anything else by a model that
    must quote it), then flag risky clauses, tight dates, sanctioned parties and every
    difference from your quote. The document isn't stored."""
    pdf = None
    if file is not None:
        pdf = await file.read(service.MAX_BYTES + 1)
    try:
        return await service.check(db, user, settings, pdf=pdf, text=text, quote_id=quote_id)
    except service.DocumentError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except NotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except LimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc

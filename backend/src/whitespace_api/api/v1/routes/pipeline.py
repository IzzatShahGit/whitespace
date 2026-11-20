"""The outreach pipeline: companies you're contacting, by stage, with follow-ups."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession, get_current_user
from whitespace_api.schemas.outreach import (
    DraftIn,
    DraftOut,
    MessageSaved,
    ReplyIn,
    SentIn,
    ThreadOut,
)
from whitespace_api.schemas.pipeline import (
    ContactAdded,
    ContactIn,
    ContactOut,
    ContactPatch,
    EventOut,
    PipelineSummary,
)
from whitespace_api.services import outreach
from whitespace_api.services import pipeline as service

router = APIRouter(prefix="/pipeline", dependencies=[Depends(get_current_user)], tags=["pipeline"])


def _http(exc: Exception) -> HTTPException:
    code = {
        service.NotFoundError: status.HTTP_404_NOT_FOUND,
        service.ConflictError: status.HTTP_409_CONFLICT,
        service.LimitError: status.HTTP_429_TOO_MANY_REQUESTS,
    }[type(exc)]
    return HTTPException(code, str(exc))


ERRORS = (service.NotFoundError, service.ConflictError, service.LimitError)


@router.get("", response_model=list[ContactOut])
async def list_contacts(db: DbSession, user: CurrentUser) -> list[ContactOut]:
    return await service.list_contacts(db, user)


@router.get("/summary", response_model=PipelineSummary)
async def summary(db: DbSession, user: CurrentUser) -> PipelineSummary:
    """Counts by stage and the follow-ups due, for the dashboard."""
    return await service.summary(db, user)


@router.post("", response_model=ContactAdded)
async def add(
    body: ContactIn, response: Response, db: DbSession, user: CurrentUser, settings: AppSettings
) -> ContactAdded:
    """Save a company (idempotent: saving it again returns the existing one)."""
    try:
        added = await service.add(db, user, body, settings)
    except ERRORS as exc:
        raise _http(exc) from exc
    response.status_code = status.HTTP_201_CREATED if added.created else status.HTTP_200_OK
    return added


@router.patch("/{contact_id}", response_model=ContactOut)
async def update(
    contact_id: uuid.UUID, body: ContactPatch, db: DbSession, user: CurrentUser
) -> ContactOut:
    """Move stage, edit the note or the follow-up date. Send the version you last saw."""
    try:
        return await service.update(db, user, contact_id, body)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove(contact_id: uuid.UUID, db: DbSession, user: CurrentUser) -> None:
    try:
        await service.remove(db, user, contact_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.get("/{contact_id}/events", response_model=list[EventOut])
async def events(contact_id: uuid.UUID, db: DbSession, user: CurrentUser) -> list[EventOut]:
    try:
        return await service.events(db, user, contact_id)
    except ERRORS as exc:
        raise _http(exc) from exc


# --- the email conversation with a contact ------------------------------------------


@router.get("/{contact_id}/messages", response_model=ThreadOut)
async def thread(contact_id: uuid.UUID, db: DbSession, user: CurrentUser) -> ThreadOut:
    """Emails sent and replies received, oldest first, with the languages to write in."""
    try:
        return await outreach.thread(db, user, contact_id)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/{contact_id}/draft", response_model=DraftOut)
async def draft(
    contact_id: uuid.UUID, body: DraftIn, db: DbSession, user: CurrentUser, settings: AppSettings
) -> DraftOut:
    """Draft the next email (first, follow-up or reply) from your quote and the thread.
    Nothing is saved: edit it, send it yourself, then log it."""
    try:
        return await outreach.draft(db, user, contact_id, body, settings)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/{contact_id}/messages", response_model=MessageSaved, status_code=201)
async def log_sent(
    contact_id: uuid.UUID, body: SentIn, db: DbSession, user: CurrentUser
) -> MessageSaved:
    """Log an email you sent: "To contact" moves to "Emailed", follow-up in five days."""
    try:
        return await outreach.log_sent(db, user, contact_id, body)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.post("/{contact_id}/replies", response_model=MessageSaved, status_code=201)
async def read_reply(
    contact_id: uuid.UUID, body: ReplyIn, db: DbSession, user: CurrentUser, settings: AppSettings
) -> MessageSaved:
    """Paste their reply: it's saved with what they ask for (each in their own words),
    warning signs, and the stage it suggests."""
    try:
        return await outreach.read_reply(db, user, contact_id, body, settings)
    except ERRORS as exc:
        raise _http(exc) from exc


@router.delete("/{contact_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_message(
    contact_id: uuid.UUID, message_id: uuid.UUID, db: DbSession, user: CurrentUser
) -> None:
    try:
        await outreach.remove_message(db, user, contact_id, message_id)
    except ERRORS as exc:
        raise _http(exc) from exc

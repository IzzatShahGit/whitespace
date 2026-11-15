"""The Whitespace guide: ask questions in plain words; replies stream as server-sent events."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.responses import StreamingResponse

from whitespace_api.api.deps import AppSettings, CurrentUser, DbSession
from whitespace_api.schemas.chat import (
    ChatEvent,
    ChatMessageIn,
    ChatSuggestions,
    ChatThreadDetail,
    ChatThreadOut,
)
from whitespace_api.services import chat as chat_service

router = APIRouter(prefix="/chat", tags=["chat"])

# no-transform: proxies and compressors must pass events through as they come.
STREAM_HEADERS = {"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"}


@router.get("/threads", response_model=list[ChatThreadOut])
async def list_threads(db: DbSession, user: CurrentUser) -> list[ChatThreadOut]:
    return await chat_service.list_threads(db, user)


@router.get("/threads/{thread_id}", response_model=ChatThreadDetail)
async def get_thread(thread_id: uuid.UUID, db: DbSession, user: CurrentUser) -> ChatThreadDetail:
    try:
        return await chat_service.get_thread(db, user, thread_id)
    except chat_service.ChatNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(thread_id: uuid.UUID, db: DbSession, user: CurrentUser) -> Response:
    try:
        await chat_service.delete_thread(db, user, thread_id)
    except chat_service.ChatNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/suggestions", response_model=ChatSuggestions)
async def suggestions(db: DbSession, user: CurrentUser, settings: AppSettings) -> ChatSuggestions:
    return await chat_service.suggestions(db, user, settings)


@router.post(
    "/messages",
    response_class=StreamingResponse,
    responses={
        200: {
            "model": ChatEvent,  # registers the event schema for clients
            "description": "Server-sent events: each `data:` line is one ChatEvent as JSON",
            "content": {"text/event-stream": {}},
        },
        404: {"description": "Conversation not found"},
        409: {"description": "A reply in this conversation is still being written"},
        429: {"description": "Daily message limit reached"},
    },
)
async def send_message(
    body: ChatMessageIn, db: DbSession, user: CurrentUser, settings: AppSettings
) -> StreamingResponse:
    """Ask the guide. Starts a new conversation when `thread_id` is omitted."""
    try:
        turn = await chat_service.start_turn(db, user, body, settings)
    except chat_service.ChatNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
    except chat_service.ChatBusyError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except chat_service.ChatLimitError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, str(exc)) from exc
    return StreamingResponse(turn.events, media_type="text/event-stream", headers=STREAM_HEADERS)

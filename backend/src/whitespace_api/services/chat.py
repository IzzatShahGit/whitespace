"""The Whitespace guide: conversations and replies.

A reply runs as a background task that streams progress to the request through a
queue. If the browser disconnects, the task still finishes and saves the reply, so it
is there when the user comes back. Claiming the turn (one pending reply per thread)
and charging the daily quota happen in one transaction: both succeed or neither does.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from whitespace_api.agents import llm
from whitespace_api.agents.chat.graph import ChatDeps, build_graph
from whitespace_api.agents.chat.prompts import SYSTEM, profile_note
from whitespace_api.agents.chat.tools import ChatContext
from whitespace_api.core import tasks
from whitespace_api.core.config import Settings
from whitespace_api.core.http import http_client
from whitespace_api.models.chat import ChatMessage, ChatThread
from whitespace_api.models.user import User
from whitespace_api.repositories import chat as repo
from whitespace_api.repositories import profiles as profile_repo
from whitespace_api.repositories import trade as trade_repo
from whitespace_api.repositories import usage as usage_repo
from whitespace_api.schemas.chat import (
    ChatMessageIn,
    ChatMessageOut,
    ChatSuggestions,
    ChatThreadDetail,
    ChatThreadOut,
)
from whitespace_api.schemas.trade import CountryOut, ProductOut
from whitespace_api.services import trade as trade_service

log = logging.getLogger(__name__)

USAGE_KIND = "chat"
REPLY_TIMEOUT_SECONDS = 75
HEARTBEAT_SECONDS = 15  # keeps proxies from closing a quiet stream
HISTORY_MESSAGES = 8
HISTORY_CHARS = 1200  # per message: old replies are context, not the main event
TITLE_CHARS = 60
THREADS_LISTED = 30
FOLLOW_UPS = 3

_DONE = object()


class ChatNotFoundError(Exception):
    """No such thread for this user. Safe to show."""


class ChatBusyError(Exception):
    """A reply in this thread is still being written. Safe to show."""


class ChatLimitError(Exception):
    """The user reached today's message limit. Safe to show."""


@dataclass(frozen=True)
class Turn:
    thread_id: uuid.UUID
    message_id: uuid.UUID
    events: AsyncIterator[str]


def _today() -> date:
    return datetime.now(UTC).date()


def _message_out(m: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut.model_validate(
        {
            "id": m.id,
            "role": m.role,
            "status": m.status,
            "content": m.content,
            "cards": m.cards,
            "follow_ups": m.follow_ups,
            "grounded": m.grounded,
            "created_at": m.created_at,
        }
    )


def _thread_out(t: ChatThread) -> ChatThreadOut:
    return ChatThreadOut(id=t.id, title=t.title, updated_at=t.updated_at)


# ---------- reading ----------
async def list_threads(db: AsyncSession, user: User) -> list[ChatThreadOut]:
    rows = await repo.list_threads(db, user_id=user.id, limit=THREADS_LISTED)
    return [_thread_out(t) for t in rows]


async def get_thread(db: AsyncSession, user: User, thread_id: uuid.UUID) -> ChatThreadDetail:
    thread = await repo.get_thread(db, user_id=user.id, thread_id=thread_id)
    if thread is None:
        raise ChatNotFoundError("Conversation not found")
    rows = await repo.messages(db, thread.id)
    return ChatThreadDetail(
        **_thread_out(thread).model_dump(), messages=[_message_out(m) for m in rows]
    )


async def delete_thread(db: AsyncSession, user: User, thread_id: uuid.UUID) -> None:
    if not await repo.delete_thread(db, user_id=user.id, thread_id=thread_id):
        raise ChatNotFoundError("Conversation not found")


async def _context(db: AsyncSession, user_id: uuid.UUID, settings: Settings) -> ChatContext:
    profile = await profile_repo.get_profile(db, user_id)
    exporter: CountryOut | None = None
    products: list[ProductOut] = []
    if profile is not None:
        exporter = await trade_service.get_exporter(db, profile.exporter)
        found = await trade_repo.products_by_code(db, profile.products)
        products = [
            ProductOut(hs6=code, description=found[code].description)
            for code in profile.products
            if code in found
        ]
    return ChatContext(
        db=db,
        http=http_client(),
        settings=settings,
        exporter=exporter,
        goal=profile.goal if profile else "sell",
        products=products,
        current_markets=frozenset(profile.current_markets) if profile else frozenset(),
    )


async def suggestions(db: AsyncSession, user: User, settings: Settings) -> ChatSuggestions:
    """Starter questions from the profile: no model call, so they cost nothing."""
    ctx = await _context(db, user.id, settings)
    used = await usage_repo.used(db, user_id=user.id, kind=USAGE_KIND, day=_today())
    remaining = max(0, settings.chat_daily_limit - used)
    if ctx.exporter is None or not ctx.products:
        starters = [
            "Where should I sell cotton towels from Pakistan?",
            "Where can I buy cotton yarn cheapest?",
            "Convert 18 lakh rupees to euros",
        ]
        return ChatSuggestions(prompts=starters, remaining_today=remaining)

    first = ctx.products[0]
    name = first.name
    prompts: list[str] = []
    if ctx.goal != "buy":
        prompts.append(f"Where should I sell my {name} next?")
        top = await trade_repo.top_markets_per_product(
            db, exporter=ctx.exporter.code, products=[first.hs6],
            exclude_markets=sorted(ctx.current_markets), per_product=1,
        )  # fmt: skip
        if top:
            market = top[0].market_name
            prompts.append(f"I have 18 lakh worth of {name}, 5 tons. Can I compete in {market}?")
            prompts.append(f"What's the latest news for {name} in {market}?")
    if ctx.goal != "sell":
        prompts.append(f"Where can I buy {name} at the best price?")
    if len(ctx.products) > 1:
        second = ctx.products[1]
        prompts.append(f"Compare my best markets for {second.name}")
    return ChatSuggestions(prompts=prompts[:4], remaining_today=remaining)


# ---------- replying ----------
async def start_turn(db: AsyncSession, user: User, body: ChatMessageIn, settings: Settings) -> Turn:
    """Claim the turn and charge the quota, then start the reply in the background."""
    if body.thread_id is not None:
        thread = await repo.get_thread(db, user_id=user.id, thread_id=body.thread_id)
        if thread is None:
            raise ChatNotFoundError("Conversation not found")
    else:
        thread = await repo.create_thread(db, user_id=user.id, title=_title(body.text))
    thread_id = thread.id
    await repo.expire_pending(
        db, thread_id=thread_id, older_than=timedelta(seconds=REPLY_TIMEOUT_SECONDS * 2)
    )
    try:
        _, reply = await repo.add_turn(db, thread_id=thread_id, text=body.text)
    except IntegrityError as exc:
        await db.rollback()
        raise ChatBusyError("Still answering your last question in this conversation") from exc
    count = await usage_repo.consume(
        db, user_id=user.id, kind=USAGE_KIND, day=_today(), limit=settings.chat_daily_limit
    )
    if count is None:
        await db.rollback()
        raise ChatLimitError(
            f"You've used today's {settings.chat_daily_limit} questions. "
            "The limit resets at midnight UTC."
        )
    await db.commit()

    queue: asyncio.Queue[Any] = asyncio.Queue()
    tasks.spawn(
        _reply(
            user_id=user.id, thread_id=thread_id,
            message_id=reply.id, text=body.text, settings=settings, queue=queue,
        )
    )  # fmt: skip
    return Turn(thread_id, reply.id, _events(queue, thread_id, reply.id))


def _title(text: str) -> str:
    line = " ".join(text.split())
    return line if len(line) <= TITLE_CHARS else line[: TITLE_CHARS - 1].rstrip() + "…"


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


async def _events(
    queue: asyncio.Queue[Any], thread_id: uuid.UUID, message_id: uuid.UUID
) -> AsyncIterator[str]:
    yield _sse({"event": "thread", "thread_id": thread_id, "message_id": message_id})
    while True:
        try:
            item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_SECONDS)
        except TimeoutError:
            yield ": ping\n\n"
            continue
        if item is _DONE:
            yield _sse({"event": "done", "message_id": message_id})
            return
        yield _sse(item)


def _history_messages(rows: list[ChatMessage]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for m in rows:
        text = m.content[:HISTORY_CHARS]
        if m.role == "user":
            out.append(HumanMessage(text))
        else:
            out.append(AIMessage(f"{text}\n[Context: {m.memo}]" if m.memo else text))
    return out


def follow_ups(cards: list[dict[str, Any]]) -> list[str]:
    """Next questions from what the reply showed. Built in code: free and always relevant."""
    out: list[str] = []
    for card in cards:
        kind = card["type"]
        if kind == "markets" and card["items"]:
            top = card["items"][0]["market"]["name"]
            out += [f"Tell me more about {top}", f"Can I compete on price in {top}?"]
            if len(card["items"]) > 1:
                out.append(f"How does {card['items'][1]['market']['name']} compare?")
        elif kind == "market":
            market = card["market"]["name"]
            out += [f"What changed recently in {market}?", f"Any news about {market}?"]
        elif kind == "sourcing":
            out += ["Which supplier is the most reliable?", "How much would 10 tons cost?"]
        elif kind == "price":
            out.append(f"What else could I sell in {card['market']['name']}?")
    return list(dict.fromkeys(out))[:FOLLOW_UPS]


async def _reply(
    *,
    user_id: uuid.UUID,
    thread_id: uuid.UUID,
    message_id: uuid.UUID,
    text: str,
    settings: Settings,
    queue: asyncio.Queue[Any],
) -> None:
    async with tasks.session_factory() as db:
        try:
            async with asyncio.timeout(REPLY_TIMEOUT_SECONDS):
                ctx = await _context(db, user_id, settings)
                rows = await repo.history(
                    db, thread_id=thread_id, before=message_id, limit=HISTORY_MESSAGES
                )
                note = profile_note(ctx, _today())
                state = {
                    "messages": [
                        SystemMessage(SYSTEM),
                        SystemMessage(note),
                        *_history_messages(rows),
                        HumanMessage(text),
                    ],
                    "known": [text, note, *(m.content for m in rows)],
                }
                deps = ChatDeps(chat=lambda spec: llm.get_chat_model(spec, settings=settings))
                final: dict[str, Any] = {}
                stream = build_graph(deps, ctx).astream(state, stream_mode=["custom", "values"])
                async for mode, chunk in stream:
                    if mode == "custom":
                        await queue.put(chunk)
                    else:
                        final = chunk
            cards = final.get("cards", [])
            answer = final.get("answer") or "I couldn't find an answer to that. Try rephrasing?"
            grounded = not final.get("unsupported")
            suggested = follow_ups(cards)
            usage = {
                "input": sum(u["input"] for u in final.get("usage", [])),
                "output": sum(u["output"] for u in final.get("usage", [])),
            }
            await repo.finish(
                db, message_id=message_id, status="done", content=answer, cards=cards,
                follow_ups=suggested, memo="; ".join(final.get("memo", [])) or None,
                grounded=grounded, usage=usage,
            )  # fmt: skip
            await queue.put(
                {"event": "answer", "text": answer, "follow_ups": suggested, "grounded": grounded}
            )
        except Exception as exc:
            await db.rollback()
            message = _failure(exc)
            if not isinstance(exc, (TimeoutError, llm.LLMConfigError)):
                log.exception("Guide reply %s failed", message_id)
            await repo.finish(db, message_id=message_id, status="failed", content=message)
            await queue.put({"event": "error", "text": message})
        finally:
            await queue.put(_DONE)


def _failure(exc: Exception) -> str:
    if isinstance(exc, TimeoutError):
        return "That took too long. Please try again, or ask something narrower."
    if isinstance(exc, llm.LLMConfigError):
        return "The guide isn't configured on this server yet."
    return "Something went wrong while answering. Please try again."

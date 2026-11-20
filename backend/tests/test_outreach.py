"""Emails with pipeline contacts: drafting from facts, logging, reading replies, red flags."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from tests.seed import TOWELS
from tests.test_quotes import BASE, lane, offline  # noqa: F401  (fixtures)
from whitespace_api.agents.llm import CallSpec
from whitespace_api.core.config import Settings, get_settings
from whitespace_api.main import app
from whitespace_api.services import outreach
from whitespace_api.services.red_flags import message_flags

RAW = AIMessage(content="", response_metadata={"model_name": "fake"})
REPLY = (
    "Dear Ahmed,\n\nThanks for your email. Could you send us 3 samples of the 500 gsm "
    "towels? Please also quote your best price for 2 containers, CIF Hamburg.\n"
    "We need your offer by 15 December.\n\nBest regards,\nKlaus Becker"
)


def today() -> str:
    return str(datetime.now(UTC).date())


# --- rules in code -------------------------------------------------------------------


def test_red_flags_quote_the_words_that_raised_them() -> None:
    flags = message_flags(
        "Kindly note our bank account has been changed. Pay the registration fee "
        "via Western Union within 24 hours."
    )
    codes = {f.code for f in flags}
    assert codes == {"bank_change", "advance_fee", "untraceable_payment", "pressure"}
    assert all(f.quote and f.label for f in flags)
    assert message_flags(REPLY) == []  # an ordinary buyer email raises nothing


def test_draft_checks_list_unsourced_figures_and_blanks() -> None:
    checks = outreach.draft_checks(
        "Our price is USD 5.20 per kg, 2 weeks lead time, MOQ 12,000 kg. [Lead time] [Lead time]",
        ["Price: USD 5.20 per kg"],
    )
    assert checks == [
        "Check 12000: it isn't in your quote, details or the conversation",
        "Fill in [Lead time]",
    ]


def test_quotes_must_be_in_the_reply() -> None:
    assert outreach.found_in("could you send us 3 SAMPLES", REPLY)
    assert outreach.found_in("“best price for 2 containers”", REPLY)
    assert not outreach.found_in("send 10 samples", REPLY)
    assert not outreach.found_in("a", REPLY)  # too short to prove anything


def test_stage_suggestions_only_move_forward() -> None:
    sample = outreach.Ask(kind="samples", detail="samples", quote="x")
    assert outreach.suggest_stage("replied", "interested", [sample]) == "samples"
    assert outreach.suggest_stage("negotiating", "interested", [sample]) is None
    assert outreach.suggest_stage("replied", "order", []) == "negotiating"
    assert outreach.suggest_stage("emailed", "not_interested", []) == "lost"
    assert outreach.suggest_stage("won", "not_interested", []) is None
    assert outreach.suggest_stage("emailed", "out_of_office", []) is None


# --- the conversation, end to end ----------------------------------------------------


@pytest.fixture
def model(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """A fake model: drafts cite one real and one invented figure; the reply reading
    includes one ask whose quote isn't in the email."""
    prompts: list[str] = []

    def fake(spec: CallSpec, settings: Any = None) -> Any:
        def run(messages: Any) -> Any:
            prompts.append(messages[-1][1])
            if spec.schema is outreach.EmailDraft:
                draft = outreach.EmailDraft(
                    subject="Towels for Holiday Heimtex",
                    body="Our price is USD 5.00 per kg FOB Karachi; MOQ 7,500 kg.\n\nAhmed",
                )
                return {"raw": RAW, "parsed": draft}
            read = outreach._Read(
                intent="interested",
                summary="They want samples and a CIF price for two containers.",
                language="en",
                asks=[
                    outreach._Ask(kind="samples", detail="3 samples", quote="send us 3 samples"),
                    outreach._Ask(
                        kind="price",
                        detail="CIF price, 2 containers",
                        quote="quote your best price for 2 containers, CIF Hamburg",
                    ),
                    outreach._Ask(kind="certification", detail="OEKO-TEX", quote="OEKO-TEX"),
                ],
                deadline_quote="by 15 December",
            )
            return {"raw": RAW, "parsed": read}

        return RunnableLambda(run)

    monkeypatch.setattr(outreach.llm, "get_chat_model", fake)
    yield prompts


async def contact(user: AsyncClient) -> dict[str, Any]:
    body = {"hs6": TOWELS, "market": "DEU", "name": "Holiday Heimtex GmbH", "kind": "importer"}
    response = await user.post("/api/v1/pipeline", json=body)
    assert response.status_code == 201, response.text
    return response.json()["contact"]


async def test_draft_send_reply_cycle(
    user: AsyncClient,
    model: list[str],
    lane: None,  # noqa: F811
) -> None:
    c = await contact(user)
    url = f"/api/v1/pipeline/{c['id']}"
    quote = await user.post("/api/v1/quotes", json=BASE | {"contact_id": c["id"]})
    assert quote.status_code == 201, quote.text

    thread = (await user.get(f"{url}/messages")).json()
    assert thread["messages"] == [] and thread["next_purpose"] == "first"
    assert [lang["code"] for lang in thread["languages"]] == ["de", "en"]

    draft = (await user.post(f"{url}/draft", json={"language": "de"})).json()
    assert draft["purpose"] == "first" and draft["drafted_by"] == "ai"
    assert draft["language"] == "de" and draft["quote_number"] == quote.json()["number"]
    # 5.00 is the quoted price; 7,500 was invented by the model.
    assert draft["checks"] == ["Check 7500: it isn't in your quote, details or the conversation"]
    assert "Price: USD 5.00 per kg, FOB Karachi" in model[-1]
    assert "SIGNATURE:\nAhmed\n[Your company]" in model[-1]

    sent = await user.post(
        f"{url}/messages", json={"subject": draft["subject"], "body": draft["body"]}
    )
    assert sent.status_code == 201
    after = sent.json()["contact"]
    assert after["stage"] == "emailed" and after["emails"] == 1
    assert after["follow_up_on"] == str(datetime.now(UTC).date() + timedelta(days=5))
    assert (await user.get(f"{url}/messages")).json()["next_purpose"] == "follow_up"

    read = await user.post(f"{url}/replies", json={"text": REPLY})
    assert read.status_code == 201, read.text
    analysis = read.json()["message"]["analysis"]
    assert [a["kind"] for a in analysis["asks"]] == ["samples", "price"]
    assert analysis["removed"] == 1  # "OEKO-TEX" isn't in their email
    assert analysis["deadline"] == "by 15 December" and analysis["red_flags"] == []
    assert analysis["suggested_stage"] == "samples" and analysis["read_by"] == "ai"
    moved = read.json()["contact"]
    assert moved["stage"] == "replied" and moved["follow_up_on"] == today()
    assert moved["reply_waiting"] is True and moved["emails"] == 2

    # The reply draft sees their open asks, and 15 from their email is not "invented".
    answer = (await user.post(f"{url}/draft", json={})).json()
    assert answer["purpose"] == "reply"
    assert "THEIR OPEN ASKS:\n- 3 samples" in model[-1]

    events = [e["kind"] for e in (await user.get(f"{url}/events")).json()]
    assert events[:4] == ["stage", "email_in", "stage", "email_out"]

    message_id = read.json()["message"]["id"]
    assert (await user.delete(f"{url}/messages/{message_id}")).status_code == 204
    assert (await user.delete(f"{url}/messages/{message_id}")).status_code == 404
    assert len((await user.get(f"{url}/messages")).json()["messages"]) == 1


async def test_model_down_uses_template_and_rules(
    user: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(spec: CallSpec, settings: Any = None) -> Any:
        def fail(_: Any) -> Any:
            raise RuntimeError("quota")

        return RunnableLambda(fail)

    monkeypatch.setattr(outreach.llm, "get_chat_model", broken)
    c = await contact(user)
    url = f"/api/v1/pipeline/{c['id']}"
    draft = (await user.post(f"{url}/draft", json={"language": "de"})).json()
    assert draft["drafted_by"] == "template" and draft["language"] == "en"
    assert "Dear Holiday Heimtex GmbH team" in draft["body"]

    scam = "Please pay the registration fee by Western Union to receive our order."
    read = (await user.post(f"{url}/replies", json={"text": scam})).json()
    analysis = read["message"]["analysis"]
    assert analysis["read_by"] == "template" and analysis["asks"] == []
    assert {f["code"] for f in analysis["red_flags"]} == {"advance_fee", "untraceable_payment"}
    assert read["contact"]["stage"] == "replied"


async def test_daily_allowance_and_privacy(user: AsyncClient, model: list[str]) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None,  # type: ignore[call-arg]
        intro_daily_limit=1,
    )
    try:
        c = await contact(user)
        url = f"/api/v1/pipeline/{c['id']}"
        assert (await user.post(f"{url}/draft", json={})).status_code == 200
        limited = await user.post(f"{url}/replies", json={"text": REPLY})
        assert limited.status_code == 429 and "tomorrow" in limited.json()["detail"]
        # Logging your own email is never limited.
        assert (await user.post(f"{url}/messages", json={"body": "Hello"})).status_code == 201
    finally:
        app.dependency_overrides.pop(get_settings, None)

    other = await user.post(
        "/api/v1/auth/register",
        json={"email": "rival@example.com", "full_name": "Rival", "password": "towels-2026!"},
    )
    assert other.status_code == 201
    for response in (
        await user.get(f"{url}/messages"),
        await user.post(f"{url}/draft", json={}),
        await user.post(f"{url}/messages", json={"body": "Hello"}),
        await user.post(f"{url}/replies", json={"text": REPLY}),
    ):
        assert response.status_code == 404

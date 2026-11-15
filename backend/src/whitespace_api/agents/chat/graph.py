"""The guide's loop, as a LangGraph graph.

    agent ──tool calls──▶ tools ──▶ agent ... (at most MAX_TOOL_ROUNDS)
      │
      └─ answer ─▶ check ──unsupported figures──▶ repair ─▶ check ─▶ end

- One model (main tier) decides and answers; tools are bound only while rounds remain,
  so the last call must answer.
- `check` is code, not a model: every number in the answer must appear in the tool
  results, the user's words or the conversation. One repair pass fixes the rest;
  whatever still can't be supported is reported as `grounded=False`.
- Progress (tool labels, cards) is streamed as custom events while the graph runs.
"""

from __future__ import annotations

import operator
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from whitespace_api.agents.brief.grounding import numbers
from whitespace_api.agents.chat.tools import DEFINITIONS, TOOLS, ChatContext, run_tool
from whitespace_api.agents.llm import CallSpec

MAX_TOOL_ROUNDS = 3
MAX_OUTPUT_TOKENS = 900
FREE_INTEGERS = 12  # small counts and list numbers ("3 steps", "1.") need no source

AGENT_SPEC = CallSpec(tier="main", max_output_tokens=MAX_OUTPUT_TOKENS, tools=DEFINITIONS)
ANSWER_SPEC = CallSpec(tier="main", max_output_tokens=MAX_OUTPUT_TOKENS)


@dataclass(frozen=True)
class ChatDeps:
    chat: Callable[[CallSpec], Runnable[Any, Any]]


class ChatState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], operator.add]
    known: list[str]  # text whose figures the answer may use (user words, history, profile)
    rounds: int
    cards: Annotated[list[dict[str, Any]], operator.add]
    evidence: Annotated[list[str], operator.add]
    memo: Annotated[list[str], operator.add]
    answer: str
    unsupported: list[str]
    repaired: bool
    usage: Annotated[list[dict[str, int]], operator.add]


def _usage(message: AIMessage) -> list[dict[str, int]]:
    meta = message.usage_metadata
    if not meta:
        return []
    return [{"input": meta.get("input_tokens", 0), "output": meta.get("output_tokens", 0)}]


def unsupported_figures(answer: str, sources: list[str]) -> list[str]:
    """Numbers in the answer that appear in none of the sources."""
    available: set[str] = set()
    for text in sources:
        available |= numbers(text)
    return sorted(
        n for n in numbers(answer) - available if not (n.isdigit() and int(n) <= FREE_INTEGERS)
    )


def build_graph(deps: ChatDeps, ctx: ChatContext) -> Any:
    async def agent(state: ChatState) -> dict[str, Any]:
        rounds = state.get("rounds", 0)
        spec = AGENT_SPEC if rounds < MAX_TOOL_ROUNDS else ANSWER_SPEC
        reply: AIMessage = await deps.chat(spec).ainvoke(state["messages"])
        out: dict[str, Any] = {"messages": [reply], "usage": _usage(reply)}
        if reply.tool_calls and spec is AGENT_SPEC:
            out["rounds"] = rounds + 1
        else:
            out["answer"] = reply.text.strip()
        return out

    async def tools(state: ChatState) -> dict[str, Any]:
        write = get_stream_writer()
        last = state["messages"][-1]
        assert isinstance(last, AIMessage)
        messages: list[BaseMessage] = []
        cards: list[dict[str, Any]] = []
        evidence: list[str] = []
        memo: list[str] = []
        # One at a time: tools share the request's database session.
        for call in last.tool_calls:
            tool = TOOLS.get(call["name"])
            write({"event": "status", "text": tool.label if tool else "Working"})
            outcome = await run_tool(ctx, call["name"], call["args"])
            if outcome.result is None:
                content = f"Error: {outcome.error}"
            else:
                content = outcome.result.text
                evidence.append(content)
                if outcome.result.memo:
                    memo.append(outcome.result.memo)
                if outcome.result.card is not None:
                    card = outcome.result.card.model_dump(mode="json")
                    cards.append(card)
                    write({"event": "card", "card": card})
            messages.append(
                ToolMessage(content=content, tool_call_id=call["id"], name=call["name"])
            )
        return {"messages": messages, "cards": cards, "evidence": evidence, "memo": memo}

    def check(state: ChatState) -> dict[str, Any]:
        sources = state.get("evidence", []) + state.get("known", [])
        return {"unsupported": unsupported_figures(state.get("answer", ""), sources)}

    async def repair(state: ChatState) -> dict[str, Any]:
        figures = ", ".join(state["unsupported"])
        request = HumanMessage(
            "Rewrite your last reply. These figures aren't in the data you were given: "
            f"{figures}. Remove them or replace them with the exact figures from the data. "
            "Keep everything else, in the same language."
        )
        reply: AIMessage = await deps.chat(ANSWER_SPEC).ainvoke([*state["messages"], request])
        return {"answer": reply.text.strip(), "repaired": True, "usage": _usage(reply)}

    def after_agent(state: ChatState) -> str:
        return "answer" if "answer" in state and state.get("answer") is not None else "tools"

    def after_check(state: ChatState) -> str:
        return "repair" if state["unsupported"] and not state.get("repaired") else END

    graph = StateGraph(ChatState)
    graph.add_node("agent", agent)
    graph.add_node("tools", tools)
    graph.add_node("check", check)
    graph.add_node("repair", repair)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", after_agent, {"tools": "tools", "answer": "check"})
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges("check", after_check, {"repair": "repair", END: END})
    graph.add_edge("repair", "check")
    return graph.compile()

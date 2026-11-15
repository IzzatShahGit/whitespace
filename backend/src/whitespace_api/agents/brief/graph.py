"""The brief as a LangGraph flow:  research -> extract -> write -> check.

  research  web search, planned by templates                 (no tokens)
  extract   cited claims from the snippets                   (small model, one call)
  write     the structured brief from facts + claims         (main model, one call)
  check     every figure traced to a fact or cited claim     (code, no tokens)

Measured facts are built before the graph runs (see facts.py). Token usage of every
call accumulates in the state, so each brief records exactly what it cost.
"""

from __future__ import annotations

import logging
import operator
from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

import httpx
from langchain_core.runnables import Runnable
from langgraph.graph import END, START, StateGraph

from whitespace_api.agents.brief import grounding, prompts
from whitespace_api.agents.brief.research import Query, research
from whitespace_api.agents.llm import CallSpec
from whitespace_api.schemas.brief import (
    BriefClaim,
    BriefContent,
    BriefFact,
    BriefPoint,
    BriefSource,
    BriefStep,
)

log = logging.getLogger(__name__)

EXTRACT_SPEC = CallSpec(tier="small", max_output_tokens=600, schema=prompts.Extraction)
WRITE_SPEC = CallSpec(tier="main", max_output_tokens=1100, schema=prompts.Draft)


class BriefError(RuntimeError):
    """The brief couldn't be written. The message is safe to show."""


class CallUsage(TypedDict):
    model: str
    input_tokens: int
    output_tokens: int


class BriefState(TypedDict, total=False):
    context: str  # "Exporter: ... Product: ... Market: ..."
    queries: list[Query]
    facts: list[BriefFact]
    sources: list[BriefSource]
    snippets: dict[str, str]
    claims: list[BriefClaim]
    draft: prompts.Draft
    content: BriefContent
    usage: Annotated[list[CallUsage], operator.add]  # appended by each model call


@dataclass(frozen=True)
class BriefDeps:
    http: httpx.AsyncClient
    search_key: str | None
    chat: Callable[[CallSpec], Runnable[Any, Any]]  # llm.get_chat_model, or a fake in tests


def _usage(raw: Any) -> CallUsage:
    meta = getattr(raw, "usage_metadata", None) or {}
    model = (getattr(raw, "response_metadata", None) or {}).get("model_name", "unknown")
    return {
        "model": str(model),
        "input_tokens": int(meta.get("input_tokens", 0)),
        "output_tokens": int(meta.get("output_tokens", 0)),
    }


def build_graph(deps: BriefDeps) -> Any:
    async def research_node(state: BriefState) -> BriefState:
        sources, snippets = await research(deps.http, deps.search_key, state["queries"])
        return {"sources": sources, "snippets": snippets}

    async def extract_node(state: BriefState) -> BriefState:
        sources, snippets = state.get("sources", []), state.get("snippets", {})
        if not sources:
            return {"claims": []}  # nothing to read: skip the call entirely
        out = await deps.chat(EXTRACT_SPEC).ainvoke(
            [
                ("system", prompts.EXTRACT_SYSTEM),
                ("human", prompts.extract_message(state["context"], sources, snippets)),
            ]
        )
        parsed: prompts.Extraction | None = out.get("parsed")
        known = {s.id: s for s in sources}
        claims: list[BriefClaim] = []
        for item in parsed.claims if parsed else []:
            source = known.get(item.source.strip())
            # A claim must come from a snippet we sent, and its figures must be in it.
            if source and grounding.supported(item.text, [snippets[source.id], source.title]):
                claims.append(
                    BriefClaim(id=f"C{len(claims) + 1}", text=item.text.strip(), source=source.id)
                )
        return {"claims": claims, "usage": [_usage(out.get("raw"))]}

    async def write_node(state: BriefState) -> BriefState:
        by_id = {s.id: s for s in state.get("sources", [])}
        claim_rows = [
            (c.id, c.text, f"{by_id[c.source].domain}, {by_id[c.source].published or 'undated'}")
            for c in state.get("claims", [])
        ]
        out = await deps.chat(WRITE_SPEC).ainvoke(
            [
                ("system", prompts.WRITE_SYSTEM),
                ("human", prompts.write_message(state["context"], state["facts"], claim_rows)),
            ]
        )
        draft: prompts.Draft | None = out.get("parsed")
        if draft is None:
            raise BriefError("The brief came back in an unexpected format. Please try again.")
        return {"draft": draft, "usage": [_usage(out.get("raw"))]}

    async def check_node(state: BriefState) -> BriefState:
        return {"content": check(state)}

    graph = StateGraph(BriefState)
    graph.add_node("research", research_node)
    graph.add_node("extract", extract_node)
    graph.add_node("write", write_node)
    graph.add_node("check", check_node)
    graph.add_edge(START, "research")
    graph.add_edge("research", "extract")
    graph.add_edge("extract", "write")
    graph.add_edge("write", "check")
    graph.add_edge("check", END)
    return graph.compile()


def check(state: BriefState) -> BriefContent:
    """Keep only points whose refs exist and whose figures appear in what they cite."""
    draft, facts = state["draft"], state["facts"]
    claims, sources = state.get("claims", []), state.get("sources", [])
    fact_text = {f.id: f"{f.label}: {f.value}" for f in facts}
    claim_text = {c.id: c.text for c in claims}
    every_fact = list(fact_text.values())
    removed = 0

    def keep(
        points: list[prompts.DraftPoint], allowed: str, needs: str | None = None
    ) -> list[BriefPoint]:
        nonlocal removed
        kept = []
        for p in points:
            refs = [
                r
                for r in dict.fromkeys(p.refs)
                if r[:1] in allowed and (r in fact_text or r in claim_text)
            ]
            evidence = [fact_text.get(r) or claim_text[r] for r in refs]
            ok = refs and (needs is None or any(r.startswith(needs) for r in refs))
            if ok and grounding.supported(p.text, evidence):
                kept.append(BriefPoint(text=p.text.strip(), refs=refs))
            else:
                removed += 1
        return kept

    def guidance_ok(text: str) -> bool:
        nonlocal removed
        ok = grounding.supported(text, every_fact)  # guidance may only repeat measured figures
        removed += 0 if ok else 1
        return ok

    why_now = keep(draft.why_now, "F")
    drivers = keep(draft.drivers, "FC", needs="C")
    risks = keep(draft.risks, "FC")
    entry_checks = [c.strip() for c in draft.entry_checks if guidance_ok(c)]
    roadmap = [
        BriefStep(title=s.title.strip(), detail=s.detail.strip())
        for s in draft.roadmap
        if guidance_ok(f"{s.title} {s.detail}")
    ]
    headline = draft.headline.strip()
    if not grounding.supported(headline, every_fact + list(claim_text.values())):
        removed += 1
        headline = next((f.value.split(". ")[0] for f in facts if "verdict" in f.label), "")

    cited = {r for p in drivers + risks for r in p.refs if r.startswith("C")}
    used_claims = [c for c in claims if c.id in cited]
    used_sources = {c.source for c in used_claims}
    return BriefContent(
        headline=headline,
        why_now=why_now,
        drivers=drivers,
        risks=risks,
        entry_checks=entry_checks,
        roadmap=roadmap,
        facts=facts,
        claims=used_claims,
        sources=[s for s in sources if s.id in used_sources],
        research_available=bool(sources),
        removed_points=removed,
    )

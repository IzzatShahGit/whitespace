"""Apify: runs a public "Amazon Best Sellers" actor and reads its results.

Amazon has no free API for its best-seller lists, so a third party (Apify, free plan:
$5 of usage a month) collects the public pages. We only start a run, check on it, and
read its dataset; every call carries a cost cap so a mistake can't exceed the free plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

BASE_URL = "https://api.apify.com/v2"
ACTOR = "junglee~amazon-bestsellers"
TIMEOUT = httpx.Timeout(30.0, connect=8.0)
RUNNING = frozenset({"READY", "RUNNING"})


class ApifyError(RuntimeError):
    """Apify didn't answer usefully. Details are for logs."""


@dataclass(frozen=True)
class Run:
    id: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    dataset_id: str

    @property
    def running(self) -> bool:
        return self.status in RUNNING


def _run(data: dict[str, Any]) -> Run:
    finished = data.get("finishedAt")
    return Run(
        id=data["id"],
        status=data["status"],
        started_at=datetime.fromisoformat(data["startedAt"]),
        finished_at=datetime.fromisoformat(finished) if finished else None,
        dataset_id=data["defaultDatasetId"],
    )


async def _call(
    client: httpx.AsyncClient, method: str, path: str, token: str, **kwargs: Any
) -> httpx.Response:
    try:
        response = await client.request(
            method,
            f"{BASE_URL}{path}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT,
            **kwargs,
        )
    except httpx.HTTPError as exc:
        raise ApifyError(f"{type(exc).__name__}: {exc}") from exc
    if response.status_code == 404:
        return response
    if response.is_error:
        raise ApifyError(f"HTTP {response.status_code}: {response.text[:200]}")
    return response


async def last_run(client: httpx.AsyncClient, token: str, *, succeeded: bool = False) -> Run | None:
    """The actor's latest run on this account (only successful ones if asked)."""
    params = {"status": "SUCCEEDED"} if succeeded else {}
    response = await _call(client, "GET", f"/acts/{ACTOR}/runs/last", token, params=params)
    if response.status_code == 404:  # never run
        return None
    try:
        return _run(response.json()["data"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ApifyError(f"unexpected run: {exc}") from exc


async def start(
    client: httpx.AsyncClient, token: str, run_input: dict[str, Any], *, max_charge_usd: float
) -> Run:
    """Start a run without waiting for it; it takes a few minutes."""
    response = await _call(
        client,
        "POST",
        f"/acts/{ACTOR}/runs",
        token,
        params={"maxTotalChargeUsd": f"{max_charge_usd:.2f}"},
        json=run_input,
    )
    try:
        return _run(response.json()["data"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ApifyError(f"unexpected run: {exc}") from exc


async def items(client: httpx.AsyncClient, token: str, dataset_id: str) -> list[dict[str, Any]]:
    response = await _call(
        client,
        "GET",
        f"/datasets/{dataset_id}/items",
        token,
        params={"format": "json", "clean": "true", "limit": "1000"},
    )
    data = response.json() if response.status_code != 404 else []
    if not isinstance(data, list):
        raise ApifyError("dataset items aren't a list")
    return [item for item in data if isinstance(item, dict)]

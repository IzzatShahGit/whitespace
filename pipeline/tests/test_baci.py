"""BACI bronze stage, against a tiny fake release. No network: HTTP is faked."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx
import polars as pl
import pytest

from whitespace_pipeline.config import PipelineSettings
from whitespace_pipeline.sources import baci

V = "209901"


def make_zip(years: range) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for y in years:
            z.writestr(
                f"BACI_HS17_Y{y}_V{V}.csv",
                f"t,i,j,k,v,q\n{y},586,276,630260,1250.5,310.2\n{y},586,840,080810,2.295,NA\n",
            )
        z.writestr(f"product_codes_HS17_V{V}.csv", 'code,description\n630260,"Towels, terry"\n')
        z.writestr(
            f"country_codes_V{V}.csv",
            "country_code,country_name,country_iso2,country_iso3\n586,Pakistan,PK,PAK\n",
        )
        z.writestr("Readme.txt", "test")
    return buf.getvalue()


@pytest.fixture
def settings(tmp_path: Path) -> PipelineSettings:
    return PipelineSettings(
        _env_file=None,  # type: ignore[call-arg]
        data_dir=tmp_path,
        baci_version=V,
        baci_base_url="https://example.test/baci",
    )


def fake_server(payload: bytes, *, honour_range: bool = True, cut_at: int | None = None):  # type: ignore[no-untyped-def]
    """An httpx client whose server serves `payload`, optionally dropping mid-way."""
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.headers.get("range", "full"))
        if request.method == "HEAD":
            return httpx.Response(200, headers={"content-length": str(len(payload))})
        start = 0
        rng = request.headers.get("range")
        if rng and honour_range:
            start = int(rng.removeprefix("bytes=").rstrip("-"))
        body = payload[start : cut_at if cut_at and not rng else None]
        return httpx.Response(206 if rng and honour_range else 200, content=body)

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_extract_keeps_last_four_years_with_codes_as_text(settings: PipelineSettings) -> None:
    zip_path = settings.data_dir / "release.zip"
    zip_path.write_bytes(make_zip(range(2017, 2025)))

    years = baci.extract(zip_path, settings)

    assert years == [2021, 2022, 2023, 2024]
    root = baci.bronze_root(settings)
    flows = pl.read_parquet(root / "flows" / "year=2024" / "part-0.parquet")
    assert flows.schema == baci.FLOW_SCHEMA
    assert flows["k"].to_list() == ["630260", "080810"]  # leading zero kept
    assert flows["q"].to_list()[1] is None  # "NA" -> null
    assert not (root / "flows" / "year=2020").exists()
    assert pl.read_parquet(root / "countries.parquet")["country_iso3"].to_list() == ["PAK"]


def test_extract_refuses_short_release(settings: PipelineSettings) -> None:
    zip_path = settings.data_dir / "release.zip"
    zip_path.write_bytes(make_zip(range(2023, 2025)))
    with pytest.raises(baci.BaciError, match="Need 4 years"):
        baci.extract(zip_path, settings)


def test_download_resumes_after_a_dropped_connection(settings: PipelineSettings) -> None:
    payload = make_zip(range(2017, 2025))
    client, calls = fake_server(payload, cut_at=len(payload) // 2)

    with pytest.raises(baci.BaciError, match="Incomplete download"):
        baci.download(settings, client=client)
    path = baci.download(settings, client=client)  # second run resumes

    assert path.read_bytes() == payload
    assert any(c.startswith("bytes=") for c in calls)  # a Range request was made


def test_download_restarts_when_server_ignores_range(settings: PipelineSettings) -> None:
    payload = make_zip(range(2017, 2025))
    partial = settings.bronze_dir / "baci" / f"BACI_HS17_V{V}.zip.part"
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"stale-bytes")
    client, _ = fake_server(payload, honour_range=False)

    assert baci.download(settings, client=client).read_bytes() == payload


def test_run_is_idempotent_and_deletes_zip(
    settings: PipelineSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = make_zip(range(2017, 2025))
    client, calls = fake_server(payload)
    monkeypatch.setattr(baci.httpx, "Client", lambda **_: client)

    assert baci.run(settings) == [2021, 2022, 2023, 2024]
    assert not (settings.bronze_dir / "baci" / f"BACI_HS17_V{V}.zip").exists()

    calls.clear()
    assert baci.run(settings) == [2021, 2022, 2023, 2024]
    assert calls == []  # second run touched nothing on the network

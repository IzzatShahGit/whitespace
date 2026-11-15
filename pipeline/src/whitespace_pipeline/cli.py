"""Pipeline command line: one command per stage, plus `run` for all of them.

uv run ws-pipeline --help
"""

from __future__ import annotations

import logging

import typer

from whitespace_pipeline.config import get_settings
from whitespace_pipeline.gold import opportunity
from whitespace_pipeline.load import postgres
from whitespace_pipeline.silver import baci as silver_baci
from whitespace_pipeline.sources import baci

app = typer.Typer(help="Whitespace data pipeline", no_args_is_help=True)


@app.command()
def info() -> None:
    """Show where data lives and what v0 covers."""
    settings = get_settings()
    typer.echo(f"data dir:    {settings.data_dir}")
    typer.echo(f"HS revision: {settings.baci_hs_revision}")
    typer.echo(f"exporters:   {', '.join(settings.exporters)}")


@app.callback()
def _setup(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _progress() -> baci.ProgressFn:
    last = -1

    def report(done: int, total: int) -> None:
        nonlocal last
        pct = done * 100 // total if total else 0
        if pct // 5 != last // 5:  # print every 5%
            last = pct
            typer.echo(
                f"  downloading BACI: {pct:3d}%  ({done / 1e6:,.0f} / {total / 1e6:,.0f} MB)"
            )

    return report


@app.command()
def bronze(
    force: bool = typer.Option(False, help="Redo even if this release is already in bronze."),
) -> None:
    """Download raw sources into data/bronze, untouched (CSV -> Parquet only)."""
    settings = get_settings()
    years = baci.run(settings, force=force, progress=_progress())
    typer.secho(
        f"bronze ready: BACI {settings.baci_hs_revision} V{settings.baci_version}, "
        f"years {years[0]}-{years[-1]}",
        fg=typer.colors.GREEN,
    )


@app.command()
def silver() -> None:
    """Clean bronze into data/silver (ISO country codes, 6-digit products, USD)."""
    path = silver_baci.run(get_settings())
    typer.secho(f"silver ready: {path}", fg=typer.colors.GREEN)


@app.command()
def gold() -> None:
    """Compute market metrics and opportunity scores into data/gold."""
    path = opportunity.run(get_settings())
    typer.secho(f"gold ready: {path}", fg=typer.colors.GREEN)


@app.command()
def load() -> None:
    """Replace the trade tables in Postgres with the latest gold data."""
    counts = postgres.run(get_settings())
    for table, rows in counts.items():
        typer.echo(f"  {table}: {rows:,} rows")
    typer.secho("load complete", fg=typer.colors.GREEN)


@app.command()
def run(force: bool = typer.Option(False, help="Re-download bronze too.")) -> None:
    """All stages in order: bronze -> silver -> gold -> load."""
    bronze(force=force)
    silver()
    gold()
    load()


if __name__ == "__main__":
    app()

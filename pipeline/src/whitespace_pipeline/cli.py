"""Pipeline command line. One command per stage, plus `run` for all of them.

uv run ws-pipeline --help
"""

from __future__ import annotations

import typer

from whitespace_pipeline.config import get_settings

app = typer.Typer(help="Whitespace data pipeline", no_args_is_help=True)


@app.command()
def info() -> None:
    """Show where data lives and what v0 covers."""
    settings = get_settings()
    typer.echo(f"data dir:    {settings.data_dir}")
    typer.echo(f"HS revision: {settings.baci_hs_revision}")
    typer.echo(f"exporters:   {', '.join(settings.exporters)}")


def _not_yet(stage: str) -> None:
    typer.secho(f"{stage}: not implemented yet", fg=typer.colors.YELLOW)
    raise typer.Exit(code=1)


@app.command()
def bronze() -> None:
    """Download raw sources into data/bronze, untouched."""
    _not_yet("bronze")


@app.command()
def silver() -> None:
    """Clean bronze into data/silver."""
    _not_yet("silver")


@app.command()
def gold() -> None:
    """Compute market metrics and opportunity scores into data/gold."""
    _not_yet("gold")


@app.command()
def load() -> None:
    """Load gold tables into Postgres."""
    _not_yet("load")


if __name__ == "__main__":
    app()

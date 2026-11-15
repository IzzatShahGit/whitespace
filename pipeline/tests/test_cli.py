from typer.testing import CliRunner

from whitespace_pipeline.cli import app

runner = CliRunner()


def test_info_runs() -> None:
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "HS17" in result.output

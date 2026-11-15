import logging

from whitespace_api.core.logging import RedactQueryFilter, redact


def test_oauth_values_are_redacted() -> None:
    line = "/api/v1/auth/google/callback?state=abc123&iss=x&code=4%2F0secret&scope=email"
    assert redact(line) == (
        "/api/v1/auth/google/callback?state=[redacted]&iss=x&code=[redacted]&scope=email"
    )


def test_ordinary_paths_untouched() -> None:
    assert redact("/api/v1/markets?product=towels&country=PAK") == (
        "/api/v1/markets?product=towels&country=PAK"
    )


def test_filter_rewrites_access_log_args() -> None:
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s"',
        ("1.2.3.4", "GET", "/cb?code=x"),
        None,
    )
    RedactQueryFilter().filter(record)
    assert record.getMessage() == '1.2.3.4 - "GET /cb?code=[redacted]"'

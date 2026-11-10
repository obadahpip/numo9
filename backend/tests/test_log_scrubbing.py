"""S-03-T06 — log scrubbing: structlog processor and Sentry before_send remove SIN, bank and card
numbers, tokens and passwords. Acceptance: a log line with a SIN shows [REDACTED]."""

from __future__ import annotations

import io
import json
import logging
import os
import secrets
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import sentry_sdk
import structlog
from django.conf import settings
from sentry_sdk.transport import Transport

from numo9.security.logging import SHARED_PROCESSORS, formatter_processors, sentry_options
from numo9.security.scrubbing import (
    REDACTED,
    is_sensitive_key,
    scrub,
    scrub_text,
    sentry_before_send,
)

SIN = "046 454 286"  # valid check digit (Luhn)
SIN_PLAIN = "046454286"
CARD = "4242 4242 4242 4242"
BANK = "12345-003-1234567"  # transit-institution-account
BACKEND_DIR = Path(__file__).resolve().parent.parent
# Fake credentials, assembled at run time so secret scanners (gitleaks) see no literal token.
FAKE_TOKEN = "abcdef" + "123456"
FAKE_STRIPE_KEY = "sk_" + "live_" + "51Habcdefghij"


@pytest.fixture
def json_log() -> Iterator[tuple[logging.Logger, io.StringIO]]:
    """A logger writing through the project's scrubbing formatter (JSON) into a buffer."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            processors=formatter_processors(json=True), foreign_pre_chain=SHARED_PROCESSORS
        )
    )
    logger = logging.getLogger("numo9.test.scrubbing")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    yield logger, stream
    logger.removeHandler(handler)


def lines(stream: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line]


# ---- Acceptance --------------------------------------------------------------------------------


def test_log_with_a_sin_shows_redacted(json_log: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = json_log
    logger.info("Employee %s has SIN %s", "Dana Lee", SIN)
    logger.info("Payroll record", extra={"sin": SIN_PLAIN, "employee": "Dana Lee"})
    [first, second] = lines(stream)
    assert first["event"] == f"Employee Dana Lee has SIN {REDACTED}"
    assert second["sin"] == REDACTED
    assert second["employee"] == "Dana Lee"
    assert "454" not in stream.getvalue()


def test_structlog_events_are_scrubbed(json_log: tuple[logging.Logger, io.StringIO]) -> None:
    _, stream = json_log
    log = structlog.get_logger("numo9.test.scrubbing")
    log.info(
        "card payment",
        card_number=CARD,
        password="hunter2-hunter2",  # noqa: S106 — must be scrubbed
        note=f"customer read out {CARD} and bank {BANK}",
        amount="125.00",
    )
    [event] = lines(stream)
    assert event["card_number"] == REDACTED
    assert event["password"] == REDACTED
    assert event["note"] == f"customer read out {REDACTED} and bank {REDACTED}"
    assert event["amount"] == "125.00"


def test_tracebacks_are_scrubbed(json_log: tuple[logging.Logger, io.StringIO]) -> None:
    logger, stream = json_log
    try:
        raise ValueError(f"cannot charge card {CARD} for SIN {SIN_PLAIN}")
    except ValueError:
        logger.exception("payment failed")
    [event] = lines(stream)
    assert "ValueError: cannot charge card [REDACTED] for SIN [REDACTED]" in event["exception"]
    assert "4242" not in stream.getvalue()


def test_project_logging_uses_the_scrubbing_formatter() -> None:
    formatter = settings.LOGGING["formatters"]["scrubbed"]
    assert formatter["()"] is structlog.stdlib.ProcessorFormatter
    from numo9.security.scrubbing import structlog_processor

    assert structlog_processor in formatter["foreign_pre_chain"]
    assert structlog_processor in formatter["processors"]
    assert settings.LOGGING["root"]["handlers"] == ["console"]
    assert settings.LOGGING["handlers"]["console"]["formatter"] == "scrubbed"


def test_deployed_process_logs_json_without_the_sin() -> None:
    """End to end in a fresh prod-settings process: Django's own logging config writes the line."""
    env = {
        **{
            k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "NUMO9_", "SENTRY"))
        },
        "DJANGO_SETTINGS_MODULE": "numo9.settings.prod",
        "DJANGO_SECRET_KEY": secrets.token_urlsafe(64),
        "DJANGO_ALLOWED_HOSTS": "app.numo9.ca",
        "DATABASE_URL": "sqlite:///:memory:",
    }
    script = (
        "import django, logging; django.setup();"
        f"logging.getLogger('numo9.payroll').warning('SIN on file: {SIN}, token={FAKE_TOKEN}')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    record = json.loads(result.stderr.strip().splitlines()[-1])
    assert record["event"] == f"SIN on file: {REDACTED}, token={REDACTED}"
    assert record["level"] == "warning"
    assert record["logger"] == "numo9.payroll"


# ---- Scrubbing rules ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"SIN {SIN}", f"SIN {REDACTED}"),
        ("SIN 046-454-286", f"SIN {REDACTED}"),
        (f"nas={SIN_PLAIN}", f"nas={REDACTED}"),
        (f"card {CARD}", f"card {REDACTED}"),
        ("card 4242-4242-4242-4242", f"card {REDACTED}"),
        (f"deposit to {BANK}", f"deposit to {REDACTED}"),
        ("Authorization: Bearer abc.def.ghijkl123", f"Authorization: {REDACTED} {REDACTED}"),
        ("jwt eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0.SflKxwRJSMeKKF2QT4", f"jwt {REDACTED}"),
        (f"key {FAKE_STRIPE_KEY}", f"key {REDACTED}"),
        ("hook whsec_abcdefghijkl", f"hook {REDACTED}"),
        ("postgres://numo9:S3cret!@db:5432/numo9", f"postgres://numo9:{REDACTED}@db:5432/numo9"),
        ("login password=hunter2&next=/", f"login password={REDACTED}&next=/"),
        ('{"password": "hunter2"}', f'{{"password": "{REDACTED}"}}'),
        ("?token=abc123&page=2", f"?token={REDACTED}&page=2"),
        ("AGE-SECRET-KEY-1QQQQQQQQQQQQQQQQQQQQQQQQQQQQQ", REDACTED),
    ],
)
def test_sensitive_text_is_redacted(text: str, expected: str) -> None:
    assert scrub_text(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Invoice INV-123456789 total $1,234.56",  # not Luhn-valid 9 digits
        "invoice 123456789 posted",
        "JE-000123 posted 2026-10-26",
        "phone 416-555-0142, Postal code M5V 2T6",
        "GST/HST registration 123456789RT0001",
        "order 4242424242424241 (not a card: fails Luhn)",
        "organisation Maple Leaf Supply Ltd.",
        "10 accounts imported",
    ],
)
def test_ordinary_text_is_kept(text: str) -> None:
    assert scrub_text(text) == text


@pytest.mark.parametrize(
    ("key", "sensitive"),
    [
        ("password", True),
        ("user_password", True),
        ("X-Api-Key", True),
        ("HTTP_AUTHORIZATION", True),
        ("bankAccount", True),
        ("bank_account", True),
        ("card_number", True),
        ("sin", True),
        ("employee_sin", True),
        ("account_number", True),
        ("csrftoken", True),
        ("sessionid", True),
        ("business", False),
        ("since", False),
        ("account_id", False),
        ("company", False),
        ("organisation_name", False),
        ("amount", False),
    ],
)
def test_sensitive_keys(key: str, sensitive: bool) -> None:
    assert is_sensitive_key(key) is sensitive


def test_nested_structures_are_copied_and_scrubbed() -> None:
    original: dict[str, Any] = {
        "user": {"name": "Dana", "sin": SIN},
        "lines": [f"card {CARD}", ("token", "x1")],
    }
    result = scrub(original)
    assert result == {
        "user": {"name": "Dana", "sin": REDACTED},
        "lines": [f"card {REDACTED}", ("token", REDACTED)],
    }
    assert original["user"]["sin"] == SIN  # not mutated


# ---- Sentry ------------------------------------------------------------------------------------


def test_sentry_event_is_scrubbed() -> None:
    event = {
        "message": f"failed for {SIN}",
        "request": {
            "url": "https://app.numo9.ca/api/v1/payees?token=abc123",
            "query_string": "token=abc123&page=1",
            "headers": [["Authorization", "Bearer abcdefghij"], ["Accept", "application/json"]],
            "cookies": {"sessionid": "s3ss10n", "numo9_locale": "en-ca"},
            "data": {"sin": SIN_PLAIN, "name": "Dana"},
        },
        "extra": {"bank": BANK, "count": 3},
        "user": {"id": 7, "email": "dana@example.com", "ip_address": "203.0.113.9"},
        "exception": {
            "values": [
                {
                    "type": "ValueError",
                    "value": f"card {CARD}",
                    "stacktrace": {"frames": [{"function": "pay", "vars": {"password": "pw"}}]},
                }
            ]
        },
        "breadcrumbs": {"values": [{"message": f"lookup {SIN}", "category": "query"}]},
    }
    scrubbed = sentry_before_send(event)
    flat = json.dumps(scrubbed)
    for leaked in (
        SIN,
        SIN_PLAIN,
        CARD,
        BANK,
        "abc123",
        "abcdefghij",
        "s3ss10n",
        "dana@example.com",
        "203.0.113",
    ):
        assert leaked not in flat
    assert scrubbed["user"] == {"id": 7}
    assert scrubbed["request"]["headers"][1] == ["Accept", "application/json"]
    assert scrubbed["request"]["cookies"] == REDACTED  # cookies are dropped whole
    assert scrubbed["request"]["data"]["name"] == "Dana"
    assert scrubbed["extra"]["count"] == 3


class CaptureTransport(Transport):
    def __init__(self, options: dict[str, Any] | None = None) -> None:
        super().__init__(options)
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope: Any) -> None:
        for item in envelope.items:
            if item.headers.get("type") == "event":
                self.events.append(json.loads(item.payload.get_bytes()))


def test_sentry_sdk_sends_scrubbed_events() -> None:
    transport = CaptureTransport()
    options = sentry_options("https://public@o0.ingest.example.invalid/1", environment="test")
    sentry_sdk.init(**options, transport=transport)
    try:
        assert options["data_collection"]["user_info"] is False
        assert options["data_collection"]["stack_frame_variables"] is False
        assert options["include_local_variables"] is False
        logging.getLogger("numo9.test.sentry").error("lookup for SIN %s", SIN)
        try:
            raise RuntimeError(f"bank {BANK} card {CARD}")
        except RuntimeError as error:
            sentry_sdk.capture_exception(error)
        sentry_sdk.flush()
    finally:
        sentry_sdk.init()  # disable again for the other tests
    payload = json.dumps(transport.events)
    assert len(transport.events) >= 2
    for leaked in (SIN, SIN_PLAIN, CARD, CARD.replace(" ", ""), BANK):
        assert leaked not in payload
    assert REDACTED in payload

"""Logging and error reporting with scrubbing (S-03-T06).

``logging_config(json=…)`` is the Django ``LOGGING`` dict: every standard-library record
(Django, Celery later, third-party libraries) and every structlog event goes through one
``structlog.stdlib.ProcessorFormatter`` whose chain ends with the scrubbing processor, so nothing
reaches the console, a file or the log pipeline unscrubbed. ``configure_structlog`` sets the
same chain for ``structlog.get_logger()``.

``init_sentry`` starts Sentry only when ``SENTRY_DSN`` is set, collecting no user identity,
request bodies, frame variables or SQL parameters, and ``before_send`` / ``before_send_transaction`` / ``before_breadcrumb``
scrubbing every event.
"""

from __future__ import annotations

from typing import Any

import structlog

from .scrubbing import (
    sentry_before_breadcrumb,
    sentry_before_send,
    structlog_processor,
)

# Runs for both structlog events and standard-library records, before rendering.
SHARED_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.stdlib.ExtraAdder(),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,  # traceback → text, so the scrubber sees it
    structlog.processors.UnicodeDecoder(),
    structlog_processor,  # last before rendering: S-03-T06
]


def formatter_processors(json: bool) -> list[Any]:
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json
        else structlog.dev.ConsoleRenderer(
            colors=False, exception_formatter=structlog.dev.plain_traceback
        )
    )
    return [
        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
        # The record's message is formatted ("%s" args) before scrubbing runs again on it.
        structlog_processor,
        renderer,
    ]


def logging_config(*, json: bool, level: str = "INFO") -> dict[str, Any]:
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "scrubbed": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": formatter_processors(json),
                "foreign_pre_chain": SHARED_PROCESSORS,
            }
        },
        "handlers": {
            "console": {"class": "logging.StreamHandler", "formatter": "scrubbed"},
        },
        "root": {"handlers": ["console"], "level": level},
        "loggers": {
            "django": {"handlers": ["console"], "level": level, "propagate": False},
            "django.db.backends": {"level": "WARNING"},  # SQL params could hold anything
        },
    }


def configure_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *SHARED_PROCESSORS[:-1],
            structlog.stdlib.PositionalArgumentsFormatter(),
            SHARED_PROCESSORS[-1],
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def sentry_options(dsn: str, environment: str, release: str | None = None) -> dict[str, Any]:
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    return {
        "dsn": dsn,
        "environment": environment,
        "release": release,
        "integrations": [DjangoIntegration(), LoggingIntegration()],
        # No user identity, request bodies, frame variables or SQL parameters leave the server
        # (frames and bodies would carry SINs, passwords, tokens); before_send scrubs the rest.
        "data_collection": {
            "user_info": False,
            "http_bodies": [],
            "stack_frame_variables": False,
            "database_query_data": False,
        },
        "include_local_variables": False,
        "max_request_body_size": "never",
        "before_send": sentry_before_send,
        "before_send_transaction": sentry_before_send,
        "before_breadcrumb": sentry_before_breadcrumb,
        "traces_sample_rate": 0.0,
    }


def init_sentry(dsn: str, environment: str, release: str | None = None) -> bool:
    if not dsn:
        return False
    import sentry_sdk

    sentry_sdk.init(**sentry_options(dsn, environment, release))
    return True

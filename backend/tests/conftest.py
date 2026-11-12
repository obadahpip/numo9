"""Test-session setup."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from django.db import transaction

from tools.compile_messages import main as compile_messages


def pytest_configure(config: pytest.Config) -> None:
    # Translations need compiled .mo files (build output, not committed) — A-10-T14.
    compile_messages(["--quiet"])


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Rate-limit counters and lockouts live in the cache (A-02): no test inherits another's."""
    from django.core.cache import cache

    cache.clear()


# ---- background jobs (A-08) --------------------------------------------------------------------


@pytest.fixture
def sent_on_commit() -> Iterator[list[dict[str, Any]]]:
    """Messages sent by start_job (captured instead of reaching the broker)."""
    messages: list[dict[str, Any]] = []

    def capture(self: Any, args: Any = None, kwargs: Any = None, **options: Any) -> None:
        messages.append({"task": self.name, "kwargs": kwargs, **options})

    with mock.patch("celery.app.task.Task.apply_async", capture):
        yield messages


@pytest.fixture
def sent(sent_on_commit: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    """As ``sent_on_commit``, with commit callbacks run at once: the test transaction never
    commits, while in production start_job runs in autocommit or a request that commits."""

    def now(func: Any, using: Any = None, robust: bool = False) -> None:
        func()

    with mock.patch.object(transaction, "on_commit", now):
        yield sent_on_commit

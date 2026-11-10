"""Test-session setup."""

from __future__ import annotations

import pytest

from tools.compile_messages import main as compile_messages


def pytest_configure(config: pytest.Config) -> None:
    # Translations need compiled .mo files (build output, not committed) — A-10-T14.
    compile_messages(["--quiet"])


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    """Rate-limit counters and lockouts live in the cache (A-02): no test inherits another's."""
    from django.core.cache import cache

    cache.clear()

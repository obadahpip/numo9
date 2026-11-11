"""Celery worker against a real Redis broker and result backend (A-08-T01).

Runs when ``NUMO9_TEST_REDIS_URL`` is set (CI backend job: Redis 7 service); skipped otherwise.
Kept apart from ``test_celery.py`` so its in-memory worker is stopped first.
"""

from __future__ import annotations

import os

import pytest
from celery import Celery
from celery.contrib.testing.worker import start_worker

from numo9.settings.env import redis_database

REDIS_URL = os.environ.get("NUMO9_TEST_REDIS_URL")


@pytest.mark.skipif(not REDIS_URL, reason="NUMO9_TEST_REDIS_URL not set (needs a Redis server)")
def test_worker_consumes_from_redis() -> None:
    assert REDIS_URL is not None
    app = Celery("numo9-redis-test")
    app.config_from_object("django.conf:settings", namespace="CELERY")
    app.conf.broker_url = redis_database(REDIS_URL, 14)
    app.conf.result_backend = redis_database(REDIS_URL, 15)

    @app.task(name="numo9.jobs.redis_ping")  # type: ignore[untyped-decorator]
    def redis_ping(value: int) -> int:
        return value * 2

    with start_worker(app, queues=["reports"], perform_ping_check=False, loglevel="WARNING"):
        assert redis_ping.apply_async(args=[21], queue="reports").get(timeout=15) == 42

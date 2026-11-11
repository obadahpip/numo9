"""Celery app configuration (A-08-T01).

Acceptance: a worker consumes the test task. The worker runs in a thread of the test process
(``celery.contrib.testing``) on the in-memory broker of the test settings; the same check runs
against a real Redis server in ``test_celery_redis.py``.
"""

from __future__ import annotations

from collections.abc import Iterator
from io import StringIO
from typing import Any

import pytest
from celery.contrib.testing.worker import start_worker
from celery.exceptions import QueueNotFound
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import CommandError, call_command

from numo9 import celery_app
from numo9.jobs.queues import QUEUE_NAMES
from numo9.jobs.tasks import ping
from numo9.settings.env import redis_database


@pytest.fixture(scope="module")
def worker() -> Iterator[Any]:
    """A worker thread consuming every Numo9 queue (one per module: stopping one takes ~3 s)."""
    with start_worker(
        celery_app,
        queues=list(QUEUE_NAMES),
        perform_ping_check=False,
        shutdown_timeout=10,
        loglevel="WARNING",
    ) as running:
        yield running


# ---- configuration ----------------------------------------------------------------------------


def test_reliability_settings() -> None:
    conf = celery_app.conf
    assert conf.task_acks_late is True
    assert conf.task_reject_on_worker_lost is True
    assert conf.worker_prefetch_multiplier == 1
    assert conf.task_soft_time_limit == 25 * 60
    assert conf.task_time_limit == 30 * 60
    assert conf.task_soft_time_limit < conf.task_time_limit
    # Redis redelivers unacknowledged messages after the visibility timeout: it must outlast
    # the hard time limit or a running task would be delivered a second time.
    assert settings.CELERY_BROKER_TRANSPORT_OPTIONS["visibility_timeout"] > conf.task_time_limit


def test_json_only_no_pickle() -> None:
    conf = celery_app.conf
    assert conf.accept_content == ["json"]
    assert conf.task_serializer == "json"
    assert conf.result_serializer == "json"


def test_queues_default_high_io_reports() -> None:
    conf = celery_app.conf
    assert [q.name for q in conf.task_queues] == ["high", "default", "io", "reports"]
    assert conf.task_default_queue == "default"
    assert conf.task_create_missing_queues is False


def test_tasks_are_discovered() -> None:
    celery_app.loader.import_default_modules()
    assert "numo9.jobs.ping" in celery_app.tasks


def test_broker_defaults_follow_redis_url() -> None:
    assert redis_database("redis://redis:6379/0", 2) == "redis://redis:6379/2"
    assert redis_database("rediss://:pw@cache.internal:6380/0?ssl_cert_reqs=required", 3) == (
        "rediss://:pw@cache.internal:6380/3?ssl_cert_reqs=required"
    )
    assert redis_database("redis://localhost", 2) == "redis://localhost/2"
    with pytest.raises(ImproperlyConfigured):
        redis_database("http://localhost:6379/0", 2)


def test_unknown_queue_is_refused() -> None:
    with pytest.raises(QueueNotFound):
        ping.apply_async(queue="hgih")


# ---- a worker consumes tasks ------------------------------------------------------------------


def test_worker_consumes_the_test_task(worker: Any) -> None:
    result = ping.delay({"from": "test"})
    assert result.get(timeout=10) == {"pong": True, "payload": {"from": "test"}}
    assert result.status == "SUCCESS"


@pytest.mark.parametrize("queue", QUEUE_NAMES)
def test_every_queue_is_consumed(worker: Any, queue: str) -> None:
    assert ping.apply_async(args=[queue], queue=queue).get(timeout=10)["payload"] == queue


def test_celery_ping_command(worker: Any) -> None:
    out = StringIO()
    call_command("celery_ping", "--queue", "io", "--timeout", "10", stdout=out)
    assert "Worker answered on 'io'" in out.getvalue()


def test_celery_ping_command_fails_without_a_worker() -> None:
    with pytest.raises(CommandError, match="No worker answered"):
        call_command("celery_ping", "--timeout", "0.5")

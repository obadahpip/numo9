"""Scheduled jobs: django-celery-beat with a Redis lock per tick (A-08-T05).

Acceptance: two beats → one execution. Two schedulers find the same schedule due at the same
tick; only the one that takes the tick's lock sends the task. With ``NUMO9_TEST_REDIS_URL`` set
(CI) the lock is a real Redis ``SET NX``, raced from two threads.
"""

from __future__ import annotations

import os
import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from celery import schedules
from django.conf import settings
from django.utils import timezone
from django_celery_beat.models import CrontabSchedule, PeriodicTask
from django_celery_beat.schedulers import ModelEntry

from numo9 import celery_app
from numo9.jobs import beat
from numo9.jobs.beat import (
    LocalTickStore,
    LockedDatabaseScheduler,
    RedisTickStore,
    lock_seconds,
    step_seconds,
    tick_key,
    tick_of,
)
from numo9.jobs.models import RETENTION, JobRun, JobStatus
from numo9.jobs.runtime import platform_job
from numo9.jobs.tasks import purge_job_runs
from tests.job_helpers import deliver

REDIS_URL = os.environ.get("NUMO9_TEST_REDIS_URL")
FIRES: list[str] = []


@platform_job(name="tests.beat.nightly")
def nightly(*, note: str = "") -> dict[str, str]:
    FIRES.append(note)
    return {"note": note}


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    FIRES.clear()
    beat._store = None
    # The scheduler's periodic sync calls close_old_connections(), which would close the test
    # transaction's connection; syncing schedules to the database is django-celery-beat's own.
    with mock.patch.object(LockedDatabaseScheduler, "should_sync", return_value=False):
        yield
    beat._store = None


def at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=UTC)


# ---- ticks -------------------------------------------------------------------------------------


def test_crontab_ticks_on_the_minute_and_tolerates_clock_drift() -> None:
    every_day = schedules.crontab(minute=17, hour=7)
    assert step_seconds(every_day) == 60
    on_time = tick_of(every_day, at("2026-11-12T07:17:00"))
    assert on_time == int(at("2026-11-12T07:17:00").timestamp())
    for drift in ("07:16:31", "07:16:59.5", "07:17:00.4", "07:17:29"):
        assert tick_of(every_day, at(f"2026-11-12T{drift}")) == on_time
    assert tick_of(every_day, at("2026-11-13T07:17:01")) != on_time  # the next day's tick


def test_interval_ticks_on_the_interval() -> None:
    ten_minutes = schedules.schedule(timedelta(minutes=10))
    assert step_seconds(ten_minutes) == 600
    assert tick_of(ten_minutes, at("2026-11-12T10:04:10")) == tick_of(
        ten_minutes, at("2026-11-12T09:56:00")
    )
    assert tick_of(ten_minutes, at("2026-11-12T10:06:00")) == int(
        at("2026-11-12T10:10:00").timestamp()
    )
    assert step_seconds(schedules.schedule(timedelta(milliseconds=10))) == 60


def test_lock_lives_two_steps_within_bounds() -> None:
    assert lock_seconds(schedules.crontab()) == 120
    assert lock_seconds(schedules.schedule(timedelta(minutes=10))) == 1200
    assert lock_seconds(schedules.schedule(timedelta(days=3))) == 24 * 3600


def test_tick_key() -> None:
    assert tick_key("numo9.jobs.purge_job_runs", 1794467820) == (
        "numo9:beat:numo9.jobs.purge_job_runs:1794467820"
    )


def test_local_store_claims_once_until_expiry() -> None:
    store = LocalTickStore()
    assert store.claim("k", ttl=60)
    assert not store.claim("k", ttl=60)
    assert store.claim("other", ttl=60)
    with mock.patch("numo9.jobs.beat.time.monotonic", return_value=10**9):
        assert store.claim("k", ttl=60)  # expired


def test_store_follows_the_broker() -> None:
    assert isinstance(beat.tick_store(), LocalTickStore)  # memory:// broker in tests
    beat._store = None
    with mock.patch.object(settings, "JOBS_BEAT_LOCK_URL", "redis://localhost:6390/0"):
        assert isinstance(beat.tick_store(), RedisTickStore)


@pytest.mark.skipif(not REDIS_URL, reason="NUMO9_TEST_REDIS_URL not set")
def test_redis_store_claims_once_with_expiry() -> None:
    assert REDIS_URL
    store = RedisTickStore(REDIS_URL)
    key = f"numo9:beat:test:{uuid.uuid4().hex}"
    assert store.claim(key, ttl=30)
    assert not store.claim(key, ttl=30)
    assert 0 < store.client.ttl(key) <= 30
    store.client.delete(key)


# ---- two beats → one execution -----------------------------------------------------------------


def _periodic(name: str, task: str, **kwargs: Any) -> PeriodicTask:
    cron, _ = CrontabSchedule.objects.get_or_create(
        minute="17", hour="7", day_of_week="*", day_of_month="*", month_of_year="*", timezone="UTC"
    )
    return PeriodicTask.objects.create(name=name, task=task, crontab=cron, **kwargs)


def _scheduler() -> LockedDatabaseScheduler:
    return LockedDatabaseScheduler(app=celery_app, lazy=True)


@pytest.fixture
def lock_store() -> Iterator[Any]:
    """The tick store the race runs on: real Redis when available, else the local store."""
    if REDIS_URL:
        store: Any = RedisTickStore(REDIS_URL)
        beat._store = store
        yield store
        for key in store.client.scan_iter("numo9:beat:tests.*"):
            store.client.delete(key)
    else:
        beat._store = LocalTickStore()
        yield beat._store


@pytest.mark.django_db
def test_two_beats_send_one_task(lock_store: Any) -> None:
    from numo9.jobs.tasks import ping

    name = f"tests.ping.{uuid.uuid4().hex[:8]}"
    task = _periodic(name, "numo9.jobs.ping")
    sent: list[Any] = []
    barrier = threading.Barrier(2)
    now = at("2026-11-12T07:17:01")

    def capture(*args: Any, **kwargs: Any) -> None:
        sent.append(args)

    def run_beat(drift: float) -> None:
        scheduler = _scheduler()
        entry = ModelEntry(task, app=celery_app)
        with mock.patch.object(scheduler.app, "now", return_value=now + timedelta(seconds=drift)):
            barrier.wait()
            scheduler.apply_async(entry, advance=False)

    with mock.patch.object(celery_app.tasks[ping.name].__class__, "apply_async", capture):
        beats = [threading.Thread(target=run_beat, args=(d,)) for d in (0.0, 4.5)]
        for thread in beats:
            thread.start()
        for thread in beats:
            thread.join(10)
    assert len(sent) == 1  # two beats, one execution


@pytest.mark.django_db
def test_next_tick_is_sent_again(lock_store: Any) -> None:
    from numo9.jobs.tasks import ping

    task = _periodic(f"tests.ping.{uuid.uuid4().hex[:8]}", "numo9.jobs.ping")
    scheduler = _scheduler()
    entry = ModelEntry(task, app=celery_app)
    with mock.patch.object(celery_app.tasks[ping.name].__class__, "apply_async") as send:
        for moment in ("2026-11-12T07:17:00", "2026-11-12T07:17:03", "2026-11-13T07:17:00"):
            with mock.patch.object(scheduler.app, "now", return_value=at(moment)):
                scheduler.apply_async(entry, advance=False)
    assert send.call_count == 2  # one per day's tick; the restart at :03 was skipped


@pytest.mark.django_db
def test_scheduled_platform_job_runs_once_even_without_the_lock(
    sent: list[dict[str, Any]],
) -> None:
    name = f"tests.nightly.{uuid.uuid4().hex[:8]}"
    task = _periodic(name, "tests.beat.nightly", kwargs='{"note": "n"}')
    now = at("2026-11-12T07:17:02")
    for _ in range(2):  # two beats whose lock store was lost (Redis restarted in between)
        beat._store = LocalTickStore()
        scheduler = _scheduler()
        with mock.patch.object(scheduler.app, "now", return_value=now):
            started = scheduler.apply_async(ModelEntry(task, app=celery_app), advance=False)
        assert started is not None and started.id
    runs = JobRun.platform_runs.filter(task_name="tests.beat.nightly")
    assert runs.count() == 1  # the idempotency key beat:<name>:<tick> let one run through
    run = runs.get()
    assert run.idempotency_key == (
        f"tests.beat.nightly:platform:beat:{name}:{int(at('2026-11-12T07:17:00').timestamp())}"
    )
    assert run.created_by is None
    assert len(sent) == 1
    deliver(nightly, sent[0])
    assert FIRES == ["n"]


@pytest.mark.django_db
def test_organisation_jobs_are_not_scheduled_directly() -> None:
    from tests.test_job_runtime import make_widgets

    task = _periodic(f"tests.org.{uuid.uuid4().hex[:8]}", make_widgets.name)
    with pytest.raises(ValueError, match="organisation job"):
        _scheduler().apply_async(ModelEntry(task, app=celery_app), advance=False)


# ---- configuration and the retention purge -----------------------------------------------------


def test_beat_configuration() -> None:
    assert celery_app.conf.beat_scheduler == "numo9.jobs.beat:LockedDatabaseScheduler"
    assert "django_celery_beat" in settings.INSTALLED_APPS
    entry = celery_app.conf.beat_schedule["numo9.jobs.purge_job_runs"]
    assert entry["task"] == "numo9.jobs.purge_job_runs"
    assert isinstance(entry["schedule"], schedules.crontab)


@pytest.mark.django_db
def test_purge_deletes_runs_finished_over_30_days_ago(sent: list[dict[str, Any]]) -> None:
    now = timezone.now()

    def run(key: str, status: str, finished: datetime | None) -> JobRun:
        created: JobRun = JobRun.platform_runs.create(
            task_name="tests.x", idempotency_key=key, status=status, finished_at=finished
        )
        return created

    old = now - RETENTION - timedelta(hours=1)
    run("old-done", JobStatus.SUCCEEDED, old)
    run("old-failed", JobStatus.FAILED, old)
    run("old-dead", JobStatus.DEAD, old)
    kept = [
        run("recent", JobStatus.SUCCEEDED, now - RETENTION + timedelta(hours=1)),
        run("still-retrying", JobStatus.RETRYING, None),
        run("still-queued", JobStatus.QUEUED, None),
    ]
    from numo9.jobs.runtime import start_job

    start_job(purge_job_runs, key="today")
    with mock.patch("numo9.jobs.tasks.PURGE_BATCH", 2):  # several batches
        assert deliver(purge_job_runs, sent[0]) == {"deleted": 3}
    left = set(JobRun.platform_runs.values_list("idempotency_key", flat=True))
    assert {k.idempotency_key for k in kept} <= left
    assert not left & {"old-done", "old-failed", "old-dead"}

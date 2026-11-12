"""Scheduled jobs: django-celery-beat with a Redis lock per schedule tick (A-08-T05).

Schedules live in the database (django-celery-beat's ``PeriodicTask``, edited in the Django
admin by platform staff; ``CELERY_BEAT_SCHEDULE`` entries in settings are written there at start).
``LockedDatabaseScheduler`` is the beat scheduler (``CELERY_BEAT_SCHEDULER``).

**One execution per tick, however many beats run.** Two beat processes (a deploy overlapping the
old one, a second server, a restart) each find the same schedule due. Before sending, the
scheduler takes the Redis lock ``numo9:beat:<schedule name>:<tick>`` with ``SET NX`` and an
expiry; only the beat that gets the lock sends the task, the other logs ``beat.tick_skipped``.

The **tick** is the time the schedule fired, rounded to the nearest step of the schedule — the
minute for crontab schedules, the interval for interval schedules (``every 10 minutes`` ticks at
:00, :10, …). Rounding to the nearest step lets the beats' clocks differ by up to half a step
(30 s for crontab schedules) and still agree on the tick.

**Second line: the job's idempotency key.** A scheduled *platform job* (``@platform_job``) is
started with ``start_job(key="beat:<schedule name>:<tick>")``, so even if the lock were lost (Redis
restarted between the two beats) the unique key lets only one run through. Organisation jobs are
not scheduled directly: a platform job fans out with ``start_job`` per organisation.

The lock store is the Redis server of ``JOBS_BEAT_LOCK_URL`` (default: the broker). With the
in-memory broker of tests and local runs, a process-local store is used (one beat only).
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import UTC, datetime
from typing import Any, Protocol

from celery import schedules
from django.conf import settings
from django_celery_beat.schedulers import DatabaseScheduler

logger = logging.getLogger("numo9.jobs.beat")

KEY_PREFIX = "numo9:beat"
MIN_LOCK_SECONDS = 120
MAX_LOCK_SECONDS = 24 * 60 * 60


class TickStore(Protocol):
    def claim(self, key: str, ttl: int) -> bool:
        """Set ``key`` unless it exists (atomically); True when this caller set it."""


class RedisTickStore:
    def __init__(self, url: str) -> None:
        import redis

        self.client = redis.Redis.from_url(url)

    def claim(self, key: str, ttl: int) -> bool:
        return bool(self.client.set(key, "1", nx=True, ex=ttl))


class LocalTickStore:
    """Process-local store: one beat only (tests, the in-memory broker)."""

    def __init__(self) -> None:
        self._keys: dict[str, float] = {}
        self._lock = threading.Lock()

    def claim(self, key: str, ttl: int) -> bool:
        now = time.monotonic()
        with self._lock:
            expires = self._keys.get(key)
            if expires is not None and expires > now:
                return False
            self._keys[key] = now + ttl
            return True


_store: TickStore | None = None


def tick_store() -> TickStore:
    global _store  # one client per process
    if _store is None:
        url = getattr(settings, "JOBS_BEAT_LOCK_URL", "") or str(settings.CELERY_BROKER_URL)
        redis = url.startswith(("redis://", "rediss://"))
        _store = RedisTickStore(url) if redis else LocalTickStore()
    return _store


def step_seconds(schedule: Any) -> int:
    """The schedule's tick step: its interval, else one minute (crontab, solar, clocked)."""
    if isinstance(schedule, schedules.schedule) and not isinstance(
        schedule, schedules.crontab | schedules.solar
    ):
        seconds = int(schedule.run_every.total_seconds())
        if seconds >= 1:
            return seconds
    return 60


def tick_of(schedule: Any, now: datetime) -> int:
    """The tick (Unix seconds) a schedule firing at ``now`` belongs to (nearest step)."""
    step = step_seconds(schedule)
    stamp = now.astimezone(UTC).timestamp()
    return int(round(stamp / step) * step)


def lock_seconds(schedule: Any) -> int:
    """How long a tick's lock lives: two steps, at least 2 minutes, at most a day."""
    return max(MIN_LOCK_SECONDS, min(MAX_LOCK_SECONDS, 2 * step_seconds(schedule)))


def tick_key(name: str, tick: int) -> str:
    return f"{KEY_PREFIX}:{name}:{tick}"


def claim_tick(name: str, schedule: Any, now: datetime) -> tuple[bool, int]:
    """Take the lock of this schedule's current tick: (True, tick) for the one beat that sends."""
    tick = tick_of(schedule, now)
    return tick_store().claim(tick_key(name, tick), lock_seconds(schedule)), tick


class _Started:
    """What ``apply_async`` returns for a scheduled job (beat logs its ``id``)."""

    def __init__(self, task_id: str) -> None:
        self.id = task_id


class LockedDatabaseScheduler(DatabaseScheduler):  # type: ignore[misc]  # untyped
    """django-celery-beat's scheduler + one execution per tick (see the module docstring)."""

    def apply_async(
        self, entry: Any, producer: Any = None, advance: bool = True, **kwargs: Any
    ) -> Any:
        from .runtime import JobTask, PlatformJobTask, start_job

        now = self.app.now()
        claimed, tick = claim_tick(entry.name, entry.schedule, now)
        fired_at = datetime.fromtimestamp(tick, UTC).isoformat()
        if not claimed:
            logger.info(
                "beat.tick_skipped %s %s",
                entry.name,
                fired_at,
                extra={"beat": {"schedule": entry.name, "task": entry.task, "tick": fired_at}},
            )
            if advance:
                self.reserve(entry)
            return None
        logger.info(
            "beat.tick %s %s",
            entry.name,
            fired_at,
            extra={"beat": {"schedule": entry.name, "task": entry.task, "tick": fired_at}},
        )
        task = self.app.tasks.get(entry.task)
        if isinstance(task, JobTask):
            raise ValueError(
                f"Schedule {entry.name}: {entry.task} is an organisation job; schedule a platform "
                "job that starts it for each organisation."
            )
        if not isinstance(task, PlatformJobTask):
            return super().apply_async(entry, producer=producer, advance=advance, **kwargs)
        entry = self.reserve(entry) if advance else entry
        try:
            run = start_job(task, key=f"beat:{entry.name}:{tick}", **dict(entry.kwargs or {}))
        finally:
            self._tasks_since_sync += 1
            if self.should_sync():
                self._do_sync()
        return _Started(run.celery_task_id)

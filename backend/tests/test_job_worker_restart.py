"""Worker restart (A-08-T09): kill the worker mid-task → the job completes once.

Integration test with real processes: a Celery worker (prefork pool, one child) on a real Redis
broker and the PostgreSQL test database runs ``tests.worker_restart.write_widget``, an atomic job
whose effect (one Widget) is written before it stops half-way and waits. The test then

1. **kills the worker's child process** (SIGKILL — out of memory, the hard time limit): Celery
   sees ``WorkerLostError`` and, with ``acks_late`` + ``reject_on_worker_lost``, puts the message
   back; the next child runs the job again;
2. **kills the whole worker** (main process and child) and starts a new one: the message was
   never acknowledged, so Redis hands it to the new worker once the visibility timeout has passed
   (shortened to a few seconds for the test).

Both times the job finishes and the effect exists **exactly once**: the killed try's transaction
was rolled back with its connection (which also released the run's advisory lock), and the run
shows two tries. Runs when ``NUMO9_TEST_REDIS_URL`` is set and the database is PostgreSQL (CI).
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from celery import Celery
from django.conf import settings
from django.db import connection

from numo9.jobs.models import JobRun, JobStatus
from numo9.jobs.queues import QUEUES
from numo9.jobs.runtime import start_job
from numo9.settings.env import redis_database
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.testapp.models import Widget
from tests.testapp.tasks import write_widget

REDIS_URL = os.environ.get("NUMO9_TEST_REDIS_URL")
BACKEND = Path(__file__).resolve().parents[1]
VISIBILITY_SECONDS = 3

pytestmark = [
    pytest.mark.skipif(not REDIS_URL, reason="NUMO9_TEST_REDIS_URL not set"),
    pytest.mark.skipif(connection.vendor != "postgresql", reason="needs PostgreSQL"),
    pytest.mark.django_db(transaction=True),  # the worker processes must see the rows
]


def _broker_url() -> str:
    assert REDIS_URL
    return redis_database(REDIS_URL, 9)  # a database of its own, flushed per test


def wait_for(condition: Callable[[], Any], timeout: float, what: str) -> Any:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(0.1)
    raise AssertionError(f"timed out after {timeout:.0f} s waiting for {what}")


class Worker:
    """A ``celery worker`` process with one prefork child, on the test database and broker."""

    def __init__(self, name: str, log: Path) -> None:
        db = settings.DATABASES["default"]
        env = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "numo9.settings.test",
            "DATABASE_URL": (
                f"postgres://{db['USER']}:{db['PASSWORD']}@{db['HOST'] or 'localhost'}:"
                f"{db['PORT'] or 5432}/{db['NAME']}"  # the test database
            ),
            "NUMO9_TEST_CELERY_BROKER_URL": _broker_url(),
            "CELERY_VISIBILITY_TIMEOUT": str(VISIBILITY_SECONDS),
        }
        self.log = log
        self.process = subprocess.Popen(  # noqa: S603  # fixed argument list
            [
                sys.executable,
                "-m",
                "celery",
                "-A",
                "numo9",
                "worker",
                "-Q",
                "default",
                "--pool",
                "prefork",
                "--concurrency",
                "1",
                "-n",
                f"{name}@%h",
                "--without-gossip",
                "--without-mingle",
                "--without-heartbeat",
                "--loglevel",
                "INFO",
            ],
            cwd=BACKEND,
            env=env,
            stdout=log.open("ab"),
            stderr=subprocess.STDOUT,
            start_new_session=True,  # its own process group: killed as a whole
        )

    def kill(self) -> None:
        """SIGKILL the main process and its child (nothing is acknowledged or cleaned up)."""
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(10)

    def stop(self) -> None:
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(15)
            except subprocess.TimeoutExpired:
                self.kill()


@pytest.fixture
def broker() -> Iterator[Celery]:
    """A Celery app that sends to the workers' Redis broker (the test process's app uses the
    in-memory one)."""
    import redis

    redis.Redis.from_url(_broker_url()).flushdb()
    sender = Celery("worker-restart-sender", broker=_broker_url())
    sender.conf.update(  # the routing of numo9.celery (settings § Background jobs)
        task_queues=QUEUES,
        task_default_exchange="numo9",
        task_serializer="json",
        accept_content=["json"],
    )
    yield sender
    sender.close()


@pytest.fixture
def workers(tmp_path: Path) -> Iterator[list[Worker]]:
    started: list[Worker] = []
    yield started
    for worker in started:
        worker.stop()
    for worker in started:
        sys.stdout.write(worker.log.read_text(errors="replace")[-4000:])  # shown on failure


def _start(org: Organisation, broker: Celery, control: Path) -> JobRun:
    """start_job, with the message sent through the workers' broker."""
    messages: list[dict[str, Any]] = []

    def capture(self: Any, args: Any = None, kwargs: Any = None, **options: Any) -> None:
        messages.append({"kwargs": kwargs, **options})

    with mock.patch("celery.app.task.Task.apply_async", capture):
        run = start_job(
            write_widget,
            organisation=org,
            key="restart",
            label="exactly once",
            control_dir=str(control),
        )
    [message] = messages
    broker.send_task(
        write_widget.name,
        kwargs=message["kwargs"],
        task_id=message["task_id"],
        queue=message["queue"],
    )
    return run


def _widgets(org: Organisation) -> int:
    with org_context(org):
        return Widget.objects.filter(label="exactly once").count()


def _finish_and_check(org: Organisation, run: JobRun, control: Path) -> None:
    (control / "go").write_text("")
    wait_for(
        lambda: JobRun.platform_runs.get(pk=run.pk).status == JobStatus.SUCCEEDED,
        60,
        "the job to finish",
    )
    run.refresh_from_db()
    assert run.attempts == 2  # the killed try and the one that finished
    assert run.result == {"label": "exactly once"}
    assert _widgets(org) == 1  # exactly-once effect


def test_child_killed_mid_task_completes_once(
    broker: Celery, workers: list[Worker], tmp_path: Path
) -> None:
    org = Organisation.objects.create(name="Restart Ltd.")
    control = tmp_path / "control"
    control.mkdir()
    workers.append(Worker("restart-child", tmp_path / "worker.log"))
    run = _start(org, broker, control)

    first = int(wait_for(lambda: _read(control / "started-1"), 60, "the first try"))
    assert JobRun.platform_runs.get(pk=run.pk).status == JobStatus.RUNNING
    os.kill(first, signal.SIGKILL)  # the pool child dies mid-task

    second = int(wait_for(lambda: _read(control / "started-2"), 60, "the second try"))
    assert second != first  # a new child took the redelivered message
    assert _widgets(org) == 0  # only the running try's uncommitted write: none committed yet
    _finish_and_check(org, run, control)


def test_whole_worker_killed_and_restarted_completes_once(
    broker: Celery, workers: list[Worker], tmp_path: Path
) -> None:
    org = Organisation.objects.create(name="Restart Two Ltd.")
    control = tmp_path / "control"
    control.mkdir()
    old = Worker("restart-old", tmp_path / "old.log")
    workers.append(old)
    run = _start(org, broker, control)

    wait_for(lambda: _read(control / "started-1"), 60, "the first try")
    old.kill()  # main process and child: the message stays unacknowledged in Redis
    assert _widgets(org) == 0
    time.sleep(VISIBILITY_SECONDS + 1)
    workers.append(Worker("restart-new", tmp_path / "new.log"))  # restores the unacked message

    wait_for(lambda: _read(control / "started-2"), 90, "the try on the restarted worker")
    _finish_and_check(org, run, control)


def _read(path: Path) -> str | None:
    try:
        return path.read_text() or None
    except FileNotFoundError:
        return None

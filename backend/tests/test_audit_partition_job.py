"""S-06-T04 — beat job pre-creating ``audit_event`` partitions 3 months ahead, with an alarm.

Acceptance: the partition for month + 3 exists. Run "four months later" (frozen clock), the job
creates the months up to that month + 3; run again it creates nothing; with a month that can't be
created, or rows sitting in the default partition, it reports ``ok: false``, names what's missing
and logs an ERROR (the alarm) — and keeps what it did create.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

import pytest
from django.conf import settings
from django.db import connection
from freezegun import freeze_time

from numo9.audit import partitions, tasks
from numo9.audit.service import record

pytestmark = pytest.mark.django_db


def _children() -> set[str]:
    with connection.cursor() as cursor:
        return set(partitions.partitions(cursor))


def _later(months: int) -> dt.datetime:
    month = partitions.add_months(partitions.month_start(dt.datetime.now(dt.UTC)), months)
    return dt.datetime(month.year, month.month, 2, 6, 3, tzinfo=dt.UTC)


def test_job_creates_through_month_plus_three() -> None:
    run_at = _later(4)
    target = partitions.partition_name(partitions.add_months(partitions.month_start(run_at), 3))
    assert target not in _children()
    with freeze_time(run_at):
        result = tasks.run_ensure_partitions()
    assert result["ok"] is True
    assert target in _children()
    assert target in result["created"]
    assert result["missing"] == []
    with freeze_time(run_at):
        assert tasks.run_ensure_partitions()["created"] == []  # idempotent


def test_missing_partition_raises_the_alarm(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    run_at = _later(6)
    target = partitions.partition_name(partitions.add_months(partitions.month_start(run_at), 3))
    real = partitions.create_month

    def failing(cursor: Any, month: dt.date) -> bool:
        if partitions.partition_name(month) == target:
            raise RuntimeError("disk full")
        return real(cursor, month)

    monkeypatch.setattr(partitions, "create_month", failing)
    with freeze_time(run_at), caplog.at_level(logging.ERROR, logger="numo9.audit.partitions"):
        result = tasks.run_ensure_partitions()
    assert result["ok"] is False
    assert result["missing"] == [target]
    assert any("need attention" in r.getMessage() for r in caplog.records)
    # The months before it were created and kept.
    assert partitions.partition_name(partitions.month_start(run_at)) in _children()


def test_rows_in_the_default_partition_raise_the_alarm(caplog: pytest.LogCaptureFixture) -> None:
    with freeze_time("2099-06-15T12:00:00Z"):
        record("test.partition.far", organisation=None, object_type="test", object_id="1")
    with caplog.at_level(logging.ERROR, logger="numo9.audit.partitions"):
        result = tasks.run_ensure_partitions()
    assert result["ok"] is False
    assert result["default_rows"] == 1


def test_job_is_scheduled_daily() -> None:
    entry = settings.CELERY_BEAT_SCHEDULE[tasks.JOB]
    assert entry["task"] == tasks.JOB
    assert tasks.ensure_partitions_job.name == tasks.JOB

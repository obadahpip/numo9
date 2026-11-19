"""Celery tasks of the audit app (discovered by Celery): ``audit_event`` partitions (S-06-T04).

Daily, the job keeps the current month through month + 3 in place (pg_partman's maintenance when
the extension is installed, plain DDL otherwise; ADR-0005 §3). The alarm: a missing month + 3 or
rows in the default partition are logged at ERROR (reported to Sentry) and the run's result says
``ok: false`` with what is missing — the job console shows it. The run never raises for the alarm,
so partitions it did create are kept.
"""

from __future__ import annotations

from typing import Any

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .partitions import ensure_partitions

JOB = "numo9.audit.ensure_partitions"


def run_ensure_partitions() -> dict[str, Any]:
    report = ensure_partitions()
    return {
        "ok": report.ok,
        "engine": report.engine,
        "created": report.created,
        "missing": report.missing,
        "default_rows": report.default_rows,
    }


@platform_job(name=JOB, queue=DEFAULT)
def ensure_partitions_job() -> dict[str, Any]:
    return run_ensure_partitions()

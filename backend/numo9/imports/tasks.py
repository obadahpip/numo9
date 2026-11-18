"""Celery tasks of the imports app (discovered by Celery): apply an import run (B-03-T08)."""

from __future__ import annotations

from typing import Any

from numo9.jobs.queues import REPORTS
from numo9.jobs.runtime import org_job, report_progress

from .models import ImportRun, ImportRunStatus
from .runs import apply_run

JOB = "numo9.imports.apply"


def run_apply(run: ImportRun, *, actor: Any = None) -> dict[str, Any]:
    """Import every row of ``run`` (each row in its own savepoint) and store the outcome."""
    ImportRun.objects.filter(pk=run.pk).update(status=ImportRunStatus.APPLYING)
    report = apply_run(run, actor=actor)
    return {"run": str(run.public_id), "counts": report.counts}


# The importer commits once, after every row (each row in a savepoint): a failed row leaves the
# others imported and is reported; a crash before the commit imports nothing, so a retry is safe.
@org_job(name=JOB, queue=REPORTS, max_retries=0)
def apply_import(*, org_id: str, run_id: str, user_id: int | None = None) -> dict[str, Any]:
    from numo9.accounts.models import User

    run = ImportRun.objects.get(public_id=run_id)
    actor = User.objects.filter(pk=user_id).first() if user_id else None
    report_progress(0, len(run.cells), "")
    outcome = run_apply(run, actor=actor)
    report_progress(len(run.cells), len(run.cells), "")
    return outcome

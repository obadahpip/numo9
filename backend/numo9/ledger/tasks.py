"""Background jobs of the ledger (discovered by Celery): automatic reversals (C-03-T09) and
recurring journals (C-04-T06), find & recode batches (C-07-T05)."""

from __future__ import annotations

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .recode_execute import recode_job
from .recurring import JOB as RECURRING_JOB
from .recurring import generate_all
from .reversals import auto_reversals_job


@platform_job(name=RECURRING_JOB, queue=DEFAULT)
def recurring_journals_job() -> int:
    return generate_all()


__all__ = ["auto_reversals_job", "recode_job", "recurring_journals_job"]

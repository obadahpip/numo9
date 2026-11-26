"""Background jobs of the purchases app (discovered by Celery): recurring bills (E-03-T02)."""

from __future__ import annotations

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .recurring_bills import JOB as RECURRING_BILLS
from .recurring_bills import generate_all


@platform_job(name=RECURRING_BILLS, queue=DEFAULT, atomic=False)
def recurring_bills() -> dict[str, int]:
    """Hourly (beat): every organisation's due recurring bills on its own date — each occurrence
    commits on its own (its run row makes it safe to repeat)."""
    return generate_all()

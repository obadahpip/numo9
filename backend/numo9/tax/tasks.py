"""Background jobs of the tax app (G-03a-T17)."""

from __future__ import annotations

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .filing_service import roll_forward

ROLL_FILING_PERIODS = "numo9.tax.roll_filing_periods"


@platform_job(name=ROLL_FILING_PERIODS, queue=DEFAULT, atomic=False)
def roll_filing_periods() -> dict[str, int]:
    """Nightly (beat): 24 months of filing periods ahead, closed / due soon / overdue recomputed,
    one event per period that becomes due soon or overdue (``filing_service.roll_forward``).
    Each registration is its own transaction (``atomic=False``)."""
    return roll_forward()

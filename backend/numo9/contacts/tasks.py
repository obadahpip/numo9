"""Background jobs of the contacts app (B-01-T08): exemption reminders, bulk statement runs
(D-07-T08)."""

from __future__ import annotations

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .exemptions import send_reminders
from .statement_runs import statement_run_job

EXEMPTION_REMINDERS = "numo9.contacts.exemption_reminders"


@platform_job(name=EXEMPTION_REMINDERS, queue=DEFAULT)
def exemption_reminders() -> dict[str, int]:
    """Daily (beat): expiry reminders for exemption certificates — 30 days before and once
    expired, each once per expiry date (``exemptions.send_reminders``)."""
    return send_reminders()


__all__ = ["exemption_reminders", "statement_run_job"]

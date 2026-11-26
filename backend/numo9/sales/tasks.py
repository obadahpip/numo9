"""Background jobs of the sales app: quote expiry (D-02-T05), recurring invoices (D-04-T05)."""

from __future__ import annotations

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .quotes import expire_due
from .recurring_invoices import JOB as RECURRING_INVOICES
from .recurring_invoices import generate_all

EXPIRE_QUOTES = "numo9.sales.expire_quotes"


@platform_job(name=EXPIRE_QUOTES, queue=DEFAULT)
def expire_quotes() -> int:
    """Hourly (beat): quotes past their expiry date in each organisation's time zone become
    Expired (``quotes.expire_due``) — organisations reach midnight at different UTC hours."""
    return expire_due()


@platform_job(name=RECURRING_INVOICES, queue=DEFAULT, atomic=False)
def recurring_invoices() -> dict[str, int]:
    """Hourly (beat): every organisation's due recurring invoices on its own date. Not atomic:
    each occurrence commits on its own (its run row makes it safe to repeat), so one failing
    template doesn't undo the others' invoices."""
    return generate_all()

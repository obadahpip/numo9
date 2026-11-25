"""Background jobs of the sales app (D-02-T05)."""

from __future__ import annotations

from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job

from .quotes import expire_due

EXPIRE_QUOTES = "numo9.sales.expire_quotes"


@platform_job(name=EXPIRE_QUOTES, queue=DEFAULT)
def expire_quotes() -> int:
    """Hourly (beat): quotes past their expiry date in each organisation's time zone become
    Expired (``quotes.expire_due``) — organisations reach midnight at different UTC hours."""
    return expire_due()

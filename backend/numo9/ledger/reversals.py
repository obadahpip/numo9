"""Automatic reversals (C-03-T09): an accrual dated 30 June with ``auto_reverse_on`` = 1 July is
reversed by itself on 1 July.

``post_due_reversals()`` — the hourly beat job ``numo9.ledger.auto_reversals``: for every
organisation, each posted journal whose ``auto_reverse_on`` has come (the organisation's own
date) and that isn't reversed yet is reversed with ``reverse()`` (C-02-T10) dated
``auto_reverse_on``, by the system. **Idempotent**: ``reverse()`` locks the journal row and a
reversed journal can't be reversed again, so a run after a worker restart, or two runs at once,
post each reversal exactly once. A reversal refused (its date was locked since the journal was
saved) is skipped and logged; it is tried again on the next run.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.audit import models as audit_models
from numo9.audit import service as audit
from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job
from numo9.orgsettings.locks import local_date
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import JournalEntry, JournalStatus, LedgerError
from .sequence import format_journal_number

logger = logging.getLogger(__name__)
JOB = "numo9.ledger.auto_reversals"


def due(organisation: Organisation, today: dt.date | None = None) -> list[JournalEntry]:
    """The organisation's posted journals whose automatic reversal is due (in context)."""
    today = today or local_date(organisation, timezone.now())
    return list(
        JournalEntry.objects.filter(
            status=JournalStatus.POSTED,
            auto_reverse_on__isnull=False,
            auto_reverse_on__lte=today,
            reversed_by__isnull=True,
        ).order_by("auto_reverse_on", "pk")
    )


def _exception(entry: Any, number: str, error: Exception) -> None:
    """An automatic reversal that couldn't be posted (its date locked or closed, C-06-T06) is an
    exception: audited once per entry and reason (``ledger.journalentry.auto_reversal_skipped``)
    and counted by the period-close checklist until it is posted."""
    detail = getattr(error, "detail", None)
    code = getattr(error, "code", "") or (
        detail.get("code", "") if isinstance(detail, dict) else getattr(error, "default_code", "")
    )
    code = str(code)
    seen = audit_models.AuditEvent.objects.filter(
        action="ledger.journalentry.auto_reversal_skipped",
        object_id=str(entry.public_id),
        meta__code=code,
    ).exists()
    if seen:
        return
    audit.record(
        "ledger.journalentry.auto_reversal_skipped",
        obj=entry,
        meta={"number": number, "code": code, "reason": str(error)[:500]},
        actor=None,
    )


def post_due_reversals(now: dt.datetime | None = None) -> int:
    """Reverse every due journal of every organisation; the number of reversals posted."""
    from .services import reverse

    now = now or timezone.now()
    posted = 0
    for organisation in Organisation.objects.order_by("pk").iterator():
        with org_context(organisation):
            for entry in due(organisation, local_date(organisation, now)):
                number = format_journal_number(organisation, entry.number)
                try:
                    reversal = reverse(
                        entry,
                        date=entry.auto_reverse_on,
                        narration=_("Automatic reversal of %(number)s") % {"number": number},
                        user=None,
                    )
                except LedgerError as error:  # reversed meanwhile, or its date locked since
                    logger.warning("auto-reversal of %s skipped: %s", number, error)
                    _exception(entry, number, error)
                    continue
                except Exception as error:  # a lock or closed period (409s are APIExceptions)
                    logger.warning("auto-reversal of %s skipped: %s", number, error)
                    _exception(entry, number, error)
                    continue
                audit.record(
                    "ledger.journalentry.auto_reversed",
                    obj=entry,
                    changes={"status": [JournalStatus.POSTED, JournalStatus.REVERSED]},
                    meta={
                        "number": number,
                        "reversed_by": format_journal_number(organisation, reversal.number),
                        "date": entry.auto_reverse_on.isoformat()
                        if entry.auto_reverse_on
                        else None,
                    },
                    actor=None,
                )
                posted += 1
    return posted


@platform_job(name=JOB, queue=DEFAULT)
def auto_reversals_job() -> int:
    return post_due_reversals()

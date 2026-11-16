"""Lock impact preview (A-05-T07): what a lock date would leave unfinished before it.

Before someone sets or moves a lock date, the settings page shows how many records **not yet
posted** are dated on or before the new date — after locking they can't be posted any more
without moving the lock back. Each module registers what counts (``register_impact``):

- ``gl`` — journal entries in draft or awaiting approval (C-02);
- ``ar``, ``ap``, ``bank``, ``payroll``, ``tax`` — added by their modules (draft invoices, bills,
  unreconciled lines, unposted pay runs…) as they arrive.

A module's preview includes the GL items too, since the GL lock applies to every module's
postings only when it is the GL lock: ``impact(org, "ar", date)`` counts AR items; ``impact(org,
"gl", date)`` counts GL items **and** every module's (the GL lock stops them all).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import LockModule

Counter = Callable[[Organisation, dt.date], int]


@dataclass(frozen=True)
class ImpactSource:
    module: str
    kind: str
    label: Promise | str
    count: Counter


_sources: list[ImpactSource] = []


def register_impact(module: str, kind: str, label: Promise | str, count: Counter) -> ImpactSource:
    if module not in LockModule.values:
        raise ValueError(f"Unknown lock module {module!r}")
    source = ImpactSource(module, kind, label, count)
    _sources[:] = [s for s in _sources if (s.module, s.kind) != (module, kind)] + [source]
    return source


@dataclass(frozen=True)
class ImpactItem:
    module: str
    kind: str
    label: str
    count: int


def impact(organisation: Organisation, module: str, date: dt.date) -> list[ImpactItem]:
    if module not in LockModule.values:
        raise ValueError(f"Unknown lock module {module!r}")
    wanted = [s for s in _sources if module == LockModule.GL or s.module == module]
    with org_context(organisation):
        return [
            ImpactItem(s.module, s.kind, str(s.label), s.count(organisation, date)) for s in wanted
        ]


def _unposted_journals(organisation: Organisation, date: dt.date) -> int:
    from numo9.ledger.models import JournalEntry, JournalStatus

    return int(
        JournalEntry.objects.filter(
            date__lte=date,
            status__in=[JournalStatus.DRAFT, JournalStatus.AWAITING_APPROVAL],
            deleted_at__isnull=True,
        ).count()
    )


register_impact(
    LockModule.GL,
    "journals",
    _("Journal entries not posted (draft or awaiting approval)"),
    _unposted_journals,
)

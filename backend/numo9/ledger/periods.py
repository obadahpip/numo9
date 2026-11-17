"""Lock-date and period hook of the posting engine (C-02-T07).

``assert_can_post(organisation, date, user, module="gl")`` runs before anything is written:

1. **lock dates** (A-05): the module's own lock and the general-ledger lock —
   ``numo9.orgsettings.locks.assert_not_locked`` raises ``LockedPeriod`` (409 ``lock.violation``)
   naming the lock: "The General ledger lock date is 2026-03-31 (everyone): …". A posting from a
   sales invoice passes ``module="ar"``, from a bill ``"ap"``…; a manual journal ``"gl"``;
2. **closed periods** (C-06 year-end close): every registered period check —
   ``register_period_check(check)`` where ``check(organisation, date) -> ClosedPeriod | None``.
   C-06 registers the real one; until then none is registered and every period is open (the
   stub). A closed period raises ``PeriodClosed`` (409 ``ledger.period.closed``) naming it.

The date is the entry's accounting date (organisation-local). The person decides the adviser
level of the lock (advisers may post past an *advisers only* lock); ``None`` is a system job,
stopped like everyone.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.exceptions import APIException

from numo9.orgsettings.locks import assert_not_locked
from numo9.orgsettings.models import LockModule
from numo9.tenancy.models import Organisation


@dataclass(frozen=True)
class ClosedPeriod:
    """A closed accounting period: ``label`` names it ("Fiscal year 2025")."""

    start: dt.date
    end: dt.date
    label: str

    def message(self) -> str:
        return _(
            "%(period)s (%(start)s to %(end)s) is closed: nothing can be posted in it. Date the "
            "entry after %(end)s, or ask an adviser to reopen the period."
        ) % {"period": self.label, "start": self.start.isoformat(), "end": self.end.isoformat()}

    def as_dict(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(), "label": self.label}


class PeriodClosed(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "ledger.period.closed"

    def __init__(self, period: ClosedPeriod) -> None:
        self.period = period
        super().__init__(
            detail={
                "detail": period.message(),
                "code": "ledger.period.closed",
                "period": period.as_dict(),
            }
        )


PeriodCheck = Callable[[Organisation, dt.date], ClosedPeriod | None]

_checks: list[PeriodCheck] = []


def register_period_check(check: PeriodCheck) -> PeriodCheck:
    """Register ``check(organisation, date) -> ClosedPeriod | None`` (C-06); idempotent."""
    if check not in _checks:
        _checks.append(check)
    return check


def unregister_period_check(check: PeriodCheck) -> None:
    if check in _checks:
        _checks.remove(check)


def closed_period(organisation: Organisation, date: dt.date) -> ClosedPeriod | None:
    """The closed period containing ``date``, or None (no check registered → open)."""
    for check in _checks:
        found = check(organisation, date)
        if found is not None:
            return found
    return None


def assert_can_post(
    organisation: Organisation,
    date: dt.date,
    user: Any = None,
    module: str = LockModule.GL,
) -> None:
    """Refuse a posting dated in a locked or closed period (lock first, then period)."""
    assert_not_locked(organisation, module, date, user)
    period = closed_period(organisation, date)
    if period is not None:
        raise PeriodClosed(period)

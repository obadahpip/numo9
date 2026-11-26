"""Deadlines widget service (K-05-T04): the organisation's tax and filing due dates with their
status, from the G-03a filing periods (payroll remittances register later, N-07).

``deadlines(organisation, today)`` answers the widget:

- ``items`` — every **unfiled** period that has ended (its return can be filed now) and, for each
  registration, the **next** period not ended yet; sorted by return due date (then payment due
  date), at most ``limit``;
- each item: the registration (type and display number), the period, the return and payment due
  dates, ``days`` until the return is due (negative once past) and ``status``:
  ``overdue`` (return due date passed), ``due_soon`` (due within 14 days,
  ``filing_service.DUE_SOON_DAYS``) or ``upcoming`` — the **same rule** as the nightly
  roll-forward (``filing_service.attention``), so the widget and the notifications agree;
- ``next`` — the first item (the next due period), ``overdue`` / ``due_soon`` — counts.

Filed and paid periods never appear. ``today`` is the organisation's (its time zone) by default.
Other modules add deadlines with ``register_provider(name, provider)``; a provider returns
``Deadline`` rows for the organisation (payroll remittances, T4 …).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext as _

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

OVERDUE = "overdue"
DUE_SOON = "due_soon"
UPCOMING = "upcoming"
STATUS_ORDER = {OVERDUE: 0, DUE_SOON: 1, UPCOMING: 2}
LIMIT = 10


@dataclass(frozen=True)
class Deadline:
    kind: str  # "gst_hst", "qst", "payroll_remittance" …
    label: str  # "GST/HST 123456782RT0001"
    period_start: dt.date | None
    period_end: dt.date | None
    due_date: dt.date
    payment_due_date: dt.date | None
    status: str
    href: str

    def as_dict(self, today: dt.date) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "due_date": self.due_date.isoformat(),
            "payment_due_date": (
                self.payment_due_date.isoformat() if self.payment_due_date else None
            ),
            "days": (self.due_date - today).days,
            "status": self.status,
            "href": self.href,
        }


Provider = Callable[[Organisation, dt.date], list[Deadline]]
_providers: dict[str, Provider] = {}


def register_provider(name: str, provider: Provider) -> None:
    _providers[name] = provider


def unregister_provider(name: str) -> None:
    _providers.pop(name, None)


def status_of(period: Any, today: dt.date) -> str:
    """``overdue`` / ``due_soon`` (``filing_service.attention``), else ``upcoming``."""
    from numo9.tax.filing_service import attention

    return attention(period, today) or UPCOMING


def filing_deadlines(organisation: Organisation, today: dt.date) -> list[Deadline]:
    """GST/HST and QST returns from the G-03a periods (the built-in provider)."""
    from numo9.orgsettings.models import TaxRegistration
    from numo9.tax.models import LOCKED_PERIOD_STATUSES, FilingPeriod

    found: list[Deadline] = []
    with org_context(organisation):
        registrations = [r for r in TaxRegistration.objects.all() if r.files_returns]
        href = f"/o/{organisation.public_id}/settings/tax/registrations"
        for registration in registrations:
            unfiled = FilingPeriod.objects.filter(registration=registration).exclude(
                status__in=LOCKED_PERIOD_STATUSES
            )
            ended = list(unfiled.filter(end__lt=today).order_by("start"))
            upcoming = unfiled.filter(end__gte=today).order_by("start").first()
            kind = "gst_hst" if registration.type == "rt" else str(registration.type)
            name = _("GST/HST") if kind == "gst_hst" else _("QST")
            label = f"{name} {registration.display_number}"
            for period in [*ended, *([upcoming] if upcoming else [])]:
                found.append(
                    Deadline(
                        kind=kind,
                        label=label,
                        period_start=period.start,
                        period_end=period.end,
                        due_date=period.due_date,
                        payment_due_date=period.payment_due_date,
                        status=status_of(period, today),
                        href=f"{href}/{registration.public_id}/filing",
                    )
                )
    return found


register_provider("filing", filing_deadlines)


def deadlines(
    organisation: Organisation, today: dt.date | None = None, *, limit: int = LIMIT
) -> dict[str, Any]:
    from numo9.contacts.models import organisation_today

    day = today or organisation_today(organisation)
    items: list[Deadline] = []
    for provider in list(_providers.values()):
        items.extend(provider(organisation, day))
    items.sort(key=lambda d: (d.due_date, d.payment_due_date or d.due_date, d.label))
    shown = [item.as_dict(day) for item in items[:limit]]
    return {
        "as_of": day.isoformat(),
        "items": shown,
        "next": shown[0] if shown else None,
        "overdue": sum(1 for item in items if item.status == OVERDUE),
        "due_soon": sum(1 for item in items if item.status == DUE_SOON),
        "empty_message": "" if items else _("No tax or filing deadline is coming up."),
    }

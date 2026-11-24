"""Filing periods in the database (G-03a-T10…T12): the generator (``filing.generate_periods``)
applied to a registration's stored periods, under the rules of ``docs/specs/filing-cycles.md``.

``regenerate(registration, from_date)`` (G-03a-T10) — from ``from_date`` on (the registration
start by default), in one transaction:

- **filed and paid periods are never touched** (deleted, moved or re-dated);
- an unfiled period **crossing** ``from_date`` is cut to end the day before (a ``stub``, its due
  dates recomputed);
- every other unfiled period from ``from_date`` on is deleted, except the custom (out-of-cycle)
  ones, and the generator fills the dates from ``from_date`` to the horizon (the registration's
  stop date, else 24 months from today) around the periods kept;
- the registration's periods are numbered again 1, 2, 3… in date order and get their status
  (``closed`` once ended, else ``open``; filed and paid unchanged).

Tax postings are never moved: a posting belongs to the period containing its date
(``period_for``, G-03a-T14), so they follow the new periods by themselves.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable
from typing import Any

from dateutil.relativedelta import relativedelta
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from .filing import ONE_DAY, Cycle, Period, Span, due_dates, generate_periods
from .holidays import jurisdictions_for
from .models import FilingCycle, FilingPeriod, PeriodKind, PeriodStatus, TaxError

HORIZON_MONTHS = 24


def _settings(registration: Any) -> Any:
    from numo9.orgsettings.service import get_settings

    return get_settings(registration.organisation)


def horizon(registration: Any, today: dt.date | None = None) -> dt.date:
    if registration.stop_date:
        stop: dt.date = registration.stop_date
        return stop
    today = today or timezone.localdate()
    last = today + relativedelta(months=HORIZON_MONTHS)
    return last + relativedelta(day=31)


def cycles_of(registration: Any) -> list[Cycle]:
    return [
        Cycle(c.frequency, c.effective_from)
        for c in FilingCycle.objects.filter(registration=registration).order_by("effective_from")
    ]


def dated(registration: Any, period: Period, settings: Any) -> dict[str, Any]:
    """The due dates of a generated period for this registration."""
    due, payment = due_dates(
        period.end,
        period.frequency or _frequency_at(registration, period.start),
        structure=settings.structure,
        fye=(int(settings.fye_month), int(settings.fye_day)),
        jurisdictions=jurisdictions_for(registration.type),
    )
    return {"due_date": due, "payment_due_date": payment}


def _frequency_at(registration: Any, day: dt.date) -> str:
    cycles = cycles_of(registration)
    current = cycles[0].frequency if cycles else "quarterly"
    for cycle in cycles:
        if cycle.effective_from <= day:
            current = cycle.frequency
    return current


def _status(end: dt.date, today: dt.date) -> str:
    return PeriodStatus.CLOSED if end < today else PeriodStatus.OPEN


def renumber(registration: Any, today: dt.date | None = None) -> None:
    today = today or timezone.localdate()
    periods = FilingPeriod.objects.filter(registration=registration).order_by("start")
    for n, period in enumerate(periods, start=1):
        fields = []
        if period.sequence_no != n:
            period.sequence_no = n
            fields.append("sequence_no")
        if not period.is_locked and period.status != _status(period.end, today):
            period.status = _status(period.end, today)
            fields.append("status")
        if fields:
            period.save(update_fields=fields)


def _fill(
    registration: Any,
    start: dt.date,
    end: dt.date,
    occupied: Iterable[FilingPeriod],
    settings: Any,
    today: dt.date,
) -> list[FilingPeriod]:
    """Generate the periods of ``start``…``end`` around the ``occupied`` ones and save them."""
    cycles = cycles_of(registration)
    if not cycles:
        raise TaxError(
            _("Choose the registration's filing frequency first."),
            code="tax.filing.no_cycle",
        )
    taken = sorted(occupied, key=lambda p: p.start)
    spans = [Span(p.start, p.end) for p in taken if p.end >= start and p.start <= end]
    generated = generate_periods(
        cycles, int(settings.fye_month), int(settings.fye_day), start, end, spans
    )
    created = []
    for period in generated:
        if period.kind == "custom":  # one of the periods kept
            continue
        item = FilingPeriod(
            organisation=registration.organisation,
            registration=registration,
            start=period.start,
            end=period.end,
            kind=PeriodKind.REGULAR if period.kind == "regular" else PeriodKind.STUB,
            frequency=period.frequency,
            sequence_no=0,
            status=_status(period.end, today),
            **dated(registration, period, settings),
        )
        item.save()
        created.append(item)
    return created


def regenerate(
    registration: Any, from_date: dt.date | None = None, *, today: dt.date | None = None
) -> list[FilingPeriod]:
    """Rebuild the unfiled periods from ``from_date`` (module docstring); returns them all."""
    from numo9.tenancy.context import org_context

    today = today or timezone.localdate()
    with org_context(registration.organisation), transaction.atomic():
        if registration.start_date is None:
            raise TaxError(
                _("Enter the registration's effective date first."),
                code="tax.filing.no_start",
            )
        start = max(from_date or registration.start_date, registration.start_date)
        end = horizon(registration, today)
        settings = _settings(registration)
        periods = FilingPeriod.objects.select_for_update().filter(registration=registration)
        crossing = periods.filter(start__lt=start, end__gte=start).first()
        if crossing is not None and not crossing.is_locked:
            crossing.end = start - ONE_DAY
            crossing.kind = (
                PeriodKind.CUSTOM if crossing.kind == PeriodKind.CUSTOM else PeriodKind.STUB
            )
            crossing.__dict__.update(
                dated(
                    registration,
                    Period(crossing.start, crossing.end, crossing.kind, crossing.frequency),
                    settings,
                )
            )
            crossing.save()
        elif crossing is not None:  # a filed period: the new periods start after it
            start = crossing.end + ONE_DAY
        periods.filter(start__gte=start).exclude(kind=PeriodKind.CUSTOM).exclude(
            status__in=(PeriodStatus.FILED, PeriodStatus.PAID)
        ).delete()
        periods.filter(start__gt=end).exclude(
            status__in=(PeriodStatus.FILED, PeriodStatus.PAID)
        ).delete()
        kept = list(FilingPeriod.objects.filter(registration=registration, end__gte=start))
        if start <= end:
            _fill(registration, start, end, kept, settings, today)
        renumber(registration, today)
        return list(FilingPeriod.objects.filter(registration=registration).order_by("start"))

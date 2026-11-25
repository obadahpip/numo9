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

``switch_frequency(registration, frequency, effective_from, …)`` (G-03a-T11) — validates the
change (``validate_switch``), records the new ``FilingCycle`` and regenerates from its date:

- the effective date may not fall **inside a filed or paid period** (``tax.filing.inside_filed``)
  nor before the registration starts;
- a switch that doesn't start on a financial year start needs the CRA / Revenu Québec
  **approval reference** (``tax.filing.approval_required`` — the API's 422), and is returned
  with a warning (``tax.filing.not_fiscal_year_start``) even with one.

``add_custom_period(registration, start, end, …)`` (G-03a-T12) — an out-of-cycle period: it may
not overlap a filed or paid period (``tax.filing.custom_overlaps_filed``) nor another custom
period; the unfiled periods it overlaps are removed (one crossing its start is cut to a stub)
and the regular periods realign from the day after its end. ``delete_custom_period`` removes an
unfiled one and regenerates its dates.

Tax postings are never moved: a posting belongs to the period containing its date
(``period_for``, G-03a-T14), so they follow the new periods by themselves.

``period_for(registration, date)`` (G-03a-T14) — the one period a document dated ``date``
belongs to (tax reports and returns group by it): ``None`` before the registration starts, after
it stops, or while it has no filing frequency; a date past the stored periods (beyond the
24-month horizon) extends them to the end of that date's period first, so every date of the
registration has exactly one period. ``periods_for(registration, dates)`` resolves many dates
with one query per extension.
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


# ---- switch validation (G-03a-T11) ------------------------------------------------------------


def is_fiscal_year_start(settings: Any, day: dt.date) -> bool:
    from numo9.orgsettings.fiscal import fiscal_year

    return fiscal_year(settings, day)[0] == day


def validate_switch(
    registration: Any, frequency: str, effective_from: dt.date, approval_ref: str = ""
) -> list[dict[str, str]]:
    """Refuse an invalid switch (``TaxError``); returns the warnings of a valid one."""
    from .filing import MONTHS

    if frequency not in MONTHS:
        raise TaxError(_("Choose monthly, quarterly or annual."), code="tax.filing.frequency")
    start = registration.start_date
    if start is not None and effective_from < start:
        raise TaxError(
            _("The change can't take effect before the registration starts (%(start)s).")
            % {"start": start.isoformat()},
            code="tax.filing.before_start",
        )
    filed = FilingPeriod.objects.filter(
        registration=registration,
        start__lte=effective_from,
        end__gte=effective_from,
        status__in=(PeriodStatus.FILED, PeriodStatus.PAID),
    ).first()
    if filed is not None and filed.start != effective_from:
        raise TaxError(
            _(
                "%(date)s is inside the filed period %(period)s: a filed period can't change. "
                "Choose a date after %(end)s."
            )
            % {
                "date": effective_from.isoformat(),
                "period": str(filed),
                "end": filed.end.isoformat(),
            },
            code="tax.filing.inside_filed",
        )
    if filed is not None:  # starts on a filed period's first day: it would be regenerated
        raise TaxError(
            _("%(period)s is filed: the change must take effect after it.")
            % {"period": str(filed)},
            code="tax.filing.inside_filed",
        )
    if FilingCycle.objects.filter(
        registration=registration, effective_from=effective_from
    ).exists():
        raise TaxError(
            _("A filing frequency already takes effect on %(date)s.")
            % {"date": effective_from.isoformat()},
            code="tax.filing.duplicate",
        )
    warnings: list[dict[str, str]] = []
    has_cycles = FilingCycle.objects.filter(registration=registration).exists()
    if has_cycles and not is_fiscal_year_start(_settings(registration), effective_from):
        if not approval_ref.strip():
            raise TaxError(
                _(
                    "A change during the financial year needs the CRA or Revenu Québec approval "
                    "reference."
                ),
                code="tax.filing.approval_required",
            )
        warnings.append(
            {
                "code": "tax.filing.not_fiscal_year_start",
                "message": _(
                    "%(date)s isn't the start of your financial year. The switch is saved with "
                    "approval %(ref)s."
                )
                % {"date": effective_from.isoformat(), "ref": approval_ref.strip()},
            }
        )
    return warnings


def switch_frequency(
    registration: Any,
    frequency: str,
    effective_from: dt.date,
    *,
    approval_ref: str = "",
    approval_date: dt.date | None = None,
    note: str = "",
    user: Any = None,
    today: dt.date | None = None,
) -> tuple[list[FilingPeriod], list[dict[str, str]]]:
    """Validate, record the cycle and regenerate (module docstring)."""
    from numo9.tenancy.context import org_context

    with org_context(registration.organisation), transaction.atomic():
        warnings = validate_switch(registration, frequency, effective_from, approval_ref)
        FilingCycle.objects.create(
            organisation=registration.organisation,
            registration=registration,
            frequency=frequency,
            effective_from=effective_from,
            approval_ref=approval_ref.strip(),
            approval_date=approval_date,
            note=note,
            created_by=user if getattr(user, "is_authenticated", False) else None,
        )
        return regenerate(registration, effective_from, today=today), warnings


# ---- custom periods (G-03a-T12) ---------------------------------------------------------------


def add_custom_period(
    registration: Any,
    start: dt.date,
    end: dt.date,
    *,
    note: str = "",
    today: dt.date | None = None,
) -> list[FilingPeriod]:
    """Insert an out-of-cycle period (module docstring); returns every period."""
    from numo9.tenancy.context import org_context

    with org_context(registration.organisation), transaction.atomic():
        if end < start:
            raise TaxError(_("The period ends before it starts."), code="tax.filing.custom_dates")
        if registration.start_date is not None and start < registration.start_date:
            raise TaxError(
                _("The period starts before the registration (%(start)s).")
                % {"start": registration.start_date.isoformat()},
                code="tax.filing.before_start",
            )
        periods = FilingPeriod.objects.select_for_update().filter(registration=registration)
        overlapping = periods.filter(start__lte=end, end__gte=start)
        filed = overlapping.filter(status__in=(PeriodStatus.FILED, PeriodStatus.PAID)).first()
        if filed is not None:
            raise TaxError(
                _("The period overlaps the filed period %(period)s.") % {"period": str(filed)},
                code="tax.filing.custom_overlaps_filed",
            )
        other = overlapping.filter(kind=PeriodKind.CUSTOM).first()
        if other is not None:
            raise TaxError(
                _("The period overlaps the out-of-cycle period %(period)s.")
                % {"period": str(other)},
                code="tax.filing.custom_overlap",
            )
        settings = _settings(registration)
        crossing = periods.filter(start__lt=start, end__gte=start).first()
        if crossing is not None:
            crossing.end = start - ONE_DAY
            crossing.kind = PeriodKind.STUB
            crossing.__dict__.update(
                dated(
                    registration,
                    Period(crossing.start, crossing.end, "stub", crossing.frequency),
                    settings,
                )
            )
            crossing.save()
        periods.filter(start__gte=start).exclude(kind=PeriodKind.CUSTOM).exclude(
            status__in=(PeriodStatus.FILED, PeriodStatus.PAID)
        ).delete()
        frequency = _frequency_at(registration, start)
        FilingPeriod.objects.create(
            organisation=registration.organisation,
            registration=registration,
            start=start,
            end=end,
            kind=PeriodKind.CUSTOM,
            frequency=frequency,
            sequence_no=0,
            note=note,
            **dated(registration, Period(start, end, "custom", frequency), settings),
        )
        return regenerate(registration, start, today=today)


def delete_custom_period(
    period: FilingPeriod, *, today: dt.date | None = None
) -> list[FilingPeriod]:
    """Remove an unfiled out-of-cycle period; the regular periods are regenerated over it."""
    from numo9.tenancy.context import org_context

    registration = period.registration
    with org_context(registration.organisation), transaction.atomic():
        if period.kind != PeriodKind.CUSTOM or period.is_locked:
            raise TaxError(
                _("Only an out-of-cycle period that isn't filed can be deleted."),
                code="tax.filing.custom_locked",
            )
        start = period.start
        period.delete()
        return regenerate(registration, start, today=today)


# ---- document → period (G-03a-T14) ------------------------------------------------------------


def _covered(registration: Any, day: dt.date) -> bool:
    """Is ``day`` a date the registration files for (started, not stopped, has a frequency)?"""
    start, stop = registration.start_date, registration.stop_date
    if start is None or day < start or (stop is not None and day > stop):
        return False
    return FilingCycle.objects.filter(registration=registration).exists()


def _extend(registration: Any, day: dt.date, today: dt.date) -> None:
    """Add the periods from the last stored one up to the period containing ``day``."""
    from numo9.tenancy.context import org_context

    with org_context(registration.organisation), transaction.atomic():
        periods = FilingPeriod.objects.select_for_update().filter(registration=registration)
        last = periods.order_by("-end").first()
        start = last.end + ONE_DAY if last is not None else registration.start_date
        if day < start:  # another transaction extended them meanwhile
            return
        settings = _settings(registration)
        # A regular period is at most a year long: a year past ``day`` ends its period.
        end = day + relativedelta(years=1)
        generated = generate_periods(
            cycles_of(registration), int(settings.fye_month), int(settings.fye_day), start, end
        )
        through = next(p.end for p in generated if p.start <= day <= p.end)
        _fill(registration, start, through, [], settings, today)
        renumber(registration, today)


def period_for(
    registration: Any, day: dt.date, *, today: dt.date | None = None
) -> FilingPeriod | None:
    """The filing period a document dated ``day`` belongs to (module docstring)."""
    return periods_for(registration, [day], today=today)[day]


def periods_for(
    registration: Any, days: Iterable[dt.date], *, today: dt.date | None = None
) -> dict[dt.date, FilingPeriod | None]:
    """``period_for`` for many dates: {date: its period, or None outside the registration}."""
    from numo9.tenancy.context import org_context

    today = today or timezone.localdate()
    wanted = sorted(set(days))
    out: dict[dt.date, FilingPeriod | None] = dict.fromkeys(wanted)
    with org_context(registration.organisation):
        inside = [d for d in wanted if _covered(registration, d)]
        if not inside:
            return out
        stored = FilingPeriod.objects.filter(registration=registration)
        last = stored.order_by("-end").first()
        if last is None or inside[-1] > last.end:
            _extend(registration, inside[-1], today)
        periods = list(stored.filter(end__gte=inside[0], start__lte=inside[-1]).order_by("start"))
        index = 0
        for d in inside:
            while index < len(periods) and periods[index].end < d:
                index += 1
            if index < len(periods) and periods[index].start <= d:
                out[d] = periods[index]
    return out

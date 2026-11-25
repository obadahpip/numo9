"""Filing periods in the database (G-03a-T10…T12): the generator (``filing.generate_periods``)
applied to a registration's stored periods, under the rules of ``docs/specs/filing-cycles.md``.

``regenerate(registration, from_date)`` (G-03a-T10) — from ``from_date`` on (the registration
start by default), in one transaction:

- **filed and paid periods are never touched** (deleted, moved or re-dated);
- an unfiled period **crossing** ``from_date`` is cut to end the day before (a ``stub``, its due
  dates recomputed);
- every other unfiled period from ``from_date`` on is deleted, except the custom (out-of-cycle)
  ones, and the generator fills the dates from ``from_date`` to the horizon (the registration's
  stop date, else 24 months from today — the period containing that day is made whole, the
  horizon never cuts a period) around the periods kept;
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

``apply_change(registration, change, user=…)`` runs one change — ``{"action": "switch",
"frequency", "effective_from", "approval_ref", "approval_date", "note"}``, ``{"action":
"custom", "start", "end", "note"}`` or ``{"action": "delete_custom", "period": <public id>}`` —
and writes its audit event on the registration (``tax.filing.frequency_changed``,
``tax.filing.custom_period_added`` / ``…_removed``, in the tax history).

``preview(registration, change)`` (G-03a-T15) — what the change would do, **writing nothing**:
the change runs in a transaction that is rolled back, so the preview is the service's own
result — ``{"removed", "added", "changed": [{"before", "after"}], "periods", "warnings"}``
(``diff``: a period is *changed* when the same period gets other dates, kind or due dates —
renumbering alone isn't a change). A refused change raises the same ``TaxError`` as saving it.

``roll_forward()`` (G-03a-T17, the nightly job ``numo9.tax.roll_filing_periods``) — for every
registration that files: keeps **24 months of periods ahead** (regenerating from the last
unfiled regular period, so a period once cut at the horizon is made whole), sets ``closed`` on
the periods that ended, and recomputes what needs **attention** — ``due_soon`` in the 14 days
before a return is due, ``overdue`` after (``attention``; filed and paid periods need none).
When a period's attention changes to due soon or overdue, the job **emits an event once**: each
hook of ``FILING_EVENTS`` (the O-04 deadline calendar subscribes) and a notification to the
organisation's owners and admins (``tax.filing.due_soon`` / ``tax.filing.overdue``). The
registration row is locked while its periods are rolled, so two workers running the job at once
do the work — and send each event — once.
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
from .models import (
    LOCKED_PERIOD_STATUSES,
    FilingCycle,
    FilingPeriod,
    PeriodAttention,
    PeriodKind,
    PeriodStatus,
    RegistrationAction,
    RegistrationStatusEvent,
    TaxError,
)

HORIZON_MONTHS = 24
#: A period is "due soon" from this many days before its return is due.
DUE_SOON_DAYS = 14


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


def is_rolled(registration: Any, period: FilingPeriod, settings: Any) -> bool:
    """Was the return due date moved to the next business day (a weekend or holiday)?"""
    plain, _payment = due_dates(
        period.end,
        period.frequency or _frequency_at(registration, period.start),
        structure=settings.structure,
        fye=(int(settings.fye_month), int(settings.fye_day)),
        rolled=False,
    )
    return bool(period.due_date != plain)


# ---- not-registered gaps (G-03b) ----------------------------------------------------------------


def gaps(registration: Any) -> list[tuple[dt.date, dt.date | None]]:
    """The spans the registration was **not registered** (G-03b): from the day after each stop to
    the day before the restart that follows it (``None``: still stopped)."""
    out: list[tuple[dt.date, dt.date | None]] = []
    stopped: dt.date | None = None
    events = RegistrationStatusEvent.objects.filter(registration=registration).order_by(
        "date", "created_at", "pk"
    )
    for event in events:
        if event.action == RegistrationAction.STOP and stopped is None:
            stopped = event.date
        elif event.action == RegistrationAction.RESTART and stopped is not None:
            out.append((stopped + ONE_DAY, event.date - ONE_DAY))
            stopped = None
    if stopped is not None:
        out.append((stopped + ONE_DAY, None))
    return out


def in_gap(registration: Any, day: dt.date, spans: Any = None) -> bool:
    spans = gaps(registration) if spans is None else spans
    return any(start <= day and (end is None or day <= end) for start, end in spans)


def registered_segments(
    registration: Any, start: dt.date, end: dt.date
) -> list[tuple[dt.date, dt.date]]:
    """``start``…``end`` without the not-registered gaps, as consecutive registered segments."""
    segments: list[tuple[dt.date, dt.date]] = []
    cursor = start
    for gap_start, gap_end in sorted(gaps(registration)):
        if gap_end is not None and gap_end < cursor:
            continue
        if gap_start > end:
            break
        if gap_start > cursor:
            segments.append((cursor, min(end, gap_start - ONE_DAY)))
        if gap_end is None:
            return segments
        cursor = gap_end + ONE_DAY
    if cursor <= end:
        segments.append((cursor, end))
    return segments


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
    # An open-ended registration's horizon is not a boundary: its last period is generated
    # whole (to its own end), never cut at the horizon into a stub.
    whole = registration.stop_date is None
    generated: list[tuple[Period, dt.date]] = []
    # No period in a not-registered gap (G-03b): each registered segment is generated on its
    # own, a segment ending at a stop ends with a stub, the one after a restart starts with one.
    segments = registered_segments(registration, start, end)
    for n, (seg_start, seg_end) in enumerate(segments):
        last = n == len(segments) - 1 and seg_end == end
        generated += [
            (period, seg_end)
            for period in generate_periods(
                cycles,
                int(settings.fye_month),
                int(settings.fye_day),
                seg_start,
                seg_end + relativedelta(years=1) if whole and last else seg_end,
                [span for span in spans if span.end >= seg_start and span.start <= seg_end],
            )
        ]
    created = []
    for period, seg_end in generated:
        if period.kind == "custom":  # one of the periods kept
            continue
        if period.start > seg_end:
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
    if in_gap(registration, day):  # not registered then (G-03b)
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
        end = registration.stop_date or day  # a stopped registration is filled to its stop
        _fill(registration, start, end, [], _settings(registration), today)
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


# ---- changes, their audit and their preview (G-03a-T15, T16) ------------------------------------

_COMPARED = ("start", "end", "kind", "frequency", "due_date", "payment_due_date")


def period_row(period: FilingPeriod) -> dict[str, Any]:
    return {
        "id": str(period.public_id),
        "start": period.start.isoformat(),
        "end": period.end.isoformat(),
        "kind": period.kind,
        "frequency": period.frequency,
        "sequence_no": period.sequence_no,
        "due_date": period.due_date.isoformat(),
        "payment_due_date": period.payment_due_date.isoformat(),
        "status": period.status,
        "note": period.note,
    }


def period_rows(registration: Any) -> list[dict[str, Any]]:
    periods = FilingPeriod.objects.filter(registration=registration).order_by("start")
    return [period_row(p) for p in periods]


def diff(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    """Removed / added / changed periods between two ``period_rows`` (module docstring)."""
    was = {row["id"]: row for row in before}
    now = {row["id"]: row for row in after}
    return {
        "removed": [row for key, row in was.items() if key not in now],
        "added": [row for key, row in now.items() if key not in was],
        "changed": [
            {"before": was[key], "after": row}
            for key, row in now.items()
            if key in was and any(was[key][f] != row[f] for f in _COMPARED)
        ],
    }


def _spans(result: dict[str, Any]) -> dict[str, Any]:
    """A diff without the row ids: what is compared between a preview and the saved change."""

    def bare(row: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in row.items() if key != "id"}

    return {
        "removed": [bare(r) for r in result["removed"]],
        "added": [bare(r) for r in result["added"]],
        "changed": [
            {"before": bare(c["before"]), "after": bare(c["after"])} for c in result["changed"]
        ],
    }


def apply_change(
    registration: Any,
    change: dict[str, Any],
    *,
    user: Any = None,
    today: dt.date | None = None,
) -> dict[str, Any]:
    """Run one change and audit it (module docstring) → the diff, periods and warnings."""
    from numo9.audit.service import record
    from numo9.tenancy.context import org_context

    action = change.get("action")
    with org_context(registration.organisation), transaction.atomic():
        before = period_rows(registration)
        warnings: list[dict[str, str]] = []
        if action == "switch":
            previous = _frequency_at(registration, change["effective_from"])
            first = not FilingCycle.objects.filter(registration=registration).exists()
            _periods, warnings = switch_frequency(
                registration,
                change["frequency"],
                change["effective_from"],
                approval_ref=change.get("approval_ref") or "",
                approval_date=change.get("approval_date"),
                note=change.get("note") or "",
                user=user,
                today=today,
            )
            record(
                "tax.filing.frequency_changed",
                obj=registration,
                actor=user,
                changes={"frequency": ["" if first else previous, change["frequency"]]},
                meta={
                    "effective_from": change["effective_from"].isoformat(),
                    "approval_ref": (change.get("approval_ref") or "").strip(),
                },
            )
        elif action == "custom":
            add_custom_period(
                registration,
                change["start"],
                change["end"],
                note=change.get("note") or "",
                today=today,
            )
            record(
                "tax.filing.custom_period_added",
                obj=registration,
                actor=user,
                meta={"start": change["start"].isoformat(), "end": change["end"].isoformat()},
            )
        elif action == "delete_custom":
            period = FilingPeriod.objects.filter(
                registration=registration, public_id=change.get("period")
            ).first()
            if period is None:
                raise TaxError(_("That period no longer exists."), code="tax.filing.no_period")
            span = {"start": period.start.isoformat(), "end": period.end.isoformat()}
            delete_custom_period(period, today=today)
            record("tax.filing.custom_period_removed", obj=registration, actor=user, meta=span)
        else:
            raise TaxError(_("Unknown change."), code="tax.filing.action")
        after = period_rows(registration)
        return {**diff(before, after), "periods": after, "warnings": warnings}


class _Undo(Exception):
    """Rolls a preview's transaction back."""


def preview(
    registration: Any, change: dict[str, Any], *, today: dt.date | None = None
) -> dict[str, Any]:
    """The result ``apply_change`` would give, with nothing written (module docstring)."""
    result: dict[str, Any] = {}
    try:
        with transaction.atomic():
            result = apply_change(registration, change, today=today)
            raise _Undo
    except _Undo:
        pass
    return result


# ---- nightly roll-forward (G-03a-T17) -----------------------------------------------------------

#: Hooks called once when a period becomes due soon or overdue: ``hook(period, attention)``.
FILING_EVENTS: list[Any] = []


def attention(period: FilingPeriod, today: dt.date) -> str:
    """``overdue`` once the return is past due, ``due_soon`` in its last 14 days, else ''."""
    if period.is_locked or period.end >= today:
        return ""
    if period.due_date < today:
        return PeriodAttention.OVERDUE
    if (period.due_date - today).days <= DUE_SOON_DAYS:
        return PeriodAttention.DUE_SOON
    return ""


def _notify(period: FilingPeriod, state: str) -> None:
    from numo9.notifications.services import notify
    from numo9.tenancy.models import OrganisationMember

    organisation = period.organisation
    admins = [
        member.user
        for member in OrganisationMember.objects.filter(
            organisation=organisation, role__in=("owner", "admin")
        ).select_related("user")
    ]
    notify(
        f"tax.filing.{state}",
        admins,
        organisation=organisation,
        params={
            "registration": str(period.registration),
            "period": str(period),
            "due_date": period.due_date.isoformat(),
        },
        link=f"/o/{organisation.public_id}/settings/tax",
    )


def roll_registration(registration: Any, today: dt.date) -> dict[str, int]:
    """Roll one registration's periods forward and recompute their attention (docstring)."""
    from numo9.orgsettings.models import TaxRegistration
    from numo9.tenancy.context import org_context

    counts = {"added": 0, "due_soon": 0, "overdue": 0}
    with org_context(registration.organisation), transaction.atomic():
        # One worker at a time per registration (the job may run on two workers).
        registration = TaxRegistration.objects.select_for_update().get(pk=registration.pk)
        if registration.start_date is None or not cycles_of(registration):
            return counts
        periods = FilingPeriod.objects.filter(registration=registration)
        before = periods.count()
        last = periods.order_by("-end").first()
        if last is None:
            regenerate(registration, today=today)
        elif last.end < horizon(registration, today):
            cut = (
                last.end + ONE_DAY
                if last.is_locked or last.kind == PeriodKind.CUSTOM
                else last.start
            )
            regenerate(registration, cut, today=today)
        else:
            renumber(registration, today)
        counts["added"] = periods.count() - before
        for period in periods.exclude(status__in=LOCKED_PERIOD_STATUSES).order_by("start"):
            state = attention(period, today)
            if state == period.attention:
                continue
            period.attention = state
            period.save(update_fields=["attention"])
            if state:
                counts[state] += 1
                for hook in FILING_EVENTS:
                    hook(period, state)
                _notify(period, state)
        periods.filter(status__in=LOCKED_PERIOD_STATUSES).exclude(attention="").update(attention="")
    return counts


def roll_forward(now: Any = None) -> dict[str, int]:
    """Every filing registration (module docstring); returns the totals. Safe to run again."""
    from numo9.contacts.models import organisation_today
    from numo9.orgsettings.models import TaxRegistration

    moment = now or timezone.now()
    totals = {"registrations": 0, "added": 0, "due_soon": 0, "overdue": 0}
    registrations = (
        TaxRegistration._base_manager.filter(deleted_at__isnull=True, filing_cycles__isnull=False)
        .select_related("organisation")
        .distinct()
        .order_by("pk")
    )
    for registration in registrations:
        counts = roll_registration(
            registration, organisation_today(registration.organisation, now=moment)
        )
        totals["registrations"] += 1
        for key, value in counts.items():
            totals[key] += value
    return totals

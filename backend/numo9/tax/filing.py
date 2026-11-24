"""Filing-period engine (G-03a), as ``docs/specs/filing-cycles.md``.

**Generator** (G-03a-T07) — ``generate_periods(cycles, fye_month, fye_day, start, end, custom)``
is pure (no database): from the registration's filing cycles (frequency from a date), the
financial year end, the dates to cover and the out-of-cycle periods, it returns the periods that
cover **every day from ``start`` to ``end`` exactly once**, in date order:

- a cycle's regular periods are months (calendar months), fiscal quarters or financial years,
  counted from its **anchor**: the first of a month for monthly, the financial year start for
  quarterly and annual — then, after an out-of-cycle period, the day after it ends (the regular
  periods realign from there until the next cycle change);
- a period cut short — the registration starting or stopping mid-period, a switch taking effect
  mid-period, a custom period starting — is a ``stub``;
- custom periods are emitted as they are (``custom``).

Boundaries are the anchor plus N months (``relativedelta``, which keeps month ends: a 31 Jan
anchor gives 28/29 Feb, 31 Mar…), the way ``dateutil.rrule`` would count monthly steps without
skipping short months.
"""

from __future__ import annotations

import calendar as _calendar
import datetime as dt
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from dateutil.relativedelta import relativedelta

ONE_DAY = dt.timedelta(days=1)
MONTHS = {"monthly": 1, "quarterly": 3, "annual": 12}


@dataclass(frozen=True)
class Cycle:
    frequency: str
    effective_from: dt.date


@dataclass(frozen=True)
class Span:
    start: dt.date
    end: dt.date

    def __contains__(self, day: object) -> bool:
        return isinstance(day, dt.date) and self.start <= day <= self.end


@dataclass(frozen=True)
class Period:
    start: dt.date
    end: dt.date
    kind: str  # regular / stub / custom
    frequency: str = ""


def fiscal_anchor(fye_month: int, fye_day: int) -> dt.date:
    """A financial year start (the day after the year end), in a non-leap year."""
    last = _calendar.monthrange(2001, fye_month)[1]
    if fye_day >= last:
        return dt.date(2001, fye_month, last) + ONE_DAY
    return dt.date(2001, fye_month, fye_day) + ONE_DAY


def _anchor(frequency: str, fye_month: int, fye_day: int) -> dt.date:
    return dt.date(2001, 1, 1) if frequency == "monthly" else fiscal_anchor(fye_month, fye_day)


def _boundary(anchor: dt.date, months: int, k: int) -> dt.date:
    # Always counted from the anchor: a day-29+ anchor keeps its day where the month has it.
    return anchor + relativedelta(months=months * k)


def regular_span(anchor: dt.date, frequency: str, day: dt.date) -> Span:
    """The regular period of ``frequency`` counted from ``anchor`` that contains ``day``."""
    months = MONTHS[frequency]
    diff = (day.year - anchor.year) * 12 + day.month - anchor.month
    k = diff // months
    while _boundary(anchor, months, k) > day:
        k -= 1
    while _boundary(anchor, months, k + 1) <= day:
        k += 1
    return Span(_boundary(anchor, months, k), _boundary(anchor, months, k + 1) - ONE_DAY)


def _cycle_at(cycles: Sequence[Cycle], day: dt.date) -> Cycle:
    current = cycles[0]
    for cycle in cycles:
        if cycle.effective_from <= day:
            current = cycle
    return current


def _validate(cycles: Sequence[Cycle], custom: Sequence[Span]) -> None:
    if not cycles:
        raise ValueError("A registration needs at least one filing cycle.")
    for cycle in cycles:
        if cycle.frequency not in MONTHS:
            raise ValueError(f"Unknown frequency {cycle.frequency!r}.")
    ordered = sorted(custom, key=lambda s: s.start)
    for span in ordered:
        if span.end < span.start:
            raise ValueError("A custom period ends before it starts.")
    for a, b in zip(ordered, ordered[1:], strict=False):
        if b.start <= a.end:
            raise ValueError("Custom periods overlap.")


def generate_periods(
    cycles: Sequence[Cycle],
    fye_month: int,
    fye_day: int,
    start: dt.date,
    end: dt.date,
    custom: Sequence[Span] = (),
) -> list[Period]:
    """The periods covering ``start``…``end`` (module docstring)."""
    _validate(cycles, custom)
    cycles = sorted(cycles, key=lambda c: c.effective_from)
    customs = sorted(
        (c for c in custom if c.end >= start and c.start <= end), key=lambda s: s.start
    )
    return list(_walk(cycles, fye_month, fye_day, start, end, customs))


def _walk(
    cycles: list[Cycle],
    fye_month: int,
    fye_day: int,
    start: dt.date,
    end: dt.date,
    customs: list[Span],
) -> Iterator[Period]:
    cursor = start
    realigned: dt.date | None = None  # anchor after a custom period, until the next cycle
    realigned_for: Cycle | None = None
    while cursor <= end:
        custom = next((c for c in customs if cursor in c), None)
        if custom is not None:
            yield Period(max(custom.start, cursor), min(custom.end, end), "custom")
            cursor = custom.end + ONE_DAY
            realigned, realigned_for = cursor, _cycle_at(cycles, cursor)
            continue
        cycle = _cycle_at(cycles, cursor)
        if realigned_for is not None and cycle != realigned_for:
            realigned = realigned_for = None
        anchor = realigned or _anchor(cycle.frequency, fye_month, fye_day)
        span = regular_span(anchor, cycle.frequency, cursor)
        breaks = [end + ONE_DAY, span.end + ONE_DAY]
        breaks += [c.effective_from for c in cycles if c.effective_from > cursor]
        breaks += [c.start for c in customs if c.start > cursor]
        stop = min(breaks) - ONE_DAY
        kind = "regular" if (cursor, stop) == (span.start, span.end) else "stub"
        yield Period(cursor, stop, kind, cycle.frequency)
        cursor = stop + ONE_DAY

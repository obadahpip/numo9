"""Report parameters (K-01-T03): date range presets, comparisons, basis, book and tracking.

**Date ranges** — ``resolve_range(preset, today, settings, date_from=…, date_to=…)`` →
``DateRange(start, end, preset)``. Presets: ``this_month``, ``last_month``, ``this_quarter``,
``last_quarter``, ``this_financial_year``, ``last_financial_year``, ``month_to_date``,
``quarter_to_date``, ``year_to_date``, ``custom``. Quarters and years follow the organisation's
**financial year** (``fye_month`` / ``fye_day``, A-05, ``orgsettings.fiscal.fiscal_year``): with a
31 March year end, "last financial year" on 15 June 2026 is 1 April 2025 – 31 March 2026, and the
first quarter is April–June. Calendar months are calendar months.

**Comparisons** — ``comparison_ranges(base, compare, periods)``: ``none``; ``previous`` — the N
periods before, each the same length (a month → the months before, a quarter → quarters, a
financial year → years, anything else → the same number of days); ``prior_year`` — the same
dates one year earlier, N times. At most 12 comparison columns.

**Basis** — ``resolve_basis(organisation, override)`` → ``Basis(value, from_default, label)``: the
G-06 tax-settings default unless the report overrides it, with the header label ("Basis: Cash
(organisation default)").

**Book** — ``book_filter(book)``: the line books of a report book (``both`` + the book; lines of
the other book only never count). ``accounting`` by default; ``tax`` is filled in K-07.

**Tracking** — ``tracking_filter(selection)``: ``{category: [option, …]}`` → a filter on the lines'
``tracking`` JSON (a line matches when, for every category chosen, its option is one of those).
"""

from __future__ import annotations

import calendar
import datetime as dt
import re
from dataclasses import dataclass
from typing import Any

from django.db.models import Q

from .engine import ReportError

PRESETS = (
    "this_month",
    "last_month",
    "this_quarter",
    "last_quarter",
    "this_financial_year",
    "last_financial_year",
    "month_to_date",
    "quarter_to_date",
    "year_to_date",
    "custom",
)
COMPARISONS = ("none", "previous", "prior_year")
MAX_COMPARISONS = 12
BOOKS = ("accounting", "tax")
TRACKING_KEY = re.compile(r"^[A-Za-z0-9-]+(?:_[A-Za-z0-9-]+)*$")


@dataclass(frozen=True)
class DateRange:
    start: dt.date
    end: dt.date
    preset: str = "custom"

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def as_dict(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat(), "preset": self.preset}


@dataclass(frozen=True)
class Basis:
    value: str
    from_default: bool
    label: str


def _month_end(year: int, month: int) -> dt.date:
    return dt.date(year, month, calendar.monthrange(year, month)[1])


def _add_months(day: dt.date, months: int) -> dt.date:
    index = day.year * 12 + day.month - 1 + months
    year, month = divmod(index, 12)
    return dt.date(year, month + 1, min(day.day, calendar.monthrange(year, month + 1)[1]))


def _month(day: dt.date) -> tuple[dt.date, dt.date]:
    return day.replace(day=1), _month_end(day.year, day.month)


def _fiscal_year(settings: Any, day: dt.date) -> tuple[dt.date, dt.date]:
    from numo9.orgsettings.fiscal import fiscal_year

    return fiscal_year(settings, day)


def _fiscal_quarter(settings: Any, day: dt.date) -> tuple[dt.date, dt.date]:
    """The quarter of the financial year containing ``day`` (three months from the year start)."""
    start, end = _fiscal_year(settings, day)
    quarter_start = start
    while True:
        quarter_end = min(_add_months(quarter_start, 3) - dt.timedelta(days=1), end)
        if day <= quarter_end:
            return quarter_start, quarter_end
        quarter_start = quarter_end + dt.timedelta(days=1)


def resolve_range(
    preset: str,
    today: dt.date,
    settings: Any,
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
) -> DateRange:
    if preset not in PRESETS:
        raise ReportError(f"Unknown date range {preset!r}.", code="reports.range.unknown")
    if preset == "custom":
        if date_from is None or date_to is None:
            raise ReportError("A custom range needs both dates.", code="reports.range.dates")
        if date_from > date_to:
            raise ReportError("The range ends before it starts.", code="reports.range.order")
        return DateRange(date_from, date_to, preset)
    if preset == "this_month":
        start, end = _month(today)
    elif preset == "last_month":
        start, end = _month(today.replace(day=1) - dt.timedelta(days=1))
    elif preset == "this_quarter":
        start, end = _fiscal_quarter(settings, today)
    elif preset == "last_quarter":
        start, _end = _fiscal_quarter(settings, today)
        start, end = _fiscal_quarter(settings, start - dt.timedelta(days=1))
    elif preset == "this_financial_year":
        start, end = _fiscal_year(settings, today)
    elif preset == "last_financial_year":
        start, _end = _fiscal_year(settings, today)
        start, end = _fiscal_year(settings, start - dt.timedelta(days=1))
    elif preset == "month_to_date":
        start, end = today.replace(day=1), today
    elif preset == "quarter_to_date":
        start, end = _fiscal_quarter(settings, today)[0], today
    else:  # year_to_date
        start, end = _fiscal_year(settings, today)[0], today
    return DateRange(start, end, preset)


def _is_whole_months(base: DateRange) -> int:
    """Number of whole calendar months the range spans (0 when it isn't whole months)."""
    if base.start.day != 1 or base.end != _month_end(base.end.year, base.end.month):
        return 0
    return (base.end.year - base.start.year) * 12 + base.end.month - base.start.month + 1


def _shift(base: DateRange, steps: int) -> DateRange:
    months = _is_whole_months(base)
    if months:
        start = _add_months(base.start, -months * steps)
        end_month = _add_months(base.end.replace(day=1), -months * steps)
        return DateRange(start, _month_end(end_month.year, end_month.month), "custom")
    delta = dt.timedelta(days=base.days * steps)
    return DateRange(base.start - delta, base.end - delta, "custom")


def _year_back(day: dt.date, years: int) -> dt.date:
    year = day.year - years
    return dt.date(year, day.month, min(day.day, calendar.monthrange(year, day.month)[1]))


def comparison_ranges(base: DateRange, compare: str, periods: int = 1) -> list[DateRange]:
    """The comparison columns' ranges, most recent first."""
    if compare not in COMPARISONS:
        raise ReportError(f"Unknown comparison {compare!r}.", code="reports.compare.unknown")
    if compare == "none":
        return []
    if not 1 <= periods <= MAX_COMPARISONS:
        raise ReportError(
            f"Compare 1 to {MAX_COMPARISONS} periods.", code="reports.compare.periods"
        )
    if compare == "previous":
        return [_shift(base, n) for n in range(1, periods + 1)]
    ranges = []
    for n in range(1, periods + 1):
        start = _year_back(base.start, n)
        end = _year_back(base.end, n)
        if base.end == _month_end(base.end.year, base.end.month):  # 28/29 February
            end = _month_end(end.year, end.month)
        ranges.append(DateRange(start, end, "custom"))
    return ranges


def resolve_basis(organisation: Any, override: str | None = None) -> Basis:
    from numo9.tax.settings import basis_label, report_basis

    if override not in (None, "", "accrual", "cash"):
        raise ReportError(f"Unknown basis {override!r}.", code="reports.basis.unknown")
    value, default = report_basis(organisation, override or None)
    return Basis(value, default, basis_label(organisation, override or None))


def book_filter(book: str = "accounting") -> list[str]:
    from numo9.ledger.models import Book

    if book not in BOOKS:
        raise ReportError(f"Unknown book {book!r}.", code="reports.book.unknown")
    return [Book.BOTH, book]


def tracking_filter(selection: dict[str, list[str]] | None, prefix: str = "") -> Q:
    """Lines whose tracking matches every chosen category (``prefix`` for a related lookup)."""
    condition = Q()
    for category, options in (selection or {}).items():
        if not TRACKING_KEY.match(str(category)) or len(str(category)) > 64:
            raise ReportError(
                f"Unknown tracking category {category!r}.", code="reports.tracking.category"
            )
        wanted = [str(o) for o in options if str(o)]
        if not wanted:
            continue
        either = Q()
        for option in wanted:
            either |= Q(**{f"{prefix}tracking__{category}": option})
        condition &= either
    return condition

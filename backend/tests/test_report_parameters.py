"""K-01-T03 — report parameters: date range presets resolved against the financial year ("last
financial year" for a 31 March year end), quarters of the financial year, comparisons (previous N
periods and prior years), the basis from tax settings or overridden with its label, the book
filter, and the tracking filter on posted lines.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from django.db.models import Sum

from numo9.ledger.models import JournalLine
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.reports.engine import ReportError
from numo9.reports.parameters import (
    DateRange,
    book_filter,
    comparison_ranges,
    resolve_basis,
    resolve_range,
    tracking_filter,
)
from numo9.tax.settings import tax_settings
from numo9.tenancy.context import org_context
from tests.report_helpers import report_books

D = dt.date
MARCH = SimpleNamespace(fye_month=3, fye_day=31)
DECEMBER = SimpleNamespace(fye_month=12, fye_day=31)
TODAY = D(2026, 6, 15)


@pytest.mark.parametrize(
    ("preset", "settings", "start", "end"),
    [
        ("last_financial_year", MARCH, D(2025, 4, 1), D(2026, 3, 31)),
        ("this_financial_year", MARCH, D(2026, 4, 1), D(2027, 3, 31)),
        ("year_to_date", MARCH, D(2026, 4, 1), TODAY),
        ("this_quarter", MARCH, D(2026, 4, 1), D(2026, 6, 30)),
        ("last_quarter", MARCH, D(2026, 1, 1), D(2026, 3, 31)),
        ("quarter_to_date", MARCH, D(2026, 4, 1), TODAY),
        ("this_month", MARCH, D(2026, 6, 1), D(2026, 6, 30)),
        ("last_month", MARCH, D(2026, 5, 1), D(2026, 5, 31)),
        ("month_to_date", MARCH, D(2026, 6, 1), TODAY),
        ("last_financial_year", DECEMBER, D(2025, 1, 1), D(2025, 12, 31)),
        ("this_quarter", DECEMBER, D(2026, 4, 1), D(2026, 6, 30)),
    ],
)
def test_presets(preset: str, settings: Any, start: dt.date, end: dt.date) -> None:
    assert resolve_range(preset, TODAY, settings) == DateRange(start, end, preset)


def test_custom_and_bad_ranges() -> None:
    assert resolve_range(
        "custom", TODAY, MARCH, date_from=D(2026, 1, 5), date_to=D(2026, 2, 7)
    ) == DateRange(D(2026, 1, 5), D(2026, 2, 7), "custom")
    for kwargs, code in (
        ({}, "reports.range.dates"),
        ({"date_from": D(2026, 2, 1), "date_to": D(2026, 1, 1)}, "reports.range.order"),
    ):
        with pytest.raises(ReportError) as refused:
            resolve_range("custom", TODAY, MARCH, **kwargs)
        assert refused.value.code == code
    with pytest.raises(ReportError):
        resolve_range("next_decade", TODAY, MARCH)


def test_comparisons() -> None:
    june = DateRange(D(2026, 6, 1), D(2026, 6, 30))
    assert [(r.start, r.end) for r in comparison_ranges(june, "previous", 3)] == [
        (D(2026, 5, 1), D(2026, 5, 31)),
        (D(2026, 4, 1), D(2026, 4, 30)),
        (D(2026, 3, 1), D(2026, 3, 31)),
    ]
    year = DateRange(D(2026, 4, 1), D(2027, 3, 31))
    assert [(r.start, r.end) for r in comparison_ranges(year, "previous", 2)] == [
        (D(2025, 4, 1), D(2026, 3, 31)),
        (D(2024, 4, 1), D(2025, 3, 31)),
    ]
    february = DateRange(D(2028, 2, 1), D(2028, 2, 29))
    assert [(r.start, r.end) for r in comparison_ranges(february, "prior_year", 1)] == [
        (D(2027, 2, 1), D(2027, 2, 28))
    ]
    days = DateRange(D(2026, 6, 10), D(2026, 6, 19))
    assert comparison_ranges(days, "previous", 1) == [DateRange(D(2026, 5, 31), D(2026, 6, 9))]
    assert comparison_ranges(june, "none") == []
    assert len(comparison_ranges(june, "previous", 12)) == 12
    with pytest.raises(ReportError) as wide:
        comparison_ranges(june, "previous", 13)
    assert wide.value.code == "reports.compare.periods"


@pytest.mark.django_db
def test_basis_default_and_override() -> None:
    org = report_books()["org"]
    with org_context(org):
        settings = tax_settings(org)
        settings.basis = "cash"
        settings.save()
        default = resolve_basis(org)
        assert (default.value, default.from_default) == ("cash", True)
        assert default.label == "Basis: Cash (organisation default)"
        chosen = resolve_basis(org, "accrual")
        assert (chosen.value, chosen.from_default, chosen.label) == (
            "accrual",
            False,
            "Basis: Accrual (this report)",
        )
    with pytest.raises(ReportError):
        resolve_basis(org, "barter")


@pytest.mark.django_db
def test_book_and_tracking_filters() -> None:
    books = report_books()
    assert book_filter() == ["both", "accounting"] and book_filter("tax") == ["both", "tax"]
    with pytest.raises(ReportError):
        book_filter("both")
    with org_context(books["org"]):
        post_journal(
            JournalSpec(
                date=D(2026, 6, 30),
                lines=(
                    LineSpec(books["office"], debit=Decimal("80.00"), tracking={"region": "east"}),
                    LineSpec(books["office"], debit=Decimal("20.00"), tracking={"region": "west"}),
                    LineSpec(books["chequing"], credit=Decimal("100.00")),
                ),
            ),
            user=None,
        )
        east = JournalLine.objects.filter(tracking_filter({"region": ["east"]}))
        assert east.aggregate(s=Sum("debit"))["s"] == Decimal("80.00")
        both = JournalLine.objects.filter(tracking_filter({"region": ["east", "west"]}))
        assert both.aggregate(s=Sum("debit"))["s"] == Decimal("100.00")
        assert (
            JournalLine.objects.filter(tracking_filter({})).count() == JournalLine.objects.count()
        )
    with pytest.raises(ReportError):
        tracking_filter({"region__evil": ["x"]})

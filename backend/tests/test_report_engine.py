"""K-01-T02 — report definition framework: the two sample reports are registered (by id and by
slug, in their category); parameters are cleaned against the schema (defaults, dates, choices,
unknown names refused); run() gives the columns, rows and totals from posted lines only;
duplicate ids and slugs are refused.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.reports.engine import ReportDefinition, ReportError, ReportRegistry, registry
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db


def test_two_sample_reports_registered() -> None:
    assert "trial_balance" in registry and "account-activity" in registry
    assert registry.get("trial-balance").id == "trial_balance"
    financial = [r.id for r in registry.by_category()["financial"]]
    assert {"trial_balance", "account_activity"} <= set(financial)
    summary = registry.get("account_activity").summary()
    assert [p["name"] for p in summary["params"]] == ["date_from", "date_to", "book"]
    with pytest.raises(ReportError) as unknown:
        registry.get("nope")
    assert unknown.value.code == "reports.unknown"


def test_params_are_cleaned() -> None:
    report = registry.get("account_activity")
    params = report.clean_params({"date_from": "2026-06-01", "date_to": "2026-06-30"})
    assert params == {
        "date_from": dt.date(2026, 6, 1),
        "date_to": dt.date(2026, 6, 30),
        "book": "accounting",
    }
    for raw, code in (
        ({"date_from": "2026-06-01"}, "reports.param.required"),
        ({"date_from": "x", "date_to": "2026-06-30"}, "reports.param.invalid"),
        ({"date_from": "2026-06-01", "date_to": "2026-06-30", "book": "x"}, "reports.param.choice"),
        (
            {"date_from": "2026-06-01", "date_to": "2026-06-30", "colour": "red"},
            "reports.param.unknown",
        ),
    ):
        with pytest.raises(ReportError) as refused:
            report.clean_params(raw)
        assert refused.value.code == code


def test_trial_balance_runs_from_posted_lines() -> None:
    books = report_books()
    result = registry.get("trial_balance").run(books["org"], {"as_of": "2026-06-30"})
    rows = {r.label: r.values for r in result.rows}
    assert rows == {
        "1000 · Chequing": [Decimal("2450.00"), None],
        "4000 · Sales": [None, Decimal("5000.00")],
        "5400 · Rent": [Decimal("2400.00"), None],  # the 999.00 draft never counts
        "6100 · Office supplies": [Decimal("150.00"), None],
    }
    [total] = result.totals
    assert total.values == [Decimal("5000.00"), Decimal("5000.00")]
    assert [c.key for c in result.columns] == ["debit", "credit"]
    assert result.as_dict()["totals"][0]["values"] == ["5000.00", "5000.00"]


def test_account_activity_for_a_period() -> None:
    books = report_books()
    result = registry.get("account-activity").run(
        books["org"], {"date_from": "2026-06-01", "date_to": "2026-06-30"}
    )
    assert [(r.label, r.values) for r in result.rows] == [
        ("1000 · Chequing", [Decimal("0.00"), Decimal("2550.00"), Decimal("-2550.00")]),
        ("5400 · Rent", [Decimal("2400.00"), Decimal("0.00"), Decimal("2400.00")]),
        ("6100 · Office supplies", [Decimal("150.00"), Decimal("0.00"), Decimal("150.00")]),
    ]
    assert result.totals[0].values == [Decimal("2550.00"), Decimal("2550.00"), Decimal("0.00")]


def test_registry_refuses_duplicates() -> None:
    local = ReportRegistry()

    class One(ReportDefinition):
        id, slug = "one", "one"

    class Same(ReportDefinition):
        id, slug = "one", "other"

    class Slug(ReportDefinition):
        id, slug = "two", "one"

    local.register(One)
    for duplicate, code in ((Same, "reports.registry.id"), (Slug, "reports.registry.slug")):
        with pytest.raises(ReportError) as refused:
            local.register(duplicate)
        assert refused.value.code == code

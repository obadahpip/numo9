"""G-03-T04 — the quick method: remittance rates as effective-dated data, the 1 % credit on the
first 30,000 of eligible supplies of the fiscal year, ITCs on capital purchases only.

Worked example (Ontario, services, 8.8 %): June's taxable sale 1,000.00 + HST 130.00 → line 101
= 1,130.00; 1,130.00 × 8.8 % = 99.44, less 1 % × 1,130.00 = 11.30 → line 103 = 88.14; no capital
purchase → line 106 = 0.00; net tax 88.14.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.tax import returns
from numo9.tax.models import TaxError
from numo9.tax.quick_method import quick_lines, remittance_rate
from numo9.tax.settings import tax_settings
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.tax_report_helpers import june_books

pytestmark = pytest.mark.django_db
D = Decimal


def test_rates_are_effective_dated_data() -> None:
    assert remittance_rate("hst_on", "services", dt.date(2026, 6, 1)) == D("8.8")
    assert remittance_rate("gst", "goods", dt.date(2026, 6, 1)) == D("1.8")
    assert remittance_rate("hst_ns", "services", dt.date(2024, 6, 1)) == D("10.0")
    with pytest.raises(TaxError) as caught:
        remittance_rate("hst_ns", "services", dt.date(2026, 6, 1))  # 14 % HST: rate not entered
    assert caught.value.code == "tax.quick.rate_missing"


def test_the_worked_example() -> None:
    books = june_books()
    with org_context(books["org"]):
        lines = quick_lines(books["period"])
    assert (lines["101"], lines["103"], lines["106"], lines["109"], lines["115"]) == (
        D("1130.00"),
        D("88.14"),
        D("0.00"),
        D("88.14"),
        D("88.14"),
    )


def test_the_credit_is_used_once_per_fiscal_year(monkeypatch: pytest.MonkeyPatch) -> None:
    from numo9.tax import quick_method

    books = june_books()
    monkeypatch.setattr(quick_method, "_earlier_in_year", lambda period, kind: D("29500.00"))
    with org_context(books["org"]):
        lines = quick_lines(books["period"])
    # only 500.00 of the 30,000 is left: credit 5.00
    assert lines["103"] == D("99.44") - D("5.00")
    monkeypatch.setattr(quick_method, "_earlier_in_year", lambda period, kind: D("40000.00"))
    with org_context(books["org"]):
        assert quick_lines(books["period"])["103"] == D("99.44")


def test_goods_rates_and_a_quick_method_return() -> None:
    books = june_books()
    org = books["org"]
    with org_context(org):
        settings = tax_settings(org)
        settings.quick_method = True
        settings.quick_method_from = dt.date(2026, 1, 1)
        settings.quick_method_kind = "goods"
        settings.save()
    draft = returns.prepare(books["period"], people(org)["adviser"], method="quick")
    # 1,130.00 × 4.4 % = 49.72, less 11.30
    assert (draft.method, draft.lines["103"], draft.lines["106"]) == ("quick", "38.42", "0.00")

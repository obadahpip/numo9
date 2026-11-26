"""G-05-T12 — gap tests for the tax reports.

- gap-54 (Xero's *Taxes and balances* holds no tax report): the five tax reports are in the one
  report engine, under Tax, run on real postings and tie to the ledger;
- gap-49 (one basis): a tax report's basis is the tax-settings basis unless the run overrides it,
  and the header says which.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.ledger.services import reverse
from numo9.reports.engine import registry
from numo9.reports.header import header_for
from numo9.tax.settings import tax_settings
from numo9.tenancy.context import org_context
from tests.tax_report_helpers import Q2, tax_books

pytestmark = pytest.mark.django_db
RANGE = {"date_from": Q2[0].isoformat(), "date_to": Q2[1].isoformat()}
TAX_REPORTS = {"tax_summary", "tax_detail", "tax_audit", "itc_detail", "tax_tie_out"}


@pytest.fixture
def books() -> dict[str, Any]:
    return tax_books()


@pytest.mark.gap("gap-54")
def test_tax_reports_exist_and_tie_to_the_ledger(books: dict[str, Any]) -> None:
    tax = {r.id for r in registry.by_category().get("tax", [])}
    assert tax >= TAX_REPORTS
    assert all(registry.get(r).feature == "tax.reports.read" for r in TAX_REPORTS)
    with org_context(books["org"]):
        reverse(books["direct"], user=books["owner"])
    tie = registry.get("tax_tie_out").run(books["org"], RANGE)
    assert tie.totals[0].values[2] == Decimal("0.00")
    summary = registry.get("tax_summary").run(books["org"], RANGE)
    gst = next(r for r in tie.rows if r.key == "control:gst_hst_payable")
    assert gst.values[0] == summary.totals[0].values[1] == Decimal("195.00")


@pytest.mark.gap("gap-49")
def test_tax_report_basis_from_settings_with_a_labelled_override(books: dict[str, Any]) -> None:
    org = books["org"]
    report = registry.get("tax_summary")
    with org_context(org):
        settings = tax_settings(org)
        settings.basis = "cash"
        settings.save()
    cash = report.run(org, RANGE)
    header = header_for(org, report, cash.params, today=dt.date(2026, 7, 1))
    assert header.basis_label == "Basis: Cash (organisation default)"
    assert cash.totals[0].values[1] == Decimal("0")  # nothing paid yet
    accrual = report.run(org, {**RANGE, "basis": "accrual"})
    assert header_for(org, report, accrual.params, today=dt.date(2026, 7, 1)).basis_label == (
        "Basis: Accrual (this report)"
    )
    assert accrual.totals[0].values[1] == Decimal("195.00")

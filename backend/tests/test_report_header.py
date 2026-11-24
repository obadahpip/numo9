"""K-01-T06 — report header: display and legal names, the period label (a range or "As at"),
"Year to date — unaudited" when the period ends after today, the basis label from tax settings
(or the report's override) and the book label.
"""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.orgsettings.service import get_settings
from numo9.reports.header import report_header
from numo9.reports.parameters import DateRange
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
D = dt.date
TODAY = D(2026, 6, 15)


@pytest.fixture
def org() -> Organisation:
    org = Organisation.objects.create(name="Maple & Pine")
    with org_context(org):
        settings = get_settings(org)
        settings.display_name = "Maple & Pine Supply Co."
        settings.legal_name = "Maple and Pine Supply Company Ltd."
        settings.save()
    return org


def test_future_period_end_says_year_to_date(org: Organisation) -> None:
    header = report_header(
        org, title="Profit and loss", today=TODAY, period=DateRange(D(2026, 4, 1), D(2027, 3, 31))
    )
    assert header.as_dict() == {
        "title": "Profit and loss",
        "display_name": "Maple & Pine Supply Co.",
        "legal_name": "Maple and Pine Supply Company Ltd.",
        "period_label": "1 Apr 2026 to 31 Mar 2027",
        "status_label": "Year to date — unaudited",
        "basis_label": "Basis: Accrual (organisation default)",
        "book_label": "Accounting book",
    }


def test_past_period_and_balance_date(org: Organisation) -> None:
    closed = report_header(
        org, title="P&L", today=TODAY, period=DateRange(D(2025, 4, 1), D(2026, 3, 31))
    )
    assert closed.status_label == ""
    balance = report_header(
        org, title="Balance sheet", today=TODAY, as_of=D(2026, 6, 30), basis="cash", book="tax"
    )
    assert (balance.period_label, balance.status_label) == (
        "As at 30 Jun 2026",
        "Year to date — unaudited",
    )
    assert (balance.basis_label, balance.book_label) == ("Basis: Cash (this report)", "Tax book")
    today = report_header(org, title="BS", today=TODAY, as_of=TODAY)
    assert today.status_label == ""  # ends today: not in the future


def test_legal_name_left_out_when_the_same() -> None:
    org = Organisation.objects.create(name="Solo Ltd.")
    header = report_header(org, title="TB", today=TODAY, as_of=TODAY)
    assert header.display_name and header.legal_name == ""
    with pytest.raises(ValueError):
        report_header(org, title="TB", today=TODAY)

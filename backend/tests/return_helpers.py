"""A quarterly GST/HST registration with books, people and tax postings for the G-03 tests."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.ledger.models import Account
from numo9.ledger.services import post_journal
from numo9.ledger.template import load_template
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration
from tests.journal_helpers import people

TODAY = dt.date(2026, 6, 1)


def quarterly_books(name: str = "Returns Ltd.") -> tuple[Any, list[FilingPeriod], dict[str, Any]]:
    """(registration, its 2026 quarters, {"owner", "adviser"}) with the Ontario chart."""
    reg = registration(name, stop=dt.date(2026, 12, 31))
    load_template(reg.organisation, "ON")
    periods, _warnings = switch_frequency(reg, "quarterly", dt.date(2026, 1, 1), today=TODAY)
    return reg, periods, people(reg.organisation)


def account(org: Any, role: str = "", **lookup: Any) -> Account:
    with org_context(org):
        query = (
            Account.objects.filter(system_role=role) if role else Account.objects.filter(**lookup)
        )
        return query.order_by("code")[0]


def post_sale(org: Any, date: dt.date, user: Any, tax: str = "13.00", **spec: Any) -> Any:
    """A sale of 100.00 plus ``tax`` of GST/HST: Dr AR, Cr revenue, Cr GST/HST payable."""
    amount = Decimal(tax)
    lines = [
        LineSpec(account(org, "accounts_receivable"), debit=Decimal("100.00") + amount),
        LineSpec(account(org, type="revenue"), credit=Decimal("100.00")),
        LineSpec(account(org, "gst_hst_payable"), credit=amount),
    ]
    with org_context(org):
        return post_journal(
            JournalSpec(date=date, lines=lines, **spec), organisation=org, user=user
        )


def post_purchase(org: Any, date: dt.date, user: Any, tax: str = "13.00", **spec: Any) -> Any:
    """A purchase of 100.00 plus ``tax`` of claimable GST/HST: Dr expense, Dr ITC, Cr AP."""
    amount = Decimal(tax)
    lines = [
        LineSpec(account(org, type="expense"), debit=Decimal("100.00")),
        LineSpec(account(org, "itc_receivable"), debit=amount),
        LineSpec(account(org, "accounts_payable"), credit=Decimal("100.00") + amount),
    ]
    with org_context(org):
        return post_journal(
            JournalSpec(date=date, lines=lines, **spec), organisation=org, user=user
        )

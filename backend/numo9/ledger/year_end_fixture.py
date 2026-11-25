"""Year-end fixture (C-06-T10): a full fiscal year (1 Jan – 31 Dec 2026) with a known net income
in each book, for the year-end roll.

``load()`` (``manage.py load_year_end_fixture``) — idempotent: **Northwind Year-End Ltd.**, the
Ontario chart, and the year's journals (system postings, as history):

- sales 10,000.00 a month (both books) — 120,000.00;
- rent 5,000.00 a month (both books) — 60,000.00;
- wages 32,000.00 in December (both books);
- amortization 3,000.00 — **accounting book only** (the books' difference);
- capital cost allowance 4,500.00 — **tax book only**.

Net income: **accounting 25,000.00**, **tax 23,500.00** (``EXPECTED``): the year-end close must
credit retained earnings by exactly that in each book and leave every revenue and expense
account at zero after 31 Dec 2026.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from django.db import transaction

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .models import Account, Book, JournalEntry
from .services import post_journal
from .validation import JournalSpec, LineSpec

ORG_NAME = "Northwind Year-End Ltd."
FISCAL_YEAR = (dt.date(2026, 1, 1), dt.date(2026, 12, 31))
EXPECTED = {Book.ACCOUNTING: Decimal("25000.00"), Book.TAX: Decimal("23500.00")}
NARRATION = "Year-end fixture"


def _accounts() -> dict[str, Account]:
    expenses = list(
        Account.objects.filter(type="expense", require_contact=False).order_by("code")[:4]
    )
    return {
        "bank": Account.objects.filter(subtype="bank").order_by("code").first(),  # type: ignore[dict-item]
        "sales": Account.objects.filter(type="revenue").order_by("code").first(),  # type: ignore[dict-item]
        "rent": expenses[0],
        "wages": expenses[1],
        "amortization": expenses[2],
        "cca": expenses[3],
        "assets": Account.objects.filter(type="asset", require_contact=False)
        .exclude(subtype="bank")
        .order_by("code")
        .first(),  # type: ignore[dict-item]
    }


def _post(
    accounts: dict[str, Account],
    day: dt.date,
    what: str,
    debit: str,
    credit: str,
    amount: str,
    book: str = Book.BOTH,
) -> None:
    post_journal(
        JournalSpec(
            date=day,
            lines=[
                LineSpec(account=accounts[debit], debit=Decimal(amount), book=book),
                LineSpec(account=accounts[credit], credit=Decimal(amount), book=book),
            ],
            narration=f"{NARRATION}: {what}",
        ),
        user=None,
    )


def load() -> Organisation:
    """Northwind with its chart and the year's journals (once); the organisation."""
    from .template import load_template

    organisation = Organisation.objects.filter(name=ORG_NAME).order_by("pk").first()
    if organisation is None:
        organisation = Organisation.objects.create(name=ORG_NAME, time_zone="America/Toronto")
        load_template(organisation, "ON")
    with org_context(organisation), transaction.atomic():
        if JournalEntry.objects.filter(narration__startswith=NARRATION).exists():
            return organisation
        accounts = _accounts()
        for month in range(1, 13):
            first = dt.date(2026, month, 1)
            _post(accounts, first, "sales", "bank", "sales", "10000.00")
            _post(accounts, first + dt.timedelta(days=4), "rent", "rent", "bank", "5000.00")
        december = dt.date(2026, 12, 20)
        _post(accounts, december, "wages", "wages", "bank", "32000.00")
        _post(
            accounts, december, "amortization", "amortization", "assets", "3000.00", Book.ACCOUNTING
        )
        _post(accounts, december, "capital cost allowance", "cca", "assets", "4500.00", Book.TAX)
    return organisation

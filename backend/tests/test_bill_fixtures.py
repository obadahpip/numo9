"""E-02-T17 — fixtures: 50 bills across every province and territory (HST, GST + PST with the
PST a cost, GST + QST, GST alone; 50 % meals lines, zero-rated lines, holdbacks; drafts,
awaiting payment and void), each posted bill balanced against its journal with AP + holdback =
the total; the figures, claimable ITC and cost per bill match the snapshot."""

from __future__ import annotations

import datetime as dt
import os
from collections import Counter
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from numo9.ledger.models import JournalLine, SystemRole
from numo9.orgsettings.models import TaxRegistration
from numo9.purchases.bills import itc_split
from numo9.purchases.fixtures import COUNT, PROVINCES, build_bill_fixtures
from numo9.purchases.models import Bill
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill_books

pytestmark = pytest.mark.django_db
SNAPSHOT = Path(__file__).parent / "snapshots" / "bill_fixtures.txt"


@pytest.fixture
def built() -> dict[str, Any]:
    books = bill_books()
    with org_context(books["org"]):
        TaxRegistration(
            organisation=books["org"],
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
    return {"books": books, "bills": build_bill_fixtures(books["org"], books["owner"])}


def province(bill: Bill) -> str:
    return str(bill.contact.addresses.get(kind="billing").province)


def summary(bills: list[Bill]) -> str:
    rows = []
    for bill in bills:
        split = itc_split(bill)
        claimable = sum((Decimal(s["claimable"]) for s in split), Decimal(0))
        cost = sum((Decimal(s["cost"]) for s in split), Decimal(0))
        rows.append(
            f"{bill.number or 'draft':10} {province(bill)} {bill.status:16} {bill.subtotal:>9} "
            f"{bill.tax_total:>8} {bill.total:>9} itc {claimable:>7} cost {cost:>6} "
            f"held {bill.holdback_amount:>7}"
        )
    return "\n".join(rows) + "\n"


def test_fifty_bills_across_every_province(built: dict[str, Any]) -> None:
    org, bills = built["books"]["org"], built["bills"]
    assert len(bills) == COUNT
    with org_context(org):
        assert {province(b) for b in bills} == set(PROVINCES)
        assert Counter(b.status for b in bills) == {"awaiting_payment": 39, "draft": 7, "void": 4}
        partial = [s for b in bills for s in itc_split(b) if Decimal(s["cost"]) > 0]
        assert partial  # meals at 50 % and the provincial PST are costs
        for bill in bills:
            if bill.status == "draft":
                assert bill.number == "" and bill.journal_entry is None
                continue
            lines = JournalLine.objects.filter(entry=bill.journal_entry).select_related("account")
            debit = sum((line.debit for line in lines), Decimal(0))
            credit = sum((line.credit for line in lines), Decimal(0))
            payable = sum(
                (
                    line.credit
                    for line in lines
                    if line.account.system_role in (SystemRole.AP, SystemRole.HOLDBACK_PAYABLE)
                ),
                Decimal(0),
            )
            assert debit == credit == payable == bill.total, bill.number
        text = summary(bills)
    if os.environ.get("UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(text)
    assert text == SNAPSHOT.read_text()

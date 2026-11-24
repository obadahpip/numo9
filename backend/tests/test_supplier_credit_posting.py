"""E-03-T04/T05 — supplier credits: the models, and approval posts the bill's lines on the other
side — Dr AP / Cr expense (net + non-claimable tax) / Cr ITC — balanced, the ITC reversed in the
credit's period; refusals."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.ledger.models import Account, JournalLine, SystemRole
from numo9.orgsettings.models import TaxRegistration
from numo9.purchases.bill_posting import approve as approve_bill
from numo9.purchases.models import SupplierCredit, SupplierCreditLine, SupplierCreditStatus
from numo9.purchases.supplier_credits import SupplierCreditRefused, approve, recalculate
from numo9.tax.resolver import code_for
from numo9.tenancy.context import org_context
from tests.bill_helpers import DAY, bill, bill_books

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def books() -> dict[str, Any]:
    books = bill_books()
    with org_context(books["org"]):
        TaxRegistration(
            organisation=books["org"],
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
        books["meals"] = Account.objects.get(itc_restriction_pct=D("50"))
    return books


def credit(
    books: dict[str, Any],
    lines: list[tuple[str, str]],
    *,
    tax: str = "purchase.ON.standard",
    account: Any = None,
    supplier: str = "supplier",
    **fields: Any,
) -> SupplierCredit:
    org = books["org"]
    with org_context(org):
        note = SupplierCredit(organisation=org, contact=books[supplier], date=DAY, **fields)
        note.save()
        for position, (quantity, price) in enumerate(lines):
            SupplierCreditLine(
                organisation=org,
                document=note,
                position=position,
                description=f"Line {position + 1}",
                quantity=D(quantity),
                unit_price=D(price),
                account=account or books["expense"],
                tax_code=code_for(tax, "purchase", DAY, org) if tax else None,
            ).save()
        return recalculate(note)


def posted(entry: Any) -> dict[str, tuple[Decimal, Decimal]]:
    out: dict[str, tuple[Decimal, Decimal]] = {}
    for line in JournalLine.objects.filter(entry=entry).select_related("account"):
        key = line.account.system_role or line.account.code
        debit, credit_ = out.get(key, (D("0"), D("0")))
        out[key] = (debit + line.debit, credit_ + line.credit)
    return out


def test_posting_reverses_expense_and_itc(books: dict[str, Any]) -> None:
    original = approve_bill(
        bill(books, [("2", "500.00")], tax="purchase.ON.standard", supplier_invoice_no="C-1"),
        books["owner"],
    )
    note = credit(books, [("1", "200.00")], bill=original, supplier_reference="SC-9")
    done = approve(note, books["owner"])
    assert done.status == SupplierCreditStatus.APPROVED and done.total == D("226.00")
    with org_context(books["org"]):
        lines = posted(done.journal_entry)
        assert lines[SystemRole.AP] == (D("226.00"), D("0"))
        assert lines[books["expense"].code] == (D("0"), D("200.00"))
        assert lines[SystemRole.ITC_RECEIVABLE] == (D("0"), D("26.00"))
        assert sum(d for d, _c in lines.values()) == sum(c for _d, c in lines.values())
        entry = done.journal_entry
        assert entry is not None and entry.date == DAY
        assert entry.source_type == "purchases.supplier_credit"


def test_restricted_itc_reverses_only_the_claimed_part(books: dict[str, Any]) -> None:
    done = approve(credit(books, [("1", "100.00")], account=books["meals"]), books["owner"])
    with org_context(books["org"]):
        lines = posted(done.journal_entry)
    assert lines[books["meals"].code] == (D("0"), D("106.50"))
    assert lines[SystemRole.ITC_RECEIVABLE] == (D("0"), D("6.50"))
    assert lines[SystemRole.AP] == (D("113.00"), D("0"))


def test_refusals_and_model_checks(books: dict[str, Any]) -> None:
    with pytest.raises(SupplierCreditRefused) as error:
        approve(credit(books, [("1", "0.00")]), books["owner"])
    assert error.value.code == "purchases.supplier_credit.total_not_positive"
    other = bill(books, [("1", "50.00")], supplier="other")
    with pytest.raises(SupplierCreditRefused) as error:
        approve(credit(books, [("1", "10.00")], bill=other), books["owner"])
    assert error.value.code == "purchases.supplier_credit.bill_mismatch"
    with pytest.raises(IntegrityError), transaction.atomic():
        credit(books, [("1", "10.00")], status=SupplierCreditStatus.APPROVED)

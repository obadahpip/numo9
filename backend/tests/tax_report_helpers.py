"""Tax reports (G-05) fixture: an Ontario seller registered for GST/HST with, in Q2 2026,

- invoice INV-0001 (10 Apr): 1,000.00 + HST 130.00;
- invoice INV-0002 (15 May): 500.00 + HST 65.00;
- bill (20 Apr): meals 200.00 + HST 26.00 — ITC restricted to 50 % (13.00 recoverable);
- bill (5 May): supplies 1,000.00 + HST 130.00 (all recoverable);
- a manual journal (31 May) coded straight to GST/HST payable: Dr expense 10.00 / Cr GST/HST
  payable 10.00 — no tax line: the tie-out names it.

Collected 195.00; recoverable 143.00; non-recoverable 13.00 (meals).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.contacts.models import Address, AddressKind
from numo9.ledger.models import Account
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import TaxRegistration
from numo9.purchases.bill_posting import approve as approve_bill
from numo9.sales.posting import approve as approve_invoice
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books
from tests.contact_helpers import contact
from tests.sales_helpers import draft

Q2 = (dt.date(2026, 4, 1), dt.date(2026, 6, 30))


def tax_books() -> dict[str, Any]:
    books = bill_books("Refined Interiors Inc.")
    org = books["org"]
    with org_context(org):
        TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
        books["meals"] = Account.objects.get(itc_restriction_pct=Decimal("50"))
        books["revenue"] = Account.objects.filter(subtype="revenue").order_by("code").first()
        books["gst"] = Account.objects.get(system_role="gst_hst_payable")
        books["itc"] = Account.objects.get(system_role="itc_receivable")
        customer = contact(org, "Maple Leaf Supply Ltd.", roles=["customer"])
        Address(
            organisation=org,
            contact=customer,
            kind=AddressKind.BILLING,
            country="CA",
            province="ON",
            city="Toronto",
        ).save()
    sales = {"org": org, "revenue": books["revenue"], "customers": {"ON": customer}}
    books["sales"] = sales
    owner = books["owner"]
    books["invoices"] = [
        approve_invoice(
            draft(sales, [("1", "1000.00", "sales.ON.standard")], date=dt.date(2026, 4, 10)),
            owner,
        ),
        approve_invoice(
            draft(sales, [("1", "500.00", "sales.ON.standard")], date=dt.date(2026, 5, 15)),
            owner,
        ),
    ]
    books["bills"] = [
        approve_bill(
            bill(
                books,
                [("1", "200.00")],
                tax="purchase.ON.standard",
                account=books["meals"],
                date=dt.date(2026, 4, 20),
                supplier_invoice_no="M-1",
            ),
            owner,
        ),
        approve_bill(
            bill(
                books,
                [("1", "1000.00")],
                tax="purchase.ON.standard",
                date=dt.date(2026, 5, 5),
                supplier_invoice_no="S-1",
            ),
            owner,
        ),
    ]
    with org_context(org):
        books["direct"] = post_journal(
            JournalSpec(
                date=dt.date(2026, 5, 31),
                narration="GST correction",
                lines=[
                    LineSpec(books["expense"], debit=Decimal("10.00")),
                    LineSpec(books["gst"], credit=Decimal("10.00")),
                ],
            ),
            user=owner,
        )
    return books


JUNE = (dt.date(2026, 6, 1), dt.date(2026, 6, 30))


def june_books(*, with_inv_0001: bool = True) -> dict[str, Any]:
    """The worked example of ``docs/specs/gst-hst-return-line-mapping.md`` §4: an Ontario monthly
    filer's June 2026 — taxable, zero-rated and exempt sales, an ordinary bill, a meals bill at
    50 % and a BC bill with GST and PST. ``period``: the June filing period."""
    from numo9.tax.filing_service import switch_frequency
    from numo9.tax.models import FilingPeriod

    books = bill_books("Refined Interiors Inc.")
    org, owner = books["org"], books["owner"]
    with org_context(org):
        reg = TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        )
        reg.save()
        books["meals"] = Account.objects.get(itc_restriction_pct=Decimal("50"))
        books["revenue"] = Account.objects.filter(subtype="revenue").order_by("code").first()
        customer = contact(org, "Maple Leaf Supply Ltd.", roles=["customer"])
        Address(
            organisation=org,
            contact=customer,
            kind=AddressKind.BILLING,
            country="CA",
            province="ON",
            city="Toronto",
        ).save()
    switch_frequency(reg, "monthly", dt.date(2026, 1, 1), today=dt.date(2026, 6, 1))
    with org_context(org):
        books["period"] = FilingPeriod.objects.get(registration=reg, start=JUNE[0])
    books["registration"] = reg
    sales = {"org": org, "revenue": books["revenue"], "customers": {"ON": customer}}
    books["sales"] = sales
    day = dt.date(2026, 6, 10)
    invoices = [("1000.00", "sales.ON.standard")] if with_inv_0001 else []
    invoices += [("200.00", "sales.zero_rated"), ("50.00", "sales.exempt")]
    books["invoices"] = [
        approve_invoice(draft(sales, [("1", amount, code)], date=day), owner)
        for amount, code in invoices
    ]
    books["bills"] = [
        approve_bill(
            bill(books, [("1", amount)], tax=code, date=day, supplier_invoice_no=ref, **extra),
            owner,
        )
        for amount, code, ref, extra in (
            ("400.00", "purchase.ON.standard", "B-1", {}),
            ("100.00", "purchase.ON.standard", "B-2", {"account": books["meals"]}),
            ("100.00", "purchase.BC.standard", "B-3", {}),
        )
    ]
    return books

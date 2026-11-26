"""Conversion fixtures (C-05-T13): balanced and unbalanced conversion sets, REFINED included.

``build(organisation, key, user=None)`` starts the organisation's conversion and enters the set
``key`` of ``SETS`` (the organisation's chart is the Canadian template, C-01; the customers,
suppliers and shareholder the set needs are created). Each set carries what it must do
(``Expect``): whether it finalises and, if not, the refusal and the difference it names, and
whether the opening equity is missing (the K-09 signal of C-05-T14).

- ``balanced`` — a small trading company at 1 Jan 2026: bank, petty cash, two open invoices
  (one partly paid) and two open bills matching Accounts receivable / payable, a bank loan,
  share capital and retained earnings → finalises; equity present;
- ``unbalanced`` — the meter's example: debits 120,450.00, credits 120,437.50 → refused,
  ``conversion.unbalanced``, difference 12.50; nothing is plugged;
- ``control_mismatch`` — the balanced set with Accounts receivable entered 100.00 short of its
  invoices → refused, ``conversion.control_mismatch`` naming the account;
- ``refined`` — REFINED Interiors Inc. as the teardown found it (docs/xero_teardown.md §6.11):
  conversion date 1 Jan 2025, **no share capital, no shareholder loan beyond the bank's
  funding, no retained earnings** — only Chequing funded by the shareholder (Due to shareholder,
  with the shareholder as contact). It balances and finalises, but **no equity line** was
  entered: ``opening_equity_missing`` — what K-09 flags.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from django.db import transaction

from numo9.tenancy.context import org_context

from .documents import add_opening_bill, add_opening_invoice
from .models import ConversionSession
from .services import set_line, start_conversion


@dataclass(frozen=True)
class Expect:
    finalises: bool
    code: str = ""  # the refusal's code when it doesn't
    difference: str = "0.00"
    opening_equity_missing: bool = False


@dataclass(frozen=True)
class Document:
    contact: str
    number: str
    date: dt.date
    total: str
    outstanding: str | None = None


@dataclass(frozen=True)
class ConversionSet:
    key: str
    description: str
    conversion_date: dt.date
    #: (account code, debit, credit, contact name or "")
    lines: tuple[tuple[str, str, str, str], ...]
    expect: Expect
    invoices: tuple[Document, ...] = field(default=())
    bills: tuple[Document, ...] = field(default=())


JAN_2026 = dt.date(2026, 1, 1)
BALANCED_INVOICES = (
    Document("Maple Leaf Design Ltd", "INV-0981", dt.date(2025, 11, 20), "2260.00"),
    Document("Harbour View Hotels", "INV-0994", dt.date(2025, 12, 12), "3390.00", "1390.00"),
)
BALANCED_BILLS = (
    Document("Cedar Supply Co.", "C-7781", dt.date(2025, 12, 5), "565.00"),
    Document("Northern Hydro", "NH-2025-12", dt.date(2025, 12, 28), "412.30"),
)
#: Chequing 18,240.55 + petty cash 150.00 + AR 3,650.00 + equipment 9,800.00 = 31,840.55
#: = AP 977.30 + bank loan 12,000.00 + shares 100.00 + retained earnings 18,763.25.
BALANCED_LINES: tuple[tuple[str, str, str, str], ...] = (
    ("1010", "18240.55", "", ""),
    ("1000", "150.00", "", ""),
    ("1100", "3650.00", "", ""),
    ("1630", "9800.00", "", ""),
    ("2000", "", "977.30", ""),
    ("2700", "", "12000.00", ""),
    ("3000", "", "100.00", ""),
    ("3200", "", "18763.25", ""),
)

SETS: dict[str, ConversionSet] = {
    s.key: s
    for s in (
        ConversionSet(
            "balanced",
            "A trading company at 1 Jan 2026: bank, open invoices and bills, a loan and equity.",
            JAN_2026,
            BALANCED_LINES,
            Expect(finalises=True),
            BALANCED_INVOICES,
            BALANCED_BILLS,
        ),
        ConversionSet(
            "unbalanced",
            "Debits 120,450.00, credits 120,437.50: out by 12.50.",
            JAN_2026,
            (("1010", "120450.00", "", ""), ("3200", "", "120437.50", "")),
            Expect(finalises=False, code="conversion.unbalanced", difference="12.50"),
        ),
        ConversionSet(
            "control_mismatch",
            "The balanced set with Accounts receivable 100.00 short of its invoices.",
            JAN_2026,
            tuple(
                (code, "3550.00", "", "")
                if code == "1100"
                else (code, debit, "", "")
                if code == "1010"
                else (code, debit, "18663.25", "")
                if code == "3200"
                else (code, debit, credit, contact)
                for code, debit, credit, contact in BALANCED_LINES
            ),
            Expect(finalises=False, code="conversion.control_mismatch"),
            BALANCED_INVOICES,
            BALANCED_BILLS,
        ),
        ConversionSet(
            "refined",
            "REFINED Interiors Inc. (teardown §6.11): no share capital, no retained earnings — "
            "only Chequing funded by the shareholder.",
            dt.date(2025, 1, 1),
            (
                ("1010", "2500.00", "", ""),
                ("2600", "", "2500.00", "REFINED shareholder"),
            ),
            Expect(finalises=True, opening_equity_missing=True),
        ),
    )
}


def _contact(organisation: Any, name: str, role: str) -> Any:
    from numo9.contacts.models import Contact

    found = Contact.objects.filter(display_name=name, deleted_at__isnull=True).first()
    if found is None:
        found = Contact(organisation=organisation, display_name=name, roles=[role])
        found.save()
    return found


def build(organisation: Any, key: str, user: Any = None) -> ConversionSession:
    """Start the organisation's conversion and enter the set ``key`` (module docstring)."""
    from numo9.ledger.models import Account

    spec = SETS[key]
    with org_context(organisation), transaction.atomic():
        session = start_conversion(organisation, spec.conversion_date, user=user)
        for doc in spec.invoices:
            add_opening_invoice(
                session,
                contact=_contact(organisation, doc.contact, "customer"),
                number=doc.number,
                date=doc.date,
                due_date=doc.date + dt.timedelta(days=30),
                total=doc.total,
                outstanding=doc.outstanding,
                user=user,
            )
        for doc in spec.bills:
            add_opening_bill(
                session,
                contact=_contact(organisation, doc.contact, "supplier"),
                supplier_invoice_no=doc.number,
                date=doc.date,
                due_date=doc.date + dt.timedelta(days=30),
                total=doc.total,
                outstanding=doc.outstanding,
                user=user,
            )
        accounts = {a.code: a for a in Account.objects.all()}
        for code, debit, credit, contact in spec.lines:
            set_line(
                session,
                accounts[code],
                debit=debit or 0,
                credit=credit or 0,
                contact=_contact(organisation, contact, "employee") if contact else None,
            )
        return session

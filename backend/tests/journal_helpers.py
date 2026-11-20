"""Shared helpers for the journal-rules tests (C-03)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.files.models import Document
from numo9.ledger.models import Account
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account


def document(org: Organisation, name: str = "receipt.pdf", **fields: Any) -> Document:
    item = Document(organisation=org, name=name, file_key=f"org/{org.public_id}/x/{name}", **fields)
    item.save()
    return item


def chart(org: Organisation) -> dict[str, Account]:
    """Chequing 1000, Petty Cash 1010, Accounts receivable 1200, Sales 4000, Rent 5400, Office
    supplies 6100 (call inside the organisation's context)."""
    return {
        "chequing": account(org, "1000", "Chequing", subtype="bank"),
        "petty": account(org, "1010", "Petty Cash", subtype="bank"),
        "ar": account(org, "1200", "Accounts receivable", subtype="current_asset"),
        "sales": account(org, "4000", "Sales", subtype="revenue"),
        "rent": account(org, "5400", "Rent"),
        "office": account(org, "6100", "Office supplies"),
    }


def pay(
    debit: Account,
    credit: Account,
    amount: str,
    date: dt.date = dt.date(2026, 6, 15),
    **fields: Any,
) -> JournalSpec:
    """A two-line journal: Dr ``debit`` / Cr ``credit`` ``amount``."""
    contact = fields.pop("contact", None)
    tracking = fields.pop("tracking", {})
    return JournalSpec(
        date=date,
        lines=(
            LineSpec(debit, debit=Decimal(amount), contact=contact, tracking=tracking),
            LineSpec(credit, credit=Decimal(amount)),
        ),
        **fields,
    )

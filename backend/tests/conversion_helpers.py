"""Conversion books for the C-05 tests: an Ontario organisation with the template chart (1010
Chequing, 1100 Accounts receivable, 2000 Accounts payable, 3000 Common shares, 3200 Retained
earnings…), two customers, a supplier, the owner (not an adviser) and an assigned practice
accountant (adviser), and a draft conversion at 1 Jan 2026."""

from __future__ import annotations

import datetime as dt
from typing import Any

from numo9.conversion.services import start_conversion
from numo9.ledger.models import Account
from numo9.tenancy.context import org_context
from tests.contact_helpers import contact
from tests.journal_helpers import people
from tests.sales_helpers import sales_books

CONVERSION_DATE = dt.date(2026, 1, 1)
BEFORE = dt.date(2025, 11, 15)


def conversion_books(name: str = "Refined Interiors Inc.") -> dict[str, Any]:
    books = sales_books(name)
    org = books["org"]
    with org_context(org):
        books["supplier"] = contact(org, "Cedar Supply Co.", roles=["supplier"])
        books["accounts"] = {a.code: a for a in Account.objects.all()}
    books.update(people(org))
    books["session"] = start_conversion(org, CONVERSION_DATE, user=books["owner"])
    return books


def acct(books: dict[str, Any], code: str) -> Account:
    found: Account = books["accounts"][code]
    return found

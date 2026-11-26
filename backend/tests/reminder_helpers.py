"""Invoice reminders (D-07) test helpers: ``reminder_books()`` — the D-03a sales books (Ontario
seller, customers in ON/BC/QC) with the owner, two people at the Ontario customer (one emailed
with a mobile number, one not emailed) and ``invoice()`` approving an invoice due on a date."""

from __future__ import annotations

import datetime as dt
from typing import Any

from numo9.contacts.models import ContactPerson
from numo9.sales.posting import approve
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books


def reminder_books() -> dict[str, Any]:
    books = sales_books("Maple Leaf Supply Ltd.")
    books["owner"] = people(books["org"])["owner"]
    org, customer = books["org"], books["customers"]["ON"]
    with org_context(org):
        ContactPerson.objects.create(
            organisation=org,
            contact=customer,
            first_name="Ana",
            email="ap@oncustomer.ca",
            phone="416 555 0199",
            include_in_emails=True,
            is_primary=True,
        )
        ContactPerson.objects.create(
            organisation=org,
            contact=customer,
            first_name="Bo",
            email="bo@oncustomer.ca",
            include_in_emails=False,
        )
    return books


def invoice(
    books: dict[str, Any],
    amount: str = "100.00",
    *,
    date: dt.date = dt.date(2026, 6, 1),
    due: dt.date = dt.date(2026, 7, 1),
    province: str = "ON",
) -> Any:
    made = draft(
        books, [("1", amount, "sales.ON.standard")], date=date, due_date=due, province=province
    )
    return approve(made, books["owner"])

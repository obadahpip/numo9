"""Period close (C-06) test helpers: an Ontario organisation with its chart, a fiscal year ending
31 December, the owner (not an adviser) and an assigned practice accountant (adviser)."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.ledger.models import Account
from numo9.ledger.services import post_journal
from numo9.ledger.template import load_template
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people


def close_books(name: str = "Refined Interiors Inc.") -> dict[str, Any]:
    org = Organisation.objects.create(name=name)
    load_template(org, "ON")
    who = people(org)
    with org_context(org):
        accounts = {
            "bank": Account.objects.filter(subtype="bank").order_by("code").first(),
            "revenue": Account.objects.filter(type="revenue").order_by("code").first(),
            "expense": Account.objects.filter(type="expense").order_by("code").first(),
            "re": Account.objects.get(system_role="retained_earnings"),
        }
    return {"org": org, **who, **accounts}


def post(
    books: dict[str, Any], day: dt.date, debit: str, credit: str, amount: str, book: str = "both"
) -> Any:
    """A balanced two-line journal dated ``day``: Dr ``debit`` / Cr ``credit`` (account keys)."""
    with org_context(books["org"]):
        return post_journal(
            JournalSpec(
                date=day,
                lines=[
                    LineSpec(account=books[debit], debit=Decimal(amount), book=book),
                    LineSpec(account=books[credit], credit=Decimal(amount), book=book),
                ],
                narration="test",
            ),
            user=books["adviser"],
        )

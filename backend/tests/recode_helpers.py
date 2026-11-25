"""Find & recode (C-07) test helpers: ``recode_books()`` — the period-close books (C-06) with a
second expense account, two contacts and four posted journals of known coding:

| # | Date | Lines | By |
|---|---|---|---|
| 1 | 10 Jan 2026 | Dr bank 1,000.00 / Cr revenue 1,000.00 (tax ``sales.ON.standard``, Acme, type sales) | adviser |
| 2 | 15 Feb 2026 | Dr expense 200.00 (tax ``purchase.ON.standard``, Bolt, region east) / Cr bank | owner |
| 3 | 20 Mar 2026 | Dr expense2 50.00 (region west) / Cr bank, accounting book, "Office rent March" | adviser |
| 4 | 5 Apr 2026 | Dr expense 75.00 / Cr bank, tax book | adviser |
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from numo9.ledger.models import Account
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from tests.contact_helpers import contact
from tests.period_close_helpers import close_books


def recode_books() -> dict[str, Any]:
    books = close_books()
    org = books["org"]
    with org_context(org):
        books["expense2"] = (
            Account.objects.filter(type="expense", require_contact=False)
            .exclude(pk=books["expense"].pk)
            .order_by("code")
            .first()
        )
        books["acme"] = contact(org, "Acme Ltd", roles=["customer"])
        books["bolt"] = contact(org, "Bolt Supply", roles=["supplier"])

        def post(day: dt.date, lines: list[LineSpec], user: Any, **extra: Any) -> Any:
            return post_journal(JournalSpec(date=day, lines=lines, **extra), user=user)

        b = books
        books["entries"] = [
            post(
                dt.date(2026, 1, 10),
                [
                    LineSpec(b["bank"], debit=Decimal("1000.00")),
                    LineSpec(
                        b["revenue"],
                        credit=Decimal("1000.00"),
                        tax_code="sales.ON.standard",
                        contact=b["acme"],
                    ),
                ],
                b["adviser"],
                type="sales",
                narration="Fit-out INV-0001",
            ),
            post(
                dt.date(2026, 2, 15),
                [
                    LineSpec(
                        b["expense"],
                        debit=Decimal("200.00"),
                        tax_code="purchase.ON.standard",
                        contact=b["bolt"],
                        tracking={"region": "east"},
                    ),
                    LineSpec(b["bank"], credit=Decimal("200.00")),
                ],
                b["owner"],
                narration="Supplies",
            ),
            post(
                dt.date(2026, 3, 20),
                [
                    LineSpec(
                        b["expense2"],
                        debit=Decimal("50.00"),
                        tracking={"region": "west"},
                        book="accounting",
                    ),
                    LineSpec(b["bank"], credit=Decimal("50.00"), book="accounting"),
                ],
                b["adviser"],
                narration="Office rent March",
            ),
            post(
                dt.date(2026, 4, 5),
                [
                    LineSpec(b["expense"], debit=Decimal("75.00"), book="tax"),
                    LineSpec(b["bank"], credit=Decimal("75.00"), book="tax"),
                ],
                b["adviser"],
                narration="CCA adjustment",
            ),
        ]
    return books

"""D-02-T08 — deposit: accepting a quote that asks a deposit creates a draft deposit invoice
(D-03a) linked to it, for the % of the **accepted** total (the options chosen) or the amount, on
the Customer deposits account; approving it posts Dr AR / Cr Customer deposits; no deposit asked,
no invoice; accepting twice creates one; a deposit above the total is capped."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.sales import quotes as q
from numo9.sales.models import Invoice
from numo9.sales.posting import approve
from numo9.sales.quote_links import accept_with_evidence
from numo9.tenancy.context import org_context
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
TODAY = dt.date.today()


def sent(books: dict[str, Any], **fields: Any) -> Any:
    return q.send(
        quote(
            books,
            [("2", "500", "sales.ON.standard"), {"price": "200", "is_optional": True}],
            date=TODAY,
            expiry=TODAY + dt.timedelta(days=10),
            **fields,
        )
    )


def test_percent_of_the_accepted_total(s3: str) -> None:
    books = sales_books()
    item = sent(books, deposit_type="percent", deposit_value=Decimal("30"))
    with org_context(books["org"]):
        optional = item.lines.get(is_optional=True)
    accept_with_evidence(item, typed_name="Jo Lee", selections={str(optional.public_id): True})
    with org_context(books["org"]):
        item.refresh_from_db()
        deposit = item.deposit_invoice
        assert deposit is not None
        assert item.total == Decimal("1330.00")  # 1000 + 130 HST + 200 optional (no tax)
        assert deposit.total == Decimal("399.00")  # 30 % of the accepted total
        assert (deposit.status, deposit.number, deposit.contact_id) == (
            "draft",
            "",
            item.contact_id,
        )
        assert deposit.due_date == deposit.date and deposit.reference == item.number
        line = deposit.lines.get()
        assert line.description == f"Deposit for quote {item.number} (30 %)"
        assert line.account is not None and line.account.code == "2300"
        assert line.tax_code is None and line.amount == Decimal("399.00")
        assert deposit.deposit_for == item
    again = q.accept(item)
    assert again.deposit_invoice_id == deposit.pk
    with org_context(books["org"]):
        assert Invoice.objects.filter(reference=item.number).count() == 1


def test_amount_none_cap_and_posting() -> None:
    books = sales_books()
    owner = User.objects.create_user("owner@refined.ca", name="Owner")
    fixed = q.accept(sent(books, deposit_type="amount", deposit_value=Decimal("250")))
    with org_context(books["org"]):
        deposit = fixed.deposit_invoice
        assert deposit is not None and deposit.total == Decimal("250.00")
        assert deposit.lines.get().description == f"Deposit for quote {fixed.number}"
    posted = approve(deposit, owner)
    assert posted.journal_entry is not None
    with org_context(books["org"]):
        rows = {
            (r.account.code, r.debit, r.credit)
            for r in posted.journal_entry.lines.select_related("account")
        }
    assert ("2300", Decimal("0"), Decimal("250.00")) in rows
    assert any(debit == Decimal("250.00") for _code, debit, _credit in rows)

    plain = q.accept(sent(books))
    assert plain.deposit_invoice_id is None
    capped = q.accept(sent(books, deposit_type="amount", deposit_value=Decimal("99999")))
    with org_context(books["org"]):
        assert capped.deposit_invoice is not None
        assert capped.deposit_invoice.total == capped.total == Decimal("1130.00")

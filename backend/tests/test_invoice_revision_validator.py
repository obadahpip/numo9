"""D-03b-T05 — the revision validator: a reason is required; the currency never changes; the
customer changes only while nothing is applied to the invoice; other fields can't be set; every
refusal is a field error."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.banking.services import create_bank_account
from numo9.sales.posting import approve
from numo9.sales.receipts import receive_payment
from numo9.sales.revisions import RevisionInvalid, build_revision, validate_revision
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import DAY, draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    books["invoice"] = approve(draft(books, [("1", "100.00", "sales.ON.standard")]), books["owner"])
    return books


def errors(books: dict[str, Any], **changes: Any) -> dict[str, list[str]]:
    invoice = books["invoice"]
    with org_context(books["org"]):
        invoice.refresh_from_db()
        opened = build_revision(invoice)
        opened.reason = changes.pop("reason", "Quantity corrected")
        for key, value in changes.items():
            if key == "lines":
                opened.lines = value
            elif key == "line":
                opened.lines[0].update(value)
            else:
                opened.header[key] = value
        try:
            validate_revision(invoice, opened)
        except RevisionInvalid as refused:
            assert refused.code == "sales.revision.invalid"
            return {k: [str(m) for m in v] for k, v in refused.message_dict.items()}
    return {}


def test_a_valid_revision_passes(books: dict[str, Any]) -> None:
    assert errors(books, line={"quantity": Decimal("2")}, reference="PO-9") == {}


def test_each_rule_is_a_field_error(books: dict[str, Any]) -> None:
    assert errors(books, reason="  ") == {"reason": ["Say why the invoice is revised."]}
    assert list(errors(books, currency="USD")) == ["currency"]
    assert list(errors(books, number="101-9")) == ["number"]
    assert list(errors(books, lines=[])) == ["lines"]
    assert list(errors(books, line={"journal": 1, "quantity": "two"})) == ["lines[1]"]
    other = books["customers"]["BC"]
    assert errors(books, contact_id=other.pk) == {}  # nothing applied yet: allowed


def test_the_customer_is_fixed_once_paid(books: dict[str, Any]) -> None:
    bank = create_bank_account(books["org"], type="chequing", display_name="TD Chequing")
    receive_payment(books["customers"]["ON"], bank, DAY, Decimal("50.00"), books["owner"])
    found = errors(books, contact_id=books["customers"]["BC"].pk)
    assert list(found) == ["contact_id"] and "remove them" in found["contact_id"][0]

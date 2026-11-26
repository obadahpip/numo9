"""D-03b-T04 — the revision builder: a posted invoice's current revision cloned into an
editable draft equals the current snapshot; editing the draft changes nothing stored."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.sales.posting import approve
from numo9.sales.revisions import build_revision, document_snapshot
from numo9.tenancy.context import org_context
from tests.journal_helpers import people
from tests.sales_helpers import draft, sales_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = sales_books()
    books.update(people(books["org"]))
    return books


def test_the_clone_equals_the_current_snapshot(books: dict[str, Any]) -> None:
    invoice = approve(
        draft(books, [("2", "50.00", "sales.ON.standard"), ("1", "10.00", "sales.exempt")]),
        books["owner"],
    )
    with org_context(books["org"]):
        invoice.refresh_from_db()
        opened = build_revision(invoice)
        current = invoice.current_revision
        assert opened.document() == current.snapshot["document"]
        assert opened.document() == document_snapshot(invoice)
        assert (opened.revision, opened.base_version) == (0, invoice.version)
        assert [line["quantity"] for line in opened.lines] == [Decimal("2"), Decimal("1")]
        assert opened.header["contact_id"] == invoice.contact_id

        opened.lines[0]["quantity"] = Decimal("3")  # in memory only
        opened.header["reference"] = "PO-1"
        invoice.refresh_from_db()
        current.refresh_from_db()
        assert opened.document() != current.snapshot["document"]
        assert build_revision(invoice).document() == current.snapshot["document"]
        assert invoice.lines.order_by("position").first().quantity == Decimal("2")


def test_a_draft_has_nothing_to_revise(books: dict[str, Any]) -> None:
    with org_context(books["org"]), pytest.raises(ValueError):
        build_revision(draft(books, [("1", "10.00", "sales.ON.standard")]))

"""K-09-T07, T08, T11 — rules over manual journals: JOURNAL_TO_CASH,
EXPENSE_JOURNAL_NO_CONTACT, EXPENSE_JOURNAL_NO_ATTACHMENT, ROUND_AMOUNT, WEEKEND_POSTING.

Acceptance: both teardown journals flagged by JOURNAL_TO_CASH (and by the two expense-journal
rules); journals that don't touch cash, sales postings and reversed journals are not.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest

from numo9.assurance.rules.base import evaluate, registry
from numo9.ledger.services import reverse
from numo9.tenancy.context import org_context
from tests.assurance_helpers import NOW, post, refined
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


def _subjects(books: dict, code: str, **params: object) -> dict[str, object]:
    hits = evaluate(books["org"], code, now=NOW, params=params or None)
    return {h.subject_id: h for h in hits}


# ---- JOURNAL_TO_CASH (K-09-T07) -------------------------------------------------------------


def test_both_teardown_journals_post_to_cash() -> None:
    books = refined()
    found = _subjects(books, "JOURNAL_TO_CASH")
    assert set(found) == {str(books["journal1"].public_id), str(books["journal2"].public_id)}
    hit = found[str(books["journal1"].public_id)]
    assert hit.amount == Decimal("417.22")  # type: ignore[attr-defined]
    text = registry.get("JOURNAL_TO_CASH").explain(hit.details)  # type: ignore[attr-defined]
    assert "(3 Jun 2026) posts 417.22 to Petty Cash" in text


def test_journal_without_cash_reversed_and_small_ones_are_not_flagged() -> None:
    books = refined()
    org = books["org"]
    with org_context(org):
        accrual = post(
            books["accounts"],
            dt.date(2026, 7, 1),
            "Accrual",
            (("5920", "50.00", "0"), ("2900", "0", "50.00")),
        )
        reverse(books["journal2"], user=None)
    found = _subjects(books, "JOURNAL_TO_CASH")
    assert set(found) == {str(books["journal1"].public_id)}  # journal 2 reversed, not its mirror
    assert str(accrual.public_id) not in found
    assert _subjects(books, "JOURNAL_TO_CASH", min_amount="500") == {}


def test_sales_postings_to_cash_are_not_manual_journals() -> None:
    books = refined()
    org = books["org"]
    with org_context(org):
        books["accounts"]["1010"] = account(org, "1010", "Chequing", subtype="bank")
        sale = post(
            books["accounts"],
            dt.date(2026, 7, 1),
            "Cash sale",
            (("1010", "100.00", "0"), ("4000", "0", "100.00")),
            type="sales",
        )
    assert str(sale.public_id) not in _subjects(books, "JOURNAL_TO_CASH")


# ---- EXPENSE_JOURNAL_NO_CONTACT / NO_ATTACHMENT (K-09-T08) ---------------------------------


def test_teardown_journals_have_no_contact_and_no_attachment() -> None:
    books = refined()
    both = {str(books["journal1"].public_id), str(books["journal2"].public_id)}
    no_contact = _subjects(books, "EXPENSE_JOURNAL_NO_CONTACT")
    assert set(no_contact) == both
    hit = no_contact[str(books["journal1"].public_id)]
    assert hit.details["lines"] == [1, 2, 3, 4]  # type: ignore[attr-defined]
    assert hit.amount == Decimal("417.22")  # type: ignore[attr-defined]
    assert set(_subjects(books, "EXPENSE_JOURNAL_NO_ATTACHMENT")) == both


def test_contact_and_attachment_clear_the_findings() -> None:
    from numo9.files.attachments import attach
    from tests.contact_helpers import contact
    from tests.journal_helpers import document

    books = refined()
    org = books["org"]
    with org_context(org):
        supplier = contact(org, "Staples", roles=["supplier"])
        with_contact = post(
            books["accounts"],
            dt.date(2026, 7, 2),
            "Supplies",
            (("5515", "40.00", "0"), ("2900", "0", "40.00")),
            contact=supplier,
        )
        attach(document(org), "ledger.JournalEntry", books["journal2"].public_id, user=None)
    no_contact = _subjects(books, "EXPENSE_JOURNAL_NO_CONTACT")
    assert str(with_contact.public_id) not in no_contact
    no_attachment = _subjects(books, "EXPENSE_JOURNAL_NO_ATTACHMENT")
    assert str(books["journal2"].public_id) not in no_attachment
    assert str(books["journal1"].public_id) in no_attachment

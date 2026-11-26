"""C-05-T07 — corrections after finalising: an adviser posts a correcting opening journal; the
original is never edited.

Acceptance: original JE unchanged; correction linked (to the conversion, with its reason);
refused for a non-adviser, on a draft, without a reason; an unbalanced correction is refused by
the posting engine and posts nothing; the advisers-only balance lock doesn't stop it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from numo9.conversion.corrections import correct
from numo9.conversion.finalise import ConversionRefused, finalise
from numo9.conversion.models import ConversionCorrection
from numo9.conversion.services import set_line
from numo9.ledger.models import JournalEntry, JournalLine
from numo9.tenancy.context import org_context
from tests.conversion_helpers import CONVERSION_DATE, acct, conversion_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    books = conversion_books()
    set_line(books["session"], acct(books, "1010"), debit="1000.00")
    set_line(books["session"], acct(books, "3000"), credit="1000.00")
    return books


def snapshot(entry: JournalEntry) -> list[tuple[Any, ...]]:
    return [
        (line.line_no, line.account_id, line.debit, line.credit)
        for line in JournalLine.objects.filter(entry=entry).order_by("line_no")
    ]


def fix(books: dict[str, Any]) -> list[dict[str, Any]]:
    """Chequing was 1 000 short: a capital contribution (Contributed surplus)."""
    return [
        {"account": acct(books, "1010"), "debit": Decimal("1000.00")},
        {"account": acct(books, "3100"), "credit": Decimal("1000.00")},
    ]


def test_adviser_correction_linked_original_unchanged(books: dict[str, Any]) -> None:
    session = finalise(books["session"], books["owner"], lock=True)
    with org_context(books["org"]):
        original = JournalEntry.objects.get(pk=session.opening_entry_id)
        before = (snapshot(original), original.status, original.updated_at)
    correction = correct(session, fix(books), "Bank statement at 31 Dec", books["adviser"])
    with org_context(books["org"]):
        original.refresh_from_db()
        assert (snapshot(original), original.status, original.updated_at) == before
        entry = correction.entry
        assert entry.is_opening and entry.journal_type == "adjusting"
        assert entry.date == CONVERSION_DATE and entry.pk != original.pk
        assert entry.source_id == str(session.public_id)
        assert list(session.corrections.all()) == [correction]
        assert correction.reason == "Bank statement at 31 Dec"
        assert correction.created_by == books["adviser"]
        assert "Bank statement at 31 Dec" in entry.narration
        assert JournalEntry.objects.count() == 2


@pytest.mark.parametrize(
    ("who", "reason", "code"),
    [
        ("owner", "Wrong bank", "conversion.correction.adviser_only"),
        ("adviser", "  ", "conversion.correction.reason_required"),
    ],
)
def test_refusals(books: dict[str, Any], who: str, reason: str, code: str) -> None:
    session = finalise(books["session"], books["owner"])
    with pytest.raises(ConversionRefused) as caught:
        correct(session, fix(books), reason, books[who])
    assert caught.value.code == code
    with org_context(books["org"]):
        assert not ConversionCorrection.objects.exists()


def test_draft_refused(books: dict[str, Any]) -> None:
    with pytest.raises(ConversionRefused) as caught:
        correct(books["session"], fix(books), "Too early", books["adviser"])
    assert caught.value.code == "conversion.correction.not_finalised"


def test_unbalanced_posts_nothing(books: dict[str, Any]) -> None:
    session = finalise(books["session"], books["owner"])
    lines = fix(books)
    lines[1]["credit"] = Decimal("999.00")
    with pytest.raises(ValidationError):
        correct(session, lines, "Wrong bank", books["adviser"])
    with org_context(books["org"]):
        assert JournalEntry.objects.count() == 1
        assert not ConversionCorrection.objects.exists()

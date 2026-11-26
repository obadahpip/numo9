"""C-07-T07 — undo a recode batch: reverse the re-posts latest first and post the entries again
with their coding before; refused, listing which, when a period is locked since.

Acceptance: undo restores every line's coding (integration + data validation).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.ledger.models import JournalEntry, JournalLine, JournalStatus, RecodeStatus
from numo9.ledger.recode_execute import create_batch, execute
from numo9.ledger.recode_preview import coding
from numo9.ledger.recode_undo import RecodeUndoRefused, undo, undo_blockers
from numo9.orgsettings.models import LockDate
from numo9.tenancy.context import org_context
from tests.recode_helpers import recode_books

pytestmark = pytest.mark.django_db
EVERYTHING = {"conditions": [{"field": "date", "op": "after", "value": "2025-12-31"}]}


@pytest.fixture
def books() -> dict[str, Any]:
    return recode_books()


def pid(books: dict[str, Any], key: str) -> str:
    return str(books[key].public_id)


def live_coding(books: dict[str, Any]) -> list[tuple[Any, ...]]:
    """Every live (posted, not a reversal) line: date, narration, amounts and coding."""
    with org_context(books["org"]):
        lines = (
            JournalLine.objects.filter(
                entry__status=JournalStatus.POSTED, entry__reversal_of__isnull=True
            )
            .select_related("entry", "account", "contact")
            .order_by("entry__date", "entry__narration", "line_no")
        )
        return [
            (
                line.entry.date,
                line.entry.narration,
                line.line_no,
                line.debit,
                line.credit,
                line.book,
                tuple(sorted((k, str(v)) for k, v in coding(line).items())),
            )
            for line in lines
        ]


def balances(books: dict[str, Any]) -> dict[int, Decimal]:
    with org_context(books["org"]):
        out: dict[int, Decimal] = {}
        for line in JournalLine.objects.all():
            out[line.account_id] = out.get(line.account_id, Decimal("0")) + line.debit - line.credit
        return {k: v for k, v in out.items() if v}


def run(books: dict[str, Any], changes: dict[str, Any], criteria: Any = EVERYTHING) -> Any:
    with org_context(books["org"]):
        batch = create_batch(books["org"], criteria, changes, books["adviser"], confirm_tax=True)
        return execute(batch, books["adviser"])


def test_undo_restores_every_line(books: dict[str, Any]) -> None:
    start, sums = live_coding(books), balances(books)
    done = run(
        books,
        {
            "account": pid(books, "expense2"),
            "tracking": {"region": "north"},
            "contact": pid(books, "acme"),
            "tax_code": "",
        },
        {"conditions": [{"field": "account", "op": "is", "value": pid(books, "expense")}]},
    )
    assert done.line_count == 2 and live_coding(books) != start
    with org_context(books["org"]):
        assert undo_blockers(done, books["adviser"]) == []
        undone = undo(done, books["adviser"], reason="Wrong account")
    assert undone.status == RecodeStatus.UNDONE
    assert undone.undone_by == books["adviser"] and undone.undo_reason == "Wrong account"
    assert live_coding(books) == start
    assert balances(books) == sums
    with org_context(books["org"]):
        for change in undone.lines.all():
            assert change.repost_entry and change.undo_reversal_entry and change.undo_repost_entry
            assert change.repost_entry.status == JournalStatus.REVERSED
            assert change.undo_reversal_entry.reversal_of_id == change.repost_entry_id
            assert change.undo_repost_entry.status == JournalStatus.POSTED
        assert AuditEvent.objects.filter(action="ledger.recodebatch.undone").count() == 1
        # undone once
        with pytest.raises(RecodeUndoRefused) as caught:
            undo(undone, books["adviser"])
    assert caught.value.code == "ledger.recode.undo_not_allowed"


def test_a_line_recoded_twice_undoes_latest_first(books: dict[str, Any]) -> None:
    start = live_coding(books)
    first = run(books, {"tracking": {"region": "north"}})
    second = run(books, {"tracking": {"region": "south"}})
    with org_context(books["org"]):
        with pytest.raises(RecodeUndoRefused) as caught:
            undo(first, books["adviser"])
        assert caught.value.code == "ledger.recode.undo_later_batch"
        assert caught.value.params and caught.value.params["batch"] == str(second.public_id)
        undo(second, books["adviser"])
        middle = live_coding(books)
        assert all(dict(row[6])["tracking"] == str({"region": "north"}) for row in middle)
        undo(first, books["adviser"])
    assert live_coding(books) == start


def test_undo_refused_when_a_period_is_locked_lists_which(books: dict[str, Any]) -> None:
    done = run(books, {"tracking": {"region": "north"}})
    start = live_coding(books)
    with org_context(books["org"]):
        LockDate(
            organisation=books["org"],
            module="gl",
            level="everyone",
            date=dt.date(2026, 2, 28),
            reason="Q1 closed",
        ).save()
        blocked = undo_blockers(done, books["adviser"])
        assert sorted((b["date"], b["code"]) for b in blocked) == [
            ("2026-01-10", "locked"),
            ("2026-02-15", "locked"),
        ]
        with pytest.raises(RecodeUndoRefused) as caught:
            undo(done, books["adviser"])
    assert caught.value.code == "ledger.recode.undo_refused"
    assert len(caught.value.blocked) == 2
    assert live_coding(books) == start  # nothing undone
    with org_context(books["org"]):
        done.refresh_from_db()
        assert done.status == RecodeStatus.COMPLETED


def test_undo_refused_when_a_repost_was_reversed_since(books: dict[str, Any]) -> None:
    from numo9.ledger.services import reverse

    done = run(books, {"tracking": {"region": "north"}})
    with org_context(books["org"]):
        repost = done.lines.order_by("pk").first().repost_entry
        reverse(JournalEntry.objects.get(pk=repost.pk), user=books["adviser"])
        blocked = undo_blockers(done, books["adviser"])
        assert [b["code"] for b in blocked] == ["reversed"]
        with pytest.raises(RecodeUndoRefused):
            undo(done, books["adviser"])

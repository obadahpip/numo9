"""C-07-T06 — optimistic re-validation at execute: a line changed after the preview is reported
as a conflict and not recoded; the other chosen lines are."""

from __future__ import annotations

from typing import Any

import pytest

from numo9.ledger.models import JournalEntry, JournalStatus, RecodeLineChange, RecodeStatus
from numo9.ledger.recode_execute import create_batch, execute
from numo9.ledger.recode_preview import fingerprint, preview
from numo9.ledger.services import reverse
from numo9.tenancy.context import org_context
from tests.recode_helpers import recode_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return recode_books()


def pid(books: dict[str, Any], key: str) -> str:
    return str(books[key].public_id)


def expense(books: dict[str, Any]) -> dict[str, Any]:
    return {"conditions": [{"field": "account", "op": "is", "value": pid(books, "expense")}]}


def previewed(books: dict[str, Any], changes: dict[str, Any]) -> list[dict[str, Any]]:
    """The preview's lines as the UI sends them back: entry, line and fingerprint."""
    with org_context(books["org"]):
        rows = [r.as_dict() for r in preview(books["org"], expense(books), changes).lines]
    return [
        {"entry": r["entry"], "line_no": r["line_no"], "fingerprint": r["fingerprint"]}
        for r in rows
    ]


def test_preview_lines_carry_a_fingerprint(books: dict[str, Any]) -> None:
    rows = previewed(books, {"account": pid(books, "expense2")})
    assert len(rows) == 2 and all(len(r["fingerprint"]) == 64 for r in rows)
    assert rows[0]["fingerprint"] != rows[1]["fingerprint"]
    with org_context(books["org"]):
        line = books["entries"][1].lines.get(line_no=1)
        assert fingerprint(line) == rows[0]["fingerprint"]
        line.entry.status = JournalStatus.REVERSED  # any change of the entry's state shows
        assert fingerprint(line) != rows[0]["fingerprint"]


def test_line_recoded_by_someone_else_is_a_conflict(books: dict[str, Any]) -> None:
    org = books["org"]
    chosen = previewed(books, {"account": pid(books, "expense2")})
    with org_context(org):
        mine = create_batch(
            org,
            expense(books),
            {"account": pid(books, "expense2")},
            books["owner"],
            selection=chosen,
        )
        # meanwhile the adviser recodes entry 2's line to a tracking option and runs it
        theirs = create_batch(
            org,
            expense(books),
            {"tracking": {"region": "north"}},
            books["adviser"],
            selection=[chosen[0]],
        )
        execute(theirs, books["adviser"])
        done = execute(mine, books["owner"])
    assert done.status == RecodeStatus.COMPLETED and done.line_count == 1
    assert [(p["entry"], p["lines"], p["code"]) for p in done.problems] == [
        (chosen[0]["entry"], [1], "ledger.recode.conflict")
    ]
    with org_context(org):
        recoded = RecodeLineChange.objects.get(batch=done)
        assert recoded.entry_id == books["entries"][3].pk
        # the conflicting line kept the other person's coding
        repost = RecodeLineChange.objects.get(batch=theirs).repost_entry
        assert repost.status == JournalStatus.POSTED
        assert repost.lines.get(line_no=1).account_id == books["expense"].pk


def test_line_reversed_after_preview_is_a_conflict(books: dict[str, Any]) -> None:
    org = books["org"]
    chosen = previewed(books, {"account": pid(books, "expense2")})
    with org_context(org):
        batch = create_batch(
            org,
            expense(books),
            {"account": pid(books, "expense2")},
            books["owner"],
            selection=chosen,
        )
        reverse(books["entries"][3], user=books["adviser"])
        done = execute(batch, books["owner"])
    assert done.line_count == 1
    assert [p["entry"] for p in done.problems] == [chosen[1]["entry"]]


def test_fingerprint_mismatch_at_the_lock_is_a_conflict(books: dict[str, Any]) -> None:
    """The line is still found, but not as the preview showed it (a stale fingerprint)."""
    org = books["org"]
    chosen = previewed(books, {"account": pid(books, "expense2")})
    chosen[1]["fingerprint"] = "0" * 64
    with org_context(org):
        batch = create_batch(
            org,
            expense(books),
            {"account": pid(books, "expense2")},
            books["owner"],
            selection=chosen,
        )
        done = execute(batch, books["owner"])
        assert JournalEntry.objects.get(pk=books["entries"][3].pk).status == JournalStatus.POSTED
    assert done.line_count == 1
    assert [(p["entry"], p["code"]) for p in done.problems] == [
        (chosen[1]["entry"], "ledger.recode.conflict")
    ]


def test_without_fingerprints_nothing_is_compared(books: dict[str, Any]) -> None:
    org = books["org"]
    chosen = [
        {k: v for k, v in r.items() if k != "fingerprint"}
        for r in previewed(books, {"account": pid(books, "expense2")})
    ]
    with org_context(org):
        batch = create_batch(
            org,
            expense(books),
            {"account": pid(books, "expense2")},
            books["owner"],
            selection=chosen,
        )
        done = execute(batch, books["owner"])
    assert done.line_count == 2 and done.problems == []

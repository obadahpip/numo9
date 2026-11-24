"""K-01-T09 — cell notes: a note on a row × column survives the report running again (new
postings, another run) and lands on the same row; a row with no activity in the run keeps its
note under "unplaced"; editing replaces, an empty text removes; layout notes are apart from the
report's own.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.ledger.services import post_journal
from numo9.reports.engine import ReportError, registry
from numo9.reports.layouts import save_draft
from numo9.reports.notes import annotate, notes_for, set_note
from numo9.tenancy.context import org_context
from tests.journal_helpers import pay
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db
JUNE = {"date_from": "2026-06-01", "date_to": "2026-06-30"}


@pytest.fixture
def books() -> dict[str, Any]:
    return report_books()


def run(books: dict[str, Any], params: dict[str, str] = JUNE) -> dict[str, Any]:
    result = registry.get("account_activity").run(books["org"], params).as_dict()
    return annotate(result, notes_for(books["org"], "account_activity"))


def test_note_survives_a_rerun(books: dict[str, Any]) -> None:
    org = books["org"]
    set_note(org, "account-activity", "account:5400", "debit", "Includes June and July rent")
    first = run(books)
    rent = next(r for r in first["rows"] if r["key"] == "account:5400")
    assert rent["notes"] == {"debit": "Includes June and July rent"}
    with org_context(org):
        post_journal(
            pay(books["rent"], books["chequing"], "300.00", dt.date(2026, 6, 29)), user=None
        )
    again = run(books)
    rent = next(r for r in again["rows"] if r["key"] == "account:5400")
    assert rent["values"][0] == "2700.00" and rent["notes"] == {
        "debit": "Includes June and July rent"
    }
    may = run(books, {"date_from": "2026-05-01", "date_to": "2026-05-31"})  # no rent in May
    assert may["unplaced_notes"] == [
        {"row": "account:5400", "column": "debit", "text": "Includes June and July rent"}
    ]


def test_edit_remove_and_layout_notes(books: dict[str, Any]) -> None:
    org = books["org"]
    set_note(org, "account_activity", "account:6100", "", "Paper and toner")
    set_note(org, "account_activity", "account:6100", "", "Paper, toner and pens")
    assert notes_for(org, "account_activity") == {("account:6100", ""): "Paper, toner and pens"}
    layout = save_draft(org, "account_activity", "Board", params=JUNE, config={})
    set_note(org, "account_activity", "account:6100", "", "Board wording", layout=layout)
    assert notes_for(org, "account_activity", layout) == {("account:6100", ""): "Board wording"}
    assert notes_for(org, "account_activity") == {("account:6100", ""): "Paper, toner and pens"}
    set_note(org, "account_activity", "account:6100", "", "  ")
    assert notes_for(org, "account_activity") == {}
    with pytest.raises(ReportError):
        set_note(org, "account_activity", "", "debit", "x")

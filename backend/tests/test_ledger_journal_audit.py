"""C-03-T15 — audit hooks: journal type change, adviser override, automatic reversal posted.

Acceptance: the audit viewer (``GET audit/events``) shows each event with its label and diff —
"Journal type changed" (General → Adjusting) on a draft, "Posted below zero by an adviser, with a
reason" with the reason and the shortfall, "Reversed automatically on its reversal date" with
Posted → Reversed and the reversal's number.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from freezegun import freeze_time
from rest_framework.test import APIClient

from numo9.ledger.reversals import post_due_reversals
from numo9.ledger.services import post_journal, save_draft
from numo9.ledger.validation import JournalSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, pay, people

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")


def events(org: Organisation, user: Any, action: str) -> list[dict[str, Any]]:
    client = APIClient()
    client.force_authenticate(user)
    response = client.get(
        f"/api/v1/o/{org.public_id}/audit/events",
        {"action": action, "from": "2026-01-01", "to": "2026-12-31"},
    )
    assert response.status_code == 200, response.json()
    rows: list[dict[str, Any]] = response.json()["results"]
    return rows


def change(row: dict[str, Any], field: str) -> tuple[Any, Any]:
    found = next(c for c in row["changes"] if c["field"] == field)
    return found["old"], found["new"]


@freeze_time("2026-06-20 15:00:00")
def test_type_change_override_and_auto_reversal_in_the_viewer(org: Organisation) -> None:
    who = people(org)
    with org_context(org):
        accounts = chart(org)
        spec = pay(accounts["office"], accounts["petty"], "417.22")
        draft = save_draft(spec, user=who["owner"])
        save_draft(
            JournalSpec(date=spec.date, lines=spec.lines, journal_type="adjusting"),
            entry=draft,
            user=who["owner"],
        )
        post_journal(
            spec, user=who["adviser"], override_reason="Float topped up by the owner today."
        )
        accrual = post_journal(
            pay(
                accounts["rent"],
                accounts["ar"],
                "1130.00",
                date=dt.date(2026, 6, 30),
                auto_reverse_on=dt.date(2026, 7, 1),
            ),
            user=who["owner"],
        )
    (typed,) = events(org, who["owner"], "ledger.journalentry.type_changed")
    assert typed["action_label"] == "Journal type changed"
    assert typed["record"]["id"] == str(draft.public_id)
    assert change(typed, "journal_type") == ("general", "adjusting")

    (override,) = events(org, who["owner"], "ledger.journalentry.override")
    assert override["action_label"] == "Posted below zero by an adviser, with a reason"
    assert override["meta"]["reason"] == "Float topped up by the owner today."
    assert override["meta"]["shortfalls"] == ["Petty Cash would be −417.22 on 15 Jun 2026"]

    with freeze_time("2026-07-01 12:00:00"):
        assert post_due_reversals() == 1
        (auto,) = events(org, who["owner"], "ledger.journalentry.auto_reversed")
    assert auto["action_label"] == "Reversed automatically on its reversal date"
    assert auto["record"]["id"] == str(accrual.public_id)
    assert change(auto, "status") == ("posted", "reversed")
    assert auto["meta"]["reversed_by"]

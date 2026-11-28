"""F-07-T04 — reason capture: ``override_reason`` and ``override_by`` on the journal (the C-03
``JournalOverride`` kept with the entry), required to post past a WARN.

Acceptance: posting without a reason past a WARN → 422 (``ledger.journal.override_reason_required``
with the shortfalls) — for spend money, transfers and journals; with a reason the transaction
posts and the journal carries ``override_reason`` / ``override_by`` (shown on the transaction and
the transfer as ``override``); a BLOCK stays 409 whatever the reason; a reason under 10
characters is not a reason.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.ledger.models import Account, JournalEntry
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db
REASON = "Overdraft cleared by Friday's deposit."


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(org, "ON")
    who = people(org)
    owner = Client()
    owner.force_login(who["owner"])
    base = f"/api/v1/o/{org.public_id}/"

    def post(path: str, body: dict[str, Any]) -> Any:
        return owner.post(base + path, body, content_type="application/json")

    banks = {
        name: post("bank-accounts", {"type": kind, "display_name": label}).json()["id"]
        for name, kind, label in [
            ("chequing", "chequing", "TD Chequing"),
            ("petty", "cash", "Petty Cash"),
        ]
    }
    with org_context(org):
        office = Account.objects.filter(subtype="operating_expense").order_by("code").first()
    assert office is not None
    return {"org": org, "post": post, "banks": banks, "office": str(office.public_id), **who}


def _spend(books: dict[str, Any], bank: str, **extra: Any) -> Any:
    return books["post"](
        "bank-transactions",
        {
            "kind": "spend",
            "bank_account": books["banks"][bank],
            "date": "2026-06-15",
            "tax_mode": "no_tax",
            "lines": [{"account": books["office"], "amount": "120.00"}],
            **extra,
        },
    )


def test_spend_past_a_warn_needs_a_reason(books: dict[str, Any]) -> None:
    for reason in ({}, {"override_reason": "short"}):
        asked = _spend(books, "chequing", **reason)
        assert asked.status_code == 422
        body = asked.json()
        assert body["code"] == "ledger.journal.override_reason_required"
        assert body["shortfalls"][0]["message"] == "TD Chequing would be −120.00 on 15 Jun 2026"
        assert body["shortfalls"][0]["action"] == "warn"
    posted = _spend(books, "chequing", override_reason=REASON)
    assert posted.status_code == 201, posted.json()
    assert posted.json()["override"] == {"reason": REASON, "by": "Dana Lee"}
    with org_context(books["org"]):
        entry = JournalEntry.objects.get(public_id=posted.json()["journal"]["id"])
        assert (entry.override_reason, entry.override_by) == (REASON, books["owner"])


def test_block_stays_409_whatever_the_reason(books: dict[str, Any]) -> None:
    blocked = _spend(books, "petty", override_reason=REASON)
    assert (blocked.status_code, blocked.json()["code"]) == (409, "ledger.journal.negative_cash")
    assert blocked.json()["shortfalls"][0]["action"] == "block"


def test_transfer_and_journal_past_a_warn(books: dict[str, Any]) -> None:
    transfer = {
        "from_account": books["banks"]["chequing"],
        "to_account": books["banks"]["petty"],
        "date": "2026-06-03",
        "amount": "200.00",
    }
    assert books["post"]("bank-transfers", transfer).status_code == 422
    made = books["post"]("bank-transfers", {**transfer, "override_reason": REASON})
    assert made.status_code == 201
    assert made.json()["override"]["reason"] == REASON
    with org_context(books["org"]):
        chequing = Account.objects.get(bank_account__public_id=books["banks"]["chequing"])
    journal = {
        "date": "2026-06-15",
        "lines": [
            {"account": books["office"], "debit": "10.00"},
            {"account": str(chequing.public_id), "credit": "10.00"},
        ],
    }
    assert books["post"]("journals", journal).status_code == 422
    assert books["post"]("journals", {**journal, "override_reason": REASON}).status_code == 201


def test_no_override_when_nothing_went_negative(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        sales = Account.objects.filter(subtype="revenue").order_by("code").first()
    assert sales is not None
    received = books["post"](
        "bank-transactions",
        {
            "kind": "receive",
            "bank_account": books["banks"]["chequing"],
            "date": "2026-06-01",
            "tax_mode": "no_tax",
            "lines": [{"account": str(sales.public_id), "amount": "500.00"}],
        },
    )
    assert received.status_code == 201 and received.json()["override"] is None
    with org_context(books["org"]):
        entry = JournalEntry.objects.get(public_id=received.json()["journal"]["id"])
        assert (entry.override_reason, entry.override_by) == ("", None)

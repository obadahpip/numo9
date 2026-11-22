"""C-04-T03 — posting gate: a manual journal at or above the threshold posts only once approved.

Acceptance: a direct post of an above-threshold journal → 409 "Approval required" (service and
API), nothing written; below the threshold, or with no threshold, it posts; a draft over the
threshold can't be posted directly but posts through approval; module postings (type bank,
sales…) and reversals are never gated.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.approvals import ApprovalRequired, approve, submit_for_approval
from numo9.ledger.models import JournalEntry, JournalType
from numo9.ledger.services import post_entry, post_journal, reverse, save_draft
from numo9.ledger.validation import JournalSpec
from numo9.orgsettings.service import get_settings
from numo9.rbac.models import ApprovalLimit
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    author = User.objects.create_user("author@refined.ca", name="Ava Author")
    approver = User.objects.create_user("boss@refined.ca", name="Bo Boss")
    for user, role in ((author, "admin"), (approver, "owner")):
        OrganisationMember.objects.create(organisation=org, user=user, role=role)
    with org_context(org):
        accounts = chart(org)
        post_journal(pay(accounts["chequing"], accounts["sales"], "50000.00"), user=None)
        settings = get_settings(org)
        settings.journal_approval_threshold = Decimal("1000.00")
        settings.save()
        ApprovalLimit.objects.create(user=approver, doc_type="journal", max_amount=Decimal("9999"))
    return {"org": org, "author": author, "approver": approver, **accounts}


def test_direct_post_over_threshold_refused(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        before = JournalEntry.objects.count()
        with pytest.raises(ApprovalRequired) as caught:
            post_journal(pay(books["rent"], books["chequing"], "1000.00"), user=books["author"])
        assert caught.value.code == "ledger.journal.approval_required"
        assert caught.value.status_code == 409
        assert "1,000.00" in caught.value.messages[0]
        assert JournalEntry.objects.count() == before
        small = post_journal(pay(books["rent"], books["chequing"], "999.99"), user=books["author"])
        assert small.status == "posted"


def test_draft_over_threshold_posts_only_through_approval(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        draft = save_draft(pay(books["rent"], books["chequing"], "2500.00"), user=books["author"])
        with pytest.raises(ApprovalRequired):
            post_entry(draft, user=books["author"])
    waiting = submit_for_approval(draft, books["author"])
    with org_context(books["org"]), pytest.raises(ApprovalRequired):
        post_entry(waiting, user=books["author"])  # submitted but not approved
    posted = approve(waiting, books["approver"])
    assert posted.status == "posted"


def test_module_postings_and_reversals_not_gated(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        bank = post_journal(
            JournalSpec(
                date=dt.date(2026, 6, 15),
                lines=pay(books["rent"], books["chequing"], "4000.00").lines,
                type=JournalType.BANK,
            ),
            user=None,
        )
        assert bank.status == "posted"
        assert reverse(bank, user=None).status == "posted"


def test_no_threshold_no_gate(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        settings = get_settings(books["org"])
        settings.journal_approval_threshold = None
        settings.save()
        assert post_journal(pay(books["rent"], books["chequing"], "9000.00"), user=None).number


def test_api_answers_409(books: dict[str, Any]) -> None:
    client = Client()
    client.force_login(books["author"])
    response = client.post(
        f"/api/v1/o/{books['org'].public_id}/journals",
        {
            "date": "2026-06-15",
            "lines": [
                {"account": str(books["rent"].public_id), "debit": "1500.00"},
                {"account": str(books["chequing"].public_id), "credit": "1500.00"},
            ],
        },
        content_type="application/json",
    )
    assert response.status_code == 409
    assert response.json()["code"] == "ledger.journal.approval_required"
    assert response.json()["detail"].startswith("Approval required")

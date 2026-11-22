"""C-04-T02 — journal approval service: submit, approve (posts), reject, withdraw.

Acceptance: self-approval raises (the author, and the person who submitted); a limit of 5,000.00
cannot approve 5,000.01 (403 approval.limit_exceeded naming others) but approves 5,000.00; approval
posts the journal as the approver and records the round; reject needs a reason and returns the
journal to draft; the author withdraws; actions on a journal not awaiting approval are refused.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.ledger.approvals import (
    ApprovalRefused,
    approve,
    journal_total,
    reject,
    submit_for_approval,
    withdraw,
)
from numo9.ledger.models import JournalApproval
from numo9.ledger.services import post_journal, save_draft
from numo9.rbac.approvals import ApprovalLimitExceeded
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
        post_journal(pay(accounts["chequing"], accounts["sales"], "100000.00"), user=None)
        for user, amount in ((approver, "5000.00"), (author, "100000.00")):
            ApprovalLimit.objects.create(user=user, doc_type="journal", max_amount=Decimal(amount))
    return {"org": org, "author": author, "approver": approver, **accounts}


def _draft(b: dict[str, Any], amount: str) -> Any:
    with org_context(b["org"]):
        return save_draft(pay(b["rent"], b["chequing"], amount), user=b["author"])


def test_self_approval_raises(books: dict[str, Any]) -> None:
    entry = submit_for_approval(_draft(books, "100.00"), books["author"])
    with pytest.raises(ApprovalRefused) as caught:
        approve(entry, books["author"])  # wrote it (and has a large limit)
    assert caught.value.code == "ledger.journal.self_approval"
    with pytest.raises(ApprovalRefused):
        reject(entry, books["author"], "not mine to reject")


def test_limit_5000_cannot_approve_5000_01(books: dict[str, Any]) -> None:
    over = submit_for_approval(_draft(books, "5000.01"), books["author"])
    with pytest.raises(ApprovalLimitExceeded) as caught:
        approve(over, books["approver"])
    assert caught.value.limit == Decimal("5000.00")
    assert (caught.value.extra or {})["amount"] == "5000.01"
    with org_context(books["org"]):
        over.refresh_from_db()
        assert over.status == "awaiting_approval"
    exact = submit_for_approval(_draft(books, "5000.00"), books["author"])
    posted = approve(exact, books["approver"])
    assert (posted.status, posted.posted_by_id) == ("posted", books["approver"].pk)
    with org_context(books["org"]):
        round_ = JournalApproval.objects.get(entry=exact)
    assert (round_.decision, round_.decided_by_id, round_.limit, round_.total) == (
        "approved",
        books["approver"].pk,
        Decimal("5000.00"),
        Decimal("5000.00"),
    )
    assert round_.submitted_by_id == books["author"].pk


def test_reject_needs_a_reason_and_returns_to_draft(books: dict[str, Any]) -> None:
    entry = submit_for_approval(_draft(books, "250.00"), books["author"])
    with pytest.raises(ApprovalRefused) as caught:
        reject(entry, books["approver"], " no ")
    assert caught.value.code == "ledger.journal.reject_reason_required"
    back = reject(entry, books["approver"], "Wrong account: use 6100")
    assert back.status == "draft"
    with org_context(books["org"]):
        round_ = JournalApproval.objects.get(entry=entry)
    assert (round_.decision, round_.reason) == ("rejected", "Wrong account: use 6100")
    again = submit_for_approval(back, books["author"])  # a new round
    with org_context(books["org"]):
        assert JournalApproval.objects.filter(entry=again).count() == 2
    with pytest.raises(ApprovalRefused) as not_awaiting:
        approve(_draft(books, "1.00"), books["approver"])
    assert not_awaiting.value.code == "ledger.journal.not_awaiting"


def test_withdraw_by_the_author(books: dict[str, Any]) -> None:
    entry = submit_for_approval(_draft(books, "80.00"), books["author"])
    assert withdraw(entry, books["author"]).status == "draft"
    with org_context(books["org"]):
        assert JournalApproval.objects.get(entry=entry).decision == "withdrawn"


def test_total_is_the_larger_book(books: dict[str, Any]) -> None:
    entry = _draft(books, "123.45")
    assert journal_total(entry) == Decimal("123.45")

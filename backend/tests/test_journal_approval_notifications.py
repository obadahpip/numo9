"""C-04-T13 — journal approval notifications: submit → the approvers; approve / reject → the
author; delivered once (on commit); a rolled-back action sends nothing.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from numo9.accounts.models import User
from numo9.ledger.approvals import approve, reject, submit_for_approval
from numo9.ledger.services import post_journal, save_draft
from numo9.notifications.models import Notification
from numo9.notifications.texts import render
from numo9.rbac.models import ApprovalLimit
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    people = {}
    for key, role, _limit in (
        ("author", "admin", "100000"),
        ("boss", "owner", "5000"),
        ("junior", "admin", "100"),
    ):
        user = User.objects.create_user(f"{key}@refined.ca", name=key.title())
        OrganisationMember.objects.create(organisation=org, user=user, role=role)
        people[key] = user
    with org_context(org):
        accounts = chart(org)
        post_journal(pay(accounts["chequing"], accounts["sales"], "50000.00"), user=None)
        for key, _role, limit in (
            ("author", "", "100000"),
            ("boss", "", "5000"),
            ("junior", "", "100"),
        ):
            ApprovalLimit.objects.create(
                user=people[key], doc_type="journal", max_amount=Decimal(limit)
            )
    return {"org": org, **people, **accounts}


def _inbox(b: dict[str, Any], key: str) -> list[tuple[str, str]]:
    """(title key, rendered title) of each notification the person got."""
    with org_context(b["org"]):
        rows = Notification.objects.filter(recipient=b[key]).order_by("pk")
        return [(n.title_key, render(n.title_key, n.body_params)[0]) for n in rows]


def test_submit_notifies_approvers_once_then_author_hears_decision(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        draft = save_draft(pay(books["rent"], books["chequing"], "1200.00"), user=books["author"])
    waiting = submit_for_approval(draft, books["author"])
    boss = _inbox(books, "boss")
    assert len(boss) == 1 and boss[0][0] == "notifications.ledger.submitted"
    assert "waiting for your approval" in boss[0][1]
    assert _inbox(books, "junior") == []  # limit 100 can't approve 1,200.00
    assert _inbox(books, "author") == []  # never the author
    approve(waiting, books["boss"])
    author = _inbox(books, "author")
    assert [k for k, _t in author] == ["notifications.ledger.approved"]
    assert len(_inbox(books, "boss")) == 1  # once


def test_reject_notifies_the_author_with_the_reason(books: dict[str, Any]) -> None:
    with org_context(books["org"]):
        draft = save_draft(pay(books["rent"], books["chequing"], "300.00"), user=books["author"])
    waiting = submit_for_approval(draft, books["author"])
    reject(waiting, books["boss"], "Attach the lease, please")
    with org_context(books["org"]):
        note = Notification.objects.get(
            recipient=books["author"], title_key="notifications.ledger.rejected"
        )
    title, body = render(note.title_key, note.body_params)
    assert "sent back" in title and "Attach the lease, please" in body

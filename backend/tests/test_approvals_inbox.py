"""C-04-T08 — approvals inbox ``GET /api/v1/o/<org>/approvals``: journals awaiting approval
(bills, POs and claims register later through ``ApprovableRegistry``).

Acceptance: the inbox lists only what the person may approve, plus what they submitted (flagged
"self", never approvable); an item above their limit says so with the limit; the counts match the
items; a person without the approve permission sees only their own; another organisation's items
never show.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.approvals import submit_for_approval
from numo9.ledger.services import post_journal, save_draft
from numo9.orgsettings.service import get_settings
from numo9.rbac.inbox import approvables
from numo9.rbac.models import ApprovalLimit
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db


def member(org: Organisation, email: str, role: str) -> User:
    user = User.objects.create_user(email, name=email.split("@")[0].title())
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    people = {
        "ava": member(org, "ava@refined.ca", "admin"),
        "bo": member(org, "bo@refined.ca", "owner"),
        "sal": member(org, "sal@refined.ca", "sales"),
    }
    with org_context(org):
        accounts = chart(org)
        post_journal(pay(accounts["chequing"], accounts["sales"], "90000.00"), user=None)
        settings = get_settings(org)
        settings.journal_approval_threshold = Decimal("100.00")
        settings.save()
        ApprovalLimit.objects.create(
            user=people["bo"], doc_type="journal", max_amount=Decimal("5000")
        )
        waiting = []
        for amount, narration in (("2400.00", "Kingsway lease"), ("7500.00", "Equipment")):
            entry = save_draft(
                pay(accounts["rent"], accounts["chequing"], amount, narration=narration),
                user=people["ava"],
            )
            waiting.append(submit_for_approval(entry, people["ava"]))
    return {"org": org, "waiting": waiting, **people}


def inbox(books: dict[str, Any], user: User, **query: str) -> dict[str, Any]:
    client = Client()
    client.force_login(user)
    response = client.get(f"/api/v1/o/{books['org'].public_id}/approvals", query)
    assert response.status_code == 200, response.json()
    body: dict[str, Any] = response.json()
    return body


def test_journals_are_registered() -> None:
    journal = approvables.get("journal")
    assert journal is not None and journal.permission == "accounting.journals.approve"


def test_the_approver_sees_what_they_may_approve_with_the_limit(books: dict[str, Any]) -> None:
    body = inbox(books, books["bo"])
    rows = {r["title"]: r for r in body["results"]}
    assert set(rows) == {"Kingsway lease", "Equipment"}
    assert rows["Kingsway lease"]["can_approve"] is True
    assert rows["Kingsway lease"]["limit"] == "5000.00"
    assert (rows["Equipment"]["can_approve"], rows["Equipment"]["blocked"]) == (False, "limit")
    assert rows["Kingsway lease"]["submitted_by"]["name"] == "Ava"
    assert body["counts"] == {"total": 2, "can_approve": 1}
    (kind,) = body["kinds"]
    assert (kind["kind"], kind["count"], kind["can_approve"]) == ("journal", 2, 1)
    assert inbox(books, books["bo"], kind="bill")["results"] == []


def test_the_author_sees_their_items_flagged_self(books: dict[str, Any]) -> None:
    body = inbox(books, books["ava"])
    assert {r["blocked"] for r in body["results"]} == {"self"}
    assert body["counts"] == {"total": 2, "can_approve": 0}


def test_without_the_permission_only_their_own(books: dict[str, Any]) -> None:
    assert inbox(books, books["sal"])["results"] == []


def test_other_organisations_never_show(books: dict[str, Any]) -> None:
    other = Organisation.objects.create(name="Other Co.")
    boss = member(other, "boss@other.ca", "owner")
    assert inbox({"org": other}, boss)["counts"] == {"total": 0, "can_approve": 0}

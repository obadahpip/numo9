"""C-04-T14 — journals in the global search: narration indexed, approval state shown; quick-create
N J opens a new journal.

Acceptance: searching "Ontario Corporation" returns the journal (Phase 1 fixtures); a journal
waiting for approval is found by its narration and says "Awaiting approval"; once approved and
posted the result shows its number and no state.
"""

from __future__ import annotations

from decimal import Decimal
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.approvals import approve, submit_for_approval
from numo9.ledger.phase1_fixtures import ORG_NAME
from numo9.ledger.services import post_journal, save_draft
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.rbac.models import ApprovalLimit
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db


def _search(org: Organisation, user: User, q: str) -> list[dict[str, Any]]:
    client = Client()
    client.force_login(user)
    body = client.get(f"/api/v1/o/{org.public_id}/search", {"q": q}).json()
    return [r for r in body["records"] if r["type"] == "ledger.journalentry"]


def test_searching_ontario_corporation_returns_the_journal() -> None:
    call_command("load_phase1_fixtures", stdout=StringIO())
    (org,) = Organisation.objects.filter(name=ORG_NAME)
    owner = User.objects.create_user("search-owner@refined.ca", name="Owner")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    found = _search(org, owner, "Ontario Corporation")
    assert found and "Ontario Corporation" in found[0]["subtitle"]


def test_waiting_journal_found_by_narration_with_its_state() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    author = User.objects.create_user("author@refined.ca", name="Ava")
    boss = User.objects.create_user("boss@refined.ca", name="Bo")
    for user, role in ((author, "admin"), (boss, "owner")):
        OrganisationMember.objects.create(organisation=org, user=user, role=role)
    with org_context(org):
        accounts = chart(org)
        post_journal(pay(accounts["chequing"], accounts["sales"], "9000.00"), user=None)
        ApprovalLimit.objects.create(user=boss, doc_type="journal", max_amount=Decimal("9999"))
        draft = save_draft(
            JournalSpec(
                date=pay(accounts["rent"], accounts["chequing"], "1").date,
                narration="Kingsway warehouse lease",
                lines=(
                    LineSpec(accounts["rent"], debit=Decimal("2400.00")),
                    LineSpec(accounts["chequing"], credit=Decimal("2400.00")),
                ),
            ),
            user=author,
        )
    waiting = submit_for_approval(draft, author)
    (hit,) = _search(org, boss, "Kingsway warehouse")
    assert hit["subtitle"] == "Awaiting approval — Kingsway warehouse lease"
    posted = approve(waiting, boss)
    (hit,) = _search(org, boss, "Kingsway warehouse")
    assert hit["subtitle"] == "Kingsway warehouse lease" and hit["title"].endswith(
        str(posted.number)
    )

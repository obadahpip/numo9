"""C-04-T15 — the approval matrix and the recurrence replay.

**Matrix** — every organisation role × amount (under, at and over a 5,000.00 limit) × creator
(the approver wrote it or not), through the API: the outcome is exactly one of approved and
posted (200), ``ledger.journal.self_approval`` (409), ``approval.limit_exceeded`` (403) or no
permission (403) — never a self-approval, never above the limit, whatever the role.

**Replay** — a year of hourly ticks with "restarts" (each day's tick run twice, days out of
order) gives the same journals as one catch-up run: one per occurrence, dated on the schedule.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.approvals import submit_for_approval
from numo9.ledger.models import JournalEntry, RecurringJournalTemplate
from numo9.ledger.recurring import SOURCE_TYPE, generate_due, occurrences
from numo9.ledger.services import post_journal, save_draft
from numo9.orgsettings.service import get_settings
from numo9.rbac.models import ApprovalLimit, Role
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db
LIMIT = Decimal("5000.00")
AMOUNTS = ("4999.99", "5000.00", "5000.01")


def approve_permitted(role: str) -> bool:
    found = Role.objects.get(is_system=True, scope="organisation", key=role)
    return found.grants.filter(permission="accounting.journals.approve").exists()


@pytest.mark.parametrize("role", [r.value for r in OrganisationRole])
@pytest.mark.parametrize("amount", AMOUNTS)
@pytest.mark.parametrize("own", [False, True])
def test_matrix(role: str, amount: str, own: bool) -> None:
    org = Organisation.objects.create(name="Matrix Inc.")
    author = User.objects.create_user("author@matrix.ca", name="Author")
    OrganisationMember.objects.create(organisation=org, user=author, role="owner")
    approver = User.objects.create_user("approver@matrix.ca", name="Approver")
    OrganisationMember.objects.create(organisation=org, user=approver, role=role)
    with org_context(org):
        accounts = chart(org)
        post_journal(pay(accounts["chequing"], accounts["sales"], "90000.00"), user=None)
        settings = get_settings(org)
        settings.journal_approval_threshold = Decimal("100.00")
        settings.save()
        ApprovalLimit.objects.create(user=approver, doc_type="journal", max_amount=LIMIT)
        writer = approver if own else author
        entry = submit_for_approval(
            save_draft(pay(accounts["rent"], accounts["chequing"], amount), user=writer), writer
        )
    client = Client()
    client.force_login(approver)
    answer = client.post(f"/api/v1/o/{org.public_id}/journals/{entry.public_id}/approve")
    body: dict[str, Any] = answer.json()

    expected: tuple[int, str | None]
    if not approve_permitted(role):
        expected = (403, None)
    elif own:
        expected = (409, "ledger.journal.self_approval")
    elif Decimal(amount) > LIMIT:
        expected = (403, "approval.limit_exceeded")
    else:
        expected = (200, None)
    assert answer.status_code == expected[0], body
    if expected[1]:
        assert body["code"] == expected[1]
    with org_context(org):
        entry.refresh_from_db()
        assert entry.status == ("posted" if expected[0] == 200 else "awaiting_approval")
        if entry.status == "posted":
            assert entry.posted_by_id == approver.pk and entry.created_by_id != approver.pk


def test_replay_matches_one_catch_up_run() -> None:
    def template(org: Organisation) -> RecurringJournalTemplate:
        with org_context(org):
            accounts = chart(org)
            item = RecurringJournalTemplate(
                organisation=org,
                name="Rent",
                rrule="FREQ=MONTHLY",
                start_date=dt.date(2026, 1, 31),
                end_date=dt.date(2026, 12, 31),
                mode="post",
                lines=[
                    {"account": str(accounts["rent"].public_id), "debit": "100.00"},
                    {"account": str(accounts["ar"].public_id), "credit": "100.00"},
                ],
            )
            item.full_clean()
            item.save()
            return item

    def dates(org: Organisation) -> list[dt.date]:
        with org_context(org):
            return list(
                JournalEntry.objects.filter(source_type=SOURCE_TYPE)
                .order_by("date")
                .values_list("date", flat=True)
            )

    once, ticks = (Organisation.objects.create(name=n) for n in ("Once Ltd.", "Ticks Ltd."))
    template(once)
    template(ticks)
    generate_due(once, dt.date(2026, 12, 31))

    day = dt.date(2026, 1, 1)
    while day <= dt.date(2026, 12, 31):
        generate_due(ticks, day)
        generate_due(ticks, day)  # the worker restarts: the same tick again
        if day.day == 15:
            generate_due(ticks, day - dt.timedelta(days=20))  # a late, out-of-order tick
        day += dt.timedelta(days=1)

    expected = occurrences("FREQ=MONTHLY", dt.date(2026, 1, 31), dt.date(2026, 12, 31))
    assert len(expected) == 12
    assert dates(once) == expected
    assert dates(ticks) == expected

"""C-04-T07 — journal workflow API: submit / approve / reject / withdraw and recurring CRUD +
preview. Self-approval is refused by the API (not only the screen); an approver above their
limit gets 403 with who may approve; ``accounting.journals.approve`` is declared and needed;
recurring templates are validated, versioned on edit, paused and resumed; the preview is the
generator's dates; the tenant sweep covers the new endpoints.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client
from freezegun import freeze_time

from numo9.accounts.models import User
from numo9.ledger.models import JournalEntry, RecurringJournalTemplate
from numo9.ledger.recurring import occurrences
from numo9.ledger.services import post_journal, save_draft
from numo9.orgsettings.service import get_settings
from numo9.rbac.catalogue import catalogue
from numo9.rbac.models import ApprovalLimit
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")
    people = {}
    for email, role in (("ava@refined.ca", "admin"), ("bo@refined.ca", "owner")):
        user = User.objects.create_user(email, name=email.split("@")[0].title())
        OrganisationMember.objects.create(organisation=org, user=user, role=role)
        people[email.split("@")[0]] = user
    with org_context(org):
        accounts = chart(org)
        post_journal(pay(accounts["chequing"], accounts["sales"], "50000.00"), user=None)
        settings = get_settings(org)
        settings.journal_approval_threshold = Decimal("1000.00")
        settings.save()
        ApprovalLimit.objects.create(
            user=people["bo"], doc_type="journal", max_amount=Decimal("5000.00")
        )
    return {"org": org, **people, **accounts}


def client(user: User) -> Client:
    c = Client()
    c.force_login(user)
    return c


def url(books: dict[str, Any], suffix: str) -> str:
    return f"/api/v1/o/{books['org'].public_id}/journals/{suffix}"


def draft(books: dict[str, Any], amount: str) -> JournalEntry:
    with org_context(books["org"]):
        return save_draft(pay(books["rent"], books["chequing"], amount), user=books["ava"])


def test_permission_is_declared() -> None:
    assert catalogue.get("accounting.journals.approve").module == "accounting"


def test_submit_approve_and_self_approval_refused(books: dict[str, Any]) -> None:
    entry = draft(books, "2400.00")
    ava, bo = client(books["ava"]), client(books["bo"])
    submitted = ava.post(url(books, f"{entry.public_id}/submit"))
    assert submitted.status_code == 200, submitted.json()
    assert submitted.json()["status"] == "awaiting_approval"
    # The author can't approve — whatever the screen shows, the API refuses.
    own = ava.post(url(books, f"{entry.public_id}/approve"))
    assert own.status_code == 409, own.json()
    assert own.json()["code"] == "ledger.journal.self_approval"
    approved = bo.post(url(books, f"{entry.public_id}/approve"))
    assert approved.status_code == 200, approved.json()
    assert approved.json()["status"] == "posted"


def test_limit_exceeded_is_403_with_the_approvers(books: dict[str, Any]) -> None:
    entry = draft(books, "5000.01")
    client(books["ava"]).post(url(books, f"{entry.public_id}/submit"))
    refused = client(books["bo"]).post(url(books, f"{entry.public_id}/approve"))
    assert refused.status_code == 403, refused.json()
    body = refused.json()
    assert body["code"] == "approval.limit_exceeded" and body["limit"] == "5000.00"


def test_reject_needs_a_reason_and_withdraw(books: dict[str, Any]) -> None:
    entry = draft(books, "2400.00")
    ava, bo = client(books["ava"]), client(books["bo"])
    ava.post(url(books, f"{entry.public_id}/submit"))
    short = bo.post(url(books, f"{entry.public_id}/reject"), {"reason": "no"})
    assert (
        short.status_code == 409 and short.json()["code"] == "ledger.journal.reject_reason_required"
    )
    back = bo.post(
        url(books, f"{entry.public_id}/reject"),
        {"reason": "Wrong account: use 5410"},
        content_type="application/json",
    )
    assert back.status_code == 200 and back.json()["status"] == "draft"
    ava.post(url(books, f"{entry.public_id}/submit"))
    withdrawn = ava.post(url(books, f"{entry.public_id}/withdraw"))
    assert withdrawn.status_code == 200 and withdrawn.json()["status"] == "draft"
    missing = bo.post(url(books, "00000000-0000-4000-8000-000000000000/approve"))
    assert missing.status_code == 404


def recurring_body(books: dict[str, Any], **over: Any) -> dict[str, Any]:
    body = {
        "name": "Warehouse rent",
        "narration": "Kingsway warehouse rent",
        "lines": [
            {"account": str(books["rent"].public_id), "debit": "800.00"},
            {"account": str(books["ar"].public_id), "credit": "800.00"},
        ],
        "rrule": "FREQ=MONTHLY",
        "start_date": "2026-01-31",
        "mode": "post",
    }
    body.update(over)
    return body


@freeze_time("2026-06-15 15:00:00")
def test_recurring_crud_preview_pause_resume(books: dict[str, Any]) -> None:
    ava = client(books["ava"])
    made = ava.post(url(books, "recurring"), recurring_body(books), content_type="application/json")
    assert made.status_code == 201, made.json()
    item = made.json()
    # A start in the past: the first run is the first occurrence from today, no back-posting.
    assert (item["next_run"], item["version"], item["paused"]) == ("2026-06-30", 1, False)

    preview = ava.get(url(books, f"recurring/{item['id']}/preview"), {"count": 6}).json()
    expected = occurrences(
        "FREQ=MONTHLY", dt.date(2026, 1, 31), after=dt.date(2026, 6, 29), limit=6
    )
    assert preview["dates"] == [d.isoformat() for d in expected]
    assert preview["dates"][:3] == ["2026-06-30", "2026-07-31", "2026-08-31"]
    unsaved = ava.post(
        url(books, "recurring/preview"),
        {"rrule": "FREQ=MONTHLY", "start_date": "2026-01-31", "count": 6},
        content_type="application/json",
    ).json()
    assert unsaved["dates"] == preview["dates"]  # the editor's preview = the template's

    paused = ava.patch(
        url(books, f"recurring/{item['id']}"), {"paused": True}, content_type="application/json"
    ).json()
    assert paused["paused"] is True and paused["version"] == 1  # pausing isn't an edit
    edited = ava.patch(
        url(books, f"recurring/{item['id']}"),
        {"paused": False, "rrule": "FREQ=MONTHLY;INTERVAL=3"},
        content_type="application/json",
    ).json()
    assert (edited["paused"], edited["version"], edited["next_run"]) == (False, 2, "2026-07-31")

    listed = ava.get(url(books, "recurring"), {"status": "active"}).json()["results"]
    assert [r["id"] for r in listed] == [item["id"]]
    assert ava.delete(url(books, f"recurring/{item['id']}")).status_code == 204
    assert ava.get(url(books, f"recurring/{item['id']}")).status_code == 404


def test_recurring_validation_errors(books: dict[str, Any]) -> None:
    ava = client(books["ava"])
    for over, code in (
        ({"rrule": "FREQ=HOURLY"}, "ledger.recurring.rrule_invalid"),
        (
            {
                "lines": [
                    {"account": str(books["rent"].public_id), "debit": "10.00"},
                    {"account": str(books["ar"].public_id), "credit": "9.00"},
                ]
            },
            "ledger.recurring.unbalanced",
        ),
        ({"end_date": "2025-01-01"}, "ledger.recurring.end_before_start"),
    ):
        refused = ava.post(
            url(books, "recurring"), recurring_body(books, **over), content_type="application/json"
        )
        assert refused.status_code == 400, refused.json()
        assert refused.json()["code"] == code
    system = ava.post(
        url(books, "recurring"),
        recurring_body(books, journal_type="payroll"),
        content_type="application/json",
    )
    assert system.status_code == 400
    with org_context(books["org"]):
        assert not RecurringJournalTemplate.objects.exists()


def test_tenant_isolation(books: dict[str, Any]) -> None:
    other = Organisation.objects.create(name="Other Co.")
    stranger = User.objects.create_user("x@other.ca", name="X")
    OrganisationMember.objects.create(organisation=other, user=stranger, role="owner")
    made = (
        client(books["ava"])
        .post(url(books, "recurring"), recurring_body(books), content_type="application/json")
        .json()
    )
    peek = client(stranger).get(f"/api/v1/o/{other.public_id}/journals/recurring/{made['id']}")
    assert peek.status_code == 404

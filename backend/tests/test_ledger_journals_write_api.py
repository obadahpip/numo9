"""C-03-T10 — journals write API: ``POST journals`` (post, or keep a draft), ``POST
journals/check`` (what the screen shows as you type) and ``POST journals/<id>/post``.

Acceptance: OpenAPI shows the new fields (journal type, line contact, auto-reverse date, override
reason); a journal posts with its type, line contact and attachments; system types are refused;
rule problems come back as 400 with every problem; the cash guard is 409 with the shortfalls —
blocked for the owner, posted with a reason by an adviser; ``check`` writes nothing and lists the
problems, the shortfalls and what is still needed; a draft is posted later; permission
``accounting.journals.post`` (403), feature ``accounting.journals.write`` (402); sweep passes.
"""

from __future__ import annotations

import datetime as dt
from io import StringIO
from typing import Any

import pytest
import yaml
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.catalogue import drf as catalogue_drf
from numo9.ledger.models import JournalEntry, JournalOverride
from numo9.orgsettings.service import get_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.contact_helpers import contact
from tests.journal_helpers import chart, document, people

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def books(org: Organisation) -> dict[str, Any]:
    with org_context(org):
        found: dict[str, Any] = dict(chart(org))
        found["staples"] = contact(org, "Staples")
        found["receipt"] = document(org)
    found.update(people(org))
    return found


def browser(user: User) -> Client:
    client = Client()
    client.force_login(user)
    return client


def url(org: Organisation, suffix: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/journals{suffix}"


def body(books: dict[str, Any], amount: str = "417.22", **extra: Any) -> dict[str, Any]:
    return {
        "date": "2026-06-15",
        "narration": "Office supplies from petty cash",
        "lines": [
            {
                "account": str(books["office"].public_id),
                "debit": amount,
                "contact": str(books["staples"].public_id),
                "description": "Paper and toner",
            },
            {"account": str(books["petty"].public_id), "credit": amount},
        ],
        **extra,
    }


def send(client: Client, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, payload, content_type="application/json")


def fund(org: Organisation, books: dict[str, Any], amount: str = "1000.00") -> None:
    payload = {
        "date": "2026-06-01",
        "lines": [
            {"account": str(books["petty"].public_id), "debit": amount},
            {"account": str(books["sales"].public_id), "credit": amount},
        ],
    }
    assert send(browser(books["owner"]), url(org), payload).status_code == 201


def test_documented(org: Organisation, books: dict[str, Any]) -> None:
    schema = yaml.safe_load(browser(books["owner"]).get("/api/schema/").content)
    paths = schema["paths"]
    assert paths["/api/v1/o/{org}/journals"]["post"]["operationId"] == "journals_create"
    assert paths["/api/v1/o/{org}/journals/check"]["post"]["operationId"] == "journals_check"
    assert "/api/v1/o/{org}/journals/{public_id}/post" in paths
    fields = schema["components"]["schemas"]["JournalInputRequest"]["properties"]
    assert {"journal_type", "auto_reverse_on", "override_reason", "attachments"} <= set(fields)
    ref = fields["journal_type"]["allOf"][0]["$ref"]
    enum = schema["components"]["schemas"][ref.split("/")[-1]]
    assert set(enum["enum"]) == {"general", "adjusting", "reclass", "tax_adjustment"}
    assert "contact" in schema["components"]["schemas"]["LineInputRequest"]["properties"]


def test_posts_with_type_contact_and_attachment(org: Organisation, books: dict[str, Any]) -> None:
    fund(org, books)
    payload = body(
        books,
        journal_type="adjusting",
        attachments=[str(books["receipt"].public_id)],
        auto_reverse_on="2026-07-01",
    )
    created = send(browser(books["owner"]), url(org), payload)
    assert created.status_code == 201, created.json()
    journal = created.json()
    assert (journal["status"], journal["journal_type"], journal["journal_type_label"]) == (
        "posted",
        "adjusting",
        "Adjusting",
    )
    assert journal["auto_reverse_on"] == "2026-07-01"
    assert journal["lines"][0]["contact"]["name"] == "Staples"
    listed = browser(books["owner"]).get(url(org), {"journal_type": "adjusting"}).json()
    assert [j["id"] for j in listed["results"]] == [journal["id"]]


def test_system_type_is_refused(org: Organisation, books: dict[str, Any]) -> None:
    refused = send(browser(books["owner"]), url(org), body(books, journal_type="closing"))
    assert refused.status_code == 400
    assert "journal_type" in refused.json()


def test_rule_problems_are_400_with_every_problem(org: Organisation, books: dict[str, Any]) -> None:
    fund(org, books)
    with org_context(org):
        row = get_settings(org)
        row.journal_expense_requires_attachment = True
        row.save()
    refused = send(browser(books["owner"]), url(org), body(books))
    assert refused.status_code == 400
    assert refused.json()["code"] == "ledger.journal.invalid"
    assert [e["code"] for e in refused.json()["errors"]] == [
        "ledger.journal.expense_attachment_required"
    ]


def test_cash_guard_blocks_the_owner_and_lets_an_adviser_post_with_a_reason(
    org: Organisation, books: dict[str, Any]
) -> None:
    blocked = send(browser(books["owner"]), url(org), body(books))
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "ledger.journal.negative_cash"
    assert blocked.json()["adviser"] is False
    assert blocked.json()["shortfalls"][0]["message"] == (
        "Petty Cash would be −417.22 on 15 Jun 2026"
    )
    adviser = browser(books["adviser"])
    asked = send(adviser, url(org), body(books))
    assert (asked.status_code, asked.json()["code"]) == (
        409,
        "ledger.journal.override_reason_required",
    )
    posted = send(
        adviser, url(org), body(books, override_reason="Owner reimbursed the float on Monday.")
    )
    assert posted.status_code == 201
    assert posted.json()["overrides"][0]["reason"].startswith("Owner reimbursed")
    with org_context(org):
        assert JournalOverride.objects.count() == 1


def test_check_writes_nothing_and_says_what_is_needed(
    org: Organisation, books: dict[str, Any]
) -> None:
    with org_context(org):
        books["office"].require_contact = True
        books["office"].save()
        row = get_settings(org)
        row.journal_expense_requires_attachment = True
        row.save()
    payload = body(books, amount="994.17")
    payload["lines"][0]["contact"] = None
    checked = send(browser(books["owner"]), url(org, "/check"), payload)
    assert checked.status_code == 200
    answer = checked.json()
    assert answer["ok"] is False and answer["adviser"] is False
    assert {e["code"] for e in answer["errors"]} == {
        "ledger.journal.contact_required",
        "ledger.journal.expense_attachment_required",
    }
    assert answer["shortfalls"][0]["message"] == "Petty Cash would be −994.17 on 15 Jun 2026"
    assert answer["needs"] == {"attachment": True, "contact_lines": [1]}
    with org_context(org):
        assert not JournalEntry.objects.exists()


def test_draft_then_post(org: Organisation, books: dict[str, Any]) -> None:
    fund(org, books)
    owner = browser(books["owner"])
    draft = send(owner, url(org), body(books, post=False))
    assert (draft.status_code, draft.json()["status"]) == (201, "draft")
    posted = send(owner, url(org, f"/{draft.json()['id']}/post"), {})
    assert (posted.status_code, posted.json()["status"]) == (200, "posted")
    again = send(owner, url(org, f"/{draft.json()['id']}/post"), {})
    assert again.status_code == 409


def test_permission_feature_and_sweep(
    org: Organisation, books: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=org, user=employee, role="employee")
    assert send(browser(employee), url(org), body(books)).status_code == 403
    call_command("tenant_sweep", stdout=StringIO())

    class NoPackage:
        def allows(self, organisation: Organisation | None, key: str) -> bool:
            return key != "accounting.journals.write"

    monkeypatch.setattr(catalogue_drf, "get_resolver", lambda: NoPackage())
    refused = send(browser(books["owner"]), url(org), body(books))
    assert (refused.status_code, refused.json()["feature"]) == (402, "accounting.journals.write")


def test_unknown_account_or_contact_is_a_field_error(
    org: Organisation, books: dict[str, Any]
) -> None:
    payload = body(books)
    payload["lines"][1]["account"] = "6ca1b880-64f7-4053-80e3-0c3618895553"
    refused = send(browser(books["owner"]), url(org), payload)
    assert refused.status_code == 400
    assert "account" in refused.json()["lines"]["1"]
    assert dt.date(2026, 6, 15)

"""A-09-T05 — search API with permission / entitlement filtering, amount and number parsing, and
ranking (exact code > prefix > full text > trigram).

Acceptance: results filtered by role (a journal for the owner, not for sales; nothing for an
employee); a product outside the package is shown locked with the reason; "54" finds account
5400 first; "1,130" finds the 1,130.00 journal; "lock date" finds the settings page; a typo still
finds the contact; another organisation's address answers 404.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.search.api import parse_amount
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.contact_helpers import contact
from tests.entitlement_helpers import package, subscribe
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        bank = account(organisation, "1000", "Chequing", subtype="bank")
        rent = account(organisation, "5400", "Rent")
        account(organisation, "5410", "Rent — storage")
        contact(organisation, "Cedar Roofing Co.")
        post_journal(
            JournalSpec(
                date=dt.date(2026, 11, 2),
                narration="November rent",
                lines=(
                    LineSpec(rent, debit=Decimal("1130.00")),
                    LineSpec(bank, credit=Decimal("1130.00")),
                ),
            ),
            organisation=organisation,
            user=None,
        )
    return organisation


def as_role(org: Organisation, role: str) -> Client:
    person = User.objects.create_user(f"{role}@maple.ca", name=role)
    OrganisationMember.objects.create(organisation=org, user=person, role=role)
    client = Client()
    client.force_login(person)
    return client


def search(client: Client, org: Organisation, q: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/o/{org.public_id}/search", {"q": q})
    assert response.status_code == 200, response.content
    body: dict[str, Any] = response.json()
    return body


def types(body: dict[str, Any]) -> list[str]:
    return [r["type"] for r in body["records"]]


def test_results_are_filtered_by_role(org: Organisation) -> None:
    owner, sales, employee = (as_role(org, r) for r in ("owner", "sales", "employee"))
    assert "ledger.journalentry" in types(search(owner, org, "november"))
    assert "ledger.journalentry" not in types(search(sales, org, "november"))
    assert types(search(sales, org, "cedar")) == ["contacts.contact"]
    assert types(search(employee, org, "cedar")) == []


def test_code_prefix_ranks_first_and_exact_code_first(org: Organisation) -> None:
    owner = as_role(org, "owner")
    records = search(owner, org, "54")["records"]
    assert [r["code"] for r in records[:2]] == ["5400", "5410"]
    assert records[0]["match"] == "code_prefix"
    exact = search(owner, org, "5410")["records"][0]
    assert (exact["code"], exact["match"]) == ("5410", "code")


def test_amounts_and_typos(org: Organisation) -> None:
    owner = as_role(org, "owner")
    assert parse_amount("1,130") == Decimal("1130.00")
    assert parse_amount("$1 130.00") == Decimal("1130.00")
    assert parse_amount("cedar") is None
    found = search(owner, org, "1,130")["records"]
    assert found[0]["type"] == "ledger.journalentry" and found[0]["match"] == "amount"
    typo = search(owner, org, "Cedr Roofing")["records"]
    assert typo and typo[0]["title"] == "Cedar Roofing Co."


def test_settings_reports_navigation_groups(org: Organisation) -> None:
    body = search(as_role(org, "owner"), org, "lock date")
    assert body["settings"][0]["key"] == "settings.lock_dates"
    assert body["settings"][0]["url"] == f"/o/{org.public_id}/settings/lock-dates"
    assert (
        search(as_role(org, "admin"), org, "chart")["navigation"][0]["key"]
        == "nav.chart_of_accounts"
    )


def test_gated_product_results_are_locked_with_a_reason(org: Organisation) -> None:
    subscribe(org, package("payroll_only", ["payroll"]))
    body = search(as_role(org, "owner"), org, "cedar")
    (record,) = body["records"]
    assert record["locked"] is True and "package" in record["reason"]


def test_another_organisation_is_404(org: Organisation) -> None:
    other = Organisation.objects.create(name="Birch Ltd.")
    stranger = as_role(other, "owner")
    response = stranger.get(f"/api/v1/o/{org.public_id}/search", {"q": "cedar"})
    assert response.status_code == 404
    assert search(stranger, other, "cedar")["records"] == []

"""S-06-T09 — the perf-only posting endpoint behind the k6 "post journal" baseline.

Off by default (403); on, it posts a balanced two-line journal through ``post_journal`` (numbers
1, 2, …); it needs the accounts-manage permission; it is not in the public API schema.
"""

from __future__ import annotations

import pytest
import yaml
from django.test import Client, override_settings

from numo9.accounts.models import User
from numo9.ledger.models import JournalEntry, JournalLine
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


def _client(org: Organisation, role: str) -> Client:
    user = User.objects.create_user(f"{role}@maple.ca", password="x" * 12, name=role.title())
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        account(organisation, "1200", "Receivables", subtype="current_asset")
        account(organisation, "4000", "Sales", subtype="revenue")
    return organisation


def url(org: Organisation) -> str:
    return f"/api/v1/o/{org.public_id}/perf/journal"


def test_off_by_default(org: Organisation) -> None:
    response = _client(org, "owner").post(url(org), {}, content_type="application/json")
    assert response.status_code == 403


@override_settings(NUMO9_PERF_ENDPOINTS=True)
def test_posts_a_balanced_journal_through_the_service(org: Organisation) -> None:
    browser = _client(org, "owner")
    first = browser.post(url(org), {"amount": "12.50"}, content_type="application/json")
    second = browser.post(url(org), {}, content_type="application/json")
    assert (first.status_code, second.status_code) == (201, 201)
    assert [first.json()["number"], second.json()["number"]] == [1, 2]
    with org_context(org):
        assert JournalEntry.objects.filter(status="posted").count() == 2
        lines = JournalLine.objects.filter(entry__number=1)
        assert sorted((str(line.debit), str(line.credit)) for line in lines) == [
            ("0.00", "12.50"),
            ("12.50", "0.00"),
        ]
    bad = browser.post(url(org), {"amount": "-1"}, content_type="application/json")
    assert bad.status_code == 400


@override_settings(NUMO9_PERF_ENDPOINTS=True)
def test_needs_the_manage_permission(org: Organisation) -> None:
    response = _client(org, "employee").post(url(org), {}, content_type="application/json")
    assert response.status_code == 403


def test_not_in_the_schema(org: Organisation) -> None:
    schema = yaml.safe_load(_client(org, "owner").get("/api/schema/").content)
    assert not [path for path in schema["paths"] if "/perf/" in path]

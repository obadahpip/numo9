"""F-02-T13 (API side) — ``GET bank-accounts/<id>/statement-lines`` for the account page.

Acceptance (with the Playwright test of the page): the "Uncoded" badge equals the count of
UNCODED lines — ``counts.uncoded`` counts exactly the account's uncoded lines, whatever the
status filter; the status, import, date and text filters narrow the list; another account's or
organisation's lines never show.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.banking.models import BankAccount, StatementLine, StatementLineStatus
from numo9.banking.services import create_bank_account
from numo9.banking.statements.mappings import builtin, ensure_builtin_mappings
from numo9.banking.statements.service import commit_import
from numo9.banking.statements.source import FileStatementSource
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.statement_helpers import batch, fixture

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def owner(org: Organisation) -> Client:
    user = User.objects.create_user("dana@refined.ca", name="Dana Lee")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    client = Client()
    client.force_login(user)
    return client


def imported(org: Organisation, name: str = "Chequing") -> tuple[BankAccount, Any]:
    with org_context(org):
        bank = create_bank_account(org, type="chequing", display_name=name)
        rbc = builtin(ensure_builtin_mappings(org), "rbc")
        assert rbc is not None
        source = FileStatementSource(fixture("rbc_chequing.csv"), "rbc.csv", rbc.layout())
        return bank, commit_import(batch(bank, "rbc.csv"), source)


def lines(client: Client, org: Organisation, bank: BankAccount, query: str = "") -> Any:
    response = client.get(
        f"/api/v1/o/{org.public_id}/bank-accounts/{bank.public_id}/statement-lines{query}"
    )
    assert response.status_code == 200, response.content
    return response.json()


def test_uncoded_count_and_filters(owner: Client, org: Organisation) -> None:
    bank, done = imported(org)
    imported(org, "Other account")  # its lines never show here
    with org_context(org):
        first, second = StatementLine.objects.filter(bank_account=bank).order_by("date", "pk")[:2]
        StatementLine.objects.filter(pk=first.pk).update(status=StatementLineStatus.CODED)
        StatementLine.objects.filter(pk=second.pk).update(status=StatementLineStatus.IGNORED)
    body = lines(owner, org, bank)
    assert body["counts"] == {"all": 5, "uncoded": 3, "coded": 1, "matched": 0, "ignored": 1}
    assert body["count"] == 5 and body["results"][0]["date"] == "2026-06-15"  # newest first
    assert body["results"][0]["import"] == {"id": str(done.public_id), "file_name": "rbc.csv"}
    uncoded = lines(owner, org, bank, "?status=uncoded")
    assert uncoded["count"] == uncoded["counts"]["uncoded"] == 3
    assert {r["status"] for r in uncoded["results"]} == {"uncoded"}
    assert lines(owner, org, bank, "?q=hydro")["count"] == 1
    assert lines(owner, org, bank, "?from=2026-06-05&to=2026-06-10")["count"] == 2
    assert lines(owner, org, bank, f"?import={done.public_id}")["count"] == 5
    assert lines(owner, org, bank, "?limit=2")["results"].__len__() == 2
    bad = owner.get(
        f"/api/v1/o/{org.public_id}/bank-accounts/{bank.public_id}/statement-lines?from=June"
    )
    assert bad.status_code == 400


def test_another_organisation_gets_404(owner: Client, org: Organisation) -> None:
    bank, _done = imported(org)
    other = Organisation.objects.create(name="Other Ltd.")
    user = User.objects.create_user("lee@other.ca", name="Lee")
    OrganisationMember.objects.create(organisation=other, user=user, role="owner")
    stranger = Client()
    stranger.force_login(user)
    url = f"/api/v1/o/{other.public_id}/bank-accounts/{bank.public_id}/statement-lines"
    assert stranger.get(url).status_code == 404

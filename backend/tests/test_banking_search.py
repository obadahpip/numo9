"""F-01-T13 — banking in the global search: "petty" finds the Petty Cash bank account (it opens
the account's page); a spend is found by its reference and contact; results follow the banking
permission; renaming or archiving the account updates its result.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.banking.lifecycle import archive_bank_account
from numo9.banking.models import BankTransactionKind
from numo9.banking.services import create_bank_account
from numo9.banking.transactions import MoneyLine, MoneySpec, record_bank_transaction
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.search.reindex import drift
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.contact_helpers import contact

pytestmark = pytest.mark.django_db
BANKING = "banking.bankaccount"


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


def member(org: Organisation, email: str, role: str) -> User:
    user = User.objects.create_user(email, name=email.split("@")[0])
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    return user


def search(org: Organisation, user: User, q: str, kind: str) -> list[dict[str, Any]]:
    client = Client()
    client.force_login(user)
    body = client.get(f"/api/v1/o/{org.public_id}/search", {"q": q}).json()
    return [r for r in body["records"] if r["type"] == kind]


def test_petty_finds_the_petty_cash_account(org: Organisation) -> None:
    owner = member(org, "owner@refined.ca", "owner")
    with org_context(org):
        petty = create_bank_account(org, type="cash", display_name="Petty Cash")
    (hit,) = search(org, owner, "petty", BANKING)
    assert hit["title"] == "Petty Cash"
    assert hit["url"] == f"/o/{org.public_id}/banking/{petty.public_id}"
    assert hit["code"] == petty.gl_account.code
    # Renamed: found by its new name (its type "Cash / petty cash" still matches "petty");
    # archived: still found, and says so.
    with org_context(org):
        petty.display_name = "Office float"
        petty.save()
    (hit,) = search(org, owner, "float", BANKING)
    assert hit["title"] == "Office float"
    with org_context(org):
        archive_bank_account(petty)
    (hit,) = search(org, owner, "float", BANKING)
    assert "Archived" in hit["subtitle"]
    with org_context(org):
        assert drift(org).consistent


def test_spend_found_by_reference_and_contact(org: Organisation) -> None:
    owner = member(org, "owner@refined.ca", "owner")
    with org_context(org):
        bank = create_bank_account(org, type="chequing", display_name="TD Chequing")
        office = Account.objects.filter(type="expense").order_by("code").first()
        assert office is not None
        staples = contact(org, "Staples Canada", roles=["supplier"])
        record_bank_transaction(
            MoneySpec(
                BankTransactionKind.SPEND,
                bank,
                dt.date(2026, 6, 15),
                [MoneyLine(office, Decimal("45.20"), description="Toner cartridges")],
                contact=staples,
                reference="RCPT-8812",
            ),
            user=None,
        )
    (hit,) = search(org, owner, "RCPT-8812", "banking.banktransaction")
    assert hit["title"] == "Spend money — Staples Canada"
    assert "TD Chequing" in hit["subtitle"]
    assert hit["url"] == f"/o/{org.public_id}/banking/{bank.public_id}"
    assert search(org, owner, "toner", "banking.banktransaction")
    assert search(org, owner, "staples", "banking.banktransaction")
    with org_context(org):
        assert drift(org).consistent


def test_results_need_the_banking_permission(org: Organisation) -> None:
    owner = member(org, "owner@refined.ca", "owner")
    with org_context(org):
        create_bank_account(org, type="cash", display_name="Petty Cash")
    assert search(org, owner, "petty", BANKING)
    nobody = member(org, "employee@refined.ca", "employee")
    assert search(org, nobody, "petty", BANKING) == []

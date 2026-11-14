"""C-01-T10 (server side) — account picker contexts; gap-07 groundwork.

The design-system picker (``packages/ui/src/pickers/account-contexts.json``) and the server rules
(``numo9.ledger.contexts``) must be the same, so a document line can never be saved with an
account its picker would not offer. On the template chart: the sales context hides every expense
account, purchase hides revenue, bank offers bank accounts only, no context offers the
engine-only accounts (except journals), archived accounts are never allowed.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from numo9.ledger.contexts import CONTEXTS, ENGINE_ROLES, allowed_in_context
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

UI_CONTEXTS = (
    Path(__file__).resolve().parents[2]
    / "packages"
    / "ui"
    / "src"
    / "pickers"
    / "account-contexts.json"
)


def test_frontend_and_backend_rules_are_the_same() -> None:
    ui = json.loads(UI_CONTEXTS.read_text(encoding="utf-8"))
    assert ui["engineRoles"] == list(ENGINE_ROLES)
    assert set(ui["contexts"]) == set(CONTEXTS)
    for name, rules in CONTEXTS.items():
        mirror = ui["contexts"][name]
        assert mirror["subtypes"] == list(rules.subtypes), name
        assert mirror["excludeEngineRoles"] == rules.exclude_engine_roles, name
        assert mirror["bank"] == rules.bank, name


@pytest.fixture
def accounts() -> Iterator[dict[str, Account]]:
    org = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(org):
        load_template(org, "ON")
        yield {a.code: a for a in Account.objects.all()}


def allowed(accounts: dict[str, Account], context: str) -> set[str]:
    return {code for code, a in accounts.items() if allowed_in_context(a, context)}


@pytest.mark.django_db
@pytest.mark.gap("gap-07")
def test_sales_context_hides_expense_accounts(accounts: dict[str, Account]) -> None:
    sales = allowed(accounts, "sales")
    assert {"4000", "4010", "4530", "2300", "2310"} <= sales
    assert not any(accounts[code].type == "expense" for code in sales)
    assert not sales & {"1100", "2100", "1010", "2400"}  # AR, GST/HST, bank, credit card


@pytest.mark.django_db
def test_purchase_bank_and_journal_contexts(accounts: dict[str, Account]) -> None:
    purchase = allowed(accounts, "purchase")
    assert {"6080", "5000", "1200", "1630", "1300"} <= purchase
    assert not any(accounts[code].type == "revenue" for code in purchase)
    assert not purchase & {"1400", "1010", "2000"}  # ITC, bank, AP: engine or payment
    assert allowed(accounts, "bank") == {"1000", "1010", "1020", "2400", "2450"}
    journal = allowed(accounts, "journal")
    assert "3210" not in journal  # current year earnings: computed, never posted
    assert {"1100", "2100", "3200", "1010"} <= journal


@pytest.mark.django_db
def test_archived_never_allowed(accounts: dict[str, Account]) -> None:
    office = accounts["6080"]
    office.status = "archived"
    office.save()
    assert not any(allowed_in_context(office, context) for context in CONTEXTS)

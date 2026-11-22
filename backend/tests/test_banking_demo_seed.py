"""F-01-T15 — demo seed: the demo organisation has Chequing, Visa and Petty Cash with sample
spend / receive money and the expected balances; the trial balance stays zero; a demo reset brings
back the three accounts with the same balances.
"""

from __future__ import annotations

import pytest

from numo9.banking.balances import ledger_balance
from numo9.banking.models import BankAccount, BankTransaction
from numo9.demo.cloning import create_demo
from numo9.demo.reset import reset_demo
from numo9.demo.seeders import load_seed, order, run_seed
from numo9.ledger.models import Book
from numo9.ledger.trial_balance import trial_balance
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = [pytest.mark.django_db, pytest.mark.data_validation]


def _balances(org: Organisation) -> dict[str, str]:
    with org_context(org):
        accounts = list(BankAccount.objects.select_related("gl_account").order_by("display_name"))
    return {bank.display_name: f"{ledger_balance(bank):.2f}" for bank in accounts}


EXPECTED = {
    "Petty Cash": "254.80",
    "RBC Business Chequing": "48515.00",
    "RBC Visa Business": "-169.50",
}


def test_seed_order_and_expected_balances_in_the_document() -> None:
    keys = [s.key for s in order()]
    assert keys.index("opening_balances") < keys.index("banking")
    expected = load_seed()["banking"]["expected_balances"]
    assert expected == {"chequing": "48515.00", "petty": "254.80", "visa": "-169.50"}


def test_seeded_org_has_three_accounts_with_balances() -> None:
    org = Organisation.objects.create(name="Demo")
    run_seed(org)
    assert _balances(org) == EXPECTED
    with org_context(org):
        assert BankTransaction.objects.count() == 6
        chequing = BankAccount.objects.get(display_name="RBC Business Chequing")
        visa = BankAccount.objects.get(display_name="RBC Visa Business")
        assert (chequing.gl_account.code, chequing.masked_number) == ("1010", "•••• 4821")
        assert (visa.type, visa.gl_account.type) == ("credit_card", "liability")
        for book in (Book.ACCOUNTING, Book.TAX):
            assert trial_balance(book).balanced


def test_demo_reset_shows_the_three_accounts() -> None:
    demo = create_demo(name="Visitor demo")
    assert _balances(demo) == EXPECTED
    with org_context(demo):
        BankAccount.objects.get(display_name="Petty Cash").gl_account  # noqa: B018 - exists
    reset_demo(demo)
    assert _balances(demo) == EXPECTED

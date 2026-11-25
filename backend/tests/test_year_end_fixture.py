"""C-06-T10 — the full-year fixture: the year-end roll is correct in both books (accounting NI
25,000.00 → retained earnings +25,000.00; tax NI 23,500.00 → +23,500.00), every revenue and
expense account is zero after the fiscal year end in each book, NI = ΔRE (data validation), and
loading twice changes nothing."""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from numo9.ledger.models import Account, JournalEntry
from numo9.ledger.period_close import close_year, net_income, pl_balances
from numo9.ledger.trial_balance import trial_balance
from numo9.ledger.year_end_fixture import EXPECTED, FISCAL_YEAR, load
from numo9.tenancy.context import org_context
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


@pytest.mark.data_validation
def test_year_end_roll_correct_on_the_fixture() -> None:
    out = StringIO()
    call_command("load_year_end_fixture", stdout=out)
    assert "accounting 25000.00, tax 23500.00" in out.getvalue()
    org = load()  # idempotent
    with org_context(org):
        count = JournalEntry.objects.count()
        for book, amount in EXPECTED.items():
            assert net_income(org, book, *FISCAL_YEAR) == amount
        retained = Account.objects.get(system_role="retained_earnings")
    owner = people(org)["owner"]
    row = close_year(org, FISCAL_YEAR[1], owner)
    with org_context(org):
        assert JournalEntry.objects.count() == count + 2
        for book, amount in EXPECTED.items():
            assert pl_balances(org, book, *FISCAL_YEAR) == {}
            balances = {r.account_id: r for r in trial_balance(book, FISCAL_YEAR[1]).rows}
            re_row = balances[retained.pk]
            assert re_row.credit - re_row.debit == amount  # NI = ΔRE
            assert all(r.type not in ("revenue", "expense") for r in balances.values())
    assert row.accounting_entry is not None and row.tax_entry is not None
    assert Decimal(0) not in EXPECTED.values()

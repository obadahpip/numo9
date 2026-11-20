"""C-03-T07 — ``CashBalanceGuard``: the projected balance of every bank/cash account a journal
takes money out of — at the journal's date and today, including the journal; later entries
(future-dated too) counted.

Acceptance: Petty Cash at 0 + a journal crediting it 417.22 → projected −417.22 detected, with
the message "Petty Cash would be −417.22 on 15 Jun 2026"; money in is never a shortfall; a
backdated journal pushing a past day negative while today's balance is positive is detected on
that day; two bank accounts, one of them going negative, only that one reported. Property: for
random sequences of journals, the projection equals the balance actually reached.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.ledger.cash_guard import balance, projections, shortfalls
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec, validate_journal
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, pay

pytestmark = pytest.mark.django_db
JUNE_15 = dt.date(2026, 6, 15)


def test_petty_cash_at_zero_goes_to_minus_417_22() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        checked = validate_journal(pay(accounts["office"], accounts["petty"], "417.22"))
        (found,) = shortfalls(checked, today=dt.date(2026, 6, 20))
    assert found.account == accounts["petty"]
    assert (found.at_date, found.at_today, found.lowest) == (Decimal("-417.22"),) * 3
    assert found.message() == "Petty Cash would be −417.22 on 15 Jun 2026"


def test_money_in_and_enough_cash_are_not_shortfalls() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        money_in = validate_journal(pay(accounts["petty"], accounts["sales"], "500.00"))
        assert projections(money_in) == []
        post_journal(pay(accounts["petty"], accounts["sales"], "500.00", date=dt.date(2026, 6, 1)))
        spend = validate_journal(pay(accounts["office"], accounts["petty"], "417.22"))
        (projection,) = projections(spend, today=dt.date(2026, 6, 20))
        assert projection.at_date == Decimal("82.78") and not projection.goes_negative


def test_backdated_journal_dips_a_past_day_while_today_is_positive() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        # 1 June: 100 in; 20 June: 1,000 in. A 576.95 spend dated 15 June leaves today positive.
        post_journal(pay(accounts["petty"], accounts["sales"], "100.00", date=dt.date(2026, 6, 1)))
        post_journal(
            pay(accounts["petty"], accounts["sales"], "1000.00", date=dt.date(2026, 6, 20))
        )
        checked = validate_journal(pay(accounts["office"], accounts["petty"], "576.95"))
        (found,) = shortfalls(checked, today=dt.date(2026, 6, 25))
    assert found.at_date == Decimal("-476.95")
    assert found.at_today == Decimal("523.05")
    assert (found.lowest, found.lowest_on) == (Decimal("-476.95"), JUNE_15)


def test_future_dated_spend_later_counts_against_the_journal() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        post_journal(pay(accounts["petty"], accounts["sales"], "500.00", date=dt.date(2026, 6, 1)))
        post_journal(pay(accounts["rent"], accounts["petty"], "400.00", date=dt.date(2026, 7, 1)))
        checked = validate_journal(pay(accounts["office"], accounts["petty"], "150.00"))
        (found,) = shortfalls(checked, today=dt.date(2026, 6, 20))
    assert found.at_date == Decimal("350.00")
    assert (found.lowest, found.lowest_on) == (Decimal("-50.00"), dt.date(2026, 7, 1))


def test_two_bank_accounts_only_the_negative_one_is_reported() -> None:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
        post_journal(
            pay(accounts["chequing"], accounts["sales"], "5000.00", date=dt.date(2026, 6, 1))
        )
        checked = validate_journal(
            JournalSpec(
                date=JUNE_15,
                lines=(
                    LineSpec(accounts["rent"], debit=Decimal("1500.00")),
                    LineSpec(accounts["chequing"], credit=Decimal("1000.00")),
                    LineSpec(accounts["petty"], credit=Decimal("500.00")),
                ),
            )
        )
        found = shortfalls(checked, today=JUNE_15)
    assert [(p.account.code, p.lowest) for p in found] == [("1010", Decimal("-500.00"))]


amounts = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("900.00"), places=2)


@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(st.lists(st.tuples(st.booleans(), amounts, st.integers(0, 20)), min_size=1, max_size=8))
def test_projection_equals_the_balance_reached(moves: list[tuple[bool, Decimal, int]]) -> None:
    org = Organisation.objects.create(name="Property Bakery")
    with org_context(org):
        accounts = chart(org)
        for money_in, amount, day in moves:
            date = dt.date(2026, 6, 1) + dt.timedelta(days=day)
            if money_in:
                spec = pay(accounts["petty"], accounts["sales"], str(amount), date=date)
            else:
                spec = pay(accounts["office"], accounts["petty"], str(amount), date=date)
            predicted = projections(validate_journal(spec), today=dt.date(2026, 7, 1))
            post_journal(spec)
            if predicted:
                assert predicted[0].at_date == balance(accounts["petty"], date)
                assert predicted[0].at_today == balance(accounts["petty"], dt.date(2026, 7, 1))

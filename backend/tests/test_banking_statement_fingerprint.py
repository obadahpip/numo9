"""F-02-T07 — fingerprinting and duplicate detection, with a same-day identical-line sequence
counter.

Acceptance: importing the same file twice → 0 new lines; 2 identical coffees on the same day are
both kept on the first import (unit + Hypothesis property). Also: the fingerprint ignores case,
accents and spacing of the description; FITIDs keep identical-looking lines apart; lines with
problems get no fingerprint and no sequence number; another bank account never sees the lines as
duplicates; overlapping statements (whole days) add exactly the missing lines.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.banking.models import BankAccount, StatementLine
from numo9.banking.services import create_bank_account
from numo9.banking.statements.errors import ROW_DATE_FORMAT, LineProblem
from numo9.banking.statements.fingerprint import (
    account_key,
    existing_fingerprints,
    fingerprint_lines,
    normalise_description,
)
from numo9.banking.statements.layout import RawLine
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db

D = dt.date(2026, 6, 3)
COFFEE = RawLine(row=2, date=D, amount=Decimal("-4.25"), description="TIM HORTONS #1234")
PAY = RawLine(row=4, date=dt.date(2026, 6, 5), amount=Decimal("2500.00"), description="PAYROLL")


@pytest.fixture
def org() -> Iterator[Organisation]:
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    with org_context(organisation):
        yield organisation


@pytest.fixture
def bank(org: Organisation) -> BankAccount:
    return create_bank_account(org, type="chequing", display_name="Chequing")


def store(bank: BankAccount, lines: list[RawLine]) -> int:
    """Insert the lines that are new (what the commit does, F-02-T09); returns how many."""
    prints = fingerprint_lines(account_key(bank), lines)
    existing = existing_fingerprints(bank, prints)
    new = [
        StatementLine(
            organisation_id=bank.organisation_id,
            bank_account=bank,
            date=line.date or D,
            amount=line.amount or Decimal(0),
            description=line.description,
            fingerprint=fp,
        )
        for line, fp in zip(lines, prints, strict=True)
        if fp and fp not in existing
    ]
    StatementLine.objects.bulk_create(new)
    return len(new)


def test_two_identical_coffees_are_both_kept_and_a_reimport_adds_nothing(
    bank: BankAccount,
) -> None:
    file = [COFFEE, RawLine(**{**COFFEE.__dict__, "row": 3}), PAY]
    prints = fingerprint_lines(account_key(bank), file)
    assert len(set(prints)) == 3  # the two coffees differ by their sequence number
    assert store(bank, file) == 3
    assert StatementLine.objects.filter(bank_account=bank, amount=Decimal("-4.25")).count() == 2
    assert store(bank, file) == 0  # the same file again
    assert StatementLine.objects.filter(bank_account=bank).count() == 3


def test_a_third_coffee_in_a_later_file_is_new(bank: BankAccount) -> None:
    store(bank, [COFFEE, COFFEE])
    assert store(bank, [COFFEE, COFFEE, COFFEE]) == 1


def test_description_normalisation() -> None:
    assert normalise_description("  Café  Dépôt #12 ") == "CAFE DEPOT 12"
    a = RawLine(row=1, date=D, amount=Decimal("-4.25"), description="Café Dépôt")
    b = RawLine(row=9, date=D, amount=Decimal("-4.25"), description="CAFE  DEPOT")
    assert fingerprint_lines("x", [a]) == fingerprint_lines("x", [b])


def test_fitid_keeps_lines_apart_and_rows_do_not_matter() -> None:
    a = RawLine(row=1, date=D, amount=Decimal("-4.25"), description="TIM", fitid="F1")
    b = RawLine(row=2, date=D, amount=Decimal("-4.25"), description="TIM", fitid="F2")
    first, second = fingerprint_lines("x", [a, b])
    assert first != second
    assert fingerprint_lines("x", [b]) == [second]  # FITID differs: sequence 1 for both


def test_lines_with_problems_get_no_fingerprint_and_no_sequence() -> None:
    broken = RawLine(
        row=3,
        date=None,
        amount=Decimal("-4.25"),
        description="TIM HORTONS #1234",
        problems=(LineProblem(ROW_DATE_FORMAT, {"row": 3, "value": "x", "format": "YYYY-MM-DD"}),),
    )
    with_broken = fingerprint_lines("x", [COFFEE, broken, COFFEE])
    assert with_broken[1] is None
    assert [with_broken[0], with_broken[2]] == fingerprint_lines("x", [COFFEE, COFFEE])


def test_another_account_is_not_a_duplicate(org: Organisation, bank: BankAccount) -> None:
    store(bank, [COFFEE])
    savings = create_bank_account(org, type="savings", display_name="Savings")
    assert store(savings, [COFFEE]) == 1


# ---- properties ---------------------------------------------------------------------------------

lines_strategy = st.lists(
    st.builds(
        RawLine,
        row=st.just(0),
        date=st.dates(min_value=dt.date(2026, 6, 1), max_value=dt.date(2026, 6, 6)),
        amount=st.sampled_from([Decimal("-4.25"), Decimal("-4.25"), Decimal("10.00")]),
        description=st.sampled_from(["TIM HORTONS", "tim  hortons", "PAYROLL"]),
        fitid=st.sampled_from(["", "", "F1"]),
    ),
    max_size=30,
).map(lambda lines: sorted(lines, key=lambda line: line.date or D))


@settings(max_examples=200, deadline=None)
@given(lines=lines_strategy)
def test_property_fingerprints_of_a_file_are_unique_and_stable(lines: list[RawLine]) -> None:
    prints = fingerprint_lines("acct", lines)
    assert len(set(prints)) == len(lines)  # identical lines are all kept
    assert fingerprint_lines("acct", lines) == prints
    assert set(fingerprint_lines("acct", list(reversed(lines)))) == set(prints)


@settings(max_examples=200, deadline=None)
@given(lines=lines_strategy, split=st.integers(min_value=1, max_value=6), overlap=st.integers(0, 3))
def test_property_overlapping_statements_add_exactly_the_missing_lines(
    lines: list[RawLine], split: int, overlap: int
) -> None:
    """Statement A = days ≤ split, statement B = days > split - overlap: A then B is the whole."""
    cut = dt.date(2026, 6, split)
    start_b = cut - dt.timedelta(days=overlap)
    first = [line for line in lines if line.date and line.date <= cut]
    second = [line for line in lines if line.date and line.date > start_b]
    stored = set(fingerprint_lines("acct", first))
    added = {fp for fp in fingerprint_lines("acct", second) if fp not in stored}
    assert stored | added == set(fingerprint_lines("acct", lines))


@settings(
    max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(lines=lines_strategy)
def test_property_importing_twice_adds_nothing(bank: BankAccount, lines: list[RawLine]) -> None:
    StatementLine.objects.filter(bank_account=bank).delete()
    assert store(bank, lines) == len(lines)
    assert store(bank, lines) == 0

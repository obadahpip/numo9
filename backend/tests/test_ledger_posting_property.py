"""C-02-T13 — property test: random valid journal specs → TB of both books = 0; random invalid →
rejected.

Acceptance: 10,000 examples pass (Hypothesis). Each example is either a random **valid** journal
(1–3 book groups — both / accounting / tax — each balanced, 2–8 lines, any accounts, amounts from
one cent to ten billion) or a valid journal with one random **defect** (too few lines, a cent off
in one book, a float, a third decimal, a negative amount, both sides, no side, an unknown book, an
archived, parent or foreign account).

- valid → posted (validation, then lines while draft, number, Posted — the engine's flow) and the
  trial balance of each book has equal debits and credits and sums to zero (each example in a
  savepoint rolled back afterwards, so every example costs the same);
- invalid → ``JournalInvalid`` carrying the defect's code, and nothing written (no entry, no line,
  no number taken).
"""

from __future__ import annotations

import datetime as dt
import os
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.ledger.models import (
    Account,
    AccountStatus,
    Book,
    JournalEntry,
    JournalLine,
    JournalSequence,
    JournalStatus,
)
from numo9.ledger.trial_balance import trial_balance
from numo9.ledger.validation import JournalInvalid, JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account, post_for_test

pytestmark = pytest.mark.django_db

#: 10,000 by default (the acceptance); NUMO9_PROPERTY_EXAMPLES lowers it for a quick local run.
EXAMPLES = int(os.environ.get("NUMO9_PROPERTY_EXAMPLES", "10000"))
ONE_CENT = Decimal("0.01")

DEFECTS: dict[str, str] = {
    "too_few_lines": "ledger.journal.too_few_lines",
    "cent_off": "ledger.journal.unbalanced",
    "float": "ledger.journal.amount_type",
    "third_decimal": "ledger.journal.amount_precision",
    "negative": "ledger.journal.amount_negative",
    "both_sides": "ledger.journal.line_one_side",
    "no_side": "ledger.journal.line_one_side",
    "unknown_book": "ledger.journal.book_invalid",
    "archived_account": "ledger.account.archived",
    "parent_account": "ledger.account.not_leaf",
    "foreign_account": "ledger.journal.account_missing",
}


class _Undo(Exception):
    pass


# (side, account key, amount, book)
Line = tuple[str, str, Any, str]


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def accounts(org: Organisation) -> dict[str, Account]:
    found = {
        "cash": account(org, "1000", "Chequing", subtype="bank", gifi_id="1001"),
        "ar": account(org, "1200", "Receivables", subtype="current_asset", gifi_id="1060"),
        "accum": account(
            org, "1810", "Accumulated amortization", subtype="accumulated_amortisation"
        ),
        "hst": account(org, "2200", "HST payable", subtype="sales_tax_control"),
        "equity": account(org, "3000", "Share capital", subtype="share_capital"),
        "sales": account(org, "4000", "Sales", subtype="revenue", gifi_id="8000"),
        "amort": account(org, "6400", "Amortization", subtype="amortisation", gifi_id="8670"),
        "rent": account(org, "6800", "Rent", gifi_id="8910"),
        "archived": account(org, "6900", "Old expense", status=AccountStatus.ARCHIVED),
        "parent": account(org, "7000", "Office"),
    }
    account(org, "7010", "Office supplies", parent=found["parent"])
    other = Organisation.objects.create(name="Birch Garage")
    with org_context(other):
        found["foreign"] = account(other, "1000", "Their bank", subtype="bank")
    return found


POSTABLE = ["cash", "ar", "accum", "hst", "equity", "sales", "amort", "rent"]
amounts = st.integers(min_value=1, max_value=10**12).map(lambda n: Decimal(n) / 100)


@st.composite
def valid_lines(draw: st.DrawFn) -> list[Line]:
    keys = st.sampled_from(POSTABLE)
    lines: list[Line] = []
    for book in draw(st.lists(st.sampled_from(Book.values), min_size=1, max_size=3, unique=True)):
        debits = draw(st.lists(amounts, min_size=1, max_size=3))
        total = sum(debits, Decimal("0"))
        others = draw(st.lists(amounts, max_size=2))
        rest = total - sum(others, Decimal("0"))
        credits = [*others, rest] if rest > 0 else [total]
        lines += [("debit", draw(keys), amount, book) for amount in debits]
        lines += [("credit", draw(keys), amount, book) for amount in credits]
    return draw(st.permutations(lines))


def _replace(lines: list[Line], index: int, **change: Any) -> list[Line]:
    side, key, amount, book = lines[index]
    values = {"side": side, "key": key, "amount": amount, "book": book, **change}
    lines = list(lines)
    lines[index] = (values["side"], values["key"], values["amount"], values["book"])
    return lines


@st.composite
def invalid_lines(draw: st.DrawFn) -> tuple[str, list[Line]]:
    defect = draw(st.sampled_from(sorted(DEFECTS)))
    lines = draw(valid_lines())
    index = draw(st.integers(0, len(lines) - 1))
    side, _key, amount, _book = lines[index]
    if defect == "too_few_lines":
        lines = lines[:1]
    elif defect == "cent_off":
        lines = _replace(lines, index, amount=amount + ONE_CENT)
    elif defect == "float":
        lines = _replace(lines, index, amount=float(amount))
    elif defect == "third_decimal":
        lines = _replace(lines, index, amount=amount + Decimal("0.001"))
    elif defect == "negative":
        lines = _replace(lines, index, amount=-amount)
    elif defect == "both_sides":
        lines = _replace(lines, index, side="both")
    elif defect == "no_side":
        lines = _replace(lines, index, side="none")
    elif defect == "unknown_book":
        lines = _replace(lines, index, book="management")
    else:
        lines = _replace(lines, index, key=defect.removesuffix("_account"))
    return defect, lines


def spec_of(accounts: dict[str, Account], lines: list[Line]) -> JournalSpec:
    built = []
    for side, key, amount, book in lines:
        target = accounts[key]
        if side == "debit":
            built.append(LineSpec(target, debit=amount, book=book))
        elif side == "credit":
            built.append(LineSpec(target, credit=amount, book=book))
        elif side == "both":
            built.append(LineSpec(target, debit=amount, credit=amount, book=book))
        else:
            built.append(LineSpec(target, book=book))
    return JournalSpec(date=dt.date(2026, 3, 31), lines=built)


def counts() -> tuple[int, int, int]:
    sequence = JournalSequence.objects.first()
    return (
        JournalEntry.objects.count(),
        JournalLine.objects.count(),
        sequence.next_number if sequence else 1,
    )


@settings(
    max_examples=EXAMPLES,
    deadline=None,
    database=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
        HealthCheck.data_too_large,
    ],
)
@given(case=st.one_of(valid_lines().map(lambda lines: ("", lines)), invalid_lines()))
def test_property_valid_journals_keep_both_books_at_zero_invalid_ones_are_rejected(
    accounts: dict[str, Account], case: tuple[str, list[Line]]
) -> None:
    defect, lines = case
    spec = spec_of(accounts, lines)
    if not defect:
        # Posted in a savepoint rolled back after the check: the ledger stays the fixtures', so
        # 10,000 examples cost the same each and every trial balance is this posting's alone
        # (the cumulative case is covered by tests/test_ledger_trial_balance.py).
        try:
            with transaction.atomic():
                entry = post_for_test(spec, audit=False)
                assert entry.status == JournalStatus.POSTED and entry.number is not None
                for book in (Book.ACCOUNTING, Book.TAX):
                    tb = trial_balance(book, include_zero=True)
                    assert tb.total_debit == tb.total_credit
                    assert tb.total_balance == 0
                raise _Undo
        except _Undo:
            pass
        return
    before = counts()
    with pytest.raises(JournalInvalid) as error:
        post_for_test(spec, audit=False)
    assert DEFECTS[defect] in {item.code for item in error.value.error_list}
    assert counts() == before

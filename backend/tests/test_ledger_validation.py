"""C-02-T06 — validation service: ≥ 2 lines, balance per book, leaf/active accounts, precision.

Acceptance: an unbalanced journal → a specific error naming the book, both totals and the
difference. Also: every problem reported at once with its code; floats refused (never converted),
sub-cent amounts refused, negative, too large, both sides / neither side, unknown book, foreign,
archived and parent accounts; books (both / accounting / tax) balance separately and decide the
entry's book scope; French amount format. Hypothesis: any balanced random journal passes with
equal totals per book; moving one cent anywhere makes it fail with "unbalanced".
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest
from django.utils import translation
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.ledger.models import Account, AccountStatus, Book
from numo9.ledger.validation import (
    JournalInvalid,
    JournalSpec,
    LineSpec,
    format_amount,
    to_amount,
    validate_journal,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

D = Decimal
DATE = dt.date(2026, 3, 31)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def acc(org: Organisation) -> dict[str, Account]:
    return {
        "cash": account(org, "1000", "Chequing", subtype="bank", gifi_id="1001"),
        "sales": account(org, "4000", "Sales", subtype="revenue", gifi_id="8000"),
        "amort": account(org, "6400", "Amortization", subtype="amortisation", gifi_id="8670"),
        "accum": account(
            org, "1810", "Accumulated amortization", subtype="accumulated_amortisation"
        ),
    }


def spec(*lines: LineSpec) -> JournalSpec:
    return JournalSpec(date=DATE, lines=lines)


def codes(error: pytest.ExceptionInfo[JournalInvalid]) -> list[str]:
    return [item.code or "" for item in error.value.error_list]


def messages(error: pytest.ExceptionInfo[JournalInvalid]) -> list[str]:
    return error.value.messages


# ---- balanced journals pass ----------------------------------------------------------------------


def test_a_balanced_journal_passes(acc: dict[str, Account]) -> None:
    result = validate_journal(
        spec(
            LineSpec(acc["cash"], debit=D("113.00")),
            LineSpec(acc["sales"].pk, credit="113.00"),  # an id and a decimal string work too
        )
    )
    assert [(line.line_no, line.debit, line.credit) for line in result.lines] == [
        (1, D("113.00"), D("0.00")),
        (2, D("0.00"), D("113.00")),
    ]
    assert result.book_scope == Book.BOTH
    assert result.totals == {
        Book.ACCOUNTING: (D("113.00"), D("113.00")),
        Book.TAX: (D("113.00"), D("113.00")),
    }


def test_integers_are_exact_amounts(acc: dict[str, Account]) -> None:
    result = validate_journal(
        spec(LineSpec(acc["cash"], debit=5), LineSpec(acc["sales"], credit=5))
    )
    assert result.lines[0].debit == D("5.00")


def test_a_book_tax_difference_balances_in_each_book(acc: dict[str, Account]) -> None:
    # Book amortization 1,000 (accounting book) vs. CCA 1,500 (tax book).
    result = validate_journal(
        spec(
            LineSpec(acc["amort"], debit=D("1000.00"), book=Book.ACCOUNTING),
            LineSpec(acc["accum"], credit=D("1000.00"), book=Book.ACCOUNTING),
            LineSpec(acc["amort"], debit=D("1500.00"), book=Book.TAX),
            LineSpec(acc["accum"], credit=D("1500.00"), book=Book.TAX),
        )
    )
    assert result.book_scope == Book.BOTH
    assert result.totals[Book.ACCOUNTING] == (D("1000.00"), D("1000.00"))
    assert result.totals[Book.TAX] == (D("1500.00"), D("1500.00"))


@pytest.mark.parametrize("book", [Book.ACCOUNTING, Book.TAX])
def test_an_entry_in_one_book(acc: dict[str, Account], book: str) -> None:
    result = validate_journal(
        spec(
            LineSpec(acc["amort"], debit=D("10.00"), book=book),
            LineSpec(acc["accum"], credit=D("10.00"), book=book),
        )
    )
    assert result.book_scope == book
    assert list(result.totals) == [book]


# ---- unbalanced (acceptance) ---------------------------------------------------------------------


def test_unbalanced_names_the_book_totals_and_difference(acc: dict[str, Account]) -> None:
    with pytest.raises(JournalInvalid) as error:
        validate_journal(
            spec(
                LineSpec(acc["cash"], debit=D("1000.00")),
                LineSpec(acc["sales"], credit=D("999.99")),
            )
        )
    assert codes(error) == ["ledger.journal.unbalanced", "ledger.journal.unbalanced"]
    assert messages(error) == [
        "Debits 1,000.00 ≠ credits 999.99 in the accounting book (difference 0.01).",
        "Debits 1,000.00 ≠ credits 999.99 in the tax book (difference 0.01).",
    ]


def test_balanced_overall_but_not_in_the_tax_book(acc: dict[str, Account]) -> None:
    with pytest.raises(JournalInvalid) as error:
        validate_journal(
            spec(
                LineSpec(acc["cash"], debit=D("1000.00")),
                LineSpec(acc["sales"], credit=D("999.99")),
                LineSpec(acc["sales"], credit=D("0.01"), book=Book.ACCOUNTING),
            )
        )
    assert messages(error) == [
        "Debits 1,000.00 ≠ credits 999.99 in the tax book (difference 0.01)."
    ]


def test_french_amounts_in_messages(acc: dict[str, Account]) -> None:
    assert format_amount(D("1234567.5")) == "1,234,567.50"
    with translation.override("fr-ca"):
        assert format_amount(D("1234567.50")) == "1 234 567,50"
        assert format_amount(D("-0.01")) == "-0,01"


# ---- every other rule ----------------------------------------------------------------------------


def test_at_least_two_lines(acc: dict[str, Account]) -> None:
    with pytest.raises(JournalInvalid) as error:
        validate_journal(spec())
    assert codes(error) == ["ledger.journal.too_few_lines"]
    with pytest.raises(JournalInvalid) as error:
        validate_journal(spec(LineSpec(acc["cash"], debit=D("1"))))
    assert codes(error)[0] == "ledger.journal.too_few_lines"


def test_floats_are_refused_never_converted(acc: dict[str, Account]) -> None:
    with pytest.raises(JournalInvalid) as error:
        validate_journal(spec(LineSpec(acc["cash"], debit=0.1), LineSpec(acc["sales"], credit=0.1)))
    assert codes(error)[:2] == ["ledger.journal.amount_type", "ledger.journal.amount_type"]
    assert messages(error)[0] == ("Line 1: the debit must be an exact amount (Decimal), not 0.1.")
    with pytest.raises(TypeError):
        to_amount(True)


def test_sub_cent_amounts_are_refused(acc: dict[str, Account]) -> None:
    with pytest.raises(JournalInvalid) as error:
        validate_journal(
            spec(
                LineSpec(acc["cash"], debit=D("10.005")),
                LineSpec(acc["sales"], credit=D("10.005")),
            )
        )
    assert codes(error) == ["ledger.journal.amount_precision"] * 2
    assert messages(error)[0] == (
        "Line 1: 10.005 has more than two decimals. Amounts are in cents: allocate the pennies "
        "across lines."
    )
    # Trailing zeros are fine.
    validate_journal(
        spec(LineSpec(acc["cash"], debit=D("10.500")), LineSpec(acc["sales"], credit=D("10.5")))
    )


def test_negative_too_large_not_a_number(acc: dict[str, Account]) -> None:
    with pytest.raises(JournalInvalid) as error:
        validate_journal(
            spec(
                LineSpec(acc["cash"], debit=D("-5.00")),
                LineSpec(acc["sales"], credit=D("10000000000000000.00")),
                LineSpec(acc["sales"], credit="abc"),
                LineSpec(acc["sales"], credit=D("NaN")),
            )
        )
    assert codes(error) == [
        "ledger.journal.amount_negative",
        "ledger.journal.amount_too_large",
        "ledger.journal.amount_type",
        "ledger.journal.amount_type",
    ]


def test_one_side_per_line(acc: dict[str, Account]) -> None:
    with pytest.raises(JournalInvalid) as error:
        validate_journal(
            spec(
                LineSpec(acc["cash"], debit=D("5"), credit=D("5")),
                LineSpec(acc["sales"]),
            )
        )
    assert codes(error) == ["ledger.journal.line_one_side", "ledger.journal.line_one_side"]
    assert messages(error)[1] == "Line 2 needs a debit or a credit, not both and not neither."


def test_unknown_book(acc: dict[str, Account]) -> None:
    with pytest.raises(JournalInvalid) as error:
        validate_journal(
            spec(
                LineSpec(acc["cash"], debit=D("5"), book="cash"),
                LineSpec(acc["sales"], credit=D("5")),
            )
        )
    assert "ledger.journal.book_invalid" in codes(error)


def test_accounts_must_be_ours_active_and_leaf(org: Organisation, acc: dict[str, Account]) -> None:
    other = Organisation.objects.create(name="Birch Garage")
    with org_context(other):
        foreign = account(other, "1000", "Their bank", subtype="bank")
    archived = account(org, "6500", "Old expense", status=AccountStatus.ARCHIVED)
    parent = account(org, "6600", "Office")
    account(org, "6610", "Office supplies", parent=parent)
    with pytest.raises(JournalInvalid) as error:
        validate_journal(
            spec(
                LineSpec(foreign, debit=D("1")),
                LineSpec(archived, debit=D("1")),
                LineSpec(parent, debit=D("1")),
                LineSpec(999_999, debit=D("1")),
                LineSpec(acc["sales"], credit=D("4")),
            )
        )
    assert codes(error) == [
        "ledger.journal.account_missing",
        "ledger.account.archived",
        "ledger.account.not_leaf",
        "ledger.journal.account_missing",
    ]
    assert messages(error)[2] == (
        "Line 3: 6600 · Office has sub-accounts: post to one of its sub-accounts instead."
    )


def test_every_problem_at_once(acc: dict[str, Account]) -> None:
    with pytest.raises(JournalInvalid) as error:
        validate_journal(
            spec(
                LineSpec(acc["cash"], debit=D("1.001")),
                LineSpec(acc["sales"], credit=D("5"), book="x"),
            )
        )
    # No balance message while amounts or books are themselves wrong.
    assert codes(error) == ["ledger.journal.amount_precision", "ledger.journal.book_invalid"]


def test_needs_an_organisation(acc: dict[str, Account]) -> None:
    with org_context(None), pytest.raises(ValueError, match="active organisation"):
        validate_journal(spec())


# ---- Hypothesis ----------------------------------------------------------------------------------

cents = st.integers(min_value=1, max_value=10**12).map(lambda n: Decimal(n) / 100)
books = st.sampled_from([Book.BOTH, Book.ACCOUNTING, Book.TAX])


@st.composite
def balanced_journals(draw: st.DrawFn) -> list[tuple[str, Decimal, str]]:
    """(side, amount, book) lines; each book group's credits add up to its debits."""
    lines: list[tuple[str, Decimal, str]] = []
    for book in draw(st.lists(books, min_size=1, max_size=3, unique=True)):
        debits = draw(st.lists(cents, min_size=1, max_size=4))
        total = sum(debits, Decimal("0"))
        others = draw(st.lists(cents, max_size=3))
        rest = total - sum(others, Decimal("0"))
        credits = [*others, rest] if rest > 0 else [total]
        lines += [("debit", amount, book) for amount in debits]
        lines += [("credit", amount, book) for amount in credits]
    return draw(st.permutations(lines))


def build(acc: dict[str, Account], lines: list[tuple[str, Decimal, str]]) -> JournalSpec:
    return spec(
        *(
            LineSpec(acc["amort"], debit=amount, book=book)
            if side == "debit"
            else LineSpec(acc["accum"], credit=amount, book=book)
            for side, amount, book in lines
        )
    )


PROPERTY = settings(
    max_examples=200, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


@PROPERTY
@given(lines=balanced_journals())
def test_property_balanced_journals_pass(
    acc: dict[str, Account], lines: list[tuple[str, Decimal, str]]
) -> None:
    result = validate_journal(build(acc, lines))
    for debits, credits in result.totals.values():
        assert debits == credits


@PROPERTY
@given(lines=balanced_journals(), index=st.integers(min_value=0), raise_=st.booleans())
def test_property_one_cent_off_is_unbalanced(
    acc: dict[str, Account], lines: list[tuple[str, Decimal, str]], index: int, raise_: bool
) -> None:
    position = index % len(lines)
    side, amount, book = lines[position]
    if not raise_ and amount <= Decimal("0.01"):
        raise_ = True
    lines[position] = (side, amount + (Decimal("0.01") if raise_ else Decimal("-0.01")), book)
    with pytest.raises(JournalInvalid) as error:
        validate_journal(build(acc, lines))
    assert set(codes(error)) == {"ledger.journal.unbalanced"}

"""C-02-T11 — trial balance per book (accounting = both + accounting; tax = both + tax).

Acceptance: the TB sums to 0 per book (property test). Also: per-account debits/credits/net in
each book, a book-tax difference shows in one book only, drafts and entries awaiting approval
never count, a reversal nets its original to zero, ``as_of`` dates, zero-balance accounts hidden
unless asked, other organisations never counted, and the book is required.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal

import pytest
from django.db import transaction
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.ledger.models import Account, Book, JournalEntry, JournalLine, JournalStatus
from numo9.ledger.trial_balance import trial_balance
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account, post_for_test

pytestmark = pytest.mark.django_db

D = Decimal
MARCH = dt.date(2026, 3, 31)


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
        "accum": account(
            org, "1810", "Accumulated amortization", subtype="accumulated_amortisation"
        ),
        "hst": account(org, "2200", "HST payable", subtype="sales_tax_control"),
        "sales": account(org, "4000", "Sales", subtype="revenue", gifi_id="8000"),
        "amort": account(org, "6400", "Amortization", subtype="amortisation", gifi_id="8670"),
    }


def post(*lines: LineSpec, date: dt.date = MARCH) -> JournalEntry:
    entry: JournalEntry = post_for_test(JournalSpec(date=date, lines=lines))
    return entry


def by_code(book: str, **kwargs: object) -> dict[str, tuple[Decimal, Decimal, Decimal]]:
    tb = trial_balance(book, **kwargs)  # type: ignore[arg-type]
    return {row.code: (row.debit, row.credit, row.balance) for row in tb.rows}


def test_a_sale_in_both_books(acc: dict[str, Account]) -> None:
    post(
        LineSpec(acc["cash"], debit=D("113.00")),
        LineSpec(acc["sales"], credit=D("100.00")),
        LineSpec(acc["hst"], credit=D("13.00")),
    )
    for book in (Book.ACCOUNTING, Book.TAX):
        tb = trial_balance(book)
        assert tb.balanced
        assert (tb.total_debit, tb.total_credit, tb.total_balance) == (
            D("113.00"),
            D("113.00"),
            D("0.00"),
        )
        assert by_code(book) == {
            "1000": (D("113.00"), D("0.00"), D("113.00")),
            "2200": (D("0.00"), D("13.00"), D("-13.00")),
            "4000": (D("0.00"), D("100.00"), D("-100.00")),
        }
    row = trial_balance(Book.TAX).rows[1]
    assert (row.debit_balance, row.credit_balance) == (D("0.00"), D("13.00"))


def test_a_book_tax_difference_shows_in_its_own_book(acc: dict[str, Account]) -> None:
    post(
        LineSpec(acc["amort"], debit=D("1000.00"), book=Book.ACCOUNTING),
        LineSpec(acc["accum"], credit=D("1000.00"), book=Book.ACCOUNTING),
        LineSpec(acc["amort"], debit=D("1500.00"), book=Book.TAX),
        LineSpec(acc["accum"], credit=D("1500.00"), book=Book.TAX),
    )
    assert by_code(Book.ACCOUNTING)["6400"] == (D("1000.00"), D("0.00"), D("1000.00"))
    assert by_code(Book.TAX)["6400"] == (D("1500.00"), D("0.00"), D("1500.00"))
    assert trial_balance(Book.ACCOUNTING).balanced and trial_balance(Book.TAX).balanced


def test_only_posted_entries_count(org: Organisation, acc: dict[str, Account]) -> None:
    post(LineSpec(acc["cash"], debit=D("10.00")), LineSpec(acc["sales"], credit=D("10.00")))
    for status in (JournalStatus.DRAFT, JournalStatus.AWAITING_APPROVAL):
        draft = JournalEntry(organisation=org, date=MARCH, status=status)
        draft.save()
        JournalLine(entry=draft, line_no=1, account=acc["cash"], debit=D("99.00")).save()
        JournalLine(entry=draft, line_no=2, account=acc["sales"], credit=D("99.00")).save()
    assert by_code(Book.ACCOUNTING)["1000"][0] == D("10.00")


def test_a_reversal_nets_its_original_to_zero(acc: dict[str, Account]) -> None:
    original = post(
        LineSpec(acc["cash"], debit=D("50.00")), LineSpec(acc["sales"], credit=D("50.00"))
    )
    post_for_test(
        JournalSpec(
            date=MARCH,
            type="reversal",
            lines=[
                LineSpec(acc["cash"], credit=D("50.00")),
                LineSpec(acc["sales"], debit=D("50.00")),
            ],
        ),
        reversal_of=original,
    )
    original.refresh_from_db()
    assert original.status == JournalStatus.REVERSED
    assert trial_balance(Book.ACCOUNTING).rows == ()
    full = trial_balance(Book.ACCOUNTING, include_zero=True)
    assert {row.code: row.balance for row in full.rows} == {"1000": 0, "4000": 0}
    assert full.total_debit == D("100.00") and full.balanced


def test_as_of_date(acc: dict[str, Account]) -> None:
    post(LineSpec(acc["cash"], debit=D("10.00")), LineSpec(acc["sales"], credit=D("10.00")))
    post(
        LineSpec(acc["cash"], debit=D("5.00")),
        LineSpec(acc["sales"], credit=D("5.00")),
        date=dt.date(2026, 4, 15),
    )
    assert by_code(Book.ACCOUNTING, as_of=MARCH)["1000"][2] == D("10.00")
    assert by_code(Book.ACCOUNTING, as_of=dt.date(2026, 4, 30))["1000"][2] == D("15.00")
    assert trial_balance(Book.ACCOUNTING, as_of=dt.date(2026, 1, 1)).rows == ()


def test_other_organisations_never_count(org: Organisation, acc: dict[str, Account]) -> None:
    post(LineSpec(acc["cash"], debit=D("10.00")), LineSpec(acc["sales"], credit=D("10.00")))
    other = Organisation.objects.create(name="Birch Garage")
    with org_context(other):
        cash = account(other, "1000", "Bank", subtype="bank")
        sales = account(other, "4000", "Sales", subtype="revenue")
        post_for_test(
            JournalSpec(
                date=MARCH,
                lines=[LineSpec(cash, debit=D("777.00")), LineSpec(sales, credit=D("777.00"))],
            )
        )
        assert by_code(Book.ACCOUNTING)["1000"][0] == D("777.00")
    assert by_code(Book.ACCOUNTING)["1000"][0] == D("10.00")


def test_the_book_is_required() -> None:
    for book in (Book.BOTH, "", "management"):
        with pytest.raises(ValueError, match="accounting or the tax book"):
            trial_balance(book)


def test_needs_an_organisation() -> None:
    with org_context(None), pytest.raises(ValueError, match="active organisation"):
        trial_balance(Book.ACCOUNTING)


# ---- property: TB sums to zero per book (acceptance) -----------------------------------------

amounts = st.integers(min_value=1, max_value=10**10).map(lambda n: Decimal(n) / 100)


@st.composite
def journals(draw: st.DrawFn) -> list[list[tuple[str, str, Decimal, str]]]:
    """1–4 random balanced journals: (side, account key, amount, book) lines."""
    keys = st.sampled_from(["cash", "accum", "hst", "sales", "amort"])
    entries = []
    for _ in range(draw(st.integers(1, 4))):
        lines: list[tuple[str, str, Decimal, str]] = []
        for book in draw(
            st.lists(st.sampled_from(Book.values), min_size=1, max_size=3, unique=True)
        ):
            debits = draw(st.lists(amounts, min_size=1, max_size=3))
            others = draw(st.lists(amounts, max_size=2))
            rest = sum(debits, Decimal("0")) - sum(others, Decimal("0"))
            credits = [*others, rest] if rest > 0 else [sum(debits, Decimal("0"))]
            lines += [("debit", draw(keys), amount, book) for amount in debits]
            lines += [("credit", draw(keys), amount, book) for amount in credits]
        entries.append(lines)
    return entries


PROPERTY = settings(
    max_examples=60,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)


@PROPERTY
@given(entries=journals())
def test_property_trial_balance_sums_to_zero_per_book(
    acc: dict[str, Account], entries: list[list[tuple[str, str, Decimal, str]]]
) -> None:
    try:
        with transaction.atomic():
            for lines in entries:
                post(
                    *(
                        LineSpec(acc[key], debit=amount, book=book)
                        if side == "debit"
                        else LineSpec(acc[key], credit=amount, book=book)
                        for side, key, amount, book in lines
                    )
                )
            for book in (Book.ACCOUNTING, Book.TAX):
                tb = trial_balance(book, include_zero=True)
                assert tb.total_balance == 0
                assert tb.total_debit == tb.total_credit
                assert tb.balanced
            raise _Rollback
    except _Rollback:
        pass


class _Rollback(Exception):
    """Undo each example's postings."""

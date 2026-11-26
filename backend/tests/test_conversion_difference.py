"""C-05-T04 — the difference calculator: debits, credits and their difference, and the
Accounts receivable / payable control lines against the opening documents.

Acceptance: returns the difference and the list of unbalanced accounts (each control whose line
doesn't equal its documents, with both figures); a negative bank balance is a warning; no equity
line is reported (REFINED). Property (Hypothesis): any balanced set of lines has difference 0.00
and can be finalised; moving one line by a cent never can.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from numo9.conversion.difference import difference
from numo9.conversion.documents import add_opening_bill, add_opening_invoice
from numo9.conversion.models import ConversionLine
from numo9.conversion.services import set_line
from numo9.tenancy.context import org_context
from tests.conversion_helpers import BEFORE, acct, conversion_books

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    return conversion_books()


def test_balanced_without_documents(books: dict[str, Any]) -> None:
    session = books["session"]
    set_line(session, acct(books, "1010"), debit="12450.30")
    set_line(session, acct(books, "3000"), credit="100.00")
    set_line(session, acct(books, "3200"), credit="12350.30")
    result = difference(session)
    assert (result.debits, result.credits, result.difference) == (
        Decimal("12450.30"),
        Decimal("12450.30"),
        Decimal("0.00"),
    )
    assert result.balanced and result.can_finalise and result.accounts == []
    assert result.opening_equity_missing is False
    assert result.as_dict()["difference"] == "0.00"


def test_unbalanced_names_the_difference(books: dict[str, Any]) -> None:
    session = books["session"]
    set_line(session, acct(books, "1010"), debit="120450.00")
    set_line(session, acct(books, "3200"), credit="120437.50")
    result = difference(session)
    assert result.difference == Decimal("12.50") and not result.can_finalise
    (reason,) = result.reasons
    assert reason.code == "conversion.unbalanced"
    assert "Debits 120,450.00 · Credits 120,437.50 · Difference 12.50" in reason.message


def test_control_against_documents(books: dict[str, Any]) -> None:
    session = books["session"]
    add_opening_invoice(
        session, contact=books["customers"]["ON"], number="INV-1", date=BEFORE, total="1000.00"
    )
    add_opening_invoice(
        session,
        contact=books["customers"]["BC"],
        number="INV-2",
        date=BEFORE,
        total="900.00",
        outstanding="500.00",
    )
    add_opening_bill(
        session, contact=books["supplier"], supplier_invoice_no="S1", date=BEFORE, total="300.00"
    )
    set_line(session, acct(books, "1010"), debit="200.00")
    set_line(session, acct(books, "1100"), debit="1400.00")  # 100 short of 1 500 of documents
    set_line(session, acct(books, "3200"), credit="1600.00")
    result = difference(session)
    assert result.balanced and not result.can_finalise
    ar, ap = result.controls
    assert (ar.role, ar.control, ar.documents, ar.count, ar.gap) == (
        "ar",
        Decimal("1400.00"),
        Decimal("1500.00"),
        2,
        Decimal("-100.00"),
    )
    # A bill without an AP line: listed too (0.00 against 300.00).
    assert (ap.role, ap.control, ap.documents) == ("ap", Decimal("0.00"), Decimal("300.00"))
    assert [c.account.code for c in result.accounts] == ["1100", "2000"]
    assert {r.code for r in result.reasons} == {"conversion.control_mismatch"}
    assert "Accounts receivable" in result.reasons[0].message
    payload = result.as_dict()
    assert payload["accounts"][0]["control"] == "1400.00"
    assert payload["accounts"][0]["documents"] == "1500.00"
    # Fixed: AR equals its documents, AP has its line.
    set_line(session, acct(books, "1100"), debit="1500.00")
    set_line(session, acct(books, "2000"), credit="300.00")
    set_line(session, acct(books, "3200"), credit="1400.00")
    fixed = difference(session)
    assert fixed.accounts == [] and fixed.can_finalise


def test_credit_balance_on_ap_side_is_negative(books: dict[str, Any]) -> None:
    session = books["session"]
    set_line(session, acct(books, "2000"), debit="50.00")  # a supplier owes us: a debit on AP
    set_line(session, acct(books, "3200"), credit="50.00")
    (ap,) = difference(session).controls
    assert ap.control == Decimal("-50.00") and not ap.matches


def test_warnings_and_equity_missing(books: dict[str, Any]) -> None:
    session = books["session"]
    set_line(session, acct(books, "1000"), credit="994.17")  # petty cash overdrawn
    set_line(session, acct(books, "2600"), debit="994.17")
    result = difference(session)
    assert result.can_finalise  # a warning doesn't block
    (warning,) = result.warnings
    assert warning.code == "conversion.negative_cash" and "994.17" in warning.message
    assert result.opening_equity_missing is True


def test_empty_cannot_finalise(books: dict[str, Any]) -> None:
    result = difference(books["session"])
    assert [r.code for r in result.reasons] == ["conversion.empty"]


def put(session: Any, account: Any, amount: Decimal, debit: bool) -> None:
    if debit:
        set_line(session, account, debit=amount)
    else:
        set_line(session, account, credit=amount)


AMOUNTS = st.decimals(min_value=Decimal("0.01"), max_value=Decimal("99999.99"), places=2)
CODES = ("1010", "1020", "1500", "1620", "2010", "2600", "2700", "3000", "3100", "3200")


@settings(
    max_examples=15,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
@given(
    amounts=st.lists(AMOUNTS, min_size=1, max_size=len(CODES) - 1),
    sides=st.lists(st.booleans(), min_size=len(CODES), max_size=len(CODES)),
    off=st.sampled_from([Decimal("0.01"), Decimal("-0.01"), Decimal("12.50")]),
)
def test_property_balanced_always_unbalanced_never(
    books: dict[str, Any], amounts: list[Decimal], sides: list[bool], off: Decimal
) -> None:
    session = books["session"]
    with org_context(books["org"]):
        ConversionLine._base_manager.filter(session=session).delete()
    net = Decimal("0.00")
    for code, amount, debit in zip(CODES, amounts, sides, strict=False):
        put(session, acct(books, code), amount, debit)
        net += amount if debit else -amount
    last = acct(books, CODES[len(amounts)])
    if net == 0:
        net = Decimal("0.00")
    else:
        put(session, last, abs(net), net < 0)
    result = difference(session)
    assert result.difference == Decimal("0.00") and result.can_finalise
    # Unbalance it: one more line, ``off`` on one side.
    spare = acct(books, "1310")
    put(session, spare, abs(off), off > 0)
    broken = difference(session)
    assert broken.difference == off and not broken.can_finalise
    assert "conversion.unbalanced" in {r.code for r in broken.reasons}

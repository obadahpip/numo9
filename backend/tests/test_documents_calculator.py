"""DocumentCalculator (D-01-T03…T05): the shared fixtures (the reference sheet, also run by the
client mirror in Vitest) match to the cent, plus hand-checked cases."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from numo9.documents.calculator import (
    CalculationError,
    Component,
    DocumentInput,
    LineInput,
    calculate,
    from_fixture,
    to_fixture,
)

FIXTURES = Path(__file__).parent / "fixtures" / "documents"
HST = (Component("hst_on", Decimal("13")),)
GST_QST = (Component("gst", Decimal("5")), Component("qst", Decimal("9.975")))


def load(name: str) -> list[dict[str, Any]]:
    data: list[dict[str, Any]] = json.loads((FIXTURES / name).read_text())
    return data


EXCLUSIVE = load("calculator_exclusive.json")
INCLUSIVE = load("calculator_inclusive.json")
NO_TAX = load("calculator_no_tax.json")


def test_fifty_exclusive_fixtures() -> None:
    assert len(EXCLUSIVE) == 50


@pytest.mark.parametrize("doc", EXCLUSIVE, ids=[d["name"] for d in EXCLUSIVE])
def test_exclusive_fixtures_match_the_reference_sheet(doc: dict[str, Any]) -> None:
    assert to_fixture(calculate(from_fixture(doc))) == doc["expected"]


@pytest.mark.parametrize("doc", INCLUSIVE + NO_TAX, ids=[d["name"] for d in INCLUSIVE + NO_TAX])
def test_inclusive_and_no_tax_fixtures(doc: dict[str, Any]) -> None:
    assert to_fixture(calculate(from_fixture(doc))) == doc["expected"]


def test_inclusive_by_hand() -> None:
    result = calculate(
        DocumentInput(
            [
                LineInput(Decimal("1"), Decimal("113.00"), components=HST),
                LineInput(Decimal("1"), Decimal("1.03"), components=GST_QST),
            ],
            tax_mode="inclusive",
        )
    )
    first, second = result.lines
    assert (first.exclusive, first.tax) == (Decimal("100.00"), Decimal("13.00"))
    # No exclusive amount gives back 1.03: the residual cent goes to QST (the larger rate).
    assert second.exclusive + second.tax == Decimal("1.03")
    assert [t.amount for t in second.taxes] == [Decimal("0.05"), Decimal("0.08")]
    assert (result.subtotal, result.tax_total, result.total, result.net_total) == (
        Decimal("114.03"),
        Decimal("13.13"),
        Decimal("114.03"),
        Decimal("100.90"),
    )
    assert result.tax_included


def test_inclusive_agrees_with_the_tax_calculator() -> None:
    """Same back-out as G-01-T06 (``numo9.tax.calculator``) on rates."""
    for gross in ("0.01", "1.03", "9.99", "114.98", "1234.56", "-56.50"):
        result = calculate(
            DocumentInput(
                [LineInput(Decimal("1"), Decimal(gross), components=GST_QST)], tax_mode="inclusive"
            )
        )
        line = result.lines[0]
        assert line.exclusive + line.tax == Decimal(gross)


def test_no_tax_ignores_components() -> None:
    result = calculate(
        DocumentInput(
            [LineInput(Decimal("3"), Decimal("10.00"), components=HST)], tax_mode="no_tax"
        )
    )
    assert (result.tax_total, result.total, result.lines[0].taxes) == (
        Decimal("0.00"),
        Decimal("30.00"),
        (),
    )


def test_exclusive_by_hand() -> None:
    result = calculate(
        DocumentInput(
            [
                LineInput(Decimal("2"), Decimal("50.00"), components=HST),
                LineInput(Decimal("1"), Decimal("100.00"), "percent", Decimal("10"), GST_QST),
            ]
        )
    )
    first, second = result.lines
    assert (first.net, first.tax) == (Decimal("100.00"), Decimal("13.00"))
    assert (second.gross, second.line_discount, second.net) == (
        Decimal("100.00"),
        Decimal("10.00"),
        Decimal("90.00"),
    )
    assert [t.amount for t in second.taxes] == [Decimal("4.50"), Decimal("8.98")]
    assert result.tax_by_component == {
        "hst_on": Decimal("13.00"),
        "gst": Decimal("4.50"),
        "qst": Decimal("8.98"),
    }
    assert (result.subtotal, result.tax_total, result.total) == (
        Decimal("190.00"),
        Decimal("26.48"),
        Decimal("216.48"),
    )


def test_purchase_claimable_split() -> None:
    meals = (Component("hst_on", Decimal("13"), "hst", Decimal("50")),)
    result = calculate(
        DocumentInput(
            [LineInput(Decimal("1"), Decimal("100.00"), components=meals)], side="purchase"
        )
    )
    (tax,) = result.lines[0].taxes
    assert (tax.amount, tax.claimable, tax.cost) == (
        Decimal("13.00"),
        Decimal("6.50"),
        Decimal("6.50"),
    )


@pytest.mark.parametrize(
    "line",
    [
        LineInput(discount_type="percent", discount_value=Decimal("101")),
        LineInput(discount_type="amount", discount_value=Decimal("-1")),
        LineInput(discount_type="half", discount_value=Decimal("1")),
    ],
)
def test_bad_discounts_are_refused(line: LineInput) -> None:
    with pytest.raises(CalculationError):
        calculate(DocumentInput([line]))


def test_unknown_tax_mode_is_refused() -> None:
    with pytest.raises(CalculationError):
        calculate(DocumentInput([], tax_mode="sometimes"))


def test_empty_document() -> None:
    result = calculate(DocumentInput([]))
    assert result.subtotal == result.tax_total == result.total == Decimal("0")

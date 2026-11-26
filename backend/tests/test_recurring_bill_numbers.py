"""E-03-T03 — the supplier invoice number pattern: rendered per period (``{{month}}-{{year}}``),
generated numbers unique per supplier — a taken number (a pattern without placeholders, two
dates in one month, a bill entered by hand) gets ``-2``, ``-3``…; another supplier's number
doesn't count, a void bill's is free again; an unknown placeholder in the pattern is refused."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.core.exceptions import ValidationError

from numo9.purchases.bill_posting import approve, void
from numo9.purchases.recurring_bills import generate_due, supplier_invoice_number, unique_number
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill, bill_books
from tests.test_recurring_bill_generation import bills, make_template

pytestmark = pytest.mark.django_db
D = dt.date


@pytest.fixture
def books(db: Any) -> dict[str, Any]:
    return bill_books()


def test_the_pattern_is_rendered_for_the_period(books: dict[str, Any]) -> None:
    template = make_template(books, supplier_invoice_no="RENT-{{month}}-{{year}}")
    with org_context(books["org"]):
        assert (
            supplier_invoice_number(template, D(2026, 10, 1), D(2026, 10, 31))
            == "RENT-October-2026"
        )
        assert supplier_invoice_number(
            template, D(2026, 10, 1), D(2026, 10, 31), locale="fr-ca"
        ) == ("RENT-octobre-2026")
        template.supplier_invoice_no = ""
        assert supplier_invoice_number(template, D(2026, 10, 1), D(2026, 10, 31)) == ""


def test_generated_numbers_are_unique(books: dict[str, Any]) -> None:
    org = books["org"]
    # Weekly with a monthly pattern: four or five dates share each month's number.
    make_template(
        books, rrule="FREQ=WEEKLY", start_date=D(2026, 3, 2), supplier_invoice_no="R-{{month}}"
    )
    bill(books, [("1", "10")], supplier_invoice_no="r-march")  # entered by hand, other case
    generate_due(org, D(2026, 4, 6))
    numbers = [b.supplier_invoice_no for b in bills(org)]
    assert numbers == ["R-March-2", "R-March-3", "R-March-4", "R-March-5", "R-March-6", "R-April"]
    assert len({n.lower() for n in numbers}) == len(numbers)


def test_a_static_pattern_still_gives_unique_numbers(books: dict[str, Any]) -> None:
    org = books["org"]
    make_template(books, supplier_invoice_no="RETAINER")
    generate_due(org, D(2026, 4, 30))
    assert [b.supplier_invoice_no for b in bills(org)] == [
        "RETAINER",
        "RETAINER-2",
        "RETAINER-3",
        "RETAINER-4",
    ]


def test_other_suppliers_and_void_bills_do_not_count(books: dict[str, Any]) -> None:
    org = books["org"]
    bill(books, [("1", "10")], supplier="other", supplier_invoice_no="RENT-January-2026")
    voided = bill(books, [("1", "10")], supplier_invoice_no="RENT-February-2026")
    void(approve(voided, books["owner"]), books["owner"], reason="Entered twice")
    deleted = bill(books, [("1", "10")], supplier_invoice_no="RENT-March-2026")
    with org_context(org):
        deleted.soft_delete()
        assert unique_number(books["supplier"], "RENT-January-2026") == "RENT-January-2026"
        assert unique_number(books["supplier"], "  RENT-February-2026 ") == "RENT-February-2026"
        assert unique_number(books["supplier"], "RENT-March-2026") == "RENT-March-2026"
        assert len(unique_number(books["supplier"], "X" * 150)) == 100


def test_an_unknown_placeholder_in_the_pattern_is_refused(books: dict[str, Any]) -> None:
    with pytest.raises(ValidationError) as refused:
        make_template(books, supplier_invoice_no="RENT-{{montth}}")
    error = refused.value.error_dict["supplier_invoice_no"][0]
    assert error.code == "purchases.recurring.pattern_unknown"

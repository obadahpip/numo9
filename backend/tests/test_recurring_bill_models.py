"""E-03-T01 — RecurringBillTemplate + lines migrate; the supplier invoice number pattern, mode,
version, first run and the date / mode / discount constraints; the schedule is validated."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from numo9.purchases.models import RecurringBillLine, RecurringBillMode, RecurringBillTemplate
from numo9.tenancy.context import org_context
from tests.bill_helpers import bill_books

pytestmark = pytest.mark.django_db


def template(books: dict[str, Any], **extra: Any) -> RecurringBillTemplate:
    values: dict[str, Any] = {
        "organisation": books["org"],
        "name": "Warehouse rent",
        "contact": books["supplier"],
        "supplier_invoice_no": "RENT-{{month}}-{{year}}",
        "rrule": "FREQ=MONTHLY",
        "start_date": dt.date(2026, 1, 31),
    }
    values.update(extra)
    created: RecurringBillTemplate = RecurringBillTemplate.objects.create(**values)
    return created


def test_template_and_lines() -> None:
    books = bill_books()
    with org_context(books["org"]):
        t = template(books, reference="Rent {{month}}")
        RecurringBillLine.objects.create(
            organisation=books["org"],
            document=t,
            description="Rent {{period_start}} – {{period_end}}",
            unit_price=Decimal("2400"),
            account=books["expense"],
        )
        t.refresh_from_db()
        assert (t.version, t.mode, t.paused, t.next_run, t.last_run) == (
            1,
            RecurringBillMode.DRAFT,
            False,
            dt.date(2026, 1, 31),
            None,
        )
        assert t.lines.count() == 1 and str(t) == "Warehouse rent"
        assert t.supplier_invoice_no == "RENT-{{month}}-{{year}}"


@pytest.mark.parametrize(
    "extra",
    [
        {"end_date": dt.date(2025, 12, 1)},
        {"mode": "approve_send"},  # bills are drafted or approved, never sent
        {"discount_type": "percent", "discount_value": 120},
        {"tax_mode": "sometimes"},
    ],
)
def test_constraints(extra: dict[str, Any]) -> None:
    books = bill_books()
    with org_context(books["org"]), pytest.raises(IntegrityError), transaction.atomic():
        template(books, **extra)


def test_the_schedule_is_validated() -> None:
    books = bill_books()
    with org_context(books["org"]):
        bad = RecurringBillTemplate(
            organisation=books["org"],
            name="Bad",
            contact=books["supplier"],
            rrule="FREQ=SOMETIMES",
            start_date=dt.date(2026, 1, 1),
            next_run=dt.date(2026, 1, 1),
        )
        with pytest.raises(ValidationError) as rule:
            bad.clean()
        assert "rrule" in rule.value.message_dict
        bad.rrule, bad.end_date = "FREQ=MONTHLY", dt.date(2025, 1, 1)
        with pytest.raises(ValidationError) as backwards:
            bad.clean()
        assert backwards.value.error_dict["end_date"][0].code == (
            "purchases.recurring.end_before_start"
        )

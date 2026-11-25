"""D-04-T01 — RecurringInvoiceTemplate + lines migrate; version, mode and the date constraints."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.sales.models import RecurringInvoiceLine, RecurringInvoiceMode, RecurringInvoiceTemplate
from numo9.tenancy.context import org_context
from tests.sales_helpers import sales_books

pytestmark = pytest.mark.django_db


def template(books: dict[str, Any], **extra: Any) -> RecurringInvoiceTemplate:
    values: dict[str, Any] = {
        "organisation": books["org"],
        "name": "Monthly retainer",
        "contact": books["customers"]["ON"],
        "rrule": "FREQ=MONTHLY",
        "start_date": dt.date(2026, 1, 31),
    }
    values.update(extra)
    created: RecurringInvoiceTemplate = RecurringInvoiceTemplate.objects.create(**values)
    return created


def test_template_and_lines() -> None:
    books = sales_books()
    with org_context(books["org"]):
        t = template(books, reference="Retainer {{month}} {{year}}")
        RecurringInvoiceLine.objects.create(
            organisation=books["org"],
            document=t,
            description="Support {{period_start}}",
            unit_price=500,
        )
        t.refresh_from_db()
        assert (t.version, t.mode, t.paused, t.prorate) == (
            1,
            RecurringInvoiceMode.DRAFT,
            False,
            False,
        )
        assert t.lines.count() == 1 and str(t) == "Monthly retainer"


@pytest.mark.parametrize(
    "extra",
    [
        {"end_date": dt.date(2025, 12, 1)},
        {"mode": "post"},
        {"discount_type": "percent", "discount_value": 120},
        {"service_start": dt.date(2026, 2, 1), "service_end": dt.date(2026, 1, 1)},
    ],
)
def test_constraints(extra: dict[str, Any]) -> None:
    books = sales_books()
    with org_context(books["org"]), pytest.raises(IntegrityError), transaction.atomic():
        template(books, **extra)

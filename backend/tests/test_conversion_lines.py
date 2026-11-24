"""C-05-T02 — ConversionLine: an account's opening balance is a debit or a credit — both sides
filled, neither, or a negative amount are refused (and the database refuses both sides); one line
per account (setting it again replaces it); a finalised conversion takes no more lines.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.conversion.models import ConversionLine, ConversionSession
from numo9.conversion.services import set_line, start_conversion
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart

pytestmark = pytest.mark.django_db


@pytest.fixture
def books() -> dict[str, Any]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    with org_context(org):
        accounts = chart(org)
    return {
        "org": org,
        "session": start_conversion(org, dt.date(2026, 4, 1), user=None),
        **accounts,
    }


def codes(error: ValidationError) -> set[str]:
    return {e.code for items in error.error_dict.values() for e in items if e.code}


def test_one_side_only(books: dict[str, Any]) -> None:
    session = books["session"]
    line = set_line(session, books["chequing"], debit="12450.30")
    assert (line.debit, line.credit) == (Decimal("12450.30"), Decimal("0.00"))
    for debit, credit, code in (
        ("10.00", "10.00", "conversion.line.both_sides"),
        ("0", "0", "conversion.line.empty"),
        ("-5.00", "0", "conversion.line.negative"),
    ):
        with pytest.raises(ValidationError) as caught:
            set_line(session, books["sales"], debit=debit, credit=credit)
        assert code in codes(caught.value)
    with org_context(books["org"]), pytest.raises(IntegrityError), transaction.atomic():
        ConversionLine._base_manager.filter(pk=line.pk).update(credit=Decimal("1.00"))


def test_one_line_per_account_replaced(books: dict[str, Any]) -> None:
    session = books["session"]
    first = set_line(session, books["ar"], debit="1000.00")
    again = set_line(session, books["ar"], credit="250.00", description="Customer deposits")
    assert again.pk == first.pk and (again.debit, again.credit) == (
        Decimal("0.00"),
        Decimal("250.00"),
    )
    with org_context(books["org"]):
        assert ConversionLine.objects.filter(session=session).count() == 1
        with pytest.raises(IntegrityError), transaction.atomic():
            ConversionLine(
                organisation=books["org"], session=session, account=books["ar"], debit=Decimal("1")
            ).save()


def test_finalised_conversion_takes_no_lines(books: dict[str, Any]) -> None:
    session = books["session"]
    with org_context(books["org"]):
        ConversionSession._base_manager.filter(pk=session.pk).update(
            status="finalised", finalised_at=timezone.now()
        )
        session.refresh_from_db()
    with pytest.raises(ValidationError) as caught:
        set_line(session, books["chequing"], debit="1.00")
    assert "conversion.session.finalised" in codes(caught.value)

"""G-03-T02 — ``TaxReturn``: versions unique per period, one filed return that isn't amended, one
return in progress; a filed return carries its confirmation; the period is its registration's."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod, ReturnMethod, ReturnStatus, TaxReturn
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

pytestmark = pytest.mark.django_db
day = dt.date


@pytest.fixture
def periods() -> list[FilingPeriod]:
    reg = registration(stop=day(2026, 12, 31))
    return switch_frequency(reg, "quarterly", day(2026, 1, 1), today=day(2026, 6, 1))[0]


def make(period: FilingPeriod, **fields: Any) -> TaxReturn:
    with org_context(period.organisation):
        item = TaxReturn(
            organisation=period.organisation,
            registration=period.registration,
            period=period,
            **fields,
        )
        item.save()
    return item


def refused(period: FilingPeriod, **fields: Any) -> bool:
    try:
        with transaction.atomic():
            make(period, **fields)
    except IntegrityError:
        return True
    return False


FILED = {"status": ReturnStatus.FILED, "filed_on": day(2026, 4, 20), "confirmation_no": "GH-1"}


def test_defaults_and_line_values(periods: list[FilingPeriod]) -> None:
    item = make(periods[0], lines={"101": "1000.00", "103": "130.00"})
    assert (item.version, item.status, item.method) == (1, ReturnStatus.DRAFT, ReturnMethod.REGULAR)
    assert item.lines["103"] == "130.00" and item.is_current
    assert str(item) == "2026-01-01 – 2026-03-31 v1"


def test_one_open_and_one_filed_return_per_period(periods: list[FilingPeriod]) -> None:
    q1, q2 = periods[0], periods[1]
    make(q1)
    assert refused(q1, version=2)  # a second return in progress
    assert refused(q1, version=1, status=ReturnStatus.AMENDED)  # the same version twice
    make(q2, **FILED)
    assert refused(q2, version=2, **FILED)  # two filed returns that aren't amended
    with org_context(q2.organisation):
        TaxReturn.objects.filter(period=q2).update(status=ReturnStatus.AMENDED)
    amended = make(q2, version=2, **FILED)  # the amendment, filed; the first stays as amended
    with org_context(q2.organisation):
        rows = list(TaxReturn.objects.filter(period=q2).order_by("version"))
    assert [(r.version, r.status, r.is_current) for r in rows] == [
        (1, "amended", False),
        (2, "filed", True),
    ]
    assert amended.is_current


def test_filed_needs_its_confirmation_and_valid_values(periods: list[FilingPeriod]) -> None:
    assert refused(periods[0], status=ReturnStatus.FILED)
    assert refused(periods[0], status=ReturnStatus.FILED, filed_on=day(2026, 4, 20))
    assert refused(periods[0], status="sent")
    assert refused(periods[0], method="simplified")


def test_period_of_another_registration_is_refused(periods: list[FilingPeriod]) -> None:
    other = registration("Other Ltd.", stop=day(2026, 12, 31))
    with org_context(periods[0].organisation), pytest.raises(ValidationError):
        TaxReturn(
            organisation=periods[0].organisation, registration=other, period=periods[0]
        ).save()

"""G-03a-T05 — FilingPeriod: dates, kind, sequence, due dates, status; the database refuses an
overlapping period of the same registration (daterange exclusion), not of another one."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.tax.models import FilingPeriod, PeriodKind, PeriodStatus
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

pytestmark = pytest.mark.django_db
day = dt.date


def period(reg: Any, start: dt.date, end: dt.date, n: int, **fields: Any) -> FilingPeriod:
    item: FilingPeriod = FilingPeriod.objects.create(
        organisation=reg.organisation,
        registration=reg,
        start=start,
        end=end,
        sequence_no=n,
        due_date=end + dt.timedelta(days=31),
        payment_due_date=end + dt.timedelta(days=31),
        **fields,
    )
    return item


def test_periods_and_the_overlap_constraint() -> None:
    reg = registration()
    with org_context(reg.organisation):
        q1 = period(reg, day(2026, 1, 1), day(2026, 3, 31), 1, status=PeriodStatus.FILED)
        period(reg, day(2026, 4, 1), day(2026, 6, 30), 2)
        assert q1.is_locked and str(q1) == "2026-01-01 – 2026-03-31"
        assert q1.kind == PeriodKind.REGULAR
        with pytest.raises(IntegrityError), transaction.atomic():
            period(reg, day(2026, 6, 30), day(2026, 7, 31), 3)  # shares 30 Jun
        with pytest.raises(IntegrityError), transaction.atomic():
            period(reg, day(2026, 8, 1), day(2026, 7, 31), 3)  # ends before it starts
        period(reg, day(2026, 7, 1), day(2026, 7, 31), 3, kind=PeriodKind.STUB)
    other = registration("Other Ltd.")
    with org_context(other.organisation):
        period(other, day(2026, 1, 1), day(2026, 3, 31), 1)  # another registration: fine

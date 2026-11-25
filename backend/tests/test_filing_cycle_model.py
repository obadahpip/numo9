"""G-03a-T04 — FilingCycle: a registration's frequency from a date, with the approval reference;
unique per (registration, effective_from); the frequency is one of monthly, quarterly, annual."""

from __future__ import annotations

import datetime as dt

import pytest
from django.db import IntegrityError, transaction

from numo9.tax.models import FilingCycle, FilingFrequency
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

pytestmark = pytest.mark.django_db


def test_cycles_of_a_registration() -> None:
    reg = registration()
    org = reg.organisation
    with org_context(org):
        FilingCycle.objects.create(
            organisation=org,
            registration=reg,
            frequency="quarterly",
            effective_from=dt.date(2026, 1, 1),
        )
        switch = FilingCycle.objects.create(
            organisation=org,
            registration=reg,
            frequency=FilingFrequency.MONTHLY,
            effective_from=dt.date(2026, 7, 1),
            approval_ref="2026-GST-48812",
            approval_date=dt.date(2026, 6, 12),
        )
        assert list(reg.filing_cycles.values_list("frequency", flat=True)) == [
            "quarterly",
            "monthly",
        ]
        assert str(switch) == "Monthly from 2026-07-01"
        with pytest.raises(IntegrityError), transaction.atomic():
            FilingCycle.objects.create(
                organisation=org,
                registration=reg,
                frequency="annual",
                effective_from=dt.date(2026, 7, 1),
            )
        with pytest.raises(IntegrityError), transaction.atomic():
            FilingCycle.objects.create(
                organisation=org,
                registration=reg,
                frequency="weekly",
                effective_from=dt.date(2027, 1, 1),
            )

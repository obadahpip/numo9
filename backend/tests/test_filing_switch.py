"""G-03a-T11 — switch validation: not inside a filed period, not before the registration; a
mid-year switch needs the approval reference (refused without — the API's 422) and warns; a
switch on a financial year start needs none."""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.tax.filing_service import switch_frequency
from numo9.tax.models import FilingPeriod, PeriodStatus, TaxError
from numo9.tenancy.context import org_context
from tests.filing_helpers import registration

pytestmark = pytest.mark.django_db
day = dt.date
TODAY = day(2026, 6, 1)


def started() -> object:
    reg = registration(stop=day(2027, 12, 31))
    switch_frequency(reg, "quarterly", day(2026, 1, 1), today=TODAY)
    return reg


def test_mid_year_switch_needs_the_reference_and_warns() -> None:
    reg = started()
    with pytest.raises(TaxError) as error:
        switch_frequency(reg, "monthly", day(2026, 7, 1), today=TODAY)
    assert error.value.code == "tax.filing.approval_required"
    periods, warnings = switch_frequency(
        reg, "monthly", day(2026, 7, 1), approval_ref="2026-GST-48812", today=TODAY
    )
    assert [w["code"] for w in warnings] == ["tax.filing.not_fiscal_year_start"]
    assert periods[2].start == day(2026, 7, 1) and periods[2].end == day(2026, 7, 31)


def test_fiscal_year_start_needs_no_reference() -> None:
    reg = started()
    _periods, warnings = switch_frequency(reg, "annual", day(2027, 1, 1), today=TODAY)
    assert warnings == []


def test_inside_a_filed_period_and_other_refusals() -> None:
    reg = started()
    with org_context(reg.organisation):  # type: ignore[attr-defined]
        q1 = FilingPeriod.objects.filter(registration=reg).order_by("start").first()
        assert q1 is not None
        q1.status = PeriodStatus.FILED
        q1.save()
    for when, code in (
        (day(2026, 2, 1), "tax.filing.inside_filed"),
        (day(2026, 1, 1), "tax.filing.inside_filed"),
        (day(2025, 6, 1), "tax.filing.before_start"),
    ):
        with pytest.raises(TaxError) as error:
            switch_frequency(reg, "monthly", when, approval_ref="R", today=TODAY)
        assert error.value.code == code
    with pytest.raises(TaxError) as error:
        switch_frequency(reg, "weekly", day(2026, 7, 1), approval_ref="R", today=TODAY)
    assert error.value.code == "tax.filing.frequency"

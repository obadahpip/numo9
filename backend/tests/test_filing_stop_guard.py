"""G-03b-T04 — generator guard: after a stop, the nightly job, ``period_for`` and a frequency
switch create no period after the stop date until a restart; the gap stays empty after one."""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.tax.filing_service import (
    gaps,
    period_for,
    regenerate,
    roll_forward,
    switch_frequency,
)
from numo9.tax.models import TaxError
from numo9.tax.stop_restart import stop
from numo9.tenancy.context import org_context
from tests.stop_helpers import TODAY, quarterly, spans

pytestmark = pytest.mark.django_db
day = dt.date


def test_nightly_job_does_not_create_july() -> None:
    reg, user = quarterly()
    stop(reg, day(2026, 6, 30), "deregistration", user=user, today=TODAY)
    before = spans(reg)
    roll_forward(now=dt.datetime(2026, 7, 2, 12, tzinfo=dt.UTC))
    roll_forward(now=dt.datetime(2027, 3, 2, 12, tzinfo=dt.UTC))
    assert spans(reg) == before and before[-1][1] == "2026-06-30"


def test_period_for_and_regenerate_after_the_stop() -> None:
    reg, user = quarterly()
    stop(reg, day(2026, 6, 30), "other", user=user, today=TODAY)
    with org_context(reg.organisation):
        assert period_for(reg, day(2026, 7, 15), today=TODAY) is None
        final = period_for(reg, day(2026, 6, 30), today=TODAY)
        assert final is not None and final.end == day(2026, 6, 30)
        regenerate(reg, day(2026, 1, 1), today=TODAY)
        assert gaps(reg) == [(day(2026, 7, 1), None)]
    assert spans(reg)[-1][1] == "2026-06-30"


def test_switch_after_the_stop_is_refused() -> None:
    reg, user = quarterly()
    stop(reg, day(2026, 6, 30), "other", user=user, today=TODAY)
    with org_context(reg.organisation), pytest.raises(TaxError) as err:
        switch_frequency(reg, "monthly", day(2026, 7, 1), today=TODAY)
    assert err.value.code == "tax.filing.not_registered"


def test_out_of_cycle_period_into_the_gap_is_refused() -> None:
    from numo9.tax.filing_service import add_custom_period
    from numo9.tax.stop_restart import restart

    reg, user = quarterly()
    stop(reg, day(2026, 6, 30), "other", user=user, today=TODAY)
    with org_context(reg.organisation), pytest.raises(TaxError) as err:
        add_custom_period(reg, day(2026, 6, 1), day(2026, 7, 15), today=TODAY)
    assert err.value.code == "tax.filing.not_registered"
    restart(reg, day(2026, 10, 1), "quarterly", user=user, today=TODAY)
    reg.refresh_from_db()
    with org_context(reg.organisation), pytest.raises(TaxError) as err:
        add_custom_period(reg, day(2026, 9, 20), day(2026, 10, 15), today=TODAY)
    assert err.value.code == "tax.filing.not_registered"

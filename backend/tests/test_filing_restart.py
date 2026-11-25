"""G-03b-T07 — restart filing: a cycle of the chosen frequency from the restart date, the
registration active and open-ended again, periods regenerated from that date (none in the gap),
an event and an audit entry by the person. Restart on 1 Jan recreates periods."""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.audit.models import AuditEvent
from numo9.tax.filing_service import gaps, period_for, roll_forward
from numo9.tax.models import FilingCycle, RegistrationStatusEvent, TaxError
from numo9.tax.stop_restart import is_stopped, restart, stop
from numo9.tenancy.context import org_context
from tests.stop_helpers import TODAY, quarterly, spans

pytestmark = pytest.mark.django_db
day = dt.date


def test_restart_on_1_january_recreates_periods() -> None:
    reg, user = quarterly()
    stop(reg, day(2026, 6, 30), "deregistration", user=user, today=TODAY)
    result = restart(reg, day(2027, 1, 1), "quarterly", "Registered again", user=user, today=TODAY)
    rows = spans(reg)
    assert rows[:3] == [
        ("2026-01-01", "2026-03-31", "regular"),
        ("2026-04-01", "2026-06-30", "regular"),
        ("2027-01-01", "2027-03-31", "regular"),
    ]
    assert not [r for r in rows if "2026-07-01" <= r[0] <= "2026-12-31"]
    assert result["added"] and not result["removed"]
    reg.refresh_from_db()
    assert (reg.effective_to, reg.status) == (None, "active")
    with org_context(reg.organisation):
        assert not is_stopped(reg)
        assert gaps(reg) == [(day(2026, 7, 1), day(2026, 12, 31))]
        assert period_for(reg, day(2026, 9, 1), today=TODAY) is None
        cycle = FilingCycle.objects.get(registration=reg, effective_from=day(2027, 1, 1))
        event = RegistrationStatusEvent.objects.get(registration=reg, action="restart")
        audit = AuditEvent.objects.get(action="tax.filing.restarted")
    assert cycle.frequency == "quarterly" and cycle.created_by == user
    assert (event.frequency, event.user) == ("quarterly", user)
    assert audit.meta["stopped"] == "2026-06-30" and audit.actor_user == user


def test_restart_mid_month_with_another_frequency_starts_with_a_stub() -> None:
    reg, user = quarterly()
    stop(reg, day(2026, 6, 30), "small_supplier", user=user, today=TODAY)
    restart(reg, day(2026, 7, 15), "monthly", user=user, today=TODAY)
    rows = spans(reg)
    assert ("2026-07-15", "2026-07-31", "stub") in rows
    assert ("2026-08-01", "2026-08-31", "regular") in rows
    roll_forward(now=dt.datetime(2026, 8, 2, 12, tzinfo=dt.UTC))
    assert not [r for r in spans(reg) if "2026-07-01" <= r[0] <= "2026-07-14"]


def test_restart_rules() -> None:
    reg, user = quarterly()
    with pytest.raises(TaxError) as err:
        restart(reg, day(2027, 1, 1), "quarterly", user=user, today=TODAY)
    assert err.value.code == "tax.filing.not_stopped"
    stop(reg, day(2026, 6, 30), "other", user=user, today=TODAY)
    for date, frequency, code in (
        (day(2026, 6, 30), "quarterly", "tax.filing.restart_before_stop"),
        (day(2026, 5, 1), "quarterly", "tax.filing.restart_before_stop"),
        (day(2027, 1, 1), "weekly", "tax.filing.frequency"),
    ):
        with pytest.raises(TaxError) as err:
            restart(reg, date, frequency, user=user, today=TODAY)
        assert err.value.code == code
    with pytest.raises(TaxError) as err:
        restart(reg, day(2027, 1, 1), "quarterly", user=None, today=TODAY)
    assert err.value.code == "tax.filing.no_actor"


def test_stop_before_the_last_restart_is_refused() -> None:
    reg, user = quarterly()
    stop(reg, day(2026, 1, 1), "other", user=user, today=TODAY)
    restart(reg, day(2026, 1, 3), "monthly", user=user, today=TODAY)
    for date in (day(2026, 1, 1), day(2026, 1, 2)):
        with pytest.raises(TaxError) as err:
            stop(reg, date, "other", user=user, today=TODAY)
        assert err.value.code == "tax.filing.stop_before_restart"
    stop(reg, day(2026, 1, 3), "other", user=user, today=TODAY)  # registered for one day


def test_stop_again_after_a_restart() -> None:
    reg, user = quarterly()
    stop(reg, day(2026, 3, 31), "other", user=user, today=TODAY)
    restart(reg, day(2026, 7, 1), "quarterly", user=user, today=TODAY)
    stop(reg, day(2026, 12, 31), "other", user=user, today=TODAY)
    with org_context(reg.organisation):
        assert gaps(reg) == [(day(2026, 4, 1), day(2026, 6, 30)), (day(2027, 1, 1), None)]
    assert [r[0] for r in spans(reg)] == ["2026-01-01", "2026-07-01", "2026-10-01"]

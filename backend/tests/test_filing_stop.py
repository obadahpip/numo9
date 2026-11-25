"""G-03b-T03 — stop filing: the open period is cut at the stop date (the final return), the
unfiled periods after it are deleted, the registration ends there and is closed, an event and an
audit entry name the person. After a stop on 30 Jun there is no July period."""

from __future__ import annotations

import datetime as dt

import pytest

from numo9.audit.models import AuditEvent
from numo9.tax.models import RegistrationStatusEvent, TaxError
from numo9.tax.stop_restart import is_stopped, stop
from numo9.tenancy.context import org_context
from tests.stop_helpers import TODAY, file_period, quarterly, spans

pytestmark = pytest.mark.django_db
day = dt.date


def test_stop_on_30_june_leaves_no_july_period() -> None:
    reg, user = quarterly()
    assert ("2026-07-01", "2026-09-30", "regular") in spans(reg)
    result = stop(reg, day(2026, 6, 30), "deregistration", "Business sold", user=user, today=TODAY)
    assert spans(reg) == [
        ("2026-01-01", "2026-03-31", "regular"),
        ("2026-04-01", "2026-06-30", "regular"),
    ]
    assert len(result["removed"]) >= 8 and result["added"] == []
    reg.refresh_from_db()
    assert (reg.effective_to, reg.status) == (day(2026, 6, 30), "closed")
    with org_context(reg.organisation):
        assert is_stopped(reg)
        event = RegistrationStatusEvent.objects.get(registration=reg)
        audit = AuditEvent.objects.get(action="tax.filing.stopped")
    assert (event.action, event.reason_code, event.user) == ("stop", "deregistration", user)
    assert audit.actor_user == user and audit.meta["reason"] == "deregistration"


def test_mid_period_stop_cuts_the_final_return() -> None:
    reg, user = quarterly()
    stop(reg, day(2026, 5, 15), "small_supplier", user=user, today=TODAY)
    assert spans(reg)[-1] == ("2026-04-01", "2026-05-15", "stub")


def test_stop_rules() -> None:
    reg, user = quarterly()
    file_period(reg, day(2026, 6, 30))
    with pytest.raises(TaxError) as err:
        stop(reg, day(2026, 6, 29), "other", user=user, today=TODAY)
    assert err.value.code == "tax.filing.stop_before_filed"
    with pytest.raises(TaxError) as err:
        stop(reg, day(2025, 12, 31), "other", user=user, today=TODAY)
    assert err.value.code in ("tax.filing.stop_before_start", "tax.filing.stop_before_filed")
    with pytest.raises(TaxError) as err:
        stop(reg, day(2026, 6, 30), "bored", user=user, today=TODAY)
    assert err.value.code == "tax.filing.stop_reason"
    with pytest.raises(TaxError) as err:
        stop(reg, day(2026, 6, 30), "other", user=None, today=TODAY)
    assert err.value.code == "tax.filing.no_actor"
    stop(reg, day(2026, 6, 30), "other", user=user, today=TODAY)  # = the filed period's end
    with pytest.raises(TaxError) as err:
        stop(reg, day(2026, 9, 30), "other", user=user, today=TODAY)
    assert err.value.code == "tax.filing.already_stopped"


def test_stopping_qst_leaves_gst_filing() -> None:
    gst, user = quarterly("Twin Ltd.")
    from tests.filing_helpers import registration

    qst = registration("Twin QC Ltd.", kind="qst")
    from numo9.tax.filing_service import switch_frequency

    with org_context(qst.organisation):
        switch_frequency(qst, "quarterly", qst.start_date, today=TODAY)
    stop(qst, day(2026, 6, 30), "other", user=user, today=TODAY)
    assert spans(qst)[-1][1] == "2026-06-30"
    assert spans(gst)[-1][1] > "2027-12-31"

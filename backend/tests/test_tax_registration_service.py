"""G-06-T04 — registration service bound to the filing-cycle engine. Acceptance: a new GST/HST
registration creates a cycle and its periods; other types create none; moving the dates keeps
the periods in step; filed periods refuse the change and the removal."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from numo9.audit.models import AuditEvent
from numo9.orgsettings.models import TaxRegistration
from numo9.tax.models import FilingCycle, FilingPeriod, PeriodStatus, TaxError
from numo9.tax.registrations import (
    create_registration,
    remove_registration,
    summary,
    update_registration,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db
day = dt.date
TODAY = day(2026, 6, 1)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def spans(reg: Any) -> list[tuple[str, str, str]]:
    with org_context(reg.organisation):
        return [
            (p.start.isoformat(), p.end.isoformat(), p.kind)
            for p in FilingPeriod.objects.filter(registration=reg).order_by("start")
        ]


def gst(org: Organisation, **fields: Any) -> TaxRegistration:
    fields.setdefault("effective_from", day(2026, 1, 1))
    fields.setdefault("effective_to", day(2026, 12, 31))
    return create_registration(org, type="rt", number="123456782RT0001", today=TODAY, **fields)


def test_new_gst_registration_creates_a_cycle_and_periods(org: Organisation) -> None:
    reg = gst(org, frequency="quarterly")
    with org_context(org):
        cycles = list(FilingCycle.objects.filter(registration=reg))
        assert [(c.frequency, c.effective_from) for c in cycles] == [("quarterly", day(2026, 1, 1))]
        actions = set(AuditEvent.objects.values_list("action", flat=True))
    assert spans(reg) == [
        ("2026-01-01", "2026-03-31", "regular"),
        ("2026-04-01", "2026-06-30", "regular"),
        ("2026-07-01", "2026-09-30", "regular"),
        ("2026-10-01", "2026-12-31", "regular"),
    ]
    assert "tax.filing.frequency_changed" in actions
    info = summary(reg, TODAY)
    assert info is not None and (info["frequency"], info["periods"]) == ("quarterly", 4)
    assert info["next_due"]["due_date"] == "2026-04-30" and info["overdue"] == 1


def test_default_frequency_and_types_that_file_nothing(org: Organisation) -> None:
    annual = gst(org, effective_to=None)
    assert spans(annual)[0] == ("2026-01-01", "2026-12-31", "regular")
    payroll = create_registration(org, type="rp", number="123456782RP0001", today=TODAY)
    undated = create_registration(
        org, type="qst", number="1234567890TQ0001", effective_from=None, today=TODAY
    )
    assert spans(payroll) == [] and spans(undated) == []
    assert summary(payroll, TODAY) is None
    assert summary(undated, TODAY) == {
        "frequency": "",
        "periods": 0,
        "next_due": None,
        "overdue": 0,
    }
    update_registration(undated, effective_from=day(2026, 4, 1), frequency="monthly", today=TODAY)
    assert spans(undated)[0] == ("2026-04-01", "2026-04-30", "regular")  # dated later: cycle then


def test_invalid_number_saves_nothing(org: Organisation) -> None:
    from django.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        create_registration(org, type="rt", number="12345RT1", effective_from=day(2026, 1, 1))
    with org_context(org):
        assert not TaxRegistration.objects.exists() and not FilingCycle.objects.exists()


def test_moving_the_dates_keeps_the_periods_in_step(org: Organisation) -> None:
    reg = gst(org, frequency="quarterly")
    update_registration(reg, effective_from=day(2026, 2, 15), today=TODAY)
    assert spans(reg)[:2] == [
        ("2026-02-15", "2026-03-31", "stub"),
        ("2026-04-01", "2026-06-30", "regular"),
    ]
    with org_context(org):
        assert FilingCycle.objects.get(registration=reg).effective_from == day(2026, 2, 15)
    update_registration(reg, effective_to=day(2026, 8, 15), today=TODAY)
    assert spans(reg)[-1] == ("2026-07-01", "2026-08-15", "stub")
    update_registration(reg, effective_to=None, today=TODAY)
    assert spans(reg)[2] == ("2026-07-01", "2026-09-30", "regular") and len(spans(reg)) > 6
    update_registration(reg, cra_approval_ref="L-1", today=TODAY)  # no date change: untouched
    with pytest.raises(TypeError):
        update_registration(reg, type="qst")


def test_filed_periods_refuse_date_changes_and_removal(org: Organisation) -> None:
    reg = gst(org, frequency="quarterly")
    with org_context(org):
        for period in FilingPeriod.objects.filter(registration=reg).order_by("start")[:2]:
            period.status = PeriodStatus.FILED
            period.save()
    before = spans(reg)
    changes: list[dict[str, Any]] = [
        {"effective_from": day(2026, 2, 1)},
        {"effective_to": day(2026, 5, 31)},
    ]
    for change in changes:
        with pytest.raises(TaxError) as error:
            update_registration(reg, today=TODAY, **change)
        assert error.value.code == "tax.registration.filed_periods"
        reg.refresh_from_db()
    assert spans(reg) == before
    update_registration(reg, effective_to=day(2026, 8, 31), today=TODAY)  # after the filed ones
    assert spans(reg) == [*before[:2], ("2026-07-01", "2026-08-31", "stub")]
    with pytest.raises(TaxError):
        remove_registration(reg)
    other = create_registration(
        org, type="qst", number="1234567890TQ0001", effective_from=day(2026, 1, 1), today=TODAY
    )
    remove_registration(other)
    other.refresh_from_db()
    assert other.deleted_at is not None and spans(other) == []

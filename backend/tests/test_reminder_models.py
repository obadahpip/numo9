"""D-07-T01 — ReminderSchedule and ReminderStep migrate: steps before and after the due date with
template, channel, minimum amount and escalation; one default schedule per organisation."""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from numo9.sales.models import (
    ReminderChannelKind,
    ReminderEscalation,
    ReminderSchedule,
    ReminderStep,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def schedule(org: Organisation, **fields: object) -> ReminderSchedule:
    row = ReminderSchedule(organisation=org, name=str(fields.pop("name", "Standard")), **fields)
    row.save()
    return row


def test_schedule_and_steps(org: Organisation) -> None:
    with org_context(org):
        made = schedule(org, is_default=True)
        assert (made.window_start, made.window_end) == (dt.time(9), dt.time(17))
        assert made.business_days_only and made.daily_cap_per_contact == 1
        for offset in (-7, 0, 7, 14, 30):
            step = ReminderStep(
                organisation=org,
                schedule=made,
                offset_days=offset,
                template="reminder.before_due" if offset < 0 else "reminder.overdue",
                min_amount=Decimal("25.00"),
                escalation=[ReminderEscalation.CREDIT_HOLD] if offset == 30 else [],
            )
            step.full_clean()
            step.save()
        assert list(made.steps.values_list("offset_days", flat=True)) == [-7, 0, 7, 14, 30]
        assert made.steps.get(offset_days=30).escalation == ["credit_hold"]
        assert made.steps.first().channel == ReminderChannelKind.EMAIL  # type: ignore[union-attr]


def test_one_default_schedule_per_organisation(org: Organisation) -> None:
    other = Organisation.objects.create(name="Other Ltd.")
    with org_context(org):
        schedule(org, is_default=True)
        schedule(org, name="Gentle")
        with pytest.raises(IntegrityError), transaction.atomic():
            schedule(org, name="Strict", is_default=True)
    with org_context(other):
        schedule(other, is_default=True)  # another organisation has its own


@pytest.mark.parametrize(
    "fields",
    [
        {"window_start": dt.time(17), "window_end": dt.time(9)},
        {"daily_cap_per_contact": 0},
    ],
)
def test_schedule_constraints(org: Organisation, fields: dict[str, object]) -> None:
    with org_context(org), pytest.raises(IntegrityError), transaction.atomic():
        schedule(org, **fields)


@pytest.mark.parametrize(
    "fields",
    [
        {"offset_days": -91},
        {"offset_days": 366},
        {"min_amount": Decimal("-1.00")},
        {"channel": "fax"},
    ],
)
def test_step_constraints(org: Organisation, fields: dict[str, object]) -> None:
    with org_context(org):
        made = schedule(org)
        values: dict[str, object] = {"offset_days": 7, "template": "reminder.overdue", **fields}
        with pytest.raises(IntegrityError), transaction.atomic():
            ReminderStep(organisation=org, schedule=made, **values).save()


def test_a_step_once_per_offset_and_channel(org: Organisation) -> None:
    with org_context(org):
        made = schedule(org)
        ReminderStep(organisation=org, schedule=made, offset_days=7, template="t").save()
        ReminderStep(
            organisation=org, schedule=made, offset_days=7, template="t", channel="sms"
        ).save()
        with pytest.raises(IntegrityError), transaction.atomic():
            ReminderStep(organisation=org, schedule=made, offset_days=7, template="t").save()


@pytest.mark.parametrize("escalation", [["phone_them"], ["credit_hold", "credit_hold"], "x"])
def test_escalation_must_be_known_actions(org: Organisation, escalation: object) -> None:
    with org_context(org):
        made = schedule(org)
        step = ReminderStep(
            organisation=org, schedule=made, offset_days=7, template="t", escalation=escalation
        )
        with pytest.raises(ValidationError) as caught:
            step.full_clean()
    assert "escalation" in caught.value.message_dict

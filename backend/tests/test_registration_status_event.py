"""G-03b-T02 — ``RegistrationStatusEvent``: a stop (date, reason) or a restart (date, frequency)
of a filing registration, always by a person; one of each action per day."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.db import IntegrityError, transaction

from numo9.accounts.models import User
from numo9.orgsettings.models import TaxRegistration
from numo9.tax.models import RegistrationStatusEvent
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def ctx() -> dict[str, Any]:
    org = Organisation.objects.create(name="Maple & Pine Supply Co.")
    user = User.objects.create_user("dana@maple.ca", name="Dana Lee")
    with org_context(org):
        reg = TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2024, 1, 1),
        )
        reg.save()
    return {"org": org, "user": user, "reg": reg}


def event(ctx: dict[str, Any], **fields: Any) -> RegistrationStatusEvent:
    with org_context(ctx["org"]):
        fields.setdefault("user", ctx["user"])
        item = RegistrationStatusEvent(organisation=ctx["org"], registration=ctx["reg"], **fields)
        item.save()
    return item


def refused(make: Any) -> bool:
    try:
        with transaction.atomic():
            make()
    except IntegrityError:
        return True
    return False


def test_stop_and_restart_events(ctx: dict[str, Any]) -> None:
    stop = event(ctx, action="stop", date=dt.date(2026, 6, 30), reason_code="deregistration")
    restart = event(ctx, action="restart", date=dt.date(2027, 1, 1), frequency="quarterly")
    assert str(stop) == "Stopped filing 2026-06-30"
    with org_context(ctx["org"]):
        assert list(ctx["reg"].status_events.all()) == [stop, restart]


def test_rules(ctx: dict[str, Any]) -> None:
    day = dt.date(2026, 6, 30)
    assert refused(lambda: event(ctx, action="stop", date=day))  # no reason
    assert refused(lambda: event(ctx, action="restart", date=day))  # no frequency
    assert refused(lambda: event(ctx, action="pause", date=day, reason_code="other"))
    event(ctx, action="stop", date=day, reason_code="other", reason_text="Sold")
    assert refused(lambda: event(ctx, action="stop", date=day, reason_code="other"))
    assert refused(lambda: event(ctx, action="stop", date=day, reason_code="other", user=None))

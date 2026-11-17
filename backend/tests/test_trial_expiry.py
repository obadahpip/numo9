"""U-05-T08 — Expiry job with a row lock; skips if converted.

Acceptance: a conversion at 23:59 local keeps the organisation active with every record intact —
the expiry job, run after it (or racing it: it waits for the conversion's row lock, then
re-reads), skips the converted subscription. A trial not converted becomes read-only (reason
``trial_ended``) once its local 23:59:59 has passed, never before; its data stays; the owners get
the day-0 email; the engine treats an ended trial as read-only even before the job runs.
"""

from __future__ import annotations

import datetime as dt
import threading
import time

import pytest
from django.db import connection, transaction

from numo9.entitlements.engine import READ_ONLY, resolve_entitlements
from numo9.entitlements.models import StatusReason, Subscription, SubscriptionStatus
from numo9.entitlements.trials import expire_trial, run_trial_expiry, start_trial
from numo9.notifications.models import EmailMessage
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
)
from tests.contact_helpers import contact
from tests.workspace_helpers import user

UTC = dt.UTC
START = dt.datetime(2026, 10, 15, 18, 0, tzinfo=UTC)
END = dt.datetime(2026, 11, 14, 4, 59, 59, tzinfo=UTC)  # 13 Nov 23:59:59 EST


def _trial(email: str = "sam@refined.ca") -> Subscription:
    org = Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")
    OrganisationMember.objects.create(
        organisation=org, user=user(email, "Sam Roy"), role=OrganisationRole.OWNER
    )
    subscription = start_trial(org, now=START)
    with org_context(org):
        for n in range(3):
            contact(org, f"Customer {n}")
    return subscription


def _status(subscription: Subscription) -> str:
    return str(Subscription._base_manager.get(pk=subscription.pk).status)


@pytest.mark.django_db
def test_not_before_local_end_then_read_only_with_data_kept() -> None:
    subscription = _trial()
    assert run_trial_expiry(END - dt.timedelta(seconds=1)) == 0  # 23:59:58 local
    assert _status(subscription) == SubscriptionStatus.TRIALING
    assert (
        resolve_entitlements(subscription.organisation, END + dt.timedelta(seconds=1)).mode
        == READ_ONLY
    )
    assert run_trial_expiry(END + dt.timedelta(minutes=5)) == 1
    row = Subscription._base_manager.get(pk=subscription.pk)
    assert (row.status, row.status_reason) == ("read_only", StatusReason.TRIAL_ENDED)
    assert row.current_period_end == END  # the trial's end stays on record
    org = Organisation.objects.get(pk=subscription.organisation_id)
    assert org.status == OrganisationStatus.READ_ONLY
    with org_context(org):
        from numo9.contacts.models import Contact

        assert Contact.objects.count() == 3  # nothing deleted
    assert EmailMessage.platform_messages.filter(kind="trial.reminder.day0").count() == 1
    assert run_trial_expiry(END + dt.timedelta(minutes=10)) == 0  # once


@pytest.mark.django_db
def test_converted_at_the_last_minute_is_skipped() -> None:
    subscription = _trial()
    with org_context(subscription.organisation):
        subscription.status = SubscriptionStatus.ACTIVE  # paid at 23:59 local
        subscription.save()
    assert run_trial_expiry(END + dt.timedelta(minutes=5)) == 0
    assert _status(subscription) == SubscriptionStatus.ACTIVE


@pytest.mark.django_db(transaction=True)
def test_race_conversion_holding_the_lock_wins() -> None:
    subscription = _trial("race@refined.ca")
    locked = threading.Event()
    done: dict[str, bool] = {}

    def convert() -> None:
        try:
            with transaction.atomic():
                row = Subscription._base_manager.select_for_update().get(pk=subscription.pk)
                locked.set()
                time.sleep(0.5)  # the expiry job tries meanwhile and must wait
                with org_context(row.organisation):
                    row.status = SubscriptionStatus.ACTIVE
                    row.save()
        finally:
            connection.close()

    worker = threading.Thread(target=convert)
    worker.start()
    assert locked.wait(5)
    done["expired"] = expire_trial(subscription.pk, END + dt.timedelta(minutes=1))
    worker.join(5)
    assert done["expired"] is False
    assert _status(subscription) == SubscriptionStatus.ACTIVE

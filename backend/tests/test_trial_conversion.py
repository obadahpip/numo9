"""U-05-T09 — Conversion: the first successful payment flips trialing → active without touching
data; the founding check (U-08) runs.

Acceptance: record counts identical before/after — every organisation-owned table holds exactly
the rows it held before the ``invoice.paid`` event (only the subscription's status, and its event
clock, change). Also: an ended trial (read-only) converts the same way; the conversion is recorded
once (a re-delivered event changes nothing), audited, and the registered conversion checks run.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from typing import Any

import pytest
from django.apps import apps

from numo9.audit.models import AuditEvent
from numo9.entitlements import trials
from numo9.entitlements.models import StatusReason, Subscription, SubscriptionStatus, TrialRegistry
from numo9.entitlements.trials import start_trial
from numo9.tenancy.context import org_context
from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
    OrgOwnedModel,
)
from tests.billing_helpers import FakeGateway, deliver, sold_package, stripe_event, stripe_invoice
from tests.contact_helpers import contact
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db
T0 = 1_790_000_000


@pytest.fixture(autouse=True)
def packages() -> Iterator[None]:
    FakeGateway.reset()
    sold_package("growth")
    yield


@pytest.fixture
def checks() -> Iterator[list[Any]]:
    seen: list[Any] = []
    check = trials.register_conversion_check(seen.append)
    yield seen
    trials._conversion_checks.remove(check)


def _trial_org() -> Organisation:
    org = Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")
    OrganisationMember.objects.create(
        organisation=org, user=user("sam@refined.ca"), role=OrganisationRole.OWNER
    )
    start_trial(org)
    Subscription._base_manager.filter(organisation=org).update(
        stripe_customer_id="cus_test_0001", stripe_subscription_id="sub_1"
    )
    with org_context(org):
        for n in range(5):
            contact(org, f"Customer {n}")
    return org


def _counts(org: Organisation) -> dict[str, int]:
    """Rows per organisation-owned table (business records), subscriptions, events and
    invoices excepted (the billing mirror is what the event adds)."""
    skip = {
        "entitlements.Subscription",
        "billing.StripeEvent",
        "billing.PlatformInvoice",
        "audit.AuditEvent",
        "notifications.Notification",
        "notifications.EmailMessage",
    }
    out = {}
    for model in apps.get_models():
        if issubclass(model, OrgOwnedModel) and model._meta.label not in skip:
            out[model._meta.label] = model._base_manager.filter(organisation=org).count()
    return out


def test_first_payment_converts_without_touching_data(checks: list[Any]) -> None:
    org = _trial_org()
    before = _counts(org)
    assert before["contacts.Contact"] == 5
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=T0))
    subscription = Subscription._base_manager.get(organisation=org)
    assert subscription.status == SubscriptionStatus.ACTIVE
    assert Organisation.objects.get(pk=org.pk).status == OrganisationStatus.ACTIVE
    assert _counts(org) == before  # record counts identical
    registry = TrialRegistry.objects.get(organisation=org)
    assert registry.converted_at == dt.datetime.fromtimestamp(T0, tz=dt.UTC)
    assert [s.pk for s in checks] == [subscription.pk]
    assert AuditEvent.platform_events.filter(action="entitlements.trial.converted").count() == 1
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=T0 + 5))  # re-delivered
    assert AuditEvent.platform_events.filter(action="entitlements.trial.converted").count() == 1
    assert len(checks) == 1


def test_ended_trial_converts_too(checks: list[Any]) -> None:
    org = _trial_org()
    Subscription._base_manager.filter(organisation=org).update(
        status=SubscriptionStatus.READ_ONLY, status_reason=StatusReason.TRIAL_ENDED
    )
    before = _counts(org)
    deliver(stripe_event("invoice.paid", stripe_invoice(), created=T0))
    subscription = Subscription._base_manager.get(organisation=org)
    assert (subscription.status, subscription.status_reason) == ("active", "")
    assert _counts(org) == before
    assert TrialRegistry.objects.get(organisation=org).converted_at is not None
    assert len(checks) == 1

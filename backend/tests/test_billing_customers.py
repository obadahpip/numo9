"""U-04-T04 — One Stripe customer per organisation. Acceptance: a second call returns the same.

Covers: the customer is created with the organisation's name, its owner's email and the
organisation in the metadata, stored on the subscription; a second call (and a call after a
retried request) creates nothing; two organisations get two customers; an organisation without a
subscription is refused; billing off → 503; the webhook lookup finds the organisation; with
stripe-mock (CI) the real client creates a customer.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from django.test import override_settings

from numo9.accounts.models import User
from numo9.billing.customers import ensure_customer, organisation_of_customer
from numo9.billing.gateway import BillingUnavailable, StripeBillingApi
from numo9.entitlements.models import Subscription
from numo9.i18n.errors import CatalogueError
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.billing_helpers import FakeGateway
from tests.entitlement_helpers import subscribe

pytestmark = pytest.mark.django_db
STRIPE_MOCK = os.environ.get("NUMO9_TEST_STRIPE_MOCK_URL", "")


@pytest.fixture(autouse=True)
def fake() -> Iterator[None]:
    FakeGateway.reset()
    with override_settings(NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway"):
        yield


def _org(name: str, owner: str = "olivia@maple.ca") -> Organisation:
    org = Organisation.objects.create(name=name)
    user = User.objects.create_user(owner, password="x" * 12, name="Olivia")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    subscribe(org, None)
    return org


def test_customer_created_once() -> None:
    org = _org("Maple Bakery Inc.")
    first = ensure_customer(org)
    assert first == "cus_test_0001"
    assert ensure_customer(org) == first
    assert [name for name, _ in FakeGateway.calls] == ["create_customer"]
    call = FakeGateway.calls[0][1]
    assert call == {
        "name": "Maple Bakery Inc.",
        "email": "olivia@maple.ca",
        "metadata": {"numo9_org": str(org.public_id)},
    }
    assert Subscription._base_manager.get(organisation=org).stripe_customer_id == first
    assert organisation_of_customer(first) == org


def test_retried_request_returns_the_same_customer() -> None:
    org = _org("Maple Bakery Inc.")
    first = ensure_customer(org)
    Subscription._base_manager.filter(organisation=org).update(stripe_customer_id="")
    assert ensure_customer(org) == first  # same idempotency key at Stripe


def test_one_customer_per_organisation() -> None:
    assert ensure_customer(_org("A Inc.", "a@a.ca")) != ensure_customer(_org("B Inc.", "b@b.ca"))


def test_no_subscription_is_refused() -> None:
    org = Organisation.objects.create(name="No Sub Inc.")
    with pytest.raises(CatalogueError) as refused:
        ensure_customer(org)
    assert refused.value.get_codes() == "billing.no_subscription"


def test_billing_off() -> None:
    org = _org("Maple Bakery Inc.")
    with (
        override_settings(NUMO9_BILLING_GATEWAY="", STRIPE_SECRET_KEY=""),
        pytest.raises(BillingUnavailable) as off,
    ):
        ensure_customer(org)
    assert off.value.status_code == 503
    assert organisation_of_customer("cus_unknown") is None


@pytest.mark.skipif(not STRIPE_MOCK, reason="needs stripe-mock (NUMO9_TEST_STRIPE_MOCK_URL)")
def test_stripe_mock_creates_a_customer() -> None:
    key = "sk_test_" + "x" * 24
    with override_settings(STRIPE_SECRET_KEY=key, STRIPE_API_BASE=STRIPE_MOCK):
        customer = StripeBillingApi().create_customer(
            name="Maple Bakery Inc.",
            email="olivia@maple.ca",
            metadata={"numo9_org": "x"},
            idempotency_key="numo9-customer-test",
        )
    assert customer.startswith("cus_")

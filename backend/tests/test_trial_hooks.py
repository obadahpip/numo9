"""U-05-T05 — Hook into organisation creation (A-02 sign-up / an accountant creates an org).

Acceptance: a new organisation is trialing — through the owner's sign-up (organisation path), a
signed-in user creating an organisation, and an accountant creating one for a client (owner
invited later). The accountant sign-up path creates a practice, never a trial.
"""

from __future__ import annotations

import json

import pytest
from django.test import Client

from numo9.entitlements.models import Subscription, SubscriptionStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationStatus
from tests.workspace_helpers import practice, user

pytestmark = pytest.mark.django_db
PASSWORD = "Correct-horse-battery-9"  # noqa: S105 (test account)


def _subscription(org: Organisation) -> Subscription:
    with org_context(org):
        subscription: Subscription = Subscription.objects.get(organisation=org)
    return subscription


def test_owner_signup_starts_a_trial() -> None:
    body = {
        "path": "organisation",
        "name": "Sam Roy",
        "email": "sam@refined.ca",
        "password": PASSWORD,
        "organisation_name": "Refined Interiors Inc.",
    }
    Client().post(
        "/_allauth/browser/v1/auth/signup", json.dumps(body), content_type="application/json"
    )
    org = Organisation.objects.get(name="Refined Interiors Inc.")
    subscription = _subscription(org)
    assert subscription.status == SubscriptionStatus.TRIALING
    assert subscription.current_period_end is not None
    assert org.status == OrganisationStatus.TRIAL


def test_accountant_signup_starts_no_trial() -> None:
    body = {
        "path": "accountant",
        "name": "Dana Lee",
        "email": "dana@cpa.ca",
        "password": PASSWORD,
        "practice_name": "Maple Leaf Accounting",
    }
    Client().post(
        "/_allauth/browser/v1/auth/signup", json.dumps(body), content_type="application/json"
    )
    assert not Subscription.objects.unscoped(reason="test: no trial anywhere").exists()


@pytest.mark.parametrize("by_accountant", [False, True])
def test_created_organisation_is_trialing(by_accountant: bool) -> None:
    person = user("dana@cpa.ca", "Dana Lee")
    firm = practice("Maple Leaf Accounting", person) if by_accountant else None
    browser = Client()
    browser.force_login(person)
    body = {"name": "Érable Bakery Inc."} | ({"practice": str(firm.public_id)} if firm else {})
    response = browser.post("/api/v1/organisations", body, content_type="application/json")
    assert response.status_code == 201, response.content
    org = Organisation.objects.get(name="Érable Bakery Inc.")
    assert _subscription(org).status == SubscriptionStatus.TRIALING

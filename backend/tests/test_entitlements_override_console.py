"""U-03-T14 (API part) — platform-owner override: grant a product for N days with a reason.

Acceptance: the override is visible in the organisation's audit log (grant and removal, with the
reason and who granted it); the product is entitled at once (cache bumped) until it ends; N is
1–365 days, the reason required; free and planned products can't be granted; only
``platform.catalogue.manage`` grants or removes (support may look).
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.entitlements.cache import entitlements_for
from numo9.entitlements.models import EntitlementOverride
from numo9.tenancy.models import Organisation
from tests.entitlement_helpers import package, payroll_keys, subscribe
from tests.test_platform_lists import staff

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    payroll_keys()
    organisation = Organisation.objects.create(name="Maple Bakery Inc.")
    subscribe(organisation, package("starter", ["accounting"]))
    return organisation


def url(org: Organisation, suffix: str = "") -> str:
    return f"/api/v1/platform/organisations/{org.public_id}/overrides{suffix}"


def test_grant_for_n_days_is_entitled_and_in_the_org_audit_log(org: Organisation) -> None:
    owner = staff("platform_owner")
    assert "payroll" not in entitlements_for(org).products
    response = owner.post(
        url(org),
        {"product": "payroll", "days": 14, "reason": "Pilot of payroll"},
        "application/json",
    )
    assert response.status_code == 201, response.content
    body = response.json()
    assert (body["product"], body["state"], body["reason"]) == (
        "payroll",
        "active",
        "Pilot of payroll",
    )
    expires = dt.datetime.fromisoformat(body["expires_at"])
    assert abs(expires - (timezone.now() + dt.timedelta(days=14))) < dt.timedelta(minutes=1)
    assert "payroll" in entitlements_for(org).products  # cache bumped
    event = AuditEvent._base_manager.get(
        organisation=org, action="entitlements.entitlementoverride.created"
    )
    assert event.changes["reason"][1] == "Pilot of payroll"
    assert event.actor_label == "platform_owner@numo9.ca" or event.actor_user is not None
    listing = owner.get(url(org)).json()
    assert [o["product"] for o in listing["overrides"]] == ["payroll"]
    assert listing["overrides"][0]["granted_by"] == "platform_owner@numo9.ca"
    assert "payroll" in [p["code"] for p in listing["products"]]
    assert listing["max_days"] == 365


def test_remove_a_grant(org: Organisation) -> None:
    owner = staff("platform_owner")
    grant = owner.post(
        url(org),
        {"product": "payroll", "days": 3, "reason": "Pilot of payroll"},
        "application/json",
    ).json()
    assert owner.delete(url(org, f"/{grant['id']}")).status_code == 204
    assert "payroll" not in entitlements_for(org).products
    assert owner.get(url(org)).json()["overrides"][0]["state"] == "removed"
    assert AuditEvent._base_manager.filter(
        organisation=org, action="entitlements.entitlementoverride.deleted"
    ).exists()
    assert owner.delete(url(org, f"/{grant['id']}")).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"product": "payroll", "days": 0, "reason": "Pilot of payroll"},
        {"product": "payroll", "days": 366, "reason": "Pilot of payroll"},
        {"product": "payroll", "days": 5, "reason": "  "},
        {"product": "practice", "days": 5, "reason": "A free product"},
        {"product": "app.commerce", "days": 5, "reason": "Not shipped yet"},
    ],
)
def test_invalid_grants_are_refused(org: Organisation, body: dict[str, object]) -> None:
    response = staff("platform_owner").post(url(org), body, "application/json")
    assert response.status_code == 400
    assert not EntitlementOverride._base_manager.exists()


def test_support_may_look_but_not_grant(org: Organisation) -> None:
    support = staff()
    assert support.get(url(org)).status_code == 200
    response = support.post(
        url(org),
        {"product": "payroll", "days": 5, "reason": "Pilot of payroll"},
        "application/json",
    )
    assert response.status_code == 403

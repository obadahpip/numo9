"""Audit of packages, prices and promo codes (U-02-T13): every change in the platform audit log
(never an organisation's), with the person who made it. Acceptance: a price change is audited
with the old and new price."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.rbac.models import Role, RoleAssignment, RoleScope

pytestmark = pytest.mark.django_db

BASE = "/api/v1/platform/packages"


@pytest.fixture
def owner() -> User:
    user = User.objects.create_user("pat@numo9.ca", name="Pat Owner")
    role = Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key="platform_owner")
    RoleAssignment.objects.create(role=role, user=user)
    return user


@pytest.fixture
def api(owner: User) -> APIClient:
    client = APIClient()
    client.force_login(owner)  # a session, as the console signs in: the request carries the actor
    return client


def events(prefix: str = "packages.") -> list[AuditEvent]:
    return list(AuditEvent.platform_events.filter(action__startswith=prefix).order_by("id"))


def post(api: APIClient, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    response = api.post(url, body or {}, format="json")
    assert response.status_code in (200, 201), response.json()
    data: dict[str, Any] = response.json()
    return data


def create_growth(api: APIClient) -> None:
    post(
        api,
        BASE,
        {"code": "growth", "name_i18n": {"en-CA": "Growth"}, "products": ["accounting"]},
    )


# ---- acceptance -------------------------------------------------------------------------------


def test_price_change_is_audited_with_old_and_new(api: APIClient, owner: User) -> None:
    create_growth(api)
    post(api, f"{BASE}/growth/activate")
    today = timezone.localdate()
    start = today + timedelta(days=30)
    post(
        api,
        f"{BASE}/growth/prices",
        {"interval": "month", "amount_cents": 3900, "effective_from": today.isoformat()},
    )
    post(
        api,
        f"{BASE}/growth/prices",
        {"interval": "month", "amount_cents": 4900, "effective_from": start.isoformat()},
    )
    first, change = events("packages.price.scheduled")
    assert first.changes == {
        "amount_cents": [None, 3900],
        "effective_from": [None, today.isoformat()],
    }
    assert change.changes == {
        "amount_cents": [3900, 4900],
        "effective_from": [today.isoformat(), start.isoformat()],
    }
    assert change.organisation is None
    assert change.actor_user_id == owner.pk
    assert change.object_type == "packages.PackagePrice"
    assert change.object_label == "growth · monthly"
    assert change.meta["package"] == "growth" and change.meta["interval"] == "month"
    # the closed window of the old version is in the log too, as a field change
    closed = AuditEvent.platform_events.get(
        action="packages.packageprice.updated", object_id=change.meta["previous_price"]
    )
    assert closed.changes == {"effective_to": [None, start.isoformat()]}


# ---- every change, in the platform log --------------------------------------------------------


def test_package_lifecycle_is_audited(api: APIClient, owner: User) -> None:
    create_growth(api)
    api.patch(
        f"{BASE}/growth", {"products": ["tax"], "limits": {"max_org_users": 5}}, format="json"
    )
    post(api, f"{BASE}/growth/activate")
    actions = [e.action for e in events()]
    assert actions[:2] == ["packages.package.created", "packages.packageproduct.created"]
    assert "packages.packageproduct.deleted" in actions  # accounting removed
    updates = events("packages.package.updated")
    assert any(e.changes.get("limits") == [{}, {"max_org_users": 5}] for e in updates)
    assert any(e.changes.get("status") == ["draft", "active"] for e in updates)
    assert all(e.organisation_id is None for e in events())
    assert all(e.actor_user_id == owner.pk for e in updates)


def test_unscheduling_a_price_is_audited(api: APIClient) -> None:
    create_growth(api)
    today = timezone.localdate()
    post(
        api,
        f"{BASE}/growth/prices",
        {"interval": "year", "amount_cents": 46800, "effective_from": today.isoformat()},
    )
    later = post(
        api,
        f"{BASE}/growth/prices",
        {
            "interval": "year",
            "amount_cents": 52800,
            "effective_from": (today + timedelta(days=9)).isoformat(),
        },
    )["price"]
    assert api.delete(f"{BASE}/growth/prices/{later['id']}").status_code == 204
    [event] = events("packages.price.unscheduled")
    assert event.changes["amount_cents"] == [52800, 46800]
    assert [e.action for e in events("packages.packageprice.deleted")] == [
        "packages.packageprice.deleted"
    ]


def test_promo_codes_are_audited(api: APIClient, owner: User) -> None:
    create_growth(api)
    post(
        api,
        f"{BASE}/promo-codes",
        {
            "code": "LAUNCH20",
            "kind": "percent",
            "percent_off": 20,
            "duration": "once",
            "packages": ["growth"],
        },
    )
    api.patch(f"{BASE}/promo-codes/LAUNCH20", {"packages": [], "max_redemptions": 5}, format="json")
    post(api, f"{BASE}/promo-codes/LAUNCH20/expire")
    [created] = events("packages.promocode.created")
    assert created.changes["code"] == [None, "LAUNCH20"]
    restriction = events("packages.promocode.packages_changed")
    assert [e.changes for e in restriction] == [
        {"packages": [[], ["growth"]]},
        {"packages": [["growth"], []]},
    ]
    updated = events("packages.promocode.updated")
    assert updated[0].changes == {"max_redemptions": [None, 5]}
    assert list(updated[1].changes) == ["expires_at"]
    assert all(e.actor_user_id == owner.pk for e in restriction + updated)
    assert all(e.organisation_id is None for e in events())

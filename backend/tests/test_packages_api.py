"""Platform packages API (U-02-T07): CRUD of packages, prices and promo codes under
/api/v1/platform/packages…, platform owner only. Acceptance: a non-owner gets 403; validation
errors come back in field form."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.packages.models import Package, PackagePrice, PackageStatus, PromoCode
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.testapp.models import SubscriptionStandIn

pytestmark = pytest.mark.django_db

BASE = "/api/v1/platform/packages"
PROMOS = f"{BASE}/promo-codes"
STAND_IN = "tests.testapp.subscriptions.StandInSubscriptions"


def platform_user(key: str | None, email: str) -> User:
    user = User.objects.create_user(email, name=email.split("@")[0].title())
    if key:
        role = Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key=key)
        RoleAssignment.objects.create(role=role, user=user)
    return user


def client_for(user: User | None) -> APIClient:
    api = APIClient()
    if user is not None:
        api.force_authenticate(user)
    return api


@pytest.fixture
def owner() -> APIClient:
    return client_for(platform_user("platform_owner", "pat@numo9.ca"))


@pytest.fixture(autouse=True)
def _stand_in_subscriptions() -> Iterator[None]:
    with override_settings(NUMO9_SUBSCRIPTION_SOURCE=STAND_IN):
        yield


GROWTH: dict[str, Any] = {
    "code": "growth",
    "name_i18n": {"en-CA": "Growth", "fr-CA": "Croissance"},
    "description_i18n": {"en-CA": "For growing teams."},
    "products": ["accounting", "tax"],
    "limits": {"max_org_users": 10},
    "is_founding_eligible": True,
}


def create(owner: APIClient, **changes: Any) -> dict[str, Any]:
    response = owner.post(BASE, {**GROWTH, **changes}, format="json")
    assert response.status_code == 201, response.json()
    body: dict[str, Any] = response.json()
    return body


def today() -> date:
    return timezone.localdate()


# ---- acceptance: platform owner only ----------------------------------------------------------


ROUTES: list[tuple[str, str]] = [
    ("get", BASE),
    ("post", BASE),
    ("get", f"{BASE}/growth"),
    ("patch", f"{BASE}/growth"),
    ("delete", f"{BASE}/growth"),
    ("post", f"{BASE}/growth/activate"),
    ("post", f"{BASE}/growth/retire"),
    ("post", f"{BASE}/growth/prices"),
    ("get", f"{BASE}/growth/prices/impact?interval=month&effective_from=2030-01-01"),
    ("delete", f"{BASE}/growth/prices/00000000-0000-0000-0000-000000000000"),
    ("get", PROMOS),
    ("post", PROMOS),
    ("get", f"{PROMOS}/LAUNCH20"),
    ("patch", f"{PROMOS}/LAUNCH20"),
    ("post", f"{PROMOS}/LAUNCH20/expire"),
]


@pytest.mark.parametrize(("method", "url"), ROUTES)
def test_non_owner_gets_403(method: str, url: str) -> None:
    Package.objects.create(code="growth", name_i18n={"en-CA": "Growth"})
    support = client_for(platform_user("platform_support", "sam@numo9.ca"))
    nobody = client_for(platform_user(None, "dana@maple.ca"))
    for api in (support, nobody):
        response = getattr(api, method)(url, {}, format="json")
        assert response.status_code == 403, (method, url, response.status_code)
        assert response.json()["code"] == "permission.denied"
    assert getattr(client_for(None), method)(url, {}, format="json").status_code in {401, 403}
    assert Package.objects.filter(code="growth", status=PackageStatus.DRAFT).exists()


@pytest.mark.parametrize(
    ("payload", "field", "code"),
    [
        ({"code": "Growth Plus"}, "code", "packages.bad_code"),
        ({"name_i18n": {"en-CA": ""}}, "name_i18n", "packages.english_required"),
        ({"name_i18n": {"es": "Crecimiento", "en-CA": "G"}}, "name_i18n", "packages.locale"),
        ({"products": ["practice"]}, "products", "packages.free_product"),
        ({"products": ["app.commerce"]}, "products", "packages.product_not_active"),
        ({"products": ["widgets"]}, "products", "packages.unknown_product"),
        ({"limits": {"max_org_users": 0}}, "limits", "min_value"),
        ({"sort": -1}, "sort", "min_value"),
    ],
)
def test_validation_errors_in_field_form(
    owner: APIClient, payload: dict[str, Any], field: str, code: str
) -> None:
    response = owner.post(BASE, {**GROWTH, **payload}, format="json")
    assert response.status_code == 400
    body = response.json()
    assert field in body, body
    assert body[field]  # message(s) for the field
    assert not Package.objects.exists()
    if code.startswith("packages."):
        assert isinstance(body[field], list) and isinstance(body[field][0], str)


# ---- packages ---------------------------------------------------------------------------------


def test_create_read_list(owner: APIClient) -> None:
    body = create(owner)
    assert body["code"] == "growth" and body["status"] == "draft"
    assert body["name"] == "Growth" and body["name_i18n"]["fr-CA"] == "Croissance"
    assert [p["code"] for p in body["products"]] == ["accounting", "tax"]
    assert body["limits"] == {"max_org_users": 10}
    assert body["is_founding_eligible"] is True
    assert body["prices"] == [] and body["current_prices"] == {"month": None, "year": None}
    assert body["subscriber_count"] == 0
    assert body["today"] == today().isoformat()
    assert "id" not in body  # codes, not database ids
    assert owner.get(f"{BASE}/growth").json() == body
    listed = owner.get(BASE).json()["packages"]
    assert [p["code"] for p in listed] == ["growth"]


def test_duplicate_code_is_a_field_error(owner: APIClient) -> None:
    create(owner)
    response = owner.post(BASE, GROWTH, format="json")
    assert response.status_code == 400
    assert "growth" in response.json()["code"][0]


def test_update_texts_products_limits(owner: APIClient) -> None:
    create(owner)
    response = owner.patch(
        f"{BASE}/growth",
        {"products": ["tax"], "limits": {"max_org_users": None}, "name_i18n": {"en-CA": "Grow"}},
        format="json",
    )
    assert response.status_code == 200, response.json()
    body = response.json()
    assert [p["code"] for p in body["products"]] == ["tax"]
    assert body["limits"] == {"max_org_users": None}
    assert body["name"] == "Grow"
    assert body["is_founding_eligible"] is True  # untouched


def test_code_cannot_be_changed_by_patch(owner: APIClient) -> None:
    create(owner)
    owner.patch(f"{BASE}/growth", {"code": "other"}, format="json")
    assert Package.objects.filter(code="growth").exists()


def test_activate_retire_delete(owner: APIClient) -> None:
    create(owner)
    create(owner, code="complete", products=["accounting"])
    assert owner.post(f"{BASE}/growth/activate").json()["status"] == "active"
    assert owner.post(f"{BASE}/complete/activate").json()["status"] == "active"
    assert owner.post(f"{BASE}/growth/retire").json()["status"] == "retired"
    refused = owner.delete(f"{BASE}/growth")
    assert refused.status_code == 409
    assert refused.json()["code"] == "packages.delete_not_draft"
    create(owner, code="starter")
    assert owner.delete(f"{BASE}/starter").status_code == 204
    assert owner.get(f"{BASE}/starter").status_code == 404


def test_activation_without_products_is_refused(owner: APIClient) -> None:
    create(owner, products=[])
    response = owner.post(f"{BASE}/growth/activate")
    assert response.status_code == 400
    assert response.json()["code"] == "packages.no_products"


def test_delete_with_subscribers_is_refused(owner: APIClient) -> None:
    create(owner)
    org = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    with org_context(org):
        SubscriptionStandIn.objects.create(
            organisation=org, package=Package.objects.get(code="growth")
        )
    response = owner.delete(f"{BASE}/growth")
    assert response.status_code == 409
    assert response.json()["code"] == "packages.in_use"
    assert owner.get(f"{BASE}/growth").json()["subscriber_count"] == 1


def test_unknown_package_is_404(owner: APIClient) -> None:
    response = owner.get(f"{BASE}/nothing")
    assert response.status_code == 404
    assert response.json()["code"] == "packages.not_found"


# ---- prices -----------------------------------------------------------------------------------


def test_schedule_prices_and_close_the_previous_version(owner: APIClient) -> None:
    create(owner)
    start = today()
    first = owner.post(
        f"{BASE}/growth/prices",
        {"interval": "month", "amount_cents": 3900, "effective_from": start.isoformat()},
        format="json",
    )
    assert first.status_code == 201, first.json()
    assert first.json()["price"]["state"] == "current"
    later = start + timedelta(days=30)
    second = owner.post(
        f"{BASE}/growth/prices",
        {"interval": "month", "amount_cents": 4900, "effective_from": later.isoformat()},
        format="json",
    )
    assert second.status_code == 201
    body = second.json()
    assert body["price"]["state"] == "scheduled"
    assert body["affected_subscriptions"] == 0
    prices = body["package"]["prices"]
    assert [(p["amount_cents"], p["effective_from"], p["effective_to"]) for p in prices] == [
        (3900, start.isoformat(), later.isoformat()),
        (4900, later.isoformat(), None),
    ]
    assert body["package"]["current_prices"]["month"]["amount_cents"] == 3900


def test_price_validation(owner: APIClient) -> None:
    create(owner)
    owner.post(f"{BASE}/growth/activate")
    url = f"{BASE}/growth/prices"
    past = owner.post(
        url,
        {"interval": "month", "amount_cents": 100, "effective_from": "2020-01-01"},
        format="json",
    )
    assert past.status_code == 400
    assert "effective_from" in past.json()
    for bad in ({"interval": "week"}, {"amount_cents": -1}, {"amount_cents": "abc"}):
        payload = {"interval": "month", "amount_cents": 100, "effective_from": "2099-01-01"}
        response = owner.post(url, {**payload, **bad}, format="json")
        assert response.status_code == 400
        assert set(response.json()) <= {"interval", "amount_cents"}
    owner.post(
        url,
        {"interval": "month", "amount_cents": 100, "effective_from": "2099-01-01"},
        format="json",
    )
    earlier = owner.post(
        url,
        {"interval": "month", "amount_cents": 200, "effective_from": "2098-01-01"},
        format="json",
    )
    assert earlier.status_code == 400
    assert "2099-01-01" in earlier.json()["effective_from"][0]


def test_draft_package_may_have_past_prices(owner: APIClient) -> None:
    create(owner)
    response = owner.post(
        f"{BASE}/growth/prices",
        {"interval": "year", "amount_cents": 46800, "effective_from": "2026-01-01"},
        format="json",
    )
    assert response.status_code == 201


def test_impact_counts_subscriptions_that_are_not_grandfathered(owner: APIClient) -> None:
    create(owner)
    package = Package.objects.get(code="growth")
    owner.post(
        f"{BASE}/growth/prices",
        {"interval": "month", "amount_cents": 3900, "effective_from": today().isoformat()},
        format="json",
    )
    for i, (interval, grandfathered) in enumerate(
        [("month", False), ("month", False), ("month", True), ("year", False)]
    ):
        org = Organisation.objects.create(name=f"Shop {i} Ltd.")
        with org_context(org):
            SubscriptionStandIn.objects.create(
                organisation=org, package=package, interval=interval, grandfathered=grandfathered
            )
    start = today() + timedelta(days=60)
    response = owner.get(
        f"{BASE}/growth/prices/impact",
        {"interval": "month", "effective_from": start.isoformat()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["affected_subscriptions"] == 2
    assert body["current"]["amount_cents"] == 3900
    bad = owner.get(f"{BASE}/growth/prices/impact", {"interval": "week"})
    assert bad.status_code == 400 and {"interval", "effective_from"} <= set(bad.json())


def test_delete_a_scheduled_price_reopens_the_previous(owner: APIClient) -> None:
    create(owner)
    url = f"{BASE}/growth/prices"
    owner.post(
        url,
        {"interval": "month", "amount_cents": 3900, "effective_from": today().isoformat()},
        format="json",
    )
    scheduled = owner.post(
        url,
        {
            "interval": "month",
            "amount_cents": 4900,
            "effective_from": (today() + timedelta(days=10)).isoformat(),
        },
        format="json",
    ).json()["price"]
    assert owner.delete(f"{url}/{scheduled['id']}").status_code == 204
    [only] = PackagePrice.objects.all()
    assert only.amount_cents == 3900 and only.effective_to is None
    started = owner.delete(f"{url}/{only.public_id}")
    assert started.status_code == 409
    assert started.json()["code"] == "packages.price_started"
    assert owner.delete(f"{url}/00000000-0000-0000-0000-000000000000").status_code == 404


# ---- promo codes ------------------------------------------------------------------------------


LAUNCH: dict[str, Any] = {
    "code": "launch20",
    "kind": "percent",
    "percent_off": 20,
    "duration": "repeating",
    "duration_months": 3,
    "max_redemptions": 10,
}


def test_promo_create_list_update_expire(owner: APIClient) -> None:
    create(owner)
    response = owner.post(PROMOS, {**LAUNCH, "packages": ["growth"]}, format="json")
    assert response.status_code == 201, response.json()
    body = response.json()
    assert body["code"] == "LAUNCH20" and body["status"] == "active"
    assert body["packages"] == [{"code": "growth", "name": "Growth"}]
    assert body["redemptions_count"] == 0 and body["max_redemptions"] == 10
    assert [p["code"] for p in owner.get(PROMOS).json()["promo_codes"]] == ["LAUNCH20"]
    changed = owner.patch(
        f"{PROMOS}/launch20",
        {"max_redemptions": 20, "packages": [], "percent_off": 90},
        format="json",
    ).json()
    assert changed["max_redemptions"] == 20 and changed["packages"] == []
    assert changed["percent_off"] == 20  # discount terms never change
    expired = owner.post(f"{PROMOS}/LAUNCH20/expire").json()
    assert expired["status"] == "expired"
    assert PromoCode.objects.get().expires_at is not None


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"code": "a"}, "code"),
        ({"percent_off": 0}, "percent_off"),
        ({"kind": "fixed", "percent_off": None}, "amount_off_cents"),
        ({"duration_months": None}, "duration_months"),
        ({"packages": ["nothing"]}, "packages"),
    ],
)
def test_promo_validation_in_field_form(
    owner: APIClient, payload: dict[str, Any], field: str
) -> None:
    response = owner.post(PROMOS, {**LAUNCH, **payload}, format="json")
    assert response.status_code == 400
    assert field in response.json(), response.json()


def test_promo_code_taken(owner: APIClient) -> None:
    owner.post(PROMOS, LAUNCH, format="json")
    response = owner.post(PROMOS, {**LAUNCH, "code": "LAUNCH20"}, format="json")
    assert response.status_code == 400
    assert "LAUNCH20" in response.json()["code"][0]
    assert owner.get(f"{PROMOS}/NOPE").status_code == 404

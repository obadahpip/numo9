"""Catalogue API (U-01-T09): GET /api/v1/catalogue/products and /feature-matrix — every key
listed once with its product and packages; public-safe fields only."""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.catalogue.models import FeatureKey, Product
from numo9.catalogue.packages import PackageRef

pytestmark = pytest.mark.django_db

PRODUCTS = "/api/v1/catalogue/products"
MATRIX = "/api/v1/catalogue/feature-matrix"

PRODUCT_FIELDS = {
    "code",
    "name",
    "name_i18n_key",
    "kind",
    "kind_label",
    "status",
    "status_label",
    "billable",
    "sort",
    "feature_count",
}
FEATURE_FIELDS = {"key", "description", "description_i18n_key", "area", "action", "is_read_only"}


class TwoPackages:
    def packages(self) -> list[PackageRef]:
        return [
            PackageRef("starter", "Starter", frozenset({"accounting", "practice", "portal"})),
            PackageRef(
                "complete", "Complete", frozenset({"accounting", "tax", "practice", "portal"})
            ),
        ]


@pytest.fixture
def client() -> APIClient:
    user = User.objects.create_user("dana@maple.ca", name="Dana Lee")
    api = APIClient()
    api.force_authenticate(user)
    return api


def test_signed_in_users_only() -> None:
    assert APIClient().get(PRODUCTS).status_code in {401, 403}
    assert APIClient().get(MATRIX).status_code in {401, 403}


def test_products_lists_every_product_with_its_keys(client: APIClient) -> None:
    body = client.get(PRODUCTS).json()
    products = body["products"]
    assert [p["code"] for p in products] == list(
        Product.objects.order_by("sort", "code").values_list("code", flat=True)
    )
    assert len([p for p in products if p["kind"] != "companion"]) == 7
    accounting = products[0]
    assert set(accounting) == PRODUCT_FIELDS | {"features"}
    assert accounting["name"] == "Accounting"
    assert accounting["status_label"] == "Active" and accounting["billable"] is True
    assert accounting["feature_count"] == len(accounting["features"]) > 0
    assert set(accounting["features"][0]) == FEATURE_FIELDS
    commerce = next(p for p in products if p["code"] == "app.commerce")
    assert commerce["status"] == "planned" and commerce["features"] == []
    practice = next(p for p in products if p["code"] == "practice")
    assert practice["billable"] is False


def test_matrix_lists_every_key_once_with_public_safe_fields(client: APIClient) -> None:
    body = client.get(MATRIX).json()
    keys = [row["key"] for row in body["features"]]
    assert len(keys) == len(set(keys)) == FeatureKey.objects.count()
    assert set(keys) == set(FeatureKey.objects.values_list("key", flat=True))
    row = body["features"][0]
    assert set(row) == FEATURE_FIELDS | {"product", "product_name", "packages"}
    assert row["product"] == "accounting" and row["packages"] == []  # no packages before U-02
    assert body["packages"] == []
    assert {p["code"] for p in body["products"]} >= {"accounting", "app.commerce"}
    for product in body["products"]:
        assert set(product) == PRODUCT_FIELDS
    # nothing internal: no database ids, public ids or timestamps anywhere
    text = str(body)
    for internal in ("'id'", "public_id", "created_at", "updated_at"):
        assert internal not in text


def test_matrix_maps_keys_to_the_packages_of_their_product(
    client: APIClient, settings: Any
) -> None:
    settings.NUMO9_PACKAGE_SOURCE = "tests.test_catalogue_api.TwoPackages"
    body = client.get(MATRIX).json()
    assert [p["code"] for p in body["packages"]] == ["starter", "complete"]
    rows = {row["key"]: row for row in body["features"]}
    assert rows["accounting.sales_invoices.write"]["packages"] == ["starter", "complete"]
    assert rows["tax.returns.approve"]["packages"] == ["complete"]


def test_texts_follow_the_request_language(client: APIClient) -> None:
    body = client.get(PRODUCTS, HTTP_ACCEPT_LANGUAGE="fr-ca").json()
    tax = next(p for p in body["products"] if p["code"] == "tax")
    assert tax["name"] == "Taxes"  # existing French entry for "Tax"
    assert tax["kind_label"]  # translated or English placeholder, never empty


def test_renaming_a_product_display_name_keeps_its_keys(client: APIClient) -> None:
    product = Product.objects.get(code="tax")
    product.name_i18n_key = "catalogue.product.taxRenamed"
    product.save()
    body = client.get(MATRIX).json()
    assert {r["key"] for r in body["features"] if r["product"] == "tax"} == set(
        FeatureKey.objects.filter(product__code="tax").values_list("key", flat=True)
    )


# ---- in an organisation (U-01-T12) ---------------------------------------------------------


class CompleteForEveryone(TwoPackages):
    def current_package(self, organisation: Any) -> str | None:
        return "complete"


def org_url(organisation: Any) -> str:
    return f"/api/v1/o/{organisation.public_id}/package-features"


@pytest.fixture
def member() -> tuple[APIClient, Any]:
    from numo9.tenancy.models import Organisation, OrganisationMember

    org = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    user = User.objects.create_user("sam@maple.ca", name="Sam Lee")
    OrganisationMember.objects.create(organisation=org, user=user, role="sales")
    api = APIClient()
    api.force_authenticate(user)
    return api, org


def test_organisation_matrix_with_no_current_package_before_u03(
    member: tuple[APIClient, Any],
) -> None:
    api, org = member
    body = api.get(org_url(org)).json()
    assert body["current_package"] is None
    assert len(body["features"]) == FeatureKey.objects.count()


def test_organisation_matrix_names_the_current_package(
    member: tuple[APIClient, Any], settings: Any
) -> None:
    settings.NUMO9_PACKAGE_SOURCE = "tests.test_catalogue_api.CompleteForEveryone"
    api, org = member
    body = api.get(org_url(org)).json()
    assert body["current_package"] == "complete"
    assert [p["code"] for p in body["packages"]] == ["starter", "complete"]


def test_organisation_matrix_is_404_for_another_organisation(
    member: tuple[APIClient, Any], client: APIClient
) -> None:
    _api, org = member
    assert client.get(org_url(org)).status_code == 404  # dana is not a member

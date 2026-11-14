"""Package model (U-02-T02): code, texts per language, status, founding flag, limits, and the
products it is made of. Acceptance: a package with 0 products cannot be activated."""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from numo9.audit.models import AuditEvent
from numo9.catalogue.models import Product, ProductStatus
from numo9.packages.models import (
    Package,
    PackageError,
    PackageProduct,
    PackageStatus,
    localised,
)

pytestmark = pytest.mark.django_db


def make(code: str = "growth", **fields: object) -> Package:
    return Package.objects.create(code=code, name_i18n={"en-CA": code.title()}, **fields)


def add(package: Package, *codes: str) -> None:
    for code in codes:
        PackageProduct.objects.create(package=package, product=Product.objects.get(code=code))


# ---- acceptance -------------------------------------------------------------------------------


def test_package_with_no_products_cannot_be_activated() -> None:
    package = make()
    package.status = PackageStatus.ACTIVE
    with pytest.raises(PackageError) as refused:
        package.save()
    assert refused.value.code == "packages.no_products"
    package.refresh_from_db()
    assert package.status == PackageStatus.DRAFT


def test_new_package_created_active_without_products_is_refused() -> None:
    with pytest.raises(PackageError):
        make(status=PackageStatus.ACTIVE)
    assert not Package.objects.exists()


def test_package_with_a_product_can_be_activated() -> None:
    package = make()
    add(package, "accounting", "tax")
    package.status = PackageStatus.ACTIVE
    package.save()
    assert set(package.products.values_list("code", flat=True)) == {"accounting", "tax"}
    assert list(Package.objects.offered()) == [package]


# ---- fields and rules -------------------------------------------------------------------------


def test_defaults() -> None:
    package = make()
    assert package.status == PackageStatus.DRAFT
    assert package.is_founding_eligible is False
    assert package.limits == {}
    assert package.limit("max_org_users") is None  # unlimited
    assert list(Package.objects.offered()) == []


def test_code_is_unique_and_never_changes() -> None:
    package = make()
    with pytest.raises(IntegrityError), transaction.atomic():
        make()
    package.code = "growth_plus"
    with pytest.raises(PackageError) as refused:
        package.save()
    assert refused.value.error_dict["code"][0].code == "packages.code_immutable"


@pytest.mark.parametrize("code", ["", "G", "Growth", "2growth", "growth-plus", "g" * 41])
def test_bad_codes_are_refused(code: str) -> None:
    with pytest.raises(PackageError):
        make(code)


def test_names_and_descriptions_per_language() -> None:
    package = Package.objects.create(
        code="growth",
        name_i18n={"en-CA": "Growth", "fr-CA": "Croissance"},
        description_i18n={"en-CA": "For growing teams."},
    )
    assert package.name("en-CA") == "Growth"
    assert package.name("fr-CA") == package.name("fr") == "Croissance"
    assert package.description("fr-CA") == "For growing teams."  # English until French is entered
    assert localised({}, "fr", "growth") == "growth"


@pytest.mark.parametrize(
    ("field", "value", "code"),
    [
        ("name_i18n", {}, "packages.english_required"),
        ("name_i18n", {"en-CA": "  "}, "packages.english_required"),
        ("name_i18n", {"en-CA": "Growth", "es": "Crecimiento"}, "packages.locale"),
        ("name_i18n", {"en-CA": "G" * 61}, "packages.text_too_long"),
        ("name_i18n", "Growth", "packages.texts_invalid"),
        ("description_i18n", {"en-CA": "d" * 301}, "packages.text_too_long"),
        ("limits", {"max_org_users": 0}, "packages.limit_value"),
        ("limits", {"max_org_users": "10"}, "packages.limit_value"),
        ("limits", {"max_org_users": True}, "packages.limit_value"),
        ("limits", {"max_practices": 3}, "packages.unknown_limit"),
        ("limits", [10], "packages.limits"),
    ],
)
def test_invalid_values_are_refused(field: str, value: object, code: str) -> None:
    package = make()
    setattr(package, field, value)
    with pytest.raises(PackageError) as refused:
        package.save()
    assert refused.value.error_dict[field][0].code == code


def test_limits() -> None:
    package = make(limits={"max_org_users": 10})
    assert package.limit("max_org_users") == 10
    package.limits = {"max_org_users": None}
    package.save()
    assert package.limit("max_org_users") is None


def test_database_refuses_an_unknown_status() -> None:
    package = make()
    with pytest.raises(IntegrityError), transaction.atomic():
        Package.objects.filter(pk=package.pk).update(status="paused")


# ---- products in a package --------------------------------------------------------------------


def test_free_sets_are_not_added_they_are_in_every_package() -> None:
    package = make()
    with pytest.raises(PackageError) as refused:
        add(package, "practice")
    assert refused.value.error_dict["product"][0].code == "packages.free_product"


def test_planned_or_retired_products_cannot_be_added() -> None:
    package = make()
    with pytest.raises(PackageError) as refused:
        add(package, "app.commerce")  # planned companion app
    assert refused.value.error_dict["product"][0].code == "packages.product_not_active"
    finance = Product.objects.get(code="finance")
    finance.status = ProductStatus.RETIRED
    finance.save()
    with pytest.raises(PackageError):
        add(package, "finance")


def test_a_product_is_in_a_package_once() -> None:
    package = make()
    add(package, "accounting")
    with pytest.raises(IntegrityError), transaction.atomic():
        add(package, "accounting")


def test_an_active_package_keeps_at_least_one_product() -> None:
    package = make()
    add(package, "accounting", "tax")
    package.status = PackageStatus.ACTIVE
    package.save()
    PackageProduct.objects.get(package=package, product__code="tax").delete()
    with pytest.raises(PackageError) as refused:
        PackageProduct.objects.get(package=package, product__code="accounting").delete()
    assert refused.value.code == "packages.last_product"
    assert package.package_products.count() == 1


def test_a_product_in_a_package_cannot_be_deleted() -> None:
    package = make()
    add(package, "tax")
    from django.db.models import ProtectedError

    with pytest.raises(ProtectedError):
        Product.objects.get(code="tax").feature_keys.all().delete()
        Product.objects.filter(code="tax").delete()


def test_changes_go_to_the_platform_audit_log() -> None:
    package = make()
    add(package, "accounting")
    events = AuditEvent.platform_events.filter(action__startswith="packages.").order_by("id")
    assert [e.action for e in events] == [
        "packages.package.created",
        "packages.packageproduct.created",
    ]
    assert all(e.organisation_id is None for e in events)
    link = AuditEvent.platform_events.get(action="packages.packageproduct.created")
    assert link.object_label == "growth: accounting"

"""Package activation and retirement (U-02-T05): guards — no delete when subscribed; retire
hides the package from sign-up. Acceptance: retiring keeps existing subscriptions active.

Subscriptions arrive with U-03; the guards ask the subscription source
(``numo9.packages.subscriptions``), here the test app's stand-in model."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.test import override_settings
from rest_framework.exceptions import APIException

from numo9.catalogue.models import Product
from numo9.catalogue.packages import get_source as package_source
from numo9.packages import services
from numo9.packages.models import Package, PackageError, PackageProduct, PackageStatus
from numo9.packages.subscriptions import NoSubscriptions, get_source
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.testapp.models import SubscriptionStandIn

pytestmark = pytest.mark.django_db

STAND_IN = "tests.testapp.subscriptions.StandInSubscriptions"


@pytest.fixture(autouse=True)
def _stand_in_subscriptions() -> Iterator[None]:
    with override_settings(NUMO9_SUBSCRIPTION_SOURCE=STAND_IN):
        yield


def make(code: str, *products: str, status: str = PackageStatus.DRAFT) -> Package:
    package = Package.objects.create(code=code, name_i18n={"en-CA": code.title()})
    for product in products:
        PackageProduct.objects.create(package=package, product=Product.objects.get(code=product))
    if status != PackageStatus.DRAFT:
        package.status = status
        package.save()
    return package


def subscribe(package: Package, name: str = "Maple Leaf Supply Ltd.") -> SubscriptionStandIn:
    org = Organisation.objects.create(name=name)
    with org_context(org):
        row: SubscriptionStandIn = SubscriptionStandIn.objects.create(
            organisation=org, package=package
        )
    return row


def code_of(error: pytest.ExceptionInfo[APIException]) -> str:
    return str(error.value.get_codes())


# ---- acceptance -------------------------------------------------------------------------------


def test_retire_keeps_existing_subscriptions_active_and_hides_from_sign_up() -> None:
    growth = make("growth", "accounting", status=PackageStatus.ACTIVE)
    make("complete", "accounting", "tax", status=PackageStatus.ACTIVE)
    subscription = subscribe(growth)

    retired = services.retire(growth)

    assert retired.status == PackageStatus.RETIRED
    subscription.refresh_from_db()
    assert subscription.status == "active"
    assert subscription.package_id == growth.pk
    assert get_source().package_of(subscription.organisation) == "growth"
    # hidden from sign-up: not offered, not in the catalogue's matrix
    assert list(Package.objects.offered().values_list("code", flat=True)) == ["complete"]
    assert [p.code for p in package_source().packages()] == ["complete"]


def test_no_delete_when_subscribed() -> None:
    growth = make("growth", "accounting")
    subscribe(growth)
    with pytest.raises(APIException) as refused:
        services.delete_package(growth)
    assert code_of(refused) == "packages.in_use"
    assert refused.value.status_code == 409
    assert "1 organisations subscribe" in str(refused.value.detail)
    with pytest.raises(PackageError):  # the model refuses too, whatever the path
        growth.delete()
    assert Package.objects.filter(pk=growth.pk).exists()


# ---- status changes ---------------------------------------------------------------------------


def test_activate_offers_the_package() -> None:
    growth = make("growth", "accounting")
    assert services.activate(growth).status == PackageStatus.ACTIVE
    assert list(Package.objects.offered()) == [growth]
    assert services.activate(growth).status == PackageStatus.ACTIVE  # already active: no-op


def test_activate_without_products_is_refused() -> None:
    empty = make("empty")
    with pytest.raises(APIException) as refused:
        services.activate(empty)
    assert code_of(refused) == "packages.no_products"
    assert refused.value.status_code == 400
    empty.refresh_from_db()
    assert empty.status == PackageStatus.DRAFT


def test_retired_package_can_be_offered_again() -> None:
    growth = make("growth", "accounting", status=PackageStatus.ACTIVE)
    make("complete", "tax", status=PackageStatus.ACTIVE)
    services.retire(growth)
    assert services.activate(growth).status == PackageStatus.ACTIVE


def test_the_only_offered_package_cannot_be_retired() -> None:
    growth = make("growth", "accounting", status=PackageStatus.ACTIVE)
    make("starter", "accounting")  # a draft is not offered
    with pytest.raises(APIException) as refused:
        services.retire(growth)
    assert code_of(refused) == "packages.last_offered"
    growth.refresh_from_db()
    assert growth.status == PackageStatus.ACTIVE


@pytest.mark.parametrize(
    ("start", "wanted"),
    [(PackageStatus.DRAFT, PackageStatus.RETIRED), (PackageStatus.ACTIVE, PackageStatus.DRAFT)],
)
def test_other_status_changes_are_refused(start: str, wanted: str) -> None:
    package = make("growth", "accounting", status=start)
    make("complete", "tax", status=PackageStatus.ACTIVE)
    with pytest.raises(APIException) as refused:
        services._change_status(package, wanted)
    assert code_of(refused) == "packages.status_change"
    package.refresh_from_db()
    assert package.status == start


# ---- delete -----------------------------------------------------------------------------------


def test_a_draft_nobody_subscribes_to_can_be_deleted() -> None:
    draft = make("growth", "accounting")
    services.delete_package(draft)
    assert not Package.objects.filter(code="growth").exists()
    assert not PackageProduct.objects.exists()


@pytest.mark.parametrize("status", [PackageStatus.ACTIVE, PackageStatus.RETIRED])
def test_only_drafts_are_deleted(status: str) -> None:
    make("complete", "tax", status=PackageStatus.ACTIVE)
    package = make("growth", "accounting", status=PackageStatus.ACTIVE)
    if status == PackageStatus.RETIRED:
        services.retire(package)
    with pytest.raises(APIException) as refused:
        services.delete_package(package)
    assert code_of(refused) == "packages.delete_not_draft"


def test_cancelled_subscriptions_do_not_count() -> None:
    growth = make("growth", "accounting")
    subscription = subscribe(growth)
    with org_context(subscription.organisation):
        subscription.status = "cancelled"
        subscription.save()
    assert services.subscriber_count(growth) == 0


# ---- catalogue matrix source ------------------------------------------------------------------


def test_matrix_source_lists_offered_packages_with_free_sets() -> None:
    growth = make("growth", "accounting", status=PackageStatus.ACTIVE)
    growth.name_i18n = {"en-CA": "Growth", "fr-CA": "Croissance"}
    growth.save()
    make("starter", "accounting")  # draft: not offered
    [ref] = package_source().packages()
    assert ref.code == "growth" and ref.name == "Growth"
    assert ref.products == frozenset({"accounting", "practice", "portal"})
    from django.utils import translation

    with translation.override("fr-ca"):
        assert package_source().packages()[0].name == "Croissance"


def test_without_subscriptions_nobody_has_a_package() -> None:
    org = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    assert NoSubscriptions().count(make("growth", "accounting")) == 0
    assert NoSubscriptions().package_of(org) is None

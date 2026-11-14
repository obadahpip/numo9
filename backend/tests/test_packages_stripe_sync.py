"""Stripe Product/Price sync job (U-02-T12): a Stripe Price per PackagePrice, never mutating an
existing one — a stub until U-04 bills with it. Acceptance: a new price version creates a new
Stripe price id; the old one is untouched. Integration with stripe-mock when
NUMO9_TEST_STRIPE_MOCK_URL is set (CI service); a recording fake gateway otherwise."""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any
from unittest import mock

import pytest
from django.test import override_settings
from django.utils import timezone

from numo9.catalogue.models import Product
from numo9.jobs.models import JobRun
from numo9.jobs.runtime import start_job
from numo9.packages import services
from numo9.packages.models import (
    BillingInterval,
    Package,
    PackageError,
    PackagePrice,
    PackageProduct,
    PackageStatus,
)
from numo9.packages.stripe_sync import StripeApi, get_gateway, sync, sync_stripe_prices
from tests.job_helpers import deliver

pytestmark = pytest.mark.django_db

STRIPE_MOCK = os.environ.get("NUMO9_TEST_STRIPE_MOCK_URL", "")
FAKE = "tests.test_packages_stripe_sync.RecordingGateway"


class RecordingGateway:
    """In-memory Stripe: ids like Stripe's, every call recorded (no update method exists)."""

    calls: list[tuple[str, str]] = []

    def create_product(self, package: Package) -> str:
        self.calls.append(("product", package.code))
        return f"numo9_pkg_{package.code}"

    def create_price(self, price: PackagePrice, product_id: str) -> str:
        self.calls.append(("price", str(price.public_id)))
        return f"price_{len(self.calls):04d}_{price.amount_cents}"


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    RecordingGateway.calls = []
    yield


def make(code: str = "growth", status: str = PackageStatus.ACTIVE) -> Package:
    package = Package.objects.create(code=code, name_i18n={"en-CA": code.title()})
    PackageProduct.objects.create(package=package, product=Product.objects.get(code="accounting"))
    if status != PackageStatus.DRAFT:
        package.status = PackageStatus.ACTIVE
        package.save()
    return package


def version(
    package: Package, cents: int, start: date, interval: str = BillingInterval.MONTH
) -> PackagePrice:
    return services.schedule_price(
        package, interval=interval, amount_cents=cents, effective_from=start
    )


# ---- acceptance -------------------------------------------------------------------------------


@override_settings(NUMO9_STRIPE_GATEWAY=FAKE)
def test_new_version_creates_a_new_stripe_price_and_leaves_the_old_one() -> None:
    package = make()
    today = timezone.localdate()
    old = version(package, 3900, today)
    assert sync(RecordingGateway()) == {"products_created": 1, "prices_created": 1}
    old.refresh_from_db()
    first_id = old.stripe_price_id
    assert first_id.startswith("price_")

    new = version(package, 4900, today + timedelta(days=30))
    assert sync(RecordingGateway()) == {"products_created": 0, "prices_created": 1}
    old.refresh_from_db()
    new.refresh_from_db()
    assert new.stripe_price_id and new.stripe_price_id != first_id
    assert old.stripe_price_id == first_id  # untouched
    assert old.effective_to == new.effective_from  # the version window closed locally only
    assert RecordingGateway.calls == [
        ("product", "growth"),
        ("price", str(old.public_id)),
        ("price", str(new.public_id)),
    ]
    package.refresh_from_db()
    assert package.stripe_product_id == "numo9_pkg_growth"


@pytest.mark.skipif(not STRIPE_MOCK, reason="needs stripe-mock (NUMO9_TEST_STRIPE_MOCK_URL)")
def test_against_stripe_mock_new_price_id_old_untouched() -> None:
    key = "sk_test_mock"  # noqa: S105 — stripe-mock accepts any key; not a secret
    with override_settings(STRIPE_SECRET_KEY=key, STRIPE_API_BASE=STRIPE_MOCK):
        gateway = get_gateway()
        assert isinstance(gateway, StripeApi)
        package = make()
        today = timezone.localdate()
        old = version(package, 3900, today, BillingInterval.YEAR)
        with mock.patch.object(
            gateway.client.v1.prices, "update", side_effect=AssertionError("never update")
        ):
            sync(gateway)
            old.refresh_from_db()
            first_id = old.stripe_price_id
            new = version(package, 4900, today + timedelta(days=10), BillingInterval.YEAR)
            sync(gateway)
        old.refresh_from_db()
        new.refresh_from_db()
        assert first_id.startswith("price_") and new.stripe_price_id.startswith("price_")
        assert new.stripe_price_id != first_id
        assert old.stripe_price_id == first_id
        stripe_price = gateway.client.v1.prices.retrieve(new.stripe_price_id)
        assert stripe_price.object == "price"


# ---- the job ----------------------------------------------------------------------------------


def test_sync_is_off_without_stripe_configured(sent: list[dict[str, Any]]) -> None:
    package = make()
    version(package, 3900, timezone.localdate())
    assert get_gateway() is None
    assert sent == []  # no job started while Stripe is not configured
    assert not JobRun.platform_runs.exists()
    run = start_job(sync_stripe_prices)  # started anyway (e.g. by hand): it does nothing
    assert deliver(sync_stripe_prices, sent[0]) == {
        "skipped": True,
        "products_created": 0,
        "prices_created": 0,
    }
    run.refresh_from_db()
    assert run.status == "succeeded"


@override_settings(NUMO9_STRIPE_GATEWAY=FAKE)
def test_scheduling_a_price_and_activating_start_the_job(sent: list[dict[str, Any]]) -> None:
    draft = make("starter", status=PackageStatus.DRAFT)
    version(draft, 1900, date(2026, 1, 1))
    assert sent == []  # a draft has never been sold: nothing to sync yet
    services.activate(draft)
    assert [m["task"] for m in sent] == ["numo9.packages.sync_stripe_prices"]
    result = deliver(sync_stripe_prices, sent[0])
    assert result == {"skipped": False, "products_created": 1, "prices_created": 1}
    version(draft, 2900, timezone.localdate() + timedelta(days=5))
    assert len(sent) == 2
    assert deliver(sync_stripe_prices, sent[1])["prices_created"] == 1


@override_settings(NUMO9_STRIPE_GATEWAY=FAKE)
def test_a_second_run_creates_nothing_and_drafts_are_skipped() -> None:
    make("growth")
    draft = make("complete", status=PackageStatus.DRAFT)
    PackagePrice.objects.create(
        package=draft, interval="month", amount_cents=9900, effective_from=date(2026, 1, 1)
    )
    version(Package.objects.get(code="growth"), 3900, timezone.localdate())
    sync(RecordingGateway())
    assert sync(RecordingGateway()) == {"products_created": 0, "prices_created": 0}
    assert PackagePrice.objects.get(package=draft).stripe_price_id == ""


def test_a_stripe_price_id_is_set_once() -> None:
    package = make()
    row = version(package, 3900, timezone.localdate())
    row.stripe_price_id = "price_A"
    row.save()
    row.stripe_price_id = "price_B"
    with pytest.raises(PackageError) as refused:
        row.save()
    assert refused.value.code == "packages.stripe_price_immutable"

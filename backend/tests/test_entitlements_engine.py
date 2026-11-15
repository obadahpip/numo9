"""U-03-T04, T05 — resolve_entitlements(org) and the read-retention rule.

Acceptance T04: a table-driven test over every status. Acceptance T05: after a downgrade Payroll
read = true, write = false. Also: free sets in every package; trial/demo packages from settings or
every active product; founding gets every active product (incl. one that ships later) but never a
planned one; overrides add a product until they expire (and bound the answer's validity); grace
end is read from the clock (clock skew); CORE always allowed; no organisation → none; practice
users never change the answer.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from django.utils import timezone

from numo9.catalogue.drf import CORE
from numo9.catalogue.models import FeatureKey, Product, ProductStatus
from numo9.entitlements.engine import (
    FULL,
    NONE,
    READ_ONLY,
    Engine,
    Entitlements,
    resolve_entitlements,
)
from numo9.entitlements.models import OrgProductHistory, StatusReason, SubscriptionStatus
from numo9.tenancy.models import Organisation, OrganisationStatus
from tests.entitlement_helpers import grant, package, payroll_keys, subscribe

pytestmark = pytest.mark.django_db

ACCOUNTING_WRITE = "accounting.sales_invoices.write"
ACCOUNTING_READ = "accounting.sales_invoices.read"
PAYROLL_READ, PAYROLL_WRITE = "payroll.pay_runs.read", "payroll.pay_runs.write"


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture(autouse=True)
def _payroll() -> None:
    payroll_keys()


def keys_of(product: str) -> set[str]:
    return set(FeatureKey.objects.filter(product__code=product).values_list("key", flat=True))


def read_keys_of(product: str) -> set[str]:
    return set(
        FeatureKey.objects.filter(product__code=product, is_read_only=True).values_list(
            "key", flat=True
        )
    )


# ---- T04: every status --------------------------------------------------------------------------

PAST = timedelta(days=-1)
FUTURE = timedelta(days=7)

STATUS_TABLE: list[tuple[str, dict[str, Any], str, str]] = [
    # status, extra fields, mode, reason
    (SubscriptionStatus.TRIALING, {}, FULL, "trialing"),
    (SubscriptionStatus.ACTIVE, {}, FULL, "active"),
    (SubscriptionStatus.PAST_DUE, {"grace_until": FUTURE}, FULL, "past_due"),
    (SubscriptionStatus.PAST_DUE, {"grace_until": PAST}, READ_ONLY, "payment_failed"),
    (
        SubscriptionStatus.READ_ONLY,
        {"status_reason": StatusReason.TRIAL_ENDED},
        READ_ONLY,
        "trial_ended",
    ),
    (
        SubscriptionStatus.READ_ONLY,
        {"status_reason": StatusReason.PAYMENT_FAILED},
        READ_ONLY,
        "payment_failed",
    ),
    (SubscriptionStatus.READ_ONLY, {}, READ_ONLY, "read_only"),
    (
        SubscriptionStatus.CANCELLED,
        {"status_reason": StatusReason.CANCELLED},
        READ_ONLY,
        "cancelled",
    ),
    (SubscriptionStatus.DEMO, {}, FULL, "demo"),
]


@pytest.mark.parametrize(("status", "fields", "mode", "reason"), STATUS_TABLE)
def test_every_status(
    org: Organisation, status: str, fields: dict[str, Any], mode: str, reason: str
) -> None:
    growth = package("growth", ["accounting"])
    values = {k: timezone.now() + v if isinstance(v, timedelta) else v for k, v in fields.items()}
    subscribe(org, growth, status, **values)
    answer = resolve_entitlements(org)
    assert (answer.mode, answer.reason, answer.status) == (mode, reason, status)
    assert answer.package == "growth"
    assert answer.products == {"accounting", "practice", "portal"}  # free sets in every package
    if mode == FULL:
        assert answer.features == keys_of("accounting") | keys_of("practice") | keys_of("portal")
        assert answer.since is None
        assert answer.allows(ACCOUNTING_WRITE)
    else:
        assert answer.features == (
            read_keys_of("accounting") | read_keys_of("practice") | read_keys_of("portal")
        )
        assert answer.since is not None
        assert answer.allows(ACCOUNTING_READ) and not answer.allows(ACCOUNTING_WRITE)
    assert not answer.allows(PAYROLL_READ)  # not in the package, never was


def test_since_is_the_grace_end_after_a_failed_payment(org: Organisation) -> None:
    grace = timezone.now() - timedelta(hours=2)
    subscribe(
        org, package("growth", ["accounting"]), SubscriptionStatus.PAST_DUE, grace_until=grace
    )
    answer = resolve_entitlements(org)
    assert (answer.mode, answer.since) == (READ_ONLY, grace)


def test_grace_end_comes_from_the_clock_not_the_status_job(org: Organisation) -> None:
    grace = timezone.now() + timedelta(minutes=5)
    subscribe(
        org, package("growth", ["accounting"]), SubscriptionStatus.PAST_DUE, grace_until=grace
    )
    before = resolve_entitlements(org, grace - timedelta(seconds=1))
    assert before.mode == FULL and before.valid_until == grace
    after = resolve_entitlements(org, grace)  # the status is still past_due
    assert (after.mode, after.reason) == (READ_ONLY, "payment_failed")


@pytest.mark.parametrize(
    ("org_status", "mode", "reason"),
    [
        (OrganisationStatus.TRIAL, FULL, "no_subscription"),
        (OrganisationStatus.ACTIVE, FULL, "no_subscription"),
        (OrganisationStatus.DEMO, FULL, "demo"),
        (OrganisationStatus.READ_ONLY, READ_ONLY, "read_only"),
        (OrganisationStatus.CANCELLED, READ_ONLY, "cancelled"),
    ],
)
def test_organisation_without_a_subscription(org_status: str, mode: str, reason: str) -> None:
    organisation = Organisation.objects.create(name="New Org", status=org_status)
    answer = resolve_entitlements(organisation)
    assert (answer.mode, answer.reason, answer.status, answer.package) == (mode, reason, None, None)
    active = set(Product.objects.filter(status=ProductStatus.ACTIVE).values_list("code", flat=True))
    assert answer.products == active  # self sign-up before choosing a package: full trial


def test_no_organisation_resolves_to_nothing() -> None:
    answer = resolve_entitlements(None)
    assert (answer.mode, answer.reason) == (NONE, "no_organisation")
    assert answer.features == frozenset() and answer.products == frozenset()
    assert not Engine().allows(None, ACCOUNTING_READ)
    assert Engine().allows(None, CORE)


def test_trial_and_demo_packages_come_from_settings(org: Organisation, settings: Any) -> None:
    package("starter", ["accounting"])
    package("demo_pack", ["accounting", "payroll"])
    settings.NUMO9_TRIAL_PACKAGE = "starter"
    settings.NUMO9_DEMO_PACKAGE = "demo_pack"
    assert resolve_entitlements(org).products == {"accounting", "practice", "portal"}
    trialing = subscribe(org, None, SubscriptionStatus.TRIALING)
    answer = resolve_entitlements(org)
    assert (answer.package, answer.reason) == ("starter", "trialing")
    trialing.status = SubscriptionStatus.CANCELLED
    trialing.save()
    subscribe(org, None, SubscriptionStatus.DEMO)
    demo = resolve_entitlements(org)
    assert demo.package == "demo_pack" and "payroll" in demo.products
    settings.NUMO9_DEMO_PACKAGE = "unknown"
    assert resolve_entitlements(org).products >= {"accounting", "tax", "payroll"}  # every active


def test_founding_gets_every_active_product_including_later_ones(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]), founding=True)
    answer = resolve_entitlements(org)
    assert answer.founding
    assert answer.products >= {"accounting", "tax", "payroll", "inventory", "finance"}
    assert "app.commerce" not in answer.products  # planned: not shipped yet
    commerce = Product.objects.get(code="app.commerce")
    commerce.status = ProductStatus.ACTIVE  # ships later
    commerce.save()
    assert "app.commerce" in resolve_entitlements(org).products


def test_subscription_override_products(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]), override={"products": ["payroll"]})
    answer = resolve_entitlements(org)
    assert answer.allows(PAYROLL_WRITE)


def test_platform_override_grants_a_product_until_it_expires(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]))
    item = grant(org, "payroll", days=3)
    answer = resolve_entitlements(org)
    assert answer.allows(PAYROLL_WRITE)
    assert answer.valid_until == item.expires_at  # the cache never keeps it past the expiry
    later = resolve_entitlements(org, item.expires_at + timedelta(seconds=1))
    assert not later.allows(PAYROLL_WRITE)
    assert later.allows(PAYROLL_READ)  # entitled once: read retention


def test_planned_products_are_never_entitled(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]), override={"products": ["app.bank"]})
    assert "app.bank" not in resolve_entitlements(org).products


def test_retired_product_in_a_package_stays_entitled(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting", "inventory"]))
    inventory = Product.objects.get(code="inventory")
    inventory.status = ProductStatus.RETIRED
    inventory.save()
    assert "inventory" in resolve_entitlements(org).products


def test_answer_round_trips_through_the_cache_form(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]), SubscriptionStatus.CANCELLED)
    answer = resolve_entitlements(org)
    assert Entitlements.from_dict(answer.as_dict()) == answer


def test_practice_users_never_change_the_answer(org: Organisation) -> None:
    # The engine takes the organisation only: an accountant acting in it gets the same answer.
    import inspect

    assert list(inspect.signature(resolve_entitlements).parameters) == [
        "organisation",
        "now",
        "record",
    ]


# ---- T05: read retention ------------------------------------------------------------------------


def test_after_a_downgrade_payroll_read_stays_write_goes(org: Organisation) -> None:
    complete = package("complete", ["accounting", "payroll"])
    starter = package("starter", ["accounting"])
    item = subscribe(org, complete)
    first = resolve_entitlements(org)
    assert first.allows(PAYROLL_READ) and first.allows(PAYROLL_WRITE)
    assert set(
        OrgProductHistory._base_manager.filter(organisation=org).values_list(
            "product__code", flat=True
        )
    ) == {"accounting", "payroll", "practice", "portal"}

    item.package = starter  # downgrade
    item.save()
    after = resolve_entitlements(org)
    assert after.allows(PAYROLL_READ) is True
    assert after.allows(PAYROLL_WRITE) is False
    assert after.read_products == {"payroll"}
    assert "payroll" not in after.products
    assert after.allows(ACCOUNTING_WRITE)


def test_history_keeps_first_and_moves_last_seen(org: Organisation) -> None:
    subscribe(org, package("starter", ["accounting"]))
    t1 = timezone.now()
    resolve_entitlements(org, t1)
    t2 = t1 + timedelta(days=1)
    resolve_entitlements(org, t2)
    row = OrgProductHistory._base_manager.get(organisation=org, product__code="accounting")
    assert (row.first_entitled_at, row.last_entitled_at) == (t1, t2)


def test_read_only_mode_does_not_add_history(org: Organisation) -> None:
    subscribe(org, package("complete", ["accounting", "payroll"]), SubscriptionStatus.CANCELLED)
    answer = resolve_entitlements(org)
    assert answer.allows(PAYROLL_READ) and not answer.allows(PAYROLL_WRITE)
    assert not OrgProductHistory._base_manager.filter(organisation=org).exists()


def test_history_is_per_organisation(org: Organisation) -> None:
    subscribe(org, package("complete", ["accounting", "payroll"]))
    resolve_entitlements(org)
    other = Organisation.objects.create(name="Birch Ltd.")
    subscribe(other, package("starter", ["accounting"]))
    assert not resolve_entitlements(other).allows(PAYROLL_READ)

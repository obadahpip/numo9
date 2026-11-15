"""Shared helpers for the entitlement tests (U-03): packages, subscriptions, Payroll keys."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.utils import timezone

from numo9.catalogue.models import FeatureKey, Product
from numo9.entitlements.models import EntitlementOverride, Subscription, SubscriptionStatus
from numo9.packages.models import Package, PackageProduct, PackageStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

#: Payroll ships its keys in Phase 3; the tests add two so Payroll has something to gate.
PAYROLL_KEYS = ("payroll.pay_runs.read", "payroll.pay_runs.write")


def payroll_keys() -> list[FeatureKey]:
    payroll = Product.objects.get(code="payroll")
    return [
        FeatureKey.objects.get_or_create(key=key, defaults={"product": payroll})[0]
        for key in PAYROLL_KEYS
    ]


def package(
    code: str, products: list[str], name: str | None = None, status: str = PackageStatus.ACTIVE
) -> Package:
    created = Package.objects.create(code=code, name_i18n={"en-CA": name or code.title()})
    for product in products:
        PackageProduct.objects.create(package=created, product=Product.objects.get(code=product))
    if status != PackageStatus.DRAFT:
        created.status = PackageStatus.ACTIVE
        created.save()
    if status == PackageStatus.RETIRED:
        created.status = status
        created.save()
    return created


def subscribe(
    organisation: Organisation,
    plan: Package | None,
    status: str = SubscriptionStatus.ACTIVE,
    **fields: Any,
) -> Subscription:
    if status == SubscriptionStatus.PAST_DUE:
        fields.setdefault("grace_until", timezone.now() + timedelta(days=7))
    with org_context(organisation):
        item = Subscription(organisation=organisation, package=plan, status=status, **fields)
        item.save()
    return item


def grant(organisation: Organisation, product: str, days: int = 14, **fields: Any) -> Any:
    with org_context(organisation):
        item = EntitlementOverride(
            organisation=organisation,
            product=Product.objects.get(code=product),
            expires_at=timezone.now() + timedelta(days=days),
            reason=fields.pop("reason", "Prospect trial of the product"),
            **fields,
        )
        item.save()
    return item

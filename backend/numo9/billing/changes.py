"""Changing the package (U-04-T10): upgrade now with proration, downgrade at the period end.

``preview(organisation, package_code, interval)`` → ``ChangePreview`` — what changing would cost:

- **upgrade** (the new price per month is higher, or monthly → annual): applies **now**; the
  amount charged today is Stripe's own figure — the preview invoice for the subscription item
  moved to the new price at ``proration_date`` (``invoices.create_preview``, the former
  ``invoices.upcoming``): unused time of the current price credited, the new price charged pro
  rata. "You'll be charged $X today";
- **downgrade** (lower per month, or annual → monthly): applies at the **end of the paid
  period**; nothing is charged today and the next renewal is billed at the new price;
- the same package and interval → nothing to change (``billing.no_change``).

``change(organisation, package_code, interval, proration_date)`` — an upgrade moves the Stripe
subscription item to the new price with ``proration_behavior=always_invoice`` and the **same
proration date as the preview**, so the amount charged equals the amount shown; the local package
follows from the ``customer.subscription.updated`` webhook (U-04-T07). A downgrade records a
``ScheduledChange`` (replacing a pending one); the platform job ``numo9.billing.apply_changes``
(with the dunning beat) moves the subscription to the new price without proration in the last hour
of the period, so the renewal invoice uses it. Choosing an upgrade cancels a pending downgrade.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from numo9.entitlements.models import Subscription, SubscriptionStatus
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.jobs.queues import DEFAULT
from numo9.jobs.runtime import platform_job
from numo9.packages.models import BillingInterval, Package, PackagePrice, PackageStatus
from numo9.packages.prices import PriceNotFound, price_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .customers import locked_subscription
from .gateway import BillingGateway, get_gateway
from .models import ScheduledChange

#: Downgrades are moved to the new price this long before the period ends.
APPLY_BEFORE = dt.timedelta(hours=1)


@dataclass(frozen=True)
class ChangePreview:
    kind: str  # "upgrade" | "downgrade"
    package: str
    interval: str
    amount_cents: int  # the new price
    charged_today_cents: int
    currency: str
    effective_at: dt.datetime
    proration_date: int


def _price(package_code: str, interval: str) -> PackagePrice:
    if interval not in BillingInterval.values:
        raise ValueError(interval)
    package = Package.objects.filter(code=package_code, status=PackageStatus.ACTIVE).first()
    if package is None:
        raise api_error(errors.BILLING_PACKAGE_UNKNOWN, package=package_code)
    try:
        price = price_for(package, interval, timezone.localdate())
    except PriceNotFound:
        raise api_error(errors.BILLING_PRICE_NOT_READY, package=package.name()) from None
    if not price.stripe_price_id:
        raise api_error(errors.BILLING_PRICE_NOT_READY, package=package.name())
    return price


def per_month(price: PackagePrice) -> Decimal:
    months = 12 if price.interval == BillingInterval.YEAR else 1
    return Decimal(price.amount_cents) / months


def _current_price(subscription: Subscription) -> PackagePrice | None:
    if subscription.package is None:
        return None
    try:
        return price_for(subscription.package, subscription.interval, timezone.localdate())
    except PriceNotFound:
        return None


def _paying(subscription: Subscription) -> None:
    if not subscription.stripe_subscription_id or subscription.status not in (
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
    ):
        raise api_error(errors.BILLING_NOT_PAYING)


def _kind(current: PackagePrice | None, new: PackagePrice) -> str:
    if current is None:
        return "upgrade"
    if current.package_id == new.package_id and current.interval == new.interval:
        raise api_error(errors.BILLING_NO_CHANGE)
    if per_month(new) > per_month(current) or (
        per_month(new) == per_month(current) and new.interval == BillingInterval.YEAR
    ):
        return "upgrade"
    if current.interval == BillingInterval.MONTH and new.interval == BillingInterval.YEAR:
        return "upgrade"
    return "downgrade"


def _item(gateway: BillingGateway, subscription: Subscription) -> str:
    remote = gateway.retrieve_subscription(subscription.stripe_subscription_id)
    items = ((remote.get("items") or {}).get("data")) or []
    if not items:
        raise api_error(errors.BILLING_NOT_PAYING)
    return str(items[0]["id"])


def preview(
    organisation: Organisation,
    package_code: str,
    interval: str,
    gateway: BillingGateway | None = None,
) -> ChangePreview:
    gateway = gateway or get_gateway()
    new = _price(package_code, interval)
    with org_context(organisation), transaction.atomic():
        subscription = locked_subscription(organisation)
        _paying(subscription)
        kind = _kind(_current_price(subscription), new)
        now = int(timezone.now().timestamp())
        if kind == "upgrade":
            invoice = gateway.preview_change(
                customer=subscription.stripe_customer_id,
                subscription=subscription.stripe_subscription_id,
                item=_item(gateway, subscription),
                price=new.stripe_price_id,
                proration_date=now,
            )
            charged = int(invoice.get("amount_due") or 0)
            effective = timezone.now()
        else:
            charged = 0
            effective = subscription.current_period_end or timezone.now()
        return ChangePreview(
            kind=kind,
            package=new.package.code,
            interval=interval,
            amount_cents=new.amount_cents,
            charged_today_cents=charged,
            currency=new.currency,
            effective_at=effective,
            proration_date=now,
        )


def change(
    organisation: Organisation,
    package_code: str,
    interval: str,
    proration_date: int | None = None,
    gateway: BillingGateway | None = None,
) -> ChangePreview:
    gateway = gateway or get_gateway()
    new = _price(package_code, interval)
    with org_context(organisation), transaction.atomic():
        subscription = locked_subscription(organisation)
        _paying(subscription)
        kind = _kind(_current_price(subscription), new)
        now = timezone.now()
        pending = ScheduledChange.objects.filter(
            subscription=subscription, applied_at__isnull=True, cancelled_at__isnull=True
        )
        pending.update(cancelled_at=now)
        when = proration_date or int(now.timestamp())
        if kind == "upgrade":
            gateway.change_price(
                subscription=subscription.stripe_subscription_id,
                item=_item(gateway, subscription),
                price=new.stripe_price_id,
                proration_behavior="always_invoice",
                proration_date=when,
                idempotency_key=f"numo9-change-{subscription.public_id}-{new.public_id}-{when}",
            )
            effective = now
        else:
            effective = subscription.current_period_end or now
            ScheduledChange.objects.create(
                organisation=organisation,
                subscription=subscription,
                package=new.package,
                interval=interval,
                effective_at=effective,
            )
        return ChangePreview(
            kind=kind,
            package=new.package.code,
            interval=interval,
            amount_cents=new.amount_cents,
            charged_today_cents=0,
            currency=new.currency,
            effective_at=effective,
            proration_date=when,
        )


def apply_due_changes(now: dt.datetime | None = None, gateway: BillingGateway | None = None) -> int:
    """Move subscriptions with a downgrade due (last hour of the period) to the new price."""
    now = now or timezone.now()
    due = ScheduledChange._base_manager.filter(
        applied_at__isnull=True, cancelled_at__isnull=True, effective_at__lte=now + APPLY_BEFORE
    ).select_related("subscription", "package", "organisation")
    applied = 0
    for scheduled in due:
        gateway = gateway or get_gateway()
        with org_context(scheduled.organisation), transaction.atomic():
            row = ScheduledChange.objects.select_for_update().get(pk=scheduled.pk)
            if row.applied_at or row.cancelled_at:
                continue
            subscription = row.subscription
            price = price_for(row.package, row.interval, timezone.localdate())
            gateway.change_price(
                subscription=subscription.stripe_subscription_id,
                item=_item(gateway, subscription),
                price=price.stripe_price_id,
                proration_behavior="none",
                proration_date=None,
                idempotency_key=f"numo9-downgrade-{row.public_id}",
            )
            row.applied_at = now
            row.save(update_fields=["applied_at", "updated_at"])
            applied += 1
    return applied


def renewal_price(subscription: Subscription) -> PackagePrice | None:
    """The price version the subscription renews at: the one in force on its renewal day."""
    if subscription.package is None or subscription.current_period_end is None:
        return None
    try:
        return price_for(
            subscription.package,
            subscription.interval,
            timezone.localdate(subscription.current_period_end),
        )
    except PriceNotFound:
        return None


def apply_renewal_prices(
    now: dt.datetime | None = None, gateway: BillingGateway | None = None
) -> int:
    """Move subscriptions renewing within the hour to the price in force on their renewal day.

    A future-dated price (U-02-T04) never touches a subscription before its first renewal on or
    after the price's start: a renewal before that day keeps the old Stripe price (U-02-T14).
    A pending downgrade takes precedence (``apply_due_changes``).
    """
    now = now or timezone.now()
    rows = Subscription._base_manager.filter(
        status__in=(SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE),
        deleted_at__isnull=True,
        current_period_end__gt=now,
        current_period_end__lte=now + APPLY_BEFORE,
        cancel_at_period_end=False,
    ).exclude(stripe_subscription_id="")
    moved = 0
    for subscription in rows.select_related("package", "organisation"):
        if ScheduledChange._base_manager.filter(
            subscription=subscription, applied_at__isnull=True, cancelled_at__isnull=True
        ).exists():
            continue
        price = renewal_price(subscription)
        if price is None or not price.stripe_price_id:
            continue
        gateway = gateway or get_gateway()
        remote = gateway.retrieve_subscription(subscription.stripe_subscription_id)
        items = ((remote.get("items") or {}).get("data")) or []
        if not items or (items[0].get("price") or {}).get("id") == price.stripe_price_id:
            continue
        gateway.change_price(
            subscription=subscription.stripe_subscription_id,
            item=str(items[0]["id"]),
            price=price.stripe_price_id,
            proration_behavior="none",
            proration_date=None,
            idempotency_key=f"numo9-renewal-{subscription.public_id}-{price.public_id}",
        )
        moved += 1
    return moved


@platform_job(name="numo9.billing.apply_changes", queue=DEFAULT)
def apply_changes_job() -> dict[str, int]:
    return {"applied": apply_due_changes(), "renewal_prices": apply_renewal_prices()}

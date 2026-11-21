"""Subscription events → the local subscription (U-04-T07).

Handlers of ``checkout.session.completed`` and ``customer.subscription.created`` / ``.updated`` /
``.deleted``. Stripe's subscription is the source of truth for billing; Numo9 keeps the state its
entitlements need (``Subscription``: status, package, interval, period end, cancellation, Stripe
ids). The **state table** (Stripe status → local status):

==================  =================  ==========================================================
Stripe              Numo9              Why
==================  =================  ==========================================================
active, trialing    active             paid (Stripe trials aren't used: the trial is Numo9's)
past_due            past_due           a renewal failed: full access until ``grace_until``
                                       (failure + 7 days, kept if already set; dunning U-04-T09)
unpaid, paused      read_only          retries exhausted: read and export only
canceled            cancelled          ended (deleted event, or ended at period end)
incomplete,         unchanged          first payment not settled yet — a PAD debit takes 3–5
incomplete_expired                     business days; the organisation keeps its access
==================  =================  ==========================================================

The local subscription is found by ``stripe_subscription_id``, else by the customer (the
organisation's current subscription), else by the organisation named in the metadata
(``numo9_org``) — a ``checkout.session.completed`` may arrive before or after the subscription
events, and before the owner's browser comes back. The package comes from the subscription's
price (``PackagePrice.stripe_price_id``), else from the metadata. The organisation is recorded on
the event.
"""

from __future__ import annotations

import datetime as dt
from datetime import timedelta
from typing import Any

from numo9.entitlements.models import (
    PaymentMethodType,
    StatusReason,
    Subscription,
    SubscriptionStatus,
    current_subscription,
)
from numo9.packages.models import BillingInterval, Package, PackagePrice
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .customers import METADATA_KEY
from .models import StripeEvent
from .processing import register_handler

#: Grace period after a failed renewal (U-04-T09: reminders day 0, 3, 5, 7; read-only at its end).
GRACE = timedelta(days=7)

#: Stripe subscription status → local status (None = leave the local status as it is).
STATE_TABLE: dict[str, str | None] = {
    "active": SubscriptionStatus.ACTIVE,
    "trialing": SubscriptionStatus.ACTIVE,
    "past_due": SubscriptionStatus.PAST_DUE,
    "unpaid": SubscriptionStatus.READ_ONLY,
    "paused": SubscriptionStatus.READ_ONLY,
    "canceled": SubscriptionStatus.CANCELLED,
    "incomplete": None,
    "incomplete_expired": None,
}


#: Tie-break when two events carry the same ``created`` second: the further-along state wins.
PRECEDENCE: dict[str, int] = {
    SubscriptionStatus.TRIALING: 0,
    SubscriptionStatus.ACTIVE: 1,
    SubscriptionStatus.PAST_DUE: 2,
    SubscriptionStatus.READ_ONLY: 3,
    SubscriptionStatus.CANCELLED: 4,
}


def is_newer(subscription: Subscription, at: dt.datetime, target: str | None = None) -> bool:
    """Should an event created ``at`` change the subscription (U-04-T15)?

    Events are applied by Stripe's ``created`` time, not by arrival: an event older than the last
    one applied changes nothing; on the same second the further-along status wins
    (``PRECEDENCE``: cancelled > read-only > past due > active).
    """
    last = subscription.stripe_event_created
    if last is None or at > last:
        return True
    if at < last:
        return False
    if target is None:
        return True
    return PRECEDENCE.get(target, 0) >= PRECEDENCE.get(subscription.status, 0)


def earlier_failure(subscription: Subscription, at: dt.datetime) -> None:
    """A late past-due signal of the same episode: the grace runs from the first failure."""
    if subscription.status == SubscriptionStatus.PAST_DUE and subscription.grace_until is not None:
        subscription.grace_until = min(subscription.grace_until, at + GRACE)


def stamp(subscription: Subscription, at: dt.datetime) -> None:
    last = subscription.stripe_event_created
    subscription.stripe_event_created = at if last is None or at > last else last


class UnknownSubscription(LookupError):
    """No organisation matches the event's subscription, customer or metadata."""


def _timestamp(value: Any) -> dt.datetime | None:
    if value in (None, ""):
        return None
    return dt.datetime.fromtimestamp(int(value), tz=dt.UTC)


def _metadata(obj: dict[str, Any]) -> dict[str, str]:
    data = obj.get("metadata") or {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _item(obj: dict[str, Any]) -> dict[str, Any]:
    items = ((obj.get("items") or {}).get("data")) or []
    return items[0] if items else {}


def find_subscription(
    *, subscription_id: str = "", customer: str = "", organisation_id: str = ""
) -> Subscription:
    """The local subscription an event is about, under a row lock."""
    rows = Subscription._base_manager.select_for_update().filter(deleted_at__isnull=True)
    if subscription_id:
        found = rows.filter(stripe_subscription_id=subscription_id).first()
        if found is not None:
            return found
    organisation: Organisation | None = None
    if customer:
        holder = rows.filter(stripe_customer_id=customer).order_by("-created_at").first()
        organisation = holder.organisation if holder is not None else None
    if organisation is None and organisation_id:
        organisation = Organisation.objects.filter(public_id=organisation_id).first()
    if organisation is None:
        raise UnknownSubscription(subscription_id or customer or organisation_id)
    with org_context(organisation):
        current = current_subscription(organisation)
    if current is None:
        raise UnknownSubscription(str(organisation.public_id))
    locked: Subscription = rows.get(pk=current.pk)
    return locked


def _package_of(price_id: str, fallback_code: str) -> Package | None:
    price = PackagePrice.objects.filter(stripe_price_id=price_id).select_related("package").first()
    if price is not None:
        return price.package
    if fallback_code:
        return Package.objects.filter(code=fallback_code).first()
    return None


def apply_status(subscription: Subscription, stripe_status: str, at: dt.datetime) -> None:
    """Move the local status by the state table (fields only; the caller saves). A trial (running
    or ended unpaid) that becomes active is a conversion (U-05-T09)."""
    target = STATE_TABLE.get(stripe_status)
    if target is None or target == subscription.status:
        return
    from numo9.entitlements.trials import is_trial, trial_converted
    from numo9.founding import services as founding

    converting = target == SubscriptionStatus.ACTIVE and is_trial(subscription)
    returning = target == SubscriptionStatus.ACTIVE and (
        subscription.status == SubscriptionStatus.CANCELLED
        or subscription.status_reason == StatusReason.CANCELLED
    )
    subscription.status = target
    if target == SubscriptionStatus.ACTIVE:
        subscription.grace_until, subscription.status_reason = None, ""
    elif target == SubscriptionStatus.PAST_DUE:
        subscription.grace_until = subscription.grace_until or at + GRACE
        subscription.status_reason = StatusReason.PAYMENT_FAILED
    elif target == SubscriptionStatus.READ_ONLY:
        subscription.status_reason = StatusReason.PAYMENT_FAILED
    elif target == SubscriptionStatus.CANCELLED:
        subscription.status_reason = StatusReason.CANCELLED
        subscription.cancel_at_period_end = False
        subscription.grace_until = None
    if converting:
        trial_converted(subscription, at)
    # Founding churn rules (U-08-T06).
    if target == SubscriptionStatus.CANCELLED:
        founding.on_cancel(subscription.organisation, at)
    elif returning:
        founding.on_return(subscription.organisation, at)
    if target == SubscriptionStatus.CANCELLED or returning:
        # The caller saves this instance: carry the flag the rules just set.
        subscription.founding = founding.founding_slot_of(subscription.organisation) is not None


def _save(subscription: Subscription, event: StripeEvent) -> Subscription:
    subscription.save()
    StripeEvent.objects.filter(pk=event.pk).update(organisation_id=subscription.organisation_id)
    return subscription


@register_handler(
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
)
def on_subscription(event: StripeEvent) -> Subscription:
    obj = event.data_object
    metadata = _metadata(obj)
    subscription = find_subscription(
        subscription_id=str(obj.get("id") or ""),
        customer=str(obj.get("customer") or ""),
        organisation_id=metadata.get(METADATA_KEY, ""),
    )
    stripe_status = "canceled" if event.type.endswith(".deleted") else str(obj.get("status"))
    # The subscription's own fields (package, interval, period, cancellation) follow the newest
    # subscription event; its status follows the newest billing event of any kind (U-04-T15).
    if not _newer_subscription_event(subscription, event):
        _apply_fields(subscription, obj, metadata)
    if is_newer(subscription, event.stripe_created, STATE_TABLE.get(stripe_status)):
        apply_status(subscription, stripe_status, event.stripe_created)
        stamp(subscription, event.stripe_created)
    elif STATE_TABLE.get(stripe_status) == SubscriptionStatus.PAST_DUE:
        earlier_failure(subscription, event.stripe_created)
    return _save(subscription, event)


def _newer_subscription_event(subscription: Subscription, event: StripeEvent) -> bool:
    """A later ``customer.subscription.*`` event of this organisation was already applied."""
    return (
        StripeEvent.objects.filter(
            organisation_id=subscription.organisation_id,
            type__startswith="customer.subscription.",
            processed_at__isnull=False,
            stripe_created__gt=event.stripe_created,
        )
        .exclude(pk=event.pk)
        .exists()
    )


def _apply_fields(
    subscription: Subscription, obj: dict[str, Any], metadata: dict[str, str]
) -> None:
    item = _item(obj)
    price = item.get("price") or {}
    subscription.stripe_subscription_id = str(obj.get("id") or "")
    subscription.stripe_customer_id = str(obj.get("customer") or subscription.stripe_customer_id)
    package = _package_of(str(price.get("id") or ""), metadata.get("numo9_package", ""))
    if package is not None:
        subscription.package = package
    interval = (price.get("recurring") or {}).get("interval") or metadata.get("numo9_interval")
    if interval in BillingInterval.values:
        subscription.interval = interval
    period_end = _timestamp(item.get("current_period_end") or obj.get("current_period_end"))
    if period_end is not None:
        subscription.current_period_end = period_end
    subscription.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
    methods = (obj.get("payment_settings") or {}).get("payment_method_types") or []
    if len(methods) == 1 and methods[0] in PaymentMethodType.values:
        subscription.payment_method_type = methods[0]


@register_handler("checkout.session.completed")
def on_checkout_completed(event: StripeEvent) -> Subscription | None:
    obj = event.data_object
    if obj.get("mode") != "subscription":
        return None
    metadata = _metadata(obj)
    subscription = find_subscription(
        subscription_id=str(obj.get("subscription") or ""),
        customer=str(obj.get("customer") or ""),
        organisation_id=metadata.get(METADATA_KEY, "") or str(obj.get("client_reference_id") or ""),
    )
    subscription.stripe_subscription_id = str(obj.get("subscription") or "")
    subscription.stripe_customer_id = str(obj.get("customer") or subscription.stripe_customer_id)
    package = Package.objects.filter(code=metadata.get("numo9_package", "")).first()
    if package is not None and subscription.package_id is None:
        subscription.package = package
    if metadata.get("numo9_interval") in BillingInterval.values:
        subscription.interval = metadata["numo9_interval"]
    methods = obj.get("payment_method_types") or []
    if len(methods) == 1 and methods[0] in PaymentMethodType.values:
        subscription.payment_method_type = methods[0]
    # Paid by card, or a PAD debit still processing ("unpaid" for 3–5 days): access continues —
    # unless a newer subscription event already decided the state (out of order, U-04-T15).
    if is_newer(subscription, event.stripe_created, SubscriptionStatus.ACTIVE) and (
        subscription.status in (SubscriptionStatus.TRIALING, SubscriptionStatus.CANCELLED)
        or obj.get("payment_status") == "paid"
    ):
        apply_status(subscription, "active", event.stripe_created)
        stamp(subscription, event.stripe_created)
    return _save(subscription, event)

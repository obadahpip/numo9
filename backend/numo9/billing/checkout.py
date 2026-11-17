"""Checkout (U-04-T05): start paying for a package with Stripe Checkout.

``start_checkout(organisation, package_code, interval, methods)``:

1. the package must be sold (active) and have a price for the interval in force today that the
   price sync already created at Stripe (``stripe_price_id``) — else 409
   ``billing.price_not_ready``;
2. an organisation already paying through Stripe changes its package instead (U-04-T10) — 409
   ``billing.already_subscribed``;
3. its Stripe customer (``ensure_customer``, U-04-T04);
4. a Checkout session in subscription mode for that price, card and/or pre-authorised debit
   (ACSS Debit, business mandate), metadata naming the organisation, the package and the
   interval, coming back to the billing page (``?checkout=success`` / ``cancelled``).

The subscription itself is recorded when Stripe's webhooks arrive (U-04-T07), never from the
redirect: the owner may close the tab, and the webhook may come first.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.packages.models import BillingInterval, Package, PackageStatus
from numo9.packages.prices import PriceNotFound, price_for
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .customers import METADATA_KEY, ensure_customer
from .gateway import CheckoutSession, get_gateway

METHODS = ("card", "acss_debit")


@dataclass(frozen=True)
class CheckoutStarted:
    session: CheckoutSession
    package: str
    interval: str
    amount_cents: int


def billing_page(organisation: Organisation, query: str = "") -> str:
    base = f"{settings.FRONTEND_URL}/o/{organisation.public_id}/settings/subscription"
    return f"{base}?{query}" if query else base


def start_checkout(
    organisation: Organisation,
    package_code: str,
    interval: str,
    methods: list[str] | None = None,
    request_key: str = "",
) -> CheckoutStarted:
    from numo9.entitlements.models import current_subscription

    gateway = get_gateway()
    if interval not in BillingInterval.values:
        raise ValueError(interval)
    package = Package.objects.filter(code=package_code, status=PackageStatus.ACTIVE).first()
    if package is None:
        raise api_error(errors.BILLING_PACKAGE_UNKNOWN, package=package_code)
    try:
        price = price_for(package, interval, timezone.localdate())
    except PriceNotFound:
        price = None
    if price is None or not price.stripe_price_id:
        raise api_error(errors.BILLING_PRICE_NOT_READY, package=package.name())
    with org_context(organisation):
        current = current_subscription(organisation)
    if current is not None and current.stripe_subscription_id:
        raise api_error(errors.BILLING_ALREADY_SUBSCRIBED)
    customer = ensure_customer(organisation, gateway)
    chosen = [m for m in (methods or list(METHODS)) if m in METHODS] or list(METHODS)
    metadata = {
        METADATA_KEY: str(organisation.public_id),
        "numo9_package": package.code,
        "numo9_interval": interval,
    }
    session = gateway.create_checkout_session(
        customer=customer,
        price=price.stripe_price_id,
        payment_method_types=chosen,
        success_url=billing_page(organisation, "checkout=success&session_id={CHECKOUT_SESSION_ID}"),
        cancel_url=billing_page(organisation, "checkout=cancelled"),
        metadata=metadata,
        idempotency_key=f"numo9-checkout-{organisation.public_id}-{request_key or uuid.uuid4()}",
    )
    return CheckoutStarted(session, package.code, interval, price.amount_cents)

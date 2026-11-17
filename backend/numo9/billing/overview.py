"""The billing page's data (U-04-T12): ``overview(organisation)`` and the payment-method portal.

One answer for the page: the current subscription (status, package, interval, price, next charge,
period end, cancellation, payment method, grace end), a pending downgrade, the packages offered
with their monthly and annual prices (the comparison), the Numo9 invoices (newest first, PDF
links) and the latest export. ``portal_url`` opens Stripe's customer portal to update the card or
the PAD details (the details never reach Numo9).
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone, translation

from numo9.entitlements.models import current_subscription
from numo9.packages.models import Package
from numo9.packages.prices import current_prices
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

from .checkout import billing_page
from .customers import ensure_customer
from .gateway import billing_enabled, get_gateway
from .models import PlatformInvoice, ScheduledChange


def _prices(package: Package) -> dict[str, int]:
    return {
        interval: p.amount_cents
        for interval, p in current_prices(package, timezone.localdate()).items()
    }


def overview(organisation: Organisation) -> dict[str, Any]:
    locale = translation.get_language() or "en-CA"
    with org_context(organisation):
        subscription = current_subscription(organisation)
        invoices = list(PlatformInvoice.objects.order_by("-issued_at", "-pk")[:24])
        pending = (
            ScheduledChange.objects.filter(applied_at=None, cancelled_at=None)
            .select_related("package")
            .first()
        )
    current: dict[str, Any] | None = None
    if subscription is not None:
        package = subscription.package
        prices = _prices(package) if package else {}
        current = {
            "status": subscription.status,
            "package": {"code": package.code, "name": package.name(locale)} if package else None,
            "interval": subscription.interval,
            "amount_cents": prices.get(subscription.interval),
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "payment_method_type": subscription.payment_method_type,
            "grace_until": subscription.grace_until,
            "paying": bool(subscription.stripe_subscription_id),
        }
    offered = Package.objects.offered().order_by("sort", "code")
    return {
        "billing_available": billing_enabled(),
        "subscription": current,
        "pending_change": {
            "package": {"code": pending.package.code, "name": pending.package.name(locale)},
            "interval": pending.interval,
            "effective_at": pending.effective_at,
        }
        if pending is not None
        else None,
        "packages": [
            {"code": p.code, "name": p.name(locale), "prices": _prices(p)} for p in offered
        ],
        "invoices": [
            {
                "id": str(i.public_id),
                "number": i.number,
                "status": i.status,
                "issued_at": i.issued_at,
                "total_cents": i.total_cents,
                "currency": i.currency,
                "pdf_url": i.pdf_url,
                "hosted_url": i.hosted_url,
            }
            for i in invoices
        ],
    }


def portal_url(organisation: Organisation) -> str:
    gateway = get_gateway()
    customer = ensure_customer(organisation, gateway)
    return gateway.create_portal_session(customer=customer, return_url=billing_page(organisation))

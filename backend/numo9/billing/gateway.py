"""The Stripe calls billing makes (U-04), behind one interface.

``get_gateway()`` returns ``settings.NUMO9_BILLING_GATEWAY`` (a dotted class path — the tests'
fake), else the Stripe API when ``STRIPE_SECRET_KEY`` is set (``STRIPE_API_BASE`` → stripe-mock in
CI), else raises ``BillingUnavailable`` (503 ``billing.unavailable``): billing is off.

Every call that creates something carries an idempotency key derived from Numo9 ids, so a retried
request never creates a second customer, session or change.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from django.conf import settings
from django.utils.module_loading import import_string

from numo9.i18n import errors
from numo9.i18n.errors import CatalogueError


class BillingUnavailable(CatalogueError):
    def __init__(self) -> None:
        super().__init__(errors.BILLING_UNAVAILABLE)


class SignatureInvalid(ValueError):
    """The webhook's ``Stripe-Signature`` doesn't match the payload (or is too old)."""


@dataclass(frozen=True)
class CheckoutSession:
    id: str
    url: str


class BillingGateway(Protocol):
    def create_customer(
        self, *, name: str, email: str, metadata: dict[str, str], idempotency_key: str
    ) -> str:
        """Create a Stripe customer; return its id (``cus_…``)."""
        ...

    def create_checkout_session(
        self,
        *,
        customer: str,
        price: str,
        payment_method_types: list[str],
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],
        idempotency_key: str,
    ) -> CheckoutSession:
        """A Checkout session in subscription mode for one price."""
        ...

    def construct_event(self, payload: bytes, signature: str, secret: str) -> dict[str, Any]:
        """Verify the signature and return the event; raise ``SignatureInvalid``."""
        ...

    def preview_change(
        self, *, customer: str, subscription: str, item: str, price: str, proration_date: int
    ) -> dict[str, Any]:
        """The upcoming invoice if the subscription item moved to ``price`` now (proration)."""
        ...

    def change_price(
        self,
        *,
        subscription: str,
        item: str,
        price: str,
        proration_behavior: str,
        proration_date: int | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Move the subscription item to ``price``; return the updated subscription."""
        ...

    def set_cancel_at_period_end(
        self, *, subscription: str, cancel: bool, idempotency_key: str
    ) -> dict[str, Any]:
        """Cancel (or keep) the subscription at the end of its period."""
        ...

    def retrieve_subscription(self, subscription: str) -> dict[str, Any]: ...

    def create_portal_session(self, *, customer: str, return_url: str) -> str:
        """A Stripe customer-portal session (update the payment method); return its URL."""
        ...


def _plain(obj: Any) -> dict[str, Any]:
    to_dict = getattr(obj, "to_dict_recursive", None) or getattr(obj, "to_dict", None)
    return dict(to_dict()) if callable(to_dict) else dict(obj)


class StripeBillingApi:
    """The Stripe API through the official client (``stripe`` package)."""

    def __init__(self) -> None:
        import stripe

        options: dict[str, Any] = {}
        if settings.STRIPE_API_BASE:
            options["base_addresses"] = {"api": settings.STRIPE_API_BASE}
        self.stripe = stripe
        self.client = stripe.StripeClient(settings.STRIPE_SECRET_KEY, **options)

    def create_customer(
        self, *, name: str, email: str, metadata: dict[str, str], idempotency_key: str
    ) -> str:
        customer = self.client.v1.customers.create(
            params={"name": name, "email": email, "metadata": metadata},
            options={"idempotency_key": idempotency_key},
        )
        return str(customer.id)

    def create_checkout_session(
        self,
        *,
        customer: str,
        price: str,
        payment_method_types: list[str],
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],
        idempotency_key: str,
    ) -> CheckoutSession:
        params: dict[str, Any] = {
            "mode": "subscription",
            "customer": customer,
            "line_items": [{"price": price, "quantity": 1}],
            "payment_method_types": payment_method_types,
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata,
            "subscription_data": {"metadata": metadata},
            "client_reference_id": metadata.get("numo9_org", ""),
        }
        if "acss_debit" in payment_method_types:
            params["payment_method_options"] = {
                "acss_debit": {
                    "currency": "cad",
                    "mandate_options": {"transaction_type": "business"},
                    "verification_method": "automatic",
                }
            }
        session = self.client.v1.checkout.sessions.create(
            params=params,  # type: ignore[arg-type]
            options={"idempotency_key": idempotency_key},
        )
        return CheckoutSession(id=str(session.id), url=str(session.url or ""))

    def construct_event(self, payload: bytes, signature: str, secret: str) -> dict[str, Any]:
        try:
            event = self.stripe.Webhook.construct_event(payload, signature, secret)
        except (ValueError, self.stripe.SignatureVerificationError) as error:
            raise SignatureInvalid(str(error)) from error
        return _plain(event)

    def preview_change(
        self, *, customer: str, subscription: str, item: str, price: str, proration_date: int
    ) -> dict[str, Any]:
        invoice = self.client.v1.invoices.create_preview(
            params={
                "customer": customer,
                "subscription": subscription,
                "subscription_details": {
                    "items": [{"id": item, "price": price}],
                    "proration_date": proration_date,
                    "proration_behavior": "always_invoice",
                },
            }
        )
        return _plain(invoice)

    def change_price(
        self,
        *,
        subscription: str,
        item: str,
        price: str,
        proration_behavior: str,
        proration_date: int | None,
        idempotency_key: str,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "items": [{"id": item, "price": price}],
            "proration_behavior": proration_behavior,
        }
        if proration_date is not None:
            params["proration_date"] = proration_date
        updated = self.client.v1.subscriptions.update(
            subscription,
            params=params,  # type: ignore[arg-type]
            options={"idempotency_key": idempotency_key},
        )
        return _plain(updated)

    def set_cancel_at_period_end(
        self, *, subscription: str, cancel: bool, idempotency_key: str
    ) -> dict[str, Any]:
        updated = self.client.v1.subscriptions.update(
            subscription,
            params={"cancel_at_period_end": cancel},
            options={"idempotency_key": idempotency_key},
        )
        return _plain(updated)

    def retrieve_subscription(self, subscription: str) -> dict[str, Any]:
        return _plain(self.client.v1.subscriptions.retrieve(subscription))

    def create_portal_session(self, *, customer: str, return_url: str) -> str:
        session = self.client.v1.billing_portal.sessions.create(
            params={"customer": customer, "return_url": return_url}
        )
        return str(session.url)


def billing_enabled() -> bool:
    return bool(getattr(settings, "NUMO9_BILLING_GATEWAY", "")) or bool(
        getattr(settings, "STRIPE_SECRET_KEY", "")
    )


def get_gateway() -> BillingGateway:
    path = getattr(settings, "NUMO9_BILLING_GATEWAY", "")
    if path:
        gateway: BillingGateway = import_string(path)()
        return gateway
    if getattr(settings, "STRIPE_SECRET_KEY", ""):
        return StripeBillingApi()
    raise BillingUnavailable()

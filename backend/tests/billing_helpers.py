"""Shared helpers for the billing tests (U-04): Stripe-shaped events and a fake gateway."""

from __future__ import annotations

import itertools
import time
from typing import Any

_ids = itertools.count(1)


def stripe_event(
    event_type: str, obj: dict[str, Any], *, created: int | None = None, event_id: str = ""
) -> dict[str, Any]:
    """An event as Stripe sends it (only the fields Numo9 reads)."""
    return {
        "id": event_id or f"evt_test_{next(_ids):06d}",
        "object": "event",
        "type": event_type,
        "created": created if created is not None else int(time.time()),
        "livemode": False,
        "data": {"object": obj},
    }


class FakeGateway:
    """A recording stand-in for Stripe (``NUMO9_BILLING_GATEWAY``): state is per test."""

    calls: list[tuple[str, dict[str, Any]]] = []
    customers: dict[str, str] = {}  # idempotency key → customer id
    preview_amount: int = 0
    subscriptions: dict[str, dict[str, Any]] = {}

    @classmethod
    def reset(cls) -> None:
        cls.calls, cls.customers, cls.preview_amount, cls.subscriptions = [], {}, 0, {}

    def _call(self, call: str, **params: Any) -> None:
        type(self).calls.append((call, params))

    def create_customer(
        self, *, name: str, email: str, metadata: dict[str, str], idempotency_key: str
    ) -> str:
        self._call("create_customer", name=name, email=email, metadata=metadata)
        known = type(self).customers
        known.setdefault(idempotency_key, f"cus_test_{len(known) + 1:04d}")
        return known[idempotency_key]

    def create_checkout_session(self, **params: Any) -> Any:
        from numo9.billing.gateway import CheckoutSession

        self._call("create_checkout_session", **params)
        return CheckoutSession(id="cs_test_1", url="https://checkout.stripe.com/c/pay/cs_test_1")

    def construct_event(self, payload: bytes, signature: str, secret: str) -> dict[str, Any]:
        import json

        from numo9.billing.gateway import SignatureInvalid

        if signature != f"t=1,v1=valid-for-{secret}":
            raise SignatureInvalid("No signatures found matching the expected signature")
        return dict(json.loads(payload))

    def preview_change(self, **params: Any) -> dict[str, Any]:
        self._call("preview_change", **params)
        return {"amount_due": type(self).preview_amount, "currency": "cad", "lines": {"data": []}}

    def change_price(self, **params: Any) -> dict[str, Any]:
        self._call("change_price", **params)
        return type(self).subscriptions.get(params["subscription"], {})

    def set_cancel_at_period_end(self, **params: Any) -> dict[str, Any]:
        self._call("set_cancel_at_period_end", **params)
        return type(self).subscriptions.get(params["subscription"], {})

    def retrieve_subscription(self, subscription: str) -> dict[str, Any]:
        return type(self).subscriptions[subscription]

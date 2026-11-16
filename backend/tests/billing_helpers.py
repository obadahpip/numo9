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

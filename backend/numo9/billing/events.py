"""Storing Stripe events once (U-04-T03): ``record_event(event)``.

``record_event`` inserts the event with ``INSERT … ON CONFLICT (event_id) DO NOTHING`` and returns
``(row, created)``: a duplicate ``event_id`` — Stripe re-delivers an event until it gets a 2xx, and
an attacker may replay a captured one — inserts nothing and returns the row already stored, so
the webhook answers 200 without processing it again.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.db import transaction

from .models import StripeEvent


class MalformedEvent(ValueError):
    """Not a Stripe event: no ``evt_`` id, type or created time."""


def _created(value: Any) -> dt.datetime:
    try:
        return dt.datetime.fromtimestamp(int(value), tz=dt.UTC)
    except (TypeError, ValueError, OverflowError) as error:
        raise MalformedEvent("created") from error


def record_event(event: dict[str, Any]) -> tuple[StripeEvent, bool]:
    """Store the event unless its ``event_id`` is already stored; ``(row, created)``."""
    event_id = str(event.get("id") or "")
    event_type = str(event.get("type") or "")
    if not event_id.startswith("evt_") or not event_type:
        raise MalformedEvent("id/type")
    row = StripeEvent(
        event_id=event_id,
        type=event_type,
        payload=event,
        stripe_created=_created(event.get("created")),
        livemode=bool(event.get("livemode", False)),
    )
    with transaction.atomic():
        inserted = StripeEvent.objects.bulk_create([row], ignore_conflicts=True)
        stored = StripeEvent.objects.get(event_id=event_id)
    created = bool(inserted) and stored.public_id == row.public_id
    return stored, created

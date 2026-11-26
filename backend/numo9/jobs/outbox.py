"""The transactional outbox (D-03b-T17): business events for webhooks (W-01) and the mobile app.

    emit(organisation, "invoice.revised", key=f"invoice.revised:{revision.public_id}",
         aggregate=("sales.invoice", str(invoice.public_id)), payload={...})

``emit`` writes an ``OutboxEvent`` **in the caller's transaction** (call it inside the
transaction of the change): the event exists exactly when the change committed. It is
idempotent on ``key`` — emitting the same key again returns the event already stored, never a
second one (the unique constraint holds even when two processes race). ``pending()`` lists what
is still to deliver, oldest first; ``mark_dispatched(event)`` records a delivery. Delivery itself
(signed webhooks, retries, the delivery log) is W-01's; consumers deduplicate on the event's
``public_id``.
"""

from __future__ import annotations

from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.tenancy.context import org_context

from .models import OutboxEvent


def emit(
    organisation: Any,
    event_type: str,
    *,
    key: str,
    aggregate: tuple[str, str],
    payload: dict[str, Any],
    occurred_at: Any = None,
) -> OutboxEvent:
    """Store the event once per ``key`` (module docstring)."""
    with org_context(organisation):
        found: OutboxEvent | None = OutboxEvent.objects.filter(key=key).first()
        if found is not None:
            return found
        event = OutboxEvent(
            organisation=organisation,
            event_type=event_type,
            key=key,
            aggregate_type=aggregate[0],
            aggregate_id=aggregate[1],
            payload=payload,
            occurred_at=occurred_at or timezone.now(),
        )
        try:
            with transaction.atomic():  # a savepoint: a racing duplicate leaves the caller's work
                event.save()
        except IntegrityError:
            stored: OutboxEvent = OutboxEvent.objects.get(key=key)
            return stored
        return event


def pending(limit: int = 100) -> list[OutboxEvent]:
    """Events not delivered yet, oldest first, across organisations (the relay's read)."""
    return list(
        OutboxEvent._base_manager.filter(dispatched_at__isnull=True).order_by("occurred_at", "pk")[
            :limit
        ]
    )


def mark_dispatched(event: OutboxEvent) -> None:
    OutboxEvent._base_manager.filter(pk=event.pk).update(
        dispatched_at=timezone.now(), attempts=event.attempts + 1
    )

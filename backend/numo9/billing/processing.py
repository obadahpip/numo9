"""Processing stored Stripe events (U-04-T06): handlers by event type.

``process_event(pk)`` (run by the Celery task ``numo9.billing.process_stripe_event``):

- locks the event row; an event already processed is skipped (a re-delivered task, or the same
  event queued twice, does nothing);
- calls the handler registered for its type (``register_handler``; U-04-T07 subscriptions,
  U-04-T08 invoices) in the event's transaction; a type without handler is recorded as
  processed (Stripe sends more types than Numo9 needs);
- on success sets ``processed_at``; on an error records ``attempts`` and ``error`` and raises
  (the task retries with backoff), the handler's changes rolled back.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.db import transaction
from django.utils import timezone

from numo9.security.scrubbing import scrub_text

from .models import StripeEvent

Handler = Callable[[StripeEvent], Any]

_handlers: dict[str, Handler] = {}

ERROR_MAX = 2000


def register_handler(*event_types: str) -> Callable[[Handler], Handler]:
    def decorator(handler: Handler) -> Handler:
        for event_type in event_types:
            _handlers[event_type] = handler
        return handler

    return decorator


def handler_for(event_type: str) -> Handler | None:
    return _handlers.get(event_type)


class EventFailed(RuntimeError):
    pass


def process_event(pk: int) -> str:
    """Run the event's handler once; ``processed``, ``skipped`` or ``ignored`` (no handler)."""
    try:
        with transaction.atomic():
            event = StripeEvent.objects.select_for_update().get(pk=pk)
            if event.processed_at is not None:
                return "skipped"
            handler = handler_for(event.type)
            if handler is not None:
                handler(event)
            StripeEvent.objects.filter(pk=pk).update(
                processed_at=timezone.now(), attempts=event.attempts + 1, error=""
            )
            return "processed" if handler is not None else "ignored"
    except Exception as error:
        message = scrub_text(f"{type(error).__name__}: {error}")[:ERROR_MAX]
        StripeEvent.objects.filter(pk=pk).update(
            attempts=StripeEvent.objects.get(pk=pk).attempts + 1, error=message
        )
        raise EventFailed(message) from error

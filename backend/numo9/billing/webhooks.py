"""Stripe webhook endpoint (U-04-T06): ``POST /webhooks/stripe/``.

1. **Signature** — the ``Stripe-Signature`` header is checked against the raw body with the
   endpoint's signing secret (``STRIPE_WEBHOOK_SECRET``; Stripe's tolerance of 5 minutes stops
   old captured requests). No secret configured, no header or a wrong signature → **400**, nothing
   stored.
2. **Persistence** — the event is stored once (``record_event``, U-04-T03).
3. **Dispatch** — a new event is queued for the Celery task ``numo9.billing.process_stripe_event``
   when the transaction commits; the endpoint answers **200** at once (Stripe needs a fast 2xx).
   A replayed or re-delivered event (same ``evt_`` id) answers 200 ``duplicate`` and queues
   nothing — the handlers never run twice.

Not under ``/api/v1/`` and without session or CSRF: Stripe authenticates with the signature.
"""

from __future__ import annotations

import json
import logging

from django.conf import settings
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .events import MalformedEvent, record_event
from .gateway import BillingUnavailable, SignatureInvalid, get_gateway

logger = logging.getLogger("numo9.billing")


def _refuse(reason: str) -> JsonResponse:
    logger.warning("billing.webhook.refused", extra={"reason": reason})
    return JsonResponse({"error": reason}, status=400)


@csrf_exempt
@require_POST
def stripe_webhook(request: HttpRequest) -> JsonResponse:
    from .tasks import process_stripe_event

    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    signature = request.headers.get("Stripe-Signature", "")
    if not secret:
        return _refuse("not_configured")
    if not signature:
        return _refuse("no_signature")
    try:
        event = get_gateway().construct_event(request.body, signature, secret)
    except (SignatureInvalid, BillingUnavailable):
        return _refuse("bad_signature")
    except (ValueError, json.JSONDecodeError):
        return _refuse("bad_payload")
    try:
        with transaction.atomic():
            row, created = record_event(event)
            if created:
                transaction.on_commit(lambda: process_stripe_event.delay(row.pk))
    except MalformedEvent:
        return _refuse("bad_event")
    logger.info(
        "billing.webhook.received",
        extra={"event": row.event_id, "type": row.type, "duplicate": not created},
    )
    return JsonResponse({"received": True, "duplicate": not created})

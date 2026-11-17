"""U-04-T06 — Stripe webhook endpoint. Acceptance: bad signature → 400; replay → no-op.

Covers: a signed event is stored and queued for the Celery task when the transaction commits
(200 at once); the task processes it once (registered handler called, ``processed_at`` set), a
type without handler is recorded as ignored; a replayed event answers 200 ``duplicate`` and queues
nothing; refused with 400 and nothing stored: no secret configured, no ``Stripe-Signature``, a
wrong signature, a malformed event; GET is 405; no session or CSRF needed; a failing handler
records the attempt and error and is retried, its changes rolled back; processing twice skips.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any
from unittest import mock

import pytest
from django.test import Client, override_settings

from numo9.billing import processing, tasks
from numo9.billing.models import StripeEvent
from numo9.billing.processing import EventFailed, process_event, register_handler
from numo9.tenancy.models import Organisation
from tests.billing_helpers import FakeGateway, stripe_event

pytestmark = pytest.mark.django_db
SECRET = "whsec_test"  # noqa: S105 - a test placeholder, not a key
GOOD = f"t=1,v1=valid-for-{SECRET}"
URL = "/webhooks/stripe/"


@pytest.fixture(autouse=True)
def configured() -> Iterator[list[int]]:
    FakeGateway.reset()
    queued: list[int] = []
    with (
        override_settings(
            NUMO9_BILLING_GATEWAY="tests.billing_helpers.FakeGateway",
            STRIPE_WEBHOOK_SECRET=SECRET,
        ),
        mock.patch.object(tasks.process_stripe_event, "delay", queued.append),
    ):
        yield queued


def send(event: dict[str, Any], signature: str = GOOD) -> Any:
    client = Client(enforce_csrf_checks=True)
    headers = {"Stripe-Signature": signature} if signature else {}
    return client.post(URL, json.dumps(event), content_type="application/json", headers=headers)


def test_signed_event_is_stored_and_queued(
    configured: list[int], django_capture_on_commit_callbacks: Any
) -> None:
    event = stripe_event("invoice.paid", {"id": "in_1"})
    with django_capture_on_commit_callbacks(execute=True):
        response = send(event)
    assert response.status_code == 200 and response.json() == {"received": True, "duplicate": False}
    row = StripeEvent.objects.get()
    assert row.event_id == event["id"] and configured == [row.pk]


def test_replay_is_a_no_op(configured: list[int], django_capture_on_commit_callbacks: Any) -> None:
    event = stripe_event("invoice.paid", {"id": "in_1"})
    with django_capture_on_commit_callbacks(execute=True):
        send(event)
        replay = send(event)
    assert replay.status_code == 200 and replay.json()["duplicate"] is True
    assert StripeEvent.objects.count() == 1 and len(configured) == 1


@pytest.mark.parametrize(
    ("signature", "secret", "reason"),
    [
        ("t=1,v1=forged", SECRET, "bad_signature"),
        ("", SECRET, "no_signature"),
        (GOOD, "", "not_configured"),
    ],
)
def test_refused_with_400(signature: str, secret: str, reason: str, configured: list[int]) -> None:
    with override_settings(STRIPE_WEBHOOK_SECRET=secret):
        response = send(stripe_event("invoice.paid", {}), signature)
    assert response.status_code == 400 and response.json() == {"error": reason}
    assert not StripeEvent.objects.exists() and configured == []


def test_malformed_event_and_get() -> None:
    assert send({"id": "nope", "type": "x", "created": 1}).status_code == 400
    assert Client().get(URL).status_code == 405
    assert not StripeEvent.objects.exists()


def test_processing_once(configured: list[int]) -> None:
    seen: list[str] = []
    register_handler("test.thing")(lambda event: seen.append(event.event_id))
    try:
        send(stripe_event("test.thing", {}))
        send(stripe_event("invoice.unknown_type", {}))
        first, second = StripeEvent.objects.order_by("pk")
        assert process_event(first.pk) == "processed"
        assert process_event(first.pk) == "skipped"
        assert process_event(second.pk) == "ignored"
        assert seen == [first.event_id]
        first.refresh_from_db()
        assert first.processed_at is not None and first.attempts == 1
    finally:
        processing._handlers.pop("test.thing", None)


def test_failing_handler_is_recorded_and_retried(configured: list[int]) -> None:
    def broken(event: StripeEvent) -> None:
        Organisation.objects.create(name="Should roll back")
        raise RuntimeError("Stripe object missing")

    register_handler("test.broken")(broken)
    try:
        send(stripe_event("test.broken", {}))
        row = StripeEvent.objects.get()
        with pytest.raises(EventFailed):
            process_event(row.pk)
        row.refresh_from_db()
        assert row.processed_at is None and row.attempts == 1
        assert "RuntimeError: Stripe object missing" in row.error
        assert not Organisation.objects.filter(name="Should roll back").exists()
        with (
            mock.patch.object(
                tasks.process_stripe_event, "retry", side_effect=RuntimeError("retry")
            ),
            pytest.raises(RuntimeError, match="retry"),
        ):
            tasks.process_stripe_event.run(row.pk)
    finally:
        processing._handlers.pop("test.broken", None)

"""U-04-T03 — ``StripeEvent``. Acceptance: a duplicate ``event_id`` insert is ignored.

Covers: an event is stored with its type, payload, Stripe's created time and live mode; the same
event id again stores nothing and returns the stored row (even with a different payload); the
database refuses a second row with the same id; malformed events (no ``evt_`` id, no type, no
created time) are refused; ``data_object``.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.db import IntegrityError, transaction

from numo9.billing.events import MalformedEvent, record_event
from numo9.billing.models import StripeEvent
from tests.billing_helpers import stripe_event

pytestmark = pytest.mark.django_db


def test_event_is_stored() -> None:
    event = stripe_event("invoice.paid", {"id": "in_1"}, created=1_790_000_000)
    row, created = record_event(event)
    assert created and row.event_id == event["id"] and row.type == "invoice.paid"
    assert row.stripe_created == dt.datetime.fromtimestamp(1_790_000_000, tz=dt.UTC)
    assert row.payload == event and row.data_object == {"id": "in_1"}
    assert row.processed_at is None and row.attempts == 0 and not row.livemode


def test_duplicate_event_id_is_ignored() -> None:
    event = stripe_event("invoice.paid", {"id": "in_1"})
    first, created = record_event(event)
    replay = {**event, "data": {"object": {"id": "in_tampered"}}}
    again, created_again = record_event(replay)
    assert created and not created_again
    assert again.pk == first.pk and again.data_object == {"id": "in_1"}
    assert StripeEvent.objects.count() == 1


def test_database_refuses_a_second_row() -> None:
    record_event(stripe_event("invoice.paid", {}, event_id="evt_dup"))
    with pytest.raises(IntegrityError), transaction.atomic():
        StripeEvent.objects.create(
            event_id="evt_dup",
            type="invoice.paid",
            payload={},
            stripe_created=dt.datetime.now(dt.UTC),
        )


@pytest.mark.parametrize(
    "event",
    [
        {"id": "in_123", "type": "invoice.paid", "created": 1},
        {"id": "evt_1", "type": "", "created": 1},
        {"id": "evt_1", "type": "invoice.paid", "created": "yesterday"},
        {"type": "invoice.paid", "created": 1},
    ],
)
def test_malformed_events_are_refused(event: dict[str, object]) -> None:
    with pytest.raises(MalformedEvent):
        record_event(event)
    assert not StripeEvent.objects.exists()

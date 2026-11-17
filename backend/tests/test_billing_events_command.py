"""U-04-T17 — ``manage.py billing_events`` (the runbook's tool): list, retry, process one."""

from __future__ import annotations

from io import StringIO
from unittest import mock

import pytest
from django.core.management import CommandError, call_command

from numo9.billing import tasks
from numo9.billing.events import record_event
from numo9.billing.models import StripeEvent
from tests.billing_helpers import stripe_event

pytestmark = pytest.mark.django_db


def run(*args: str) -> str:
    out = StringIO()
    call_command("billing_events", *args, stdout=out)
    return out.getvalue()


def test_list_retry_and_process_one() -> None:
    first, _ = record_event(stripe_event("invoice.unknown", {}, event_id="evt_cmd_1"))
    record_event(stripe_event("invoice.unknown", {}, event_id="evt_cmd_2"))
    listing = run()
    assert "evt_cmd_1" in listing and "2 unprocessed event(s)" in listing
    queued: list[int] = []
    with mock.patch.object(tasks.process_stripe_event, "delay", queued.append):
        assert "queued again" in run("--retry")
    assert len(queued) == 2
    assert "evt_cmd_1 invoice.unknown: ignored" in run("--event", "evt_cmd_1")
    assert "skipped" in run("--event", "evt_cmd_1")
    assert StripeEvent.objects.get(pk=first.pk).processed_at is not None
    assert "1 unprocessed event(s)" in run()
    with pytest.raises(CommandError):
        run("--event", "evt_missing")

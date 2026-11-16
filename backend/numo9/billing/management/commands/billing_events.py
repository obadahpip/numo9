"""``manage.py billing_events`` — look at and retry stored Stripe events (U-04-T17 runbook).

    manage.py billing_events                  # the unprocessed events (oldest first)
    manage.py billing_events --retry          # queue every unprocessed event again
    manage.py billing_events --event evt_…    # process one event now, in this process

Processing stays idempotent: an event already processed is skipped.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.billing.models import StripeEvent
from numo9.billing.processing import EventFailed, process_event


class Command(BaseCommand):
    help = "List, retry or process stored Stripe webhook events."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--retry", action="store_true", help="Queue every unprocessed event")
        parser.add_argument("--event", default="", help="Process this event id now")

    def handle(self, *args: Any, **options: Any) -> None:
        from numo9.billing.tasks import process_stripe_event

        if options["event"]:
            row = StripeEvent.objects.filter(event_id=options["event"]).first()
            if row is None:
                raise CommandError(f"No stored event {options['event']}.")
            try:
                outcome = process_event(row.pk)
            except EventFailed as error:
                raise CommandError(f"{row.event_id} failed: {error}") from error
            self.stdout.write(f"{row.event_id} {row.type}: {outcome}")
            return
        pending = StripeEvent.objects.filter(processed_at__isnull=True).order_by("stripe_created")
        for row in pending:
            self.stdout.write(
                f"{row.event_id}  {row.type}  created {row.stripe_created:%Y-%m-%d %H:%M:%S}  "
                f"attempts {row.attempts}  {row.error[:120]}"
            )
            if options["retry"]:
                process_stripe_event.delay(row.pk)
        self.stdout.write(
            f"{pending.count()} unprocessed event(s)"
            + (" queued again" if options["retry"] else "")
        )

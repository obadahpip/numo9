"""``manage.py founding_race_test --orgs 1500 --workers 30`` (U-08-T04).

Creates ``--orgs`` scratch organisations and allocates a founding slot for each from ``--workers``
concurrent threads, then checks exactly ``cap`` slots were handed out, numbered 1..cap without a
gap. For a scratch database only: it refuses to run when any slot is already allocated.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.founding.models import FoundingCounter
from numo9.founding.race import founding_race
from numo9.tenancy.models import Organisation


class Command(BaseCommand):
    help = "Race N first payments for founding slots and verify exactly cap slots, gap-free."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--orgs", type=int, default=1500)
        parser.add_argument("--workers", type=int, default=30)
        parser.add_argument("--replay-every", type=int, default=10)

    def handle(self, *args: Any, **options: Any) -> None:
        counter = FoundingCounter.current()
        if counter.allocated:
            raise CommandError("Founding slots are already allocated: use a scratch database.")
        organisations = Organisation.objects.bulk_create(
            Organisation(name=f"Founding race {n:04d}") for n in range(1, options["orgs"] + 1)
        )
        report = founding_race(
            organisations, workers=options["workers"], replay_every=options["replay_every"]
        )
        expected = min(counter.cap, len(organisations))
        self.stdout.write(
            f"attempts {report.attempts}, granted {report.granted}, refused {report.refused}, "
            f"slots {len(report.numbers)} of cap {report.cap}, gap-free {report.gap_free}, "
            f"{report.seconds:.1f} s"
        )
        if not report.ok(expected):
            raise CommandError(f"Race failed: {report}")

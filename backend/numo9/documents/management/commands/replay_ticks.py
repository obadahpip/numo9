"""``manage.py replay_ticks --date YYYY-MM-DD [--to YYYY-MM-DD] [--org ID] [--kind KIND]
[--dry-run]`` — the support tool of recurring documents (D-04-T11).

Runs the occurrences dated ``--date`` (through ``--to``) of the recurring templates again —
every organisation, or the one given by public id; every kind (``invoices``, and ``bills`` once
E-03 registers it), or ``--kind`` — through the generator's own ``run_occurrence``: its run row
is unique per (template, date), so **a day that already ran creates nothing new**; a day the job
missed (the workers were down) is generated now, once. Dates before a template existed are never
replayed and ``next_run`` isn't moved back. ``--dry-run`` lists what ran and what would run.

One line per occurrence (``created``, ``skipped (code)``, ``already ran``, ``would run``), then
the totals.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.tenancy.models import Organisation

from ...recurring import GENERATORS


def _day(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as error:
        raise CommandError(f"{value!r} isn't a date (YYYY-MM-DD).") from error


class Command(BaseCommand):
    help = "Replay the recurring-document ticks of a day (a day that already ran creates nothing)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--date", required=True, help="The first day to replay (YYYY-MM-DD)")
        parser.add_argument("--to", help="The last day to replay (default: --date)")
        parser.add_argument("--org", help="Public id of one organisation (default: all)")
        parser.add_argument("--kind", help=f"One kind of document: {', '.join(sorted(GENERATORS))}")
        parser.add_argument("--dry-run", action="store_true", help="List; create nothing")

    def handle(self, *args: Any, **options: Any) -> None:
        start = _day(options["date"])
        end = _day(options["to"]) if options.get("to") else start
        if end < start:
            raise CommandError("--to is before --date.")
        if (end - start).days > 366:
            raise CommandError("Replay at most a year at a time.")
        kinds = sorted(GENERATORS)
        if options.get("kind"):
            if options["kind"] not in GENERATORS:
                raise CommandError(f"Unknown kind {options['kind']!r}: one of {', '.join(kinds)}.")
            kinds = [options["kind"]]
        organisations = Organisation.objects.order_by("pk")
        if options.get("org"):
            organisations = organisations.filter(public_id=options["org"])
            if not organisations.exists():
                raise CommandError("There's no organisation with this public id.")
        dry = bool(options.get("dry_run"))
        totals = {"created": 0, "skipped": 0, "already ran": 0, "would run": 0}
        for kind in kinds:
            generator = GENERATORS[kind]
            for organisation in organisations.iterator():
                for template, day, run in generator.replay(organisation, start, end, dry_run=dry):
                    if run is None:
                        outcome = "would run" if dry else "already ran"
                    elif dry:
                        outcome = "already ran"
                    else:
                        outcome = run.status
                    totals[outcome] += 1
                    detail = f" ({run.code})" if run is not None and not dry and run.code else ""
                    self.stdout.write(
                        f"{kind} · {organisation.public_id} · {template.name} · "
                        f"{day.isoformat()}: {outcome}{detail}"
                    )
        self.stdout.write(
            f"{sum(totals.values())} occurrences: {totals['created']} created, "
            f"{totals['skipped']} skipped, {totals['already ran']} already ran"
            + (f", {totals['would run']} would run" if dry else "")
            + "."
        )

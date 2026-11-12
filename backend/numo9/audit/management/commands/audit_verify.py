"""``manage.py audit_verify`` — check every organisation's audit hash chain (A-04-T05).

Walks each chain in order and recomputes every event's hash. Prints one line per chain (events,
head hash) and every problem: ``hash`` — the event's content no longer matches its hash (changed
in the database); ``link`` — its ``prev_hash`` is not the previous event's hash (an event before
it was removed or one was inserted). Exit code 1 when any chain is broken.

    python manage.py audit_verify                       # the platform chain + every organisation
    python manage.py audit_verify --organisation <id>   # one organisation (public id)
    python manage.py audit_verify --quiet               # only broken chains and the summary
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.audit.chain import verify


class Command(BaseCommand):
    help = "Verify the audit log's hash chains; exit 1 if any event was changed or removed."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--organisation", help="Public id of one organisation to check")
        parser.add_argument(
            "--quiet", action="store_true", help="Print only broken chains and the summary line"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        reports = verify(options["organisation"])
        broken = [r for r in reports if not r.ok]
        for report in reports:
            if report.ok and options["quiet"]:
                continue
            state = "OK" if report.ok else "BROKEN"
            self.stdout.write(
                f"{state:<6} {report.organisation} ({report.name}): {report.events} events, "
                f"head {report.head[:16]}"
            )
            for problem in report.problems:
                what = (
                    "content does not match its hash (changed)"
                    if problem.reason == "hash"
                    else "previous hash does not match (an earlier event was removed or inserted)"
                )
                self.stdout.write(f"       event {problem.public_id} (#{problem.event_id}): {what}")
        total = sum(r.events for r in reports)
        summary = f"{len(reports)} chains, {total} events, {len(broken)} broken"
        if broken:
            raise CommandError(summary)
        self.stdout.write(summary)

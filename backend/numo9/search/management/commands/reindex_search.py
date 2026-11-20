"""``manage.py reindex_search [--org <public id> …] [--check]`` (A-09-T09).

Rebuilds the search index of the given organisations (all when none is given) from their
records, removing documents with no record behind them. ``--check`` writes nothing: it reports
missing and stale documents and exits non-zero on any drift (the nightly consistency check).
"""

from __future__ import annotations

import uuid
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.search.reindex import drift, reindex
from numo9.tenancy.models import Organisation


class Command(BaseCommand):
    help = "Rebuild (or, with --check, verify) the search index of organisations."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--org", action="append", default=[], help="Organisation public id (repeatable)"
        )
        parser.add_argument("--check", action="store_true", help="Report drift, write nothing")

    def handle(self, *args: Any, **options: Any) -> None:
        wanted: list[str] = options["org"]
        organisations = Organisation.objects.order_by("pk")
        if wanted:
            for value in wanted:
                try:
                    uuid.UUID(value)
                except ValueError as error:
                    raise CommandError(f"Not an organisation id: {value}") from error
            organisations = organisations.filter(public_id__in=wanted)
            found = {str(o.public_id) for o in organisations}
            unknown = sorted(set(wanted) - found)
            if unknown:
                raise CommandError(f"Unknown organisation: {', '.join(unknown)}")
        drifted = 0
        for organisation in organisations.iterator():
            if options["check"]:
                report = drift(organisation)
                drifted += not report.consistent
                self.stdout.write(
                    f"{report.organisation}: {sum(report.counts.values())} expected, "
                    f"{report.missing} missing, {report.stale} stale"
                )
            else:
                report = reindex(organisation)
                counts = ", ".join(f"{k} {v}" for k, v in sorted(report.counts.items()))
                self.stdout.write(
                    f"{report.organisation}: {report.indexed} indexed, {report.removed} removed"
                    + (f" ({counts})" if counts else "")
                )
        if drifted:
            raise CommandError(f"Search index drift in {drifted} organisation(s).")

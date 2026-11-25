"""``manage.py validate_statements [--org PUBLIC_ID] [--from DATE] [--to DATE]`` (K-02-T15):
the statement cross-checks of ``numo9.reports.validation`` for each organisation; exits 1 with
the failures listed when any check disagrees. The period is the financial year to date by
default."""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.utils import timezone


class Command(BaseCommand):
    help = "Cross-check the financial statements (BS, P&L, TB, GL, cash flow) of organisations."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--org", help="One organisation's public id.")
        parser.add_argument("--from", dest="start", type=dt.date.fromisoformat)
        parser.add_argument("--to", dest="end", type=dt.date.fromisoformat)
        parser.add_argument("--book", default="accounting", choices=("accounting", "tax"))

    def handle(self, *args: Any, **options: Any) -> None:
        from numo9.reports.statements import fiscal_start
        from numo9.reports.validation import validate_statements
        from numo9.tenancy.context import org_context
        from numo9.tenancy.models import Organisation

        orgs = Organisation.objects.order_by("pk")
        if options["org"]:
            orgs = orgs.filter(public_id=options["org"])
        end: dt.date = options["end"] or timezone.localdate()
        failed = 0
        for org in orgs:
            with org_context(org):
                start = options["start"] or fiscal_start(org, end)
            failures = validate_statements(org, start, end, options["book"])
            if failures:
                failed += 1
                for failure in failures:
                    self.stdout.write(f"{org.public_id} {org.name}: {failure}")
            else:
                self.stdout.write(f"{org.public_id} {org.name}: OK ({start} to {end})")
        if failed:
            raise CommandError(f"{failed} organisation(s) failed the statement checks.")

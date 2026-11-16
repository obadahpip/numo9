"""``manage.py post_storm --org <public id> --n 1000 --workers 20 [--fail-every 7]`` (C-02-T12).

Posts real journals concurrently and checks the numbers are 1..n without gaps and every book
balances. For a staging copy or a scratch organisation only — never production data.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.ledger.storm import post_storm
from numo9.tenancy.models import Organisation


class Command(BaseCommand):
    help = "Post N journals from W concurrent workers and verify gap-free numbers and balance."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--org", required=True, help="Organisation public id (scratch org)")
        parser.add_argument("--n", type=int, default=1000)
        parser.add_argument("--workers", type=int, default=20)
        parser.add_argument("--fail-every", type=int, default=0)

    def handle(self, *args: Any, **options: Any) -> None:
        organisation = Organisation.objects.filter(public_id=options["org"]).first()
        if organisation is None:
            raise CommandError(f"No organisation {options['org']}.")
        report = post_storm(
            organisation,
            n=options["n"],
            workers=options["workers"],
            fail_every=options["fail_every"],
        )
        self.stdout.write(
            f"posted {report.posted}, rolled back {report.failed}, "
            f"numbers {report.numbers[:1]}..{report.numbers[-1:]}, gap-free {report.gap_free}, "
            f"books balanced {report.books_balanced}, {report.seconds:.1f} s"
        )
        if not report.ok:
            raise CommandError(f"Storm failed: {report}")

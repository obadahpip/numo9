"""``manage.py make_fixture_practice --orgs 2000 --lines 500 --scratch`` (S-06-T08).

Builds the fixture practice for V-01's directory performance and the S-06 k6 baselines: one
practice, ``--orgs`` client organisations, ``--lines`` posted journal lines and ``--contacts``
contacts each. Scratch or staging databases only (DEBUG or NUMO9_ALLOW_FIXTURES=1, and --scratch).
Run again to add more organisations to the same practice.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.scale.fixtures import FixtureRefused, make_practice_fixture


class Command(BaseCommand):
    help = "Generate a practice with N client organisations of M journal lines (scratch only)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--orgs", type=int, required=True)
        parser.add_argument("--lines", type=int, default=500)
        parser.add_argument("--contacts", type=int, default=5)
        parser.add_argument("--seed", type=int, default=1)
        parser.add_argument("--practice", default="Fixture Practice LLP")
        parser.add_argument("--admin-email", default="fixture-admin@example.com")
        parser.add_argument(
            "--password", default="", help="Let the admin sign in (k6 baselines); verified email."
        )
        parser.add_argument(
            "--scratch", action="store_true", help="Confirm this is a scratch/staging database."
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if not options["scratch"]:
            raise CommandError("Pass --scratch to confirm this is a scratch or staging database.")
        if options["orgs"] < 1 or options["lines"] < 0 or options["contacts"] < 0:
            raise CommandError("--orgs must be at least 1; --lines and --contacts not negative.")
        step = max(options["orgs"] // 20, 1)

        def progress(done: int, total: int) -> None:
            if done % step == 0 or done == total:
                self.stdout.write(f"  {done}/{total} organisations")

        try:
            report = make_practice_fixture(
                orgs=options["orgs"],
                lines=options["lines"],
                contacts=options["contacts"],
                seed=options["seed"],
                practice_name=options["practice"],
                admin_email=options["admin_email"],
                password=options["password"],
                progress=progress,
            )
        except FixtureRefused as error:
            raise CommandError(str(error)) from None
        practice = getattr(report.practice, "public_id", "")
        self.stdout.write(
            f"practice {practice}: {len(report.organisations)} organisations, "
            f"{report.lines:,} journal lines, {report.contacts:,} contacts, "
            f"{report.seconds:.1f} s"
        )

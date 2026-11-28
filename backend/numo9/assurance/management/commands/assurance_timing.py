"""``manage.py assurance_timing [--prefix Fixture] [--limit N] --target-orgs 500 --workers 1
--window-minutes 60 [--check]`` (K-09-T26).

Times the nightly assurance run, for real, on the organisations of this database (scratch or
staging: the runs write findings): every organisation (or those whose name starts with
``--prefix``, at most ``--limit``) gets its full run, one after the other; the command prints the
time per organisation (mean, p50, p95, max), the total, and the projection for
``--target-orgs`` organisations on ``--workers`` workers against ``--window-minutes``. With
``--check`` it fails when the projection doesn't fit the window. Full scale:

    NUMO9_ALLOW_FIXTURES=1 python manage.py make_fixture_practice --orgs 500 --lines 500 --scratch
    python manage.py assurance_timing --prefix Fixture --target-orgs 500 --check

(``make perf-assurance`` runs both on the dev stack.)
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.tenancy.models import Organisation

from ...timing import project, time_full_runs


class Command(BaseCommand):
    help = "Time the nightly assurance run per organisation and project it to N organisations."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--prefix", default="", help="Only organisations named like this.")
        parser.add_argument("--limit", type=int, default=0, help="At most this many (0 = all).")
        parser.add_argument("--target-orgs", type=int, default=500)
        parser.add_argument("--workers", type=int, default=1)
        parser.add_argument("--window-minutes", type=float, default=60.0)
        parser.add_argument("--check", action="store_true", help="Fail when it doesn't fit.")

    def handle(self, *args: Any, **options: Any) -> None:
        organisations = Organisation.objects.order_by("pk")
        if options["prefix"]:
            organisations = organisations.filter(name__startswith=options["prefix"])
        if options["limit"]:
            organisations = organisations[: options["limit"]]
        chosen = list(organisations)
        if not chosen:
            raise CommandError("No organisation to time.")
        step = max(len(chosen) // 10, 1)

        def progress(done: int, organisation: Any, seconds: float) -> None:
            if done % step == 0 or done == len(chosen):
                self.stdout.write(f"  {done}/{len(chosen)} organisations ({seconds:.3f} s last)")

        timings = time_full_runs(chosen, progress=progress)
        window = options["window_minutes"] * 60
        projected = project(timings, options["target_orgs"], options["workers"])
        self.stdout.write(
            f"{timings.count} full runs in {timings.total:.1f} s — per organisation: "
            f"mean {timings.mean:.3f} s, p50 {timings.percentile(50):.3f} s, "
            f"p95 {timings.percentile(95):.3f} s, max {timings.max:.3f} s"
        )
        verdict = "fits" if projected <= window else "does NOT fit"
        self.stdout.write(
            f"projection: {options['target_orgs']} organisations on {options['workers']} "
            f"worker(s) = {projected / 60:.1f} min — {verdict} the "
            f"{options['window_minutes']:.0f}-minute window"
        )
        if options["check"] and projected > window:
            raise CommandError("The nightly run would not fit its window.")

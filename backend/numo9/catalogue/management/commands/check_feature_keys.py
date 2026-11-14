"""``manage.py check_feature_keys`` — every business endpoint declares a known feature key
(U-01-T07).

Prints one line per endpoint method with its declaration (key, ``@core`` or nothing; ``*`` marks
business endpoints), then every problem (``feature.E001``–``E003``, see
``numo9.catalogue.checks``), and fails with exit code 1 when there is any. CI runs it in the
backend job after ``migrate`` (the known keys are catalogue rows), plus a canary on
``tests.testapp.feature_urls_ci_canary`` that must fail — proving the gate turns CI red.

    python manage.py check_feature_keys
    python manage.py check_feature_keys --urlconf tests.testapp.feature_urls_ci_canary  # exit 1
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.catalogue.checks import check


class Command(BaseCommand):
    help = "List every API endpoint method with its feature key; fail on missing or unknown keys."
    requires_system_checks: list[str] = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--urlconf", help="URLconf module to check (default: ROOT_URLCONF)")
        parser.add_argument(
            "--quiet", action="store_true", help="Print only problems and the summary line"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        rows, found = check(options["urlconf"])
        if not options["quiet"]:
            width = max((len(r.route) for r in rows), default=10)
            for r in rows:
                mark = "*" if r.business else " "
                shown = r.feature or ("— undeclared —" if r.business else "— no key needed —")
                self.stdout.write(f"{mark} {r.method:<6} /{r.route:<{width}} {shown}")
        for problem in found:
            self.stdout.write(f"FAIL {problem.id}: {problem.msg}")
            self.stdout.write(f"     hint: {problem.hint}")
        business = sum(1 for r in rows if r.business)
        self.stdout.write(
            f"\ncheck_feature_keys: {len(rows)} endpoint methods ({business} business), "
            f"{len(found)} problem(s)"
        )
        if found:
            raise CommandError(f"{len(found)} feature-key problem(s) — see above")

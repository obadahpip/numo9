"""``manage.py permission_check`` — every API endpoint declares its permission (A-03-T06).

Prints one line per endpoint method with what it requires (catalogue key, ``@public`` or
``@authenticated``), then every problem found by the ``rbac`` system check (``rbac.E001``–
``E005``, see ``numo9.rbac.checks``), and fails with exit code 1 when there is any. CI runs it in
the backend job, plus a canary on ``tests.testapp.rbac_urls_bad`` (undeclared fixture view) that
must fail — so the gate itself is proven to turn CI red.

    python manage.py permission_check
    python manage.py permission_check --urlconf tests.testapp.rbac_urls_bad   # exit 1
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.rbac.checks import check_permission_declarations, declarations


class Command(BaseCommand):
    help = "List every API endpoint method with its required permission; fail on undeclared ones."
    # The report replaces the generic system-check output (which would stop before it).
    requires_system_checks: list[str] = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--urlconf", help="URLconf module to check (default: ROOT_URLCONF)")
        parser.add_argument(
            "--quiet", action="store_true", help="Print only problems and the summary line"
        )

    def handle(self, *args: Any, **options: Any) -> None:
        urlconf = options["urlconf"]
        rows = declarations(urlconf)
        if not options["quiet"]:
            width = max((len(r.route) for r in rows), default=10)
            for r in rows:
                shown = r.permission or "— undeclared —"
                self.stdout.write(f"{r.method:<6} /{r.route:<{width}} {shown}")
        problems = check_permission_declarations(urlconf=urlconf)
        for problem in problems:
            self.stdout.write(f"FAIL {problem.id}: {problem.msg}")
            if problem.hint:
                self.stdout.write(f"     hint: {problem.hint}")
        self.stdout.write(
            f"\npermission_check: {len(rows)} endpoint methods, {len(problems)} problem(s)"
        )
        if problems:
            raise CommandError(f"{len(problems)} endpoint declaration problem(s) — see above")

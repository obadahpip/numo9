"""``manage.py tenant_sweep`` — router sweep for tenant isolation (A-01-T09).

Prints one line per endpoint and fails (exit code 1) on any leak, unbuildable URL or
unclassified endpoint. See numo9.tenancy.sweep for what is checked.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.tenancy.sweep import run_sweep


class Command(BaseCommand):
    help = "Request every organisation-scoped endpoint as another organisation's user; expect 404."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--urlconf", help="URLconf module to sweep (default: ROOT_URLCONF)")
        parser.add_argument(
            "--exempt",
            action="append",
            default=[],
            help="Extra regex of routes that are not organisation-scoped (repeatable)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        results = run_sweep(options["urlconf"], tuple(options["exempt"]))
        width = max((len(r.route) for r in results), default=10)
        for r in results:
            mark = "OK  " if r.ok else "FAIL"
            statuses = " ".join(f"{k}={v}" for k, v in r.statuses.items())
            self.stdout.write(f"{mark} {r.kind:<7} /{r.route:<{width}} {statuses}".rstrip())
            for problem in r.problems:
                self.stdout.write(f"       - {problem}")
        failures = [r for r in results if not r.ok]
        scoped = sum(r.kind == "scoped" for r in results)
        exempt = sum(r.kind == "exempt" for r in results)
        self.stdout.write(
            f"\ntenant_sweep: {len(results)} endpoints — {scoped} organisation-scoped, "
            f"{exempt} exempt, {len(failures)} failing"
        )
        if failures:
            raise CommandError(f"{len(failures)} endpoint(s) failed the tenant sweep")

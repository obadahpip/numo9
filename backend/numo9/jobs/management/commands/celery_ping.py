"""``manage.py celery_ping`` — send the ping task and wait for a worker's answer (A-08-T01).

Exit code 0 when a worker answered within ``--timeout`` seconds, 1 otherwise. Used after a
deploy and in the dev stack's worker health check.
"""

from __future__ import annotations

from typing import Any

from celery.exceptions import TimeoutError as CeleryTimeout
from django.core.management.base import BaseCommand, CommandError, CommandParser

from numo9.jobs.queues import QUEUE_NAMES
from numo9.jobs.tasks import ping


class Command(BaseCommand):
    help = "Send numo9.jobs.ping to a queue and wait for a worker to answer."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--queue", default="default", choices=QUEUE_NAMES)
        parser.add_argument("--timeout", type=float, default=10.0)

    def handle(self, *args: Any, **options: Any) -> None:
        result = ping.apply_async(args=["celery_ping"], queue=options["queue"])
        try:
            answer = result.get(timeout=options["timeout"])
        except CeleryTimeout as exc:
            raise CommandError(
                f"No worker answered on queue {options['queue']!r} within {options['timeout']} s."
            ) from exc
        self.stdout.write(self.style.SUCCESS(f"Worker answered on {options['queue']!r}: {answer}"))

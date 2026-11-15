"""``manage.py rebuild_directory`` — rebuild every organisation directory row now (V-01-T03).

The nightly job does the same; run this after a bulk import or a restore.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from numo9.workspace.summary import rebuild_all


class Command(BaseCommand):
    help = "Rebuild every organisation directory row (V-01) from the source records."

    def handle(self, *args: Any, **options: Any) -> None:
        result = rebuild_all()
        self.stdout.write(
            f"{result['organisations']} organisations, {result['rows']} directory rows "
            f"({result['removed']} orphan rows removed)."
        )

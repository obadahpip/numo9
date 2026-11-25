"""``manage.py load_year_end_fixture`` — the C-06-T10 full-year fixture (idempotent)."""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from numo9.ledger.period_close import net_income
from numo9.ledger.year_end_fixture import EXPECTED, FISCAL_YEAR, load
from numo9.tenancy.context import org_context


class Command(BaseCommand):
    help = (
        "Load the year-end fixture: a full fiscal year with a known net income per book (C-06-T10)."
    )

    def handle(self, *args: Any, **options: Any) -> None:
        organisation = load()
        with org_context(organisation):
            found = {book: net_income(organisation, book, *FISCAL_YEAR) for book in EXPECTED}
        self.stdout.write(
            f"{organisation.name} ({organisation.public_id}): net income "
            + ", ".join(f"{book} {amount:.2f}" for book, amount in found.items())
        )

"""``manage.py load_phase1_fixtures`` (C-03-T16): REFINED and its teardown journals, once."""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.core.management.base import BaseCommand

from numo9.ledger.cash_guard import balance
from numo9.ledger.models import Account
from numo9.ledger.phase1_fixtures import SCENARIOS, load
from numo9.tenancy.context import org_context


class Command(BaseCommand):
    help = "Load the Phase 1 fixtures: REFINED's teardown journals and negative-cash scenarios."

    def handle(self, *args: Any, **options: Any) -> None:
        organisation = load()
        with org_context(organisation):
            petty = Account.objects.get(code="1000")
            cash = balance(petty, dt.date.max)
        self.stdout.write(
            f"{organisation.name} ({organisation.public_id}): Petty Cash {cash:.2f}; "
            f"{len(SCENARIOS)} negative-cash scenarios"
        )

"""Books for the K-01 report tests: the small chart of journal_helpers and a few posted
journals in May–July 2026, plus a draft that never counts."""

from __future__ import annotations

import datetime as dt
from typing import Any

from numo9.ledger.services import post_journal, save_draft
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.journal_helpers import chart, pay


def report_books(name: str = "Refined Interiors Inc.") -> dict[str, Any]:
    org = Organisation.objects.create(name=name)
    with org_context(org):
        accounts = chart(org)
        post_journal(
            pay(accounts["chequing"], accounts["sales"], "5000.00", dt.date(2026, 5, 3)), user=None
        )
        post_journal(
            pay(accounts["rent"], accounts["chequing"], "2400.00", dt.date(2026, 6, 1)), user=None
        )
        post_journal(
            pay(accounts["office"], accounts["chequing"], "150.00", dt.date(2026, 6, 20)), user=None
        )
        post_journal(
            pay(accounts["chequing"], accounts["sales"], "1200.00", dt.date(2026, 7, 8)), user=None
        )
        save_draft(
            pay(accounts["rent"], accounts["chequing"], "999.00", dt.date(2026, 6, 2)), user=None
        )
    return {"org": org, **accounts}

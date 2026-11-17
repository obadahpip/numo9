"""C-02-T12 — Concurrency: 1,000 concurrent postings across 20 workers → gap-free, balanced.

20 threads, each on its own PostgreSQL connection, released together, post 1,000 journals
through ``post_journal``; every 7th attempt fails after its lines and number were written (rolled
back). Acceptance: the posted numbers are exactly 1..1000, every entry balances, both books'
trial balances are zero, no line is left from a failed posting. A second organisation posting
at the same time numbers independently (1..200).
"""

from __future__ import annotations

import threading

import pytest
from django.db import connection

from numo9.ledger.storm import StormReport, post_storm
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account


def _org(name: str) -> Organisation:
    organisation = Organisation.objects.create(name=name)
    with org_context(organisation):
        account(organisation, "1000", "Chequing", subtype="bank")
        account(organisation, "4000", "Sales", subtype="revenue")
    return organisation


@pytest.mark.django_db(transaction=True)
def test_1000_concurrent_postings_20_workers() -> None:
    bakery, other = _org("Maple Bakery Inc."), _org("Érable Distribution inc.")
    reports: dict[str, StormReport] = {}

    def side() -> None:
        try:
            reports["other"] = post_storm(other, n=200, workers=4)
        finally:
            connection.close()

    thread = threading.Thread(target=side)
    thread.start()
    reports["bakery"] = post_storm(bakery, n=1000, workers=20, fail_every=7)
    thread.join()

    main = reports["bakery"]
    assert main.errors == []
    assert main.posted == 1000 and main.failed > 100
    assert main.numbers == list(range(1, 1001))
    assert main.unbalanced == [] and main.books_balanced and main.orphan_lines == 0
    assert main.ok
    assert reports["other"].ok and reports["other"].numbers == list(range(1, 201))

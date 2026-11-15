"""C-02-T17 — performance: trial balance of a 100,000-line organisation in under one second.

Acceptance: target met — the trial balance of each book (accounting, tax) of an organisation with
100,000 posted journal lines answers in < 1 s, while another organisation holds 20,000 more lines
the query must never read. The fixture is inserted with ``generate_series`` the way the engine
writes it (entries as drafts, their lines, then Posted with consecutive numbers — the append-only
trigger allows exactly that): 10,000 entries of 10 lines each, five balanced pairs per entry
across 40 accounts, three pairs in both books, one in the accounting book, one in the tax book,
dated over a year. The trial balances are balanced, and an as-of (half-year) report is within
budget too.
"""

from __future__ import annotations

import datetime as dt
import time
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection

from numo9.ledger.models import Account, Book, JournalSequence
from numo9.ledger.trial_balance import trial_balance
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

ENTRIES = 10_000
LINES_PER_ENTRY = 10
OTHER_ENTRIES = 2_000
BUDGET_SECONDS = 1.0

INSERT_ENTRIES = """
INSERT INTO ledger_journalentry (public_id, organisation_id, created_at, updated_at, date, type,
    status, source_type, source_id, narration, book_scope)
SELECT md5(%(seed)s || n)::uuid, %(org)s, now(), now(), DATE '2026-01-01' + (n %% 365),
       'manual', 'draft', '', '', 'Perf entry ' || n, 'both'
FROM generate_series(1, %(entries)s) AS n
"""

# Five balanced pairs per entry: line 2k-1 debits, line 2k credits the same amount; pairs 1-3 in
# both books, pair 4 in the accounting book, pair 5 in the tax book.
INSERT_LINES = """
INSERT INTO ledger_journalline (organisation_id, entry_id, line_no, account_id, debit, credit,
    book, tracking, description, tax_code, created_at, updated_at)
SELECT e.organisation_id, e.id, l.line_no,
       (%(accounts)s::bigint[])[1 + ((e.id * 7 + l.line_no * 13) %% %(account_count)s)],
       CASE WHEN l.line_no %% 2 = 1 THEN amount ELSE 0 END,
       CASE WHEN l.line_no %% 2 = 0 THEN amount ELSE 0 END,
       CASE WHEN (l.line_no + 1) / 2 <= 3 THEN 'both'
            WHEN (l.line_no + 1) / 2 = 4 THEN 'accounting' ELSE 'tax' END,
       '{}'::jsonb, '', '', now(), now()
FROM ledger_journalentry e
CROSS JOIN generate_series(1, %(per_entry)s) AS l(line_no)
CROSS JOIN LATERAL (
    SELECT ((e.id * 31 + ((l.line_no + 1) / 2) * 17) %% 500000 + 1) / 100.0 AS amount
) a
WHERE e.organisation_id = %(org)s
"""

POST_ENTRIES = """
UPDATE ledger_journalentry e
   SET status = 'posted', number = n.number, posted_at = now()
  FROM (SELECT id, row_number() OVER (ORDER BY id) AS number
          FROM ledger_journalentry WHERE organisation_id = %(org)s) n
 WHERE e.id = n.id
"""


def _chart(org: Organisation, count: int) -> list[Account]:
    subtypes = ["current_asset", "current_liability", "revenue", "operating_expense"]
    return [
        account(org, f"{5000 + n}", f"Account {n}", subtype=subtypes[n % len(subtypes)])
        for n in range(count)
    ]


def _fill(org: Organisation, entries: int, accounts: list[Account]) -> None:
    params: dict[str, Any] = {
        "org": org.pk,
        "seed": f"perf-{org.pk}-",
        "entries": entries,
        "per_entry": LINES_PER_ENTRY,
        "accounts": [item.pk for item in accounts],
        "account_count": len(accounts),
    }
    with connection.cursor() as cursor:
        cursor.execute(INSERT_ENTRIES, params)
        # Fresh statistics, or the planner may take the new rows for an empty table and plan
        # the joins below as nested loops over sequential scans.
        cursor.execute("ANALYZE ledger_journalentry")
        cursor.execute(INSERT_LINES, params)
        cursor.execute(POST_ENTRIES, params)
    JournalSequence(organisation=org, next_number=entries + 1).save()


@pytest.fixture
def big() -> Organisation:
    org = Organisation.objects.create(name="Big Ltd.")
    other = Organisation.objects.create(name="Other Ltd.")
    with org_context(org):
        _fill(org, ENTRIES, _chart(org, 40))
    with org_context(other):
        _fill(other, OTHER_ENTRIES, _chart(other, 10))
    with connection.cursor() as cursor:
        cursor.execute("ANALYZE ledger_journalentry")
        cursor.execute("ANALYZE ledger_journalline")
    return org


def _timed(book: str) -> tuple[float, object]:
    started = time.perf_counter()
    result = trial_balance(book)
    elapsed = time.perf_counter() - started
    print(f"{book} trial balance of {ENTRIES * LINES_PER_ENTRY:,} lines: {elapsed:.3f} s")
    return elapsed, result


def test_trial_balance_of_100k_lines_under_one_second(big: Organisation) -> None:
    with org_context(big):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM ledger_journalline WHERE organisation_id = %s", [big.pk]
            )
            assert cursor.fetchone() == (ENTRIES * LINES_PER_ENTRY,)
        for book in (Book.ACCOUNTING, Book.TAX):
            elapsed, tb = _timed(book)
            assert elapsed < BUDGET_SECONDS, f"{book} trial balance took {elapsed:.3f} s"
            assert tb.balanced  # type: ignore[attr-defined]
            assert tb.total_balance == Decimal("0.00")  # type: ignore[attr-defined]
            # Every account has lines in both books: 40 rows (balances may net to zero rarely).
            assert 0 < len(tb.rows) <= 40  # type: ignore[attr-defined]
        # An as-of report (a year-end TB) stays within budget too.
        started = time.perf_counter()
        trial_balance(Book.ACCOUNTING, as_of=dt.date(2026, 6, 30))
        assert time.perf_counter() - started < BUDGET_SECONDS

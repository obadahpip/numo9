"""C-07-T14 — performance: a 10,000-line recode in under 2 minutes on staging-size data.

The organisation holds 110,000 posted lines (written with ``generate_series`` the way the engine
writes them, as the trial balance performance test does, C-02-T17): 1,000 entries of 10 lines on
ten "from" accounts — the 10,000 lines the recode moves to one account — and 10,000 entries of
10 lines on 30 other accounts that the search must pass over. The recode runs as it does in
production: ``execute()`` starts the background job (> 200 lines) and the worker runs it, each
entry reversed and posted again in its own transaction. Budget: 120 s for the whole run; the
search and preview of the same recode stay well inside it too.
"""

from __future__ import annotations

import time
from typing import Any

import pytest
from django.db import connection

from numo9.ledger.models import (
    Account,
    JournalLine,
    JournalSequence,
    RecodeLineChange,
    RecodeStatus,
)
from numo9.ledger.recode_execute import create_batch, execute, recode_job
from numo9.ledger.recode_preview import preview
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.job_helpers import deliver
from tests.journal_helpers import people
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

TARGET_ENTRIES = 1_000
NOISE_ENTRIES = 10_000
LINES_PER_ENTRY = 10
RECODED = TARGET_ENTRIES * LINES_PER_ENTRY
BUDGET_SECONDS = 120.0

INSERT_ENTRIES = """
INSERT INTO ledger_journalentry (public_id, organisation_id, created_at, updated_at, date, type,
    status, source_type, source_id, narration, book_scope)
SELECT md5(%(seed)s || n)::uuid, %(org)s, now(), now(), DATE '2026-01-01' + (n %% 365),
       'manual', 'draft', '', '', %(narration)s || n, 'both'
FROM generate_series(1, %(entries)s) AS n
"""

# Five balanced pairs per entry (line 2k-1 debits, line 2k credits the same amount), both books.
INSERT_LINES = """
INSERT INTO ledger_journalline (organisation_id, entry_id, line_no, account_id, debit, credit,
    book, tracking, description, tax_code, created_at, updated_at)
SELECT e.organisation_id, e.id, l.line_no,
       (%(accounts)s::bigint[])[1 + ((e.id * 7 + l.line_no * 13) %% %(account_count)s)],
       CASE WHEN l.line_no %% 2 = 1 THEN amount ELSE 0 END,
       CASE WHEN l.line_no %% 2 = 0 THEN amount ELSE 0 END,
       'both', '{}'::jsonb, '', '', now(), now()
FROM ledger_journalentry e
CROSS JOIN generate_series(1, %(per_entry)s) AS l(line_no)
CROSS JOIN LATERAL (
    SELECT ((e.id * 31 + ((l.line_no + 1) / 2) * 17) %% 500000 + 1) / 100.0 AS amount
) a
WHERE e.organisation_id = %(org)s AND e.status = 'draft' AND e.narration LIKE %(like)s
"""

POST_ENTRIES = """
UPDATE ledger_journalentry e
   SET status = 'posted', number = n.number, posted_at = now()
  FROM (SELECT id, row_number() OVER (ORDER BY id) AS number
          FROM ledger_journalentry WHERE organisation_id = %(org)s) n
 WHERE e.id = n.id AND e.status = 'draft'
"""


def _fill(org: Organisation, entries: int, accounts: list[Account], narration: str) -> None:
    params: dict[str, Any] = {
        "org": org.pk,
        "seed": f"recode-perf-{org.pk}-{narration}",
        "entries": entries,
        "per_entry": LINES_PER_ENTRY,
        "accounts": [item.pk for item in accounts],
        "account_count": len(accounts),
        "narration": narration,
        "like": f"{narration}%",
    }
    with connection.cursor() as cursor:
        cursor.execute(INSERT_ENTRIES, params)
        cursor.execute("ANALYZE ledger_journalentry")
        cursor.execute(INSERT_LINES, params)


@pytest.fixture
def staging() -> dict[str, Any]:
    org = Organisation.objects.create(name="Staging Size Ltd.")
    who = people(org)
    with org_context(org):
        sources = [account(org, f"6{n:03d}", f"Old expense {n}") for n in range(10)]
        others = [account(org, f"7{n:03d}", f"Other expense {n}") for n in range(30)]
        target = account(org, "6900", "New expense")
        _fill(org, TARGET_ENTRIES, sources, "Recode me ")
        _fill(org, NOISE_ENTRIES, others, "Leave me ")
        with connection.cursor() as cursor:
            cursor.execute(POST_ENTRIES, {"org": org.pk})
            cursor.execute("ANALYZE ledger_journalentry")
            cursor.execute("ANALYZE ledger_journalline")
        JournalSequence(organisation=org, next_number=TARGET_ENTRIES + NOISE_ENTRIES + 1).save()
    return {"org": org, "sources": sources, "target": target, **who}


def test_10000_line_recode_under_two_minutes(staging: dict[str, Any], sent: Any) -> None:
    org = staging["org"]
    criteria = {
        "conditions": [
            {
                "field": "account",
                "op": "in",
                "value": [str(a.public_id) for a in staging["sources"]],
            }
        ]
    }
    changes = {"account": str(staging["target"].public_id)}
    with org_context(org):
        assert JournalLine.objects.count() == (TARGET_ENTRIES + NOISE_ENTRIES) * LINES_PER_ENTRY
        started = time.perf_counter()
        shown = preview(org, criteria, changes, staging["adviser"])
        previewed = time.perf_counter() - started
        assert len(shown.lines) == RECODED and shown.totals_unchanged
        print(f"preview of {RECODED:,} lines: {previewed:.1f} s")

        started = time.perf_counter()
        batch = create_batch(org, criteria, changes, staging["adviser"], name="Perf")
        running = execute(batch, staging["adviser"])
    assert running.status == RecodeStatus.RUNNING
    deliver(recode_job, sent[0])
    elapsed = time.perf_counter() - started
    print(f"recode of {RECODED:,} lines ({TARGET_ENTRIES:,} entries): {elapsed:.1f} s")
    with org_context(org):
        running.refresh_from_db()
        assert running.status == RecodeStatus.COMPLETED, running.problems[:3]
        assert running.line_count == RECODED
        assert RecodeLineChange.objects.filter(batch=running).count() == RECODED
        assert (
            JournalLine.objects.filter(account=staging["target"], entry__status="posted").count()
            == RECODED
        )
    assert elapsed < BUDGET_SECONDS, f"the recode took {elapsed:.1f} s"

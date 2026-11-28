"""K-09-T26 — performance of the exceptions engine, measured.

- **Incremental run < 2 s per posting batch** on a large ledger: an organisation with 100,000
  posted lines (written with ``generate_series`` the way the engine writes them, as the recode and
  trial balance performance tests do) on two bank accounts and four expense accounts, then a batch
  of 20 journals posted through ``post_journal`` with the on-posting hook on — each posting queues
  its incremental run, and each queued job is run the way a worker runs it (``deliver``) and timed;
  the batch's whole scope in one run is timed too. Budget 2 s each.
- **Nightly full run of 500 organisations within the window**: a scaled run — 40 organisations
  of the S-06 fixture practice (500 posted lines each) plus the REFINED teardown organisation —
  timed with ``numo9.assurance.timing`` (the code ``manage.py assurance_timing`` runs at full
  scale) for the first night (every finding created) and the nights after (findings refreshed),
  projected to 500 organisations: the steady state within 60 minutes on one worker, the first
  night within 60 minutes on two (the reports queue runs one job per organisation). The
  full-scale command and the measured numbers are in docs/perf/baseline-report.md.
"""

from __future__ import annotations

import datetime as dt
import time
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection

from numo9.assurance.models import ExceptionFinding, ExceptionRun, RunTrigger
from numo9.assurance.rules.base import Scope
from numo9.assurance.runner import run_job
from numo9.assurance.timing import project, time_full_runs, time_incremental
from numo9.ledger.models import JournalLine, JournalSequence
from numo9.ledger.services import post_journal
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.scale.fixtures import make_practice_fixture
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.assurance_helpers import refined
from tests.job_helpers import deliver
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db

INCREMENTAL_BUDGET = 2.0
LEDGER_ENTRIES = 50_000  # x 2 lines = 100,000 posted lines
BATCH = 20
SCALED_ORGS = 40
TARGET_ORGS = 500
WINDOW_SECONDS = 60 * 60

INSERT_ENTRIES = """
INSERT INTO ledger_journalentry (public_id, organisation_id, created_at, updated_at, date, type,
    status, source_type, source_id, narration, book_scope)
SELECT md5(%(seed)s || n)::uuid, %(org)s, now(), now(), DATE '2025-12-01' + (n %% 360),
       'manual', 'draft', '', '', 'Ledger ' || n, 'both'
FROM generate_series(1, %(entries)s) AS n
"""

# Each entry: line 1 debits an account of the list, line 2 credits another, the same amount.
INSERT_LINES = """
INSERT INTO ledger_journalline (organisation_id, entry_id, line_no, account_id, debit, credit,
    book, tracking, description, tax_code, created_at, updated_at)
SELECT e.organisation_id, e.id, l.line_no,
       (%(accounts)s::bigint[])[1 + ((e.id * 7 + l.line_no * 13) %% %(account_count)s)],
       CASE WHEN l.line_no = 1 THEN a.amount ELSE 0 END,
       CASE WHEN l.line_no = 2 THEN a.amount ELSE 0 END,
       'both', '{}'::jsonb, '', '', now(), now()
FROM ledger_journalentry e
CROSS JOIN generate_series(1, 2) AS l(line_no)
CROSS JOIN LATERAL (SELECT ((e.id * 31) %% 500000 + 1) / 100.0 AS amount) a
WHERE e.organisation_id = %(org)s
"""

POST_ENTRIES = """
UPDATE ledger_journalentry e
   SET status = 'posted', number = n.number, posted_at = e.date + TIME '15:00'
  FROM (SELECT id, row_number() OVER (ORDER BY id) AS number
          FROM ledger_journalentry WHERE organisation_id = %(org)s) n
 WHERE e.id = n.id
"""


@pytest.fixture
def large() -> dict[str, Any]:
    org = Organisation.objects.create(name="Large Ledger Ltd.", time_zone="America/Toronto")
    with org_context(org):
        accounts = {
            "1010": account(org, "1010", "Chequing", subtype="bank"),
            "1020": account(org, "1020", "Savings", subtype="bank"),
            "4000": account(org, "4000", "Sales", subtype="revenue"),
            "6000": account(org, "6000", "Rent", subtype="operating_expense"),
            "6100": account(org, "6100", "Office supplies", subtype="operating_expense"),
            "6200": account(org, "6200", "Travel", subtype="operating_expense"),
            "6300": account(org, "6300", "Advertising", subtype="operating_expense"),
        }
        params: dict[str, Any] = {
            "org": org.pk,
            "seed": f"assurance-perf-{org.pk}",
            "entries": LEDGER_ENTRIES,
            "accounts": [a.pk for a in accounts.values()],
            "account_count": len(accounts),
        }
        with connection.cursor() as cursor:
            cursor.execute(INSERT_ENTRIES, params)
            # Fresh statistics before each join, or the planner may take the new rows for an
            # empty table and plan nested loops over sequential scans (as in the TB perf test).
            cursor.execute("ANALYZE ledger_journalentry")
            cursor.execute(INSERT_LINES, params)
            cursor.execute("ANALYZE ledger_journalline")
            cursor.execute(POST_ENTRIES, params)
            cursor.execute("ANALYZE ledger_journalentry")
        JournalSequence(organisation=org, next_number=LEDGER_ENTRIES + 1).save()
    return {"org": org, "accounts": accounts}


def test_incremental_run_per_posting_batch_under_two_seconds(
    large: dict[str, Any], sent: list[dict[str, Any]], settings: Any
) -> None:
    settings.NUMO9_ASSURANCE_ON_POSTING = True
    org, acc = large["org"], large["accounts"]
    with org_context(org):
        assert JournalLine.objects.count() == LEDGER_ENTRIES * 2
        entries = []
        for n in range(BATCH):  # a posting batch, as an import brings it (system postings)
            entries.append(
                post_journal(
                    JournalSpec(
                        date=dt.date(2026, 11, 2) + dt.timedelta(days=n % 20),
                        narration=f"Batch journal {n}",
                        lines=(
                            LineSpec(
                                acc[("6000", "6100", "6200", "6300")[n % 4]],
                                debit=Decimal("1000.00"),
                            ),
                            LineSpec(acc["1010"], credit=Decimal("1000.00")),
                        ),
                    ),
                    user=None,
                )
            )
    queued = [m for m in sent if m["task"] == "numo9.assurance.run"]
    assert len(queued) == BATCH  # one incremental run per posting
    per_posting = []
    for message in queued:
        started = time.perf_counter()
        deliver(run_job, message)
        per_posting.append(time.perf_counter() - started)
    scope = Scope(
        frozenset(str(e.public_id) for e in entries),
        frozenset({str(acc[c].public_id) for c in ("1010", "6000", "6100", "6200", "6300")}),
    )
    whole_batch = time_incremental(org, scope)
    with org_context(org):
        runs = ExceptionRun.objects.filter(trigger=RunTrigger.POSTING).count()
        flagged = ExceptionFinding.objects.filter(rule_code="JOURNAL_TO_CASH").count()
    print(
        f"incremental on {LEDGER_ENTRIES * 2:,} lines: per posting max {max(per_posting):.3f} s, "
        f"mean {sum(per_posting) / len(per_posting):.3f} s; batch of {BATCH} in one run "
        f"{whole_batch:.3f} s"
    )
    assert runs == BATCH + 1
    assert flagged == BATCH  # the runs did their work: every batch journal to cash is a finding
    assert max(per_posting) < INCREMENTAL_BUDGET, per_posting
    assert whole_batch < INCREMENTAL_BUDGET, whole_batch


def test_nightly_full_run_projects_500_organisations_within_the_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NUMO9_ALLOW_FIXTURES", "1")
    make_practice_fixture(orgs=SCALED_ORGS, lines=500, contacts=2, seed=7)
    refined()
    organisations = list(Organisation.objects.order_by("pk"))
    assert len(organisations) == SCALED_ORGS + 1
    # The first run creates every finding (the fixture's 250 journals per organisation are all
    # flagged: posted long after their dates, expenses with no contact or receipt); the nights
    # after it refresh them — the steady state the window is planned for.
    first = time_full_runs(organisations)
    steady = time_full_runs(organisations)
    for label, timings in (("first night", first), ("steady state", steady)):
        print(
            f"nightly ({label}): {timings.count} organisations in {timings.total:.1f} s (mean "
            f"{timings.mean:.3f} s, p95 {timings.percentile(95):.3f} s, max {timings.max:.3f} s);"
            f" {TARGET_ORGS} on one worker ≈ {project(timings, TARGET_ORGS) / 60:.1f} min"
        )
    assert ExceptionRun._base_manager.filter(trigger=RunTrigger.NIGHTLY).count() == 2 * len(
        organisations
    )
    assert project(steady, TARGET_ORGS, workers=1) < WINDOW_SECONDS
    assert project(first, TARGET_ORGS, workers=2) < WINDOW_SECONDS


def test_timing_command_reports_and_checks_the_window() -> None:
    from io import StringIO

    from django.core.management import CommandError, call_command

    refined()
    out = StringIO()
    call_command(
        "assurance_timing", "--prefix", "REFINED", "--target-orgs", "500", "--check", stdout=out
    )
    text = out.getvalue()
    assert "1 full runs in" in text and "projection: 500 organisations on 1 worker(s)" in text
    assert "fits the 60-minute window" in text
    with pytest.raises(CommandError):
        call_command(
            "assurance_timing",
            "--target-orgs",
            "100000000",
            "--window-minutes",
            "1",
            "--check",
            stdout=StringIO(),
        )
    with pytest.raises(CommandError):
        call_command("assurance_timing", "--prefix", "Nobody", stdout=StringIO())

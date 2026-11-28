# S-06 performance baseline (S-06-T09)

The three k6 baselines of Phase 0 — organisation directory search, posting a journal, the contacts
list — run against the 2,000-organisation fixture practice. Their k6 summaries are committed under
`docs/perf/baselines/<date>/`; later runs add a new dated folder so regressions show as a diff.

## How to run

```bash
# 1. Scratch or staging database with the fixture practice (S-06-T08)
NUMO9_ALLOW_FIXTURES=1 python backend/manage.py make_fixture_practice \
    --orgs 2000 --lines 200 --contacts 5 --password "$FIXTURE_PASSWORD" --scratch
# 2. The API with the perf-only posting endpoint on (numo9/scale/api.py)
NUMO9_PERF_ENDPOINTS=1 gunicorn numo9.wsgi -w 4 -b 127.0.0.1:8000
# 3. The three scripts; summaries land in docs/perf/baselines/<today>/
BASE_URL=http://127.0.0.1:8000 PASSWORD="$FIXTURE_PASSWORD" tools/perf/k6/run-baselines.sh
```

| Script | Scenario | Threshold |
|---|---|---|
| `tools/perf/k6/directory-search.js` (V-01-T07) | 30 accountants work the directory: first page + facets, word / accent / BN searches, filters, sorts, the full 2,000-row list, Ctrl+K | p95 < 300 ms, no failure |
| `tools/perf/k6/post-journal.js` | 10 bookkeepers post balanced journals through `post_journal` (validation, lock dates, gap-free numbers, audit) across the practice's organisations; `HOT=1` sends all to one organisation | p95 < 500 ms, every posting 201 |
| `tools/perf/k6/contacts-list.js` | 20 accountants open clients' contact lists: first page, role tabs, name search, archived | p95 < 300 ms, no failure |

The posting script calls `POST /api/v1/o/<org>/perf/journal`, a perf-only endpoint that is off
(403) unless `NUMO9_PERF_ENDPOINTS=1`; Phase 1's manual-journal API replaces the URL, the scenario
and threshold stay.

## Baseline — 2026-11-19

Environment: the fixture practice (2,000 organisations, 400,000 posted journal lines, 10,000
contacts) on PostgreSQL 16, gunicorn 4 sync workers, k6 v0.54.0 on the same 2-vCPU host, no
PgBouncer, 60 s per script, default think times.

| Script | Requests | p50 | p95 | p99 | max | Threshold |
|---|---:|---:|---:|---:|---:|---|
| Directory search | 1,316 (21/s) | 69 ms | 287 ms | 2,497 ms | 3,936 ms | ✅ p95 < 300 ms |
| Post journal | 839 (14/s) | 112 ms | 206 ms | 298 ms | 464 ms | ✅ p95 < 500 ms, 805/805 posted |
| Contacts list | 928 (15/s) | 75 ms | 146 ms | 582 ms | 636 ms | ✅ p95 < 300 ms |

No request failed. Notes for the next run:

- The directory's p99 is the full 2,000-row list (`page_size=2000&facets=1`, one request in 20):
  seconds, not milliseconds, on a 2-vCPU, 4-worker server; the virtualised grid loads it once per session.
  Watch it as organisations grow — it is the first candidate for a cached response.
- The baseline ran on one host with the load generator: staging (separate k6 runner, PgBouncer,
  the replica router) is the number the go-live gate compares against.

## Demo creation — 2026-11-19 (U-07-T05 / U-07-T11)

`tools/perf/k6/demo-open.js`: 10 anonymous visitors press "Try the demo" back to back for 30 s
(CSRF token, `POST /api/v1/demo` — template clone, demo user, session — then the first contacts
page), same host as above, `NUMO9_DEMO_OPEN_PER_HOUR` raised for the run.

| Requests | p50 | p95 | p99 | max | Threshold |
|---:|---:|---:|---:|---:|---|
| 344 demos opened | 352 ms | 575 ms | 2,090 ms | 2,210 ms | ✅ p95 < 10 s, 344/344 opened |

## Report engine — 2026-11-24 (K-01-T17)

`tools/perf/k6/reports.js` on the `seed_report_books` organisation (100,000 posted journal lines
over the last 12 months, 40 accounts): 5 people run reports for 60 s with 0.5–1.5 s think time —
account activity for the last 12 months, the trial balance as at today, a drill-down of one figure
and the 12-month report as XLSX, in turn. PostgreSQL 16, gunicorn 4 sync workers, k6 v0.54.0 on
the same 2-vCPU host.

| Endpoint | Requests | p50 | p95 | p99 | max | Threshold |
|---|---:|---:|---:|---:|---:|---|
| Report run (`/run`) | 128 | 138 ms | 259 ms | 667 ms | 1,380 ms | ✅ p95 < 3 s |
| Export XLSX (`/export`) | 64 | 125 ms | 373 ms | 914 ms | 1,670 ms | ✅ p95 < 3 s |
| Drill-down (`/drill`) | 63 | 141 ms | 211 ms | 414 ms | 629 ms | ✅ p95 < 1 s |

269 requests, none failed; every run answered rows and totals.

    python backend/manage.py seed_report_books --lines 100000 --password "$SEED_PASSWORD"
    k6 run -e BASE_URL=http://127.0.0.1:8000 -e PASSWORD="$SEED_PASSWORD" tools/perf/k6/reports.js

## Assurance engine — 2026-11-28 (K-09-T26)

Measured by `backend/tests/test_assurance_performance.py` (pytest, PostgreSQL 16) in the shared
2-vCPU development container while other builds were running (load average ≈ 4) — so these are upper bounds, not
staging numbers.

**Incremental run per posting batch** (budget < 2 s): an organisation with 100,000 posted lines
(50,000 entries on two bank and five other accounts), a batch of 20 journals posted through
`post_journal` with the on-posting hook on; each queued incremental job run as the worker runs it.

| Measure | Result | Budget |
|---|---:|---|
| One posting's incremental run (20 runs) | mean 0.145 s, max 0.175 s | ✅ < 2 s |
| The batch's whole scope in one run (20 journals, 5 accounts) | 0.270 s | ✅ < 2 s |

**Nightly full run** (500 organisations within a 60-minute window; the job starts at 03:47
Toronto): a scaled run of 41 organisations — 40 of the S-06 fixture practice with 500 posted lines
each and the REFINED teardown organisation — every rule on, findings written, one transaction per
organisation, projected linearly to 500 (the nightly job queues one job per organisation on the
reports queue).

| Night | 41 organisations | Per organisation (mean / p95 / max) | 500 organisations | Window |
|---|---:|---|---|---|
| First night (every finding created: each fixture journal is backdated and an expense without contact or receipt, ~600 findings per organisation) | 179.4 s | 4.38 s / 6.36 s / 7.81 s | ≈ 36.5 min on one worker | ✅ < 60 min |
| Steady state (the findings refreshed) | 132.1 s | 3.22 s / 4.70 s / 5.24 s | ≈ 26.8 min on one worker | ✅ < 60 min |

The time is in writing findings and their audit events, not in the rules: evaluating all 18 rules
on a 500-line organisation takes about 1.1 s (`EXPENSE_JOURNAL_NO_CONTACT` 0.39 s, `BACKDATED`,
`EXPENSE_JOURNAL_NO_ATTACHMENT`, `JOURNAL_TO_CASH` and `ROUND_AMOUNT` ~0.13 s each, the rest under
0.02 s). The fixture is a worst case (every journal is a finding); real organisations have few
findings. A second reports worker halves the window.

Full scale on a scratch or staging database (`make perf-assurance` on the dev stack):

    NUMO9_ALLOW_FIXTURES=1 python backend/manage.py make_fixture_practice --orgs 500 --lines 500 --scratch
    python backend/manage.py assurance_timing --prefix Fixture --target-orgs 500 --workers 2 --check  # first night
    python backend/manage.py assurance_timing --prefix Fixture --target-orgs 500 --workers 1 --check  # steady state

`assurance_timing` runs every chosen organisation's full run for real, prints mean / p50 / p95 /
max per organisation and the projection, and with `--check` fails when it doesn't fit
`--window-minutes` (default 60).

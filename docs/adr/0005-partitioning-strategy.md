# ADR-0005: Partitioning strategy — audit events by month (pg_partman when installed), journal lines by organisation hash

| | |
|---|---|
| **Status** | accepted — 2026-11-18 (takes effect when the S-06 pull request is merged) |
| **Date** | 2026-11-18 |
| **Deciders** | Obadah Abu Odeh — project lead and decision-maker (approval = merging the PR) |
| **Deliverable / task** | S-06-T02 (supersedes nothing; completes ADR-0003 §5 for `audit_event`) |

## Context and problem statement

Two tables grow with every action of every organisation and decide the platform's scale:
`audit_event` (one row per change, A-04) and `ledger_journalline` (every posted line, C-02). The
Phase 0 plan asks S-06 to partition both now, so they never need a rewrite of a full table later
(Phase 5 target: 500 organisations × 100k lines).

The S-06 card proposes **range by month + an `organisation_id` index** for both. ADR-0003 §5
already decided the journal-line part differently (hash by organisation, 16 partitions) for
reasons that hold; this ADR records the whole strategy in one place and settles the audit part,
including how partitions are created ahead of time and what happens when the PostgreSQL server
lacks the pg_partman extension (the CI service image `postgres:16-alpine` and the staging image
don't ship it).

## Decision drivers

1. **Retention by age, never by deleting rows** — audit events are append-only (A-04-T02: the
   database refuses `UPDATE`/`DELETE`); CRA retention is ≥ 6 years, after which whole months leave.
2. **Per-organisation reads touch one small slice** — every audit and ledger query is scoped to
   one organisation (manager + RLS).
3. **No maintenance surprises** — a missing future partition must never make an insert fail or
   silently land in a catch-all; it must be created ahead of time and alarmed if absent.
4. **Same schema everywhere** — tests, CI, staging and production have identical tables, whether
   or not pg_partman is installed.
5. **Django-compatible** — table names, columns and index names don't change; the ORM keeps working.

## Considered options

**A. `audit_event`**
1. Native `PARTITION BY RANGE (created_at)`, monthly children `audit_event_pYYYYMMDD` plus a
   default partition; pg_partman manages it when the extension is installed, Numo9's own
   maintenance otherwise — **chosen**
2. Range by month, pg_partman required (fails on servers without the extension).
3. Hash by organisation (like journal lines).
4. No partitioning (retention would need `DELETE`, which the append-only rule forbids).

**B. `ledger_journalline`**
1. Hash by `organisation_id`, 16 partitions (ADR-0003 §5) — **chosen, unchanged**
2. Range by month, sub-partitioned by hash.

**C. Creating future partitions**
1. A Celery beat job (daily) creating partitions **3 months ahead**, alarm if month+3 is missing
   — **chosen**
2. Create on insert (a trigger) — slow, racy, and hides the failure.

## Decision outcome

### 1. `audit_event` — monthly range partitions on `created_at` (S-06-T03, T04)

- The parent is `audit_event PARTITION BY RANGE (created_at)`; the primary key `(created_at, id)`
  already includes the partition key (A-04 made the model partition-ready), `public_id` is
  indexed, not unique, and nothing references the table.
- Children are named `audit_event_pYYYYMMDD` (the first day of the month, pg_partman's naming), one
  per calendar month in UTC, plus `audit_event_default` that catches anything outside the created
  range. A row in the default partition is an alarm condition (the maintenance job reports it).
- Indexes stay as Django declared them (same names); they are partitioned indexes on the parent,
  so every child has them. With every audit index starting with `organisation_id`, a
  per-organisation query over a date range reads one index per month it covers.
- **Append-only applies to every partition**: the `BEFORE UPDATE OR DELETE` trigger is on the
  parent (cloned on each child) and `UPDATE`, `DELETE`, `TRUNCATE` are revoked on the parent and on
  every child as it is created (privileges on a child are checked when it is addressed directly).
- **pg_partman when installed**: the migration registers the parent with `partman.create_parent`
  (`p_interval => '1 month'`, `p_premake => 3`, default partition) and the job runs
  `partman.run_maintenance('public.audit_event')`. **Without it**, `numo9.audit.partitions` creates
  the same children with plain DDL. Both paths produce identical names and bounds, tested in CI
  (native path) and locally against PostgreSQL with pg_partman 5.
- **Retention**: whole months older than the retention period are detached and archived (Phase 5
  S-04 runbook); rows are never deleted. No partition is dropped in Phase 0.
- **Existing rows**: the migration moves rows of a non-partitioned `audit_event` into the new
  parent (the hash chain is unchanged — the rows are copied as they are; the sequence
  `audit_event_id_seq` is kept).

### 2. `ledger_journalline` — hash by organisation, 16 partitions (C-02-T03, ADR-0003 §5)

Unchanged from ADR-0003: lines are kept for the life of the organisation, every query is per
organisation and reports span years, so range partitions would buy nothing and split every report
across many partitions. Hash partitions need no maintenance and nothing to pre-create; the job in
§3 doesn't touch them. Primary key `(organisation_id, id)`.

### 3. Pre-creating partitions and alarms (S-06-T04)

Celery beat runs `numo9.audit.ensure_partitions` daily. It creates (or lets pg_partman create)
every month from the current month to **month + 3**, then checks that the partition covering
month + 3 exists and that the default partition is empty. A missing partition or rows in the
default partition is logged at `ERROR` (Sentry), and the job reports `ok = false`, which the job
console shows. Creation is idempotent and safe to run on several beats (DDL with `IF NOT EXISTS`
semantics under a transaction advisory lock).

### Consequences

- Good: retention by dropping months, never by deleting audit rows; per-month vacuum and index
  builds stay small; one schema whether or not the server has pg_partman.
- Good: the ledger keeps the simpler hash layout; no maintenance for it.
- Bad: two layouts to know. Mitigated by this ADR and by tests for both.
- Bad: inserts with a timestamp beyond month + 3 land in the default partition until the job
  catches up — they still succeed and raise the alarm; moving them out is a manual step documented
  in the runbook.
- Bad: privileges must be revoked on each new child — done by the same code that creates it, and
  tested.

### Confirmation

| Rule | Checked by |
|---|---|
| Inserts route to the month's partition; default partition catches the rest | S-06-T03 test |
| Append-only on every partition (trigger and privileges) | S-06-T03 test, A-04 tests on the parent |
| Month + 3 exists after the job; alarm when missing | S-06-T04 test |
| Journal lines in 16 hash partitions | C-02-T03 test |

## Pros and cons of the options

- **A2 (pg_partman required)** — one code path, but the migration fails on the CI and staging
  images; installing the extension is a server decision (S-02), not a migration's.
- **A3 (hash)** — no maintenance, but retention would require `DELETE` on an append-only table.
- **B2 (range + hash for lines)** — 16 × months partitions, every multi-year report reads dozens of
  them, and no retention benefit.
- **C2 (create on insert)** — a trigger that runs DDL on the hot path; concurrent first inserts of a
  month race.

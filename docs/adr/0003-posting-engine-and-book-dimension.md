# ADR-0003: Journal posting engine with a book dimension — append-only lines, gap-free numbers, partitioned by organisation

| | |
|---|---|
| **Status** | accepted — 2026-11-14 (takes effect when the C-02 ADR pull request is merged) |
| **Date** | 2026-11-14 |
| **Deciders** | Obadah Abu Odeh — project lead and decision-maker (approval = merging the PR) |
| **Deliverable / task** | C-02-T01 (the phase plan calls it "ADR-006"; repository numbering is sequential) |

## Context and problem statement

Every amount in Numo9 — invoices, bills, payments, payroll, depreciation, tax adjustments, opening
balances — ends up as journal lines. C-02 builds the **one** double-entry engine they all go
through. It must be correct to the cent, impossible to edit after posting, numbered without gaps
under concurrency, isolated per organisation, and fast for trial balances on large files. It also
carries Numo9's two-book model: one set of lines can serve the **accounting** (management) book,
the **tax** book, or **both**, so a book-tax difference (e.g. CCA vs. book amortization) is a pair of
lines, not a second ledger. Decisions made here are expensive to reverse (data model, money type,
numbering, storage layout), hence an ADR before C-02-T02.

The Phase 0 plan has two partitioning statements that disagree: the C-02 card (T03) asks for
journal lines **hash-partitioned by organisation (16 partitions)**, the S-06 card (T02/T03) for
**range partitions by month** for both `journal_line` and `audit_event`. This ADR settles the
journal-line part.

References: Phase 0 plan §6 C-02 and S-06 cards; Project Plan v2 component C; xero_teardown §5.8–5.9
(journals that bypass controls, no contact per line, no approval); A-01 tenancy and RLS
(`docs/architecture/tenancy.md`), A-04 audit (`docs/architecture/audit.md`), A-05 lock dates and
numbering, C-01 chart of accounts.

## Decision drivers

1. **Correctness of money** — exact decimal arithmetic, balanced to the cent, per book.
2. **Immutability** — posted entries can't change (CRA record-keeping, six-year retention; auditors
   must trust the ledger); corrections are reversals.
3. **Gap-free numbering per organisation** under concurrent posting (1,000 concurrent postings → numbers
   1…1,000), without serialising unrelated organisations.
4. **Tenant isolation** — defence in depth like every sensitive table (A-01: scoped manager + RLS).
5. **Read performance** — trial balance of a 100k-line organisation < 1 s (C-02-T17); every query is
   per organisation.
6. **One way in** — modules can't write lines directly, so every rule is enforced in one place.
7. **Operability** — PostgreSQL 16 self-hosted on Hetzner (ADR-0002), PgBouncer in transaction mode
   (S-06-T01), no extension we can't run there; little routine maintenance.

## Considered options

**A. Book dimension**
1. A `book` column per line: `accounting`, `tax` or `both`. — **chosen**
2. Two separate ledgers (entries duplicated per book).
3. A tax-adjustments side table applied on top of the accounting ledger.

**B. Immutability**
1. PostgreSQL trigger refusing changes to posted rows + Django `save()` guard. — **chosen**
2. Django guard only.
3. Revoke `UPDATE`/`DELETE` privileges on the tables (as `audit_event` does).

**C. Numbering**
1. One `JournalSequence` row per organisation, `UPDATE … RETURNING` in the posting transaction. — **chosen**
2. A PostgreSQL `SEQUENCE` per organisation.
3. `MAX(number) + 1` under an advisory lock.

**D. Journal-line partitioning**
1. Hash partitions on `organisation_id`, 16 partitions. — **chosen**
2. Range partitions by month (pg_partman), as S-06-T02 proposed.
3. No partitioning.

## Decision outcome

### 1. Data model (C-02-T02)

`JournalEntry` — organisation record (`OrgOwnedModel`), audited:
`number` (empty until posted), `date`, `type` (manual, sales, purchase, payment, payroll, opening,
adjustment… — extended by modules), `status`, `source_type`/`source_id` (the document that posted it),
`narration`, `book_scope` (`accounting`, `tax`, `both` — the books the entry touches, derived from
its lines), `reversal_of` (one-to-one, the entry it reverses), `created_by`, `posted_by`,
`posted_at`.

`JournalLine` — `entry`, `account` (C-01, leaf and active), `debit`, `credit`, `book`, `contact`
(nullable; C-03-T02), `tracking` (JSON, C-03), `description`, `tax_code` (nullable, G-01),
`line_no`. Lines carry `organisation_id` (denormalised from the entry) because it is the partition
key and the RLS key.

**Money:** `numeric(18,2)` columns, Python `Decimal` everywhere, quantised to 0.01 with
`ROUND_HALF_UP`. Debit and credit are **separate non-negative columns, exactly one of them > 0** per
line (check constraints). No floats in `numo9.ledger` (lint rule, C-02-T14 adds it beside the
import contract). The engine never rounds a caller's split: an entry that doesn't balance to the
cent is refused, and callers allocate pennies (e.g. tax split across lines).

**Books:** each line belongs to `accounting`, `tax` or `both`. The **accounting book** is the lines
with `book ∈ {both, accounting}`; the **tax book** is the lines with `book ∈ {both, tax}`. An entry
must balance **in each book it touches**: Σdebit = Σcredit over (both + accounting) and over
(both + tax). An ordinary invoice is all `both`; a CCA-vs-amortization difference is an extra
balanced pair in `tax` (or `accounting`) only. Trial balance per book is a single grouped query
with that filter (C-02-T11), and each book's TB is zero by construction.

### 2. Lifecycle (C-02-T09) and the single service (C-02-T08)

States: **Draft → Awaiting approval → Posted → Reversed**, by explicit transition functions only
(an illegal transition raises). Approval uses the A-03 approval limits (`doc_type = journal`).

`numo9.ledger.services.post_journal(spec)` is the only way to create posted lines. In **one**
transaction it: validates (≥ 2 lines; balanced per book; accounts in the organisation, leaf,
active, not archived; amounts quantised; lock date for module `gl` and the document's own module via
the A-05 lock service; period-close hook for C-06, a no-op stub until then; entitlement) →
allocates the number → inserts entry and lines → sets Posted, `posted_by`, `posted_at` → writes the
audit event. Any failure rolls everything back: no partial rows, no consumed number. Error messages
name the exact reason ("Debits 1,000.00 ≠ credits 999.99 in the tax book (difference 0.01)").

`reverse(entry, date, reason)` locks the original row (`SELECT … FOR UPDATE`), posts a mirror entry
(debits ↔ credits, same books, `reversal_of` = original) through the same service, and marks the
original Reversed. Reversing a reversal, or an entry already reversed, is refused; two concurrent
reversals serialise on the row lock and the second is refused.

**One way in:** no module imports the line model to write it. C-02-T14 adds the contract (only
`numo9.ledger.services` may create/update `JournalLine`) as a CI check with a failing fixture, the
same approach as the A-01-T08 OrgOwnedModel check.

### 3. Immutability (C-02-T04)

- A PostgreSQL trigger on the entry and line tables: `BEFORE UPDATE OR DELETE` on a **posted or
  reversed** entry's rows raises `insufficient_privilege`. The only change allowed on a posted entry
  is the Posted → Reversed transition (status and the reversal link), checked column by column in the
  trigger. Draft and awaiting-approval rows stay editable.
- The Django `save()`/`delete()` guard refuses the same changes earlier with a readable error.
- Privileges are **not** revoked (unlike `audit_event`): draft lines must stay editable, so the
  trigger is the database rule. Trigger functions are created on the partitioned parent and apply to
  every partition.

### 4. Gap-free numbering (C-02-T05)

`JournalSequence(organisation, next_number, prefix, padding)` — one row per organisation. Inside the
posting transaction: `UPDATE ledger_journalsequence SET next_number = next_number + 1 WHERE
organisation_id = %s RETURNING next_number - 1`. The row lock is held only until the posting commits
(milliseconds), so one organisation's postings serialise on its own row and other organisations
never wait. A rollback returns the number (no gap). Drafts have no number; a number is given when
the entry is posted, and a reversal gets its own number. Same pattern as A-05's
`allocate_number()` (documents), kept separate because the journal sequence is the ledger's audit
trail. Compatible with PgBouncer transaction pooling (no session state; the tenant GUC is
transaction-local).

### 5. Partitioning (C-02-T03) — hash by organisation

`ledger_journalline` is a parent table **partitioned by `HASH (organisation_id)` into 16
partitions** (`ledger_journalline_p00` … `p15`):

- every query is per organisation (RLS and the scoped manager guarantee it), so the planner reads
  exactly one partition; a large organisation's trial balance scans its partition's
  `(organisation_id, account_id, book)` index only;
- no partition maintenance job and nothing to pre-create; ledger rows are never dropped by age (unlike
  audit events, which leave by monthly partition after retention), so range partitions would buy no
  retention benefit and would split every multi-year report across many partitions;
- the primary key is `(organisation_id, id)` (PostgreSQL requires the partition key in unique
  constraints; Django `CompositePrimaryKey`, as `audit_event` uses). Tables that later refer to a line
  (bank reconciliation matches, F) use the composite key;
- 16 partitions keep each one small enough for vacuum and index builds at the planned scale; more can be
  had later by splitting with `ALTER TABLE … DETACH/ATTACH` (a planned migration, not routine work).

`ledger_journalentry` stays unpartitioned (one row per entry, a fraction of the line volume).
`audit_event` keeps **range partitions by month** as S-06-T02/T03 propose — its retention is by age.
**This ADR replaces the journal-line part of S-06-T02**; S-06-T03 creates only the `audit_event`
range partitions and its pg_partman job covers only that table.

### 6. Tenant isolation

Both tables are business records scoped by `OrgOwnedModel`'s manager, and both get PostgreSQL
row-level security (`EnableOrgRLS`, A-01-T12 names the journal line table among the sensitive ones).
The tenant sweep (A-01-T09) covers the read API (C-02-T15).

### Consequences

- Good: one engine, one place for every rule; trial balances per book are cheap and always zero;
  posted history can't be altered even by a bug or a raw SQL statement; numbers are gap-free per
  organisation with no cross-tenant contention; no partition maintenance for the ledger.
- Good: book-tax differences are ordinary balanced lines, visible in both books' audit trails.
- Bad: debit/credit as two columns makes some queries a little longer (`SUM(debit) - SUM(credit)`) —
  accepted for clarity and for the "one side per line" constraint.
- Bad: a composite primary key on lines; later references must carry `organisation_id`. Mitigated by
  the convention above and by the fact that lines are referenced by few tables.
- Bad: hash partitions can't be dropped by age; not needed for a ledger kept for the life of the
  organisation (archived organisations are exported, then removed by organisation, not by date).
- Bad: a busy organisation's postings serialise on its sequence row. Mitigated by short
  transactions (validation before taking the lock, insert after); C-02-T12 measures 1,000 concurrent
  postings over 20 workers.

### Confirmation

| Rule | Checked by |
|---|---|
| Debit/credit non-negative, one side, numeric(18,2) | C-02-T02 constraint tests |
| Inserts route to the organisation's hash partition | C-02-T03 integration test |
| UPDATE/DELETE of posted rows fails at the database | C-02-T04 trigger test (raw SQL) |
| Gap-free numbers under concurrency | C-02-T05 unit + C-02-T12 (1,000 postings, 20 workers) |
| Unbalanced per book refused with the exact difference | C-02-T06 + Hypothesis C-02-T13 |
| Lock dates enforced | C-02-T07 |
| Atomic posting, no partial rows | C-02-T08 failure-injection test |
| Only `ledger.services` writes lines; no floats in `ledger` | C-02-T14 CI check with failing fixtures |
| TB per book = 0; 100k lines < 1 s | C-02-T11, C-02-T13, C-02-T17 |
| RLS on entries and lines; sweep on the read API | Migration tests, C-02-T15 |

## Pros and cons of the options

### A1. Book column per line (chosen)

- Good, because one posting writes both books at once and an ordinary transaction is written once.
- Good, because each book's TB is a simple filter and balancing per book is a local rule.
- Bad, because every report must state its book — mitigated by a required book parameter in the TB
  and report queries.

### A2. Two ledgers

- Good, because each ledger is simple.
- Bad, because every transaction is written twice and the two can drift; reconciling them is work.

### A3. Tax-adjustments side table

- Good, because the accounting ledger stays untouched.
- Bad, because the tax book is computed, not posted: no audit trail per adjustment, no TB that is
  zero by construction.

### B1. Trigger + guard (chosen)

- Good, because it holds for raw SQL, bugs and superusers alike, while drafts stay editable.
- Bad, because trigger code lives in migrations — kept small and tested.

### B2. Guard only

- Bad, because any raw SQL, bulk `update()` or bug bypasses it.

### B3. Revoke privileges

- Good for append-only tables (`audit_event`).
- Bad here: drafts and the Posted → Reversed status change need `UPDATE`.

### C1. Sequence row + UPDATE … RETURNING (chosen)

- Good, because it is transactional: a rollback gives the number back (gap-free).
- Good, because contention is per organisation only.

### C2. PostgreSQL SEQUENCE per organisation

- Bad, because sequences are not transactional: a rolled-back posting leaves a gap (CRA expects an
  explainable, continuous journal numbering); also one database object per tenant.

### C3. MAX + 1 under an advisory lock

- Bad, because it scans the table and depends on every writer taking the same lock.

### D1. Hash by organisation, 16 partitions (chosen)

- Good, because every query prunes to one partition; zero maintenance.
- Bad, because partitions can't be retired by age (not needed for the ledger).

### D2. Range by month (pg_partman)

- Good for data retired by age (audit events).
- Bad here: needs pg_partman and a pre-creation job; a multi-year report or TB touches many
  partitions; a missing future partition blocks posting.

### D3. No partitioning

- Good, because it is simplest.
- Bad, because a single table of every organisation's lines grows without bound; vacuum and index
  builds get slower for everyone; partitioning later means rewriting the largest table under load.

## More information

- Follow-up tasks: C-02-T02 … T17 implement this ADR; S-06-T02/T03 narrowed to `audit_event`.
- Revisit when an organisation exceeds ~20 million lines (consider more partitions) or if Phase 2's
  two-book reporting (Phase 2 plan) needs a book the three values can't express.

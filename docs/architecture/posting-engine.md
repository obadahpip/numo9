# Posting engine (C-02)

| | |
|---|---|
| **Deliverable** | C-02 · Journal posting engine, Phase 0 (component C — General ledger) |
| **Branch** | `feature/C-02-posting-engine` |
| **Decision** | [ADR-0003 — Posting engine and book dimension](../adr/0003-posting-engine-and-book-dimension.md) |
| **Code** | `backend/numo9/ledger/` (models: `JournalEntry`, `JournalLine`, `JournalSequence`; `sequence`, `validation`, `trial_balance`; migration `0004_journal_append_only`) |
| **Depends on** | A-01 (tenancy, RLS), A-04 (audit), A-05 (lock dates), C-01 (chart of accounts) |
| **Used by** | Every module that posts: D sales, E purchases, F banking, M payroll, I fixed assets, C-04 manual journals, C-05 conversion balances |

The one double-entry engine: every amount in Numo9 ends up as journal lines, balanced to the cent
in each book, numbered without gaps, impossible to change once posted.

## Entries and lines (C-02-T02)

`JournalEntry` (header) and `JournalLine` (one debit or credit) — data dictionary:
[`ledger_journalentry`](../reference/data-dictionary.md#ledger-journalentry),
[`ledger_journalline`](../reference/data-dictionary.md#ledger-journalline).

| Rule | Where |
|---|---|
| Amounts are `numeric(18,2)`, Python `Decimal` | Columns `debit`, `credit` |
| Debit and credit non-negative, exactly one of them > 0 | Checks `ledger_line_debit_not_negative`, `ledger_line_credit_not_negative`, `ledger_line_one_side` |
| `book` ∈ `both`, `accounting`, `tax` | Check `ledger_line_book_valid` |
| Line numbers unique per entry | `ledger_line_no_unique` |
| Journal number unique per organisation; posted/reversed entries have a number and a posting time, drafts none | `ledger_journal_number_unique_per_org`, `ledger_journal_number_when_posted` |
| An entry is reversed at most once, never by itself | One-to-one `reversal_of`, `ledger_journal_not_own_reversal` |
| Tenant isolation | Scoped manager + row-level security on both tables |
| Partition-ready lines | Primary key `(organisation_id, id)`, `id` from `ledger_journalline_id_seq`; the line's organisation is copied from its entry |

Accounts with lines on posted (or reversed) entries "have transactions" for the chart rules: the
ledger registers that probe (`numo9.ledger.postings`), so such an account can't become a parent
or be deleted. Draft lines don't count.

## Append-only (C-02-T04)

Posted and reversed journals can't change — corrections are reversals (C-02-T10). Two layers:

| Layer | Rule |
|---|---|
| Database (migration `ledger.0004_journal_append_only`) | Trigger `ledger_journalentry_append_only` (`BEFORE UPDATE OR DELETE`): a posted/reversed entry can't be deleted; the only update allowed is Posted → Reversed changing nothing but `status` (and `updated_at`). Trigger `ledger_journalline_append_only` (`BEFORE INSERT OR UPDATE OR DELETE`): no line added to, changed in, moved into/out of or deleted from a posted/reversed entry. Both raise `insufficient_privilege` (SQLSTATE 42501), so raw SQL, bulk `update()`/`delete()` and superusers are refused too; on the partitioned table (C-02-T03) the row triggers apply to every partition |
| Django guard | `JournalEntry.save()`/`delete()`/`soft_delete()` and `JournalLine.save()`/`delete()` raise `JournalLocked` (`ledger.journal.locked`: "Journal 7 is posted: it can't be changed or deleted. Reverse it instead.") before reaching the database; even an unchanged save of a posted entry is refused (it would rewrite `updated_at`) |

Drafts and entries awaiting approval stay fully editable. The engine inserts lines while the entry
is a draft and then posts it (C-02-T08). Privileges aren't revoked (unlike `audit_event`) because
drafts need `UPDATE`/`DELETE`.

## Gap-free journal numbers (C-02-T05)

`JournalSequence` — one row per organisation (`ledger_journalseq_one_per_org`): `next_number`
(≥ 1), `prefix` (`JE-`) and `padding` (6) for display. `numo9.ledger.sequence`:

- `allocate_journal_number(organisation)` — inside the posting transaction only (outside it raises
  `SequenceOutsideTransaction`): `UPDATE ledger_journalsequence SET next_number = next_number + 1
  WHERE organisation_id = %s RETURNING next_number - 1`. The row lock serialises the organisation's
  postings until commit; a rollback gives the number back. The first posting creates the row
  (`INSERT … ON CONFLICT DO NOTHING`) and takes 1. Other organisations never wait;
- `format_journal_number(organisation, number)` — `JE-000042`; `""` for a draft.

The entry stores the integer (`JournalEntry.number`); a number is given only when an entry is
posted (drafts have none) and a reversal gets its own. No PostgreSQL `SEQUENCE` (not
transactional) and no session state (PgBouncer transaction pooling).

## Validation (C-02-T06)

`numo9.ledger.validation.validate_journal(JournalSpec) → ValidatedJournal` runs every posting rule
for the active organisation and raises `JournalInvalid` (a `LedgerError`) listing **all**
problems, each with a code and a message naming the line and the exact reason:

| Code | Rule |
|---|---|
| `ledger.journal.too_few_lines` | At least two lines |
| `ledger.journal.amount_type` | Amounts are `Decimal`, `int` or a decimal string — a `float` is refused, never converted; `NaN`/text refused |
| `ledger.journal.amount_precision` | At most two decimals: the engine never rounds a caller's split, callers allocate the pennies |
| `ledger.journal.amount_negative`, `amount_too_large` | Non-negative; within `numeric(18,2)` |
| `ledger.journal.line_one_side` | A debit or a credit, not both and not neither |
| `ledger.journal.book_invalid` | Book `both`, `accounting` or `tax` |
| `ledger.journal.account_missing` | One of the organisation's accounts |
| `ledger.account.archived`, `ledger.account.not_leaf` | Active, leaf accounts (C-01 `assert_postable`) |
| `ledger.journal.unbalanced` | Σ debits = Σ credits in **each book the entry touches** — accounting book = lines `both` + `accounting`, tax book = `both` + `tax`: "Debits 1,000.00 ≠ credits 999.99 in the tax book (difference 0.01)." (French amounts `1 000,00`). Not reported while an amount or a book is itself invalid |

`JournalSpec(date, lines, type, narration, source_type, source_id)`; `LineSpec(account (Account
or id), debit, credit, book, contact, tracking, description, tax_code)`. The result carries the
lines with exact amounts (`ValidatedLine`), the totals per book and the entry's `book_scope`
(`both` when it touches both books, else the one it touches). Lock dates and the period hook
(C-02-T07) and numbering/insertion/audit (C-02-T08) come on top.

## Lock dates and closed periods (C-02-T07)

`numo9.ledger.periods.assert_can_post(organisation, date, user=None, module="gl")` — run by the
posting service before anything is written:

1. **Lock dates** (A-05): the module's own lock and the general-ledger lock
   (`assert_not_locked`) — `LockedPeriod`, 409 `lock.violation`, naming the lock ("The General
   ledger lock date is 2026-03-31 (everyone): …"). Sales postings pass `module="ar"`, bills
   `"ap"`, bank `"bank"`, payroll `"payroll"`; manual journals `"gl"`. When both stop it, the
   module's lock is named. Advisers pass an *everyone except advisers* lock; a system job
   (`user=None`) is stopped like everyone.
2. **Closed periods** (C-06): every check registered with `register_period_check(check)` —
   `check(organisation, date) -> ClosedPeriod | None`. C-06 registers the year-end close; until
   then nothing is registered and every period is open (the stub). A closed period raises
   `PeriodClosed`, 409 `ledger.period.closed`, body `period` (`start`, `end`, `label`): "Fiscal
   year 2025 (2025-01-01 to 2025-12-31) is closed: nothing can be posted in it. …".

The lock is checked first. `JournalEntry.save()` still refuses becoming posted on or before the GL
lock (A-05-T06) — a second layer for code that bypasses the service.

## Posting service (C-02-T08)

`numo9.ledger.services.post_journal(spec, *, user=…, module="gl", reversal_of=None) →
JournalEntry` — the one way to post. In **one transaction**:

| Step | What |
|---|---|
| 1. Validate | `validate_journal` (C-02-T06) — `JournalInvalid` lists every problem |
| 2. Period | `assert_can_post` (C-02-T07) — module + GL lock, closed periods |
| 3. Insert | The entry as a draft, then its lines (`bulk_create`: contact, tracking, description, tax code); the trigger accepts lines only while the entry is a draft |
| 4. Sequence | `allocate_journal_number` (C-02-T05) — taken last, so the sequence row lock is held as briefly as possible |
| 5. Posted | `status`, `number`, `posted_by`, `posted_at` |
| 6. Audit | One event `ledger.journalentry.posted`: changes `status` draft → posted and `number`; meta `number` (`JE-000042`), `date`, `type`, `source`, `reversal_of`, every line (account, debit, credit, book, contact) |

**All or nothing**: a failure at any step (invalid journal, lock, closed period, a database error
after the lines were written, the audit write) rolls everything back — no entry, no line, no audit
event, and the number isn't used (the next posting takes it). `user` defaults to the audit
context's person; `None` is a system job (no `posted_by`, stopped by every lock). The active
organisation only.

## States (C-02-T09)

```
Draft ──submit()──▶ Awaiting approval ──post_entry()──▶ Posted ──reverse()──▶ Reversed
  │                   │   ▲                                ▲
  │                   └───┘ return_to_draft()              │
  └──────────────────────── post_entry() ──────────────────┘
```

`numo9.ledger.services.TRANSITIONS` is the whole table; `assert_transition(entry, to)` raises
`IllegalTransition` (`ledger.journal.illegal_transition`: "Journal 7 is posted: it can't become
draft.") for anything else. Every move reloads the entry under a row lock.

| Function | Move |
|---|---|
| `save_draft(spec, entry=None)` | Creates a draft or replaces a draft's header and lines; the journal is validated (C-02-T06) but not checked against lock dates (a draft may sit in a locked period). Only drafts are edited (`ledger.journal.not_draft`) |
| `submit(entry)` | Draft → Awaiting approval (who may approve — limits, approver ≠ creator — is C-04) |
| `return_to_draft(entry)` | Awaiting approval → Draft |
| `post_entry(entry, user=…, module="gl")` | Draft or Awaiting approval → Posted: steps 1–2 and 4–6 of `post_journal` on the stored lines (re-validated, lock and period checked at posting time) |
| `reverse(entry, …)` | Posted → Reversed (C-02-T10) — the only way out of Posted; Reversed is final |

## Reversal (C-02-T10)

`reverse(entry, *, date=None, narration="", user=…, module="gl") → JournalEntry` (the reversal):

- the original is reloaded **under a row lock** — two people reversing it at once: one wins, the
  other gets `ledger.journal.illegal_transition` (it is already Reversed);
- the reversal is posted through `post_journal`: every line mirrored (debit ↔ credit, same
  account, book, contact, tracking, description, tax code), type `reversal`, the original's
  source, `reversal_of` = the original, its own number, dated `date` (default: the original's
  date) and checked against lock dates and closed periods **on that date** — a locked original
  date is reversed into an open period by passing `date`; narration "Reversal of JE-000007"
  unless given;
- the original goes Posted → Reversed (status only — the append-only trigger allows exactly
  that) with an audit event `ledger.journalentry.reversed` (meta `reversed_by`);
- refused: an entry not posted (draft, awaiting approval, already reversed —
  `ledger.journal.illegal_transition`), and a reversal (`ledger.journal.reversal_of_reversal`:
  post a new journal instead).

Original and reversal net to zero in every account of both books.

## Concurrency (C-02-T12)

`numo9.ledger.storm.post_storm(organisation, n=1000, workers=20, fail_every=0)` posts `n`
journals through `post_journal` from `workers` threads, each on its own database connection,
released together by a barrier; every `fail_every`-th attempt fails **after** its lines and its
number were written and is rolled back — exactly where a gap could appear. The `StormReport`
checks the posted numbers are exactly `1..n`, every entry balances, both books' trial balances are
zero and no line of a failed posting is left.

`tests/test_ledger_post_storm.py` (CI): 1,000 postings, 20 workers, every 7th attempt rolled back,
while a second organisation posts 200 from 4 workers — numbers 1..1000 and 1..200, all balanced
(about 25 s). `manage.py post_storm --org <public id> --n 1000 --workers 20 [--fail-every 7]` runs
it against a staging copy (scratch organisation only: it posts real journals).

## Only the service writes lines (C-02-T14)

An import-linter contract (`backend/pyproject.toml` `[tool.importlinter]`, custom type
`ledger_writes` in `backend/tools/import_contracts.py`; CI step "import-linter" runs
`lint-imports` in `backend/`): **only `numo9.ledger.services` writes `JournalLine`**. Other apps
must import `numo9.ledger.models` (accounts; entries to read), so a module-level *forbidden*
contract can't express it: the contract takes every module of `numo9` that imports the ledger
models from the import graph and fails on a journal-line write in its code — `JournalLine(...)`,
`JournalLine.objects`/`_base_manager` `.create`/`.bulk_create`/`.get_or_create`/
`.update_or_create`/`.update`/`.bulk_update`/`.delete` (also at the end of a queryset chain) — and,
in any module, raw SQL `INSERT INTO`/`UPDATE`/`DELETE FROM ledger_journalline`. Migrations are
skipped; reads are fine anywhere. The database triggers (C-02-T04) remain the last line.

## Journals read API (C-02-T15)

| Endpoint | Answer |
|---|---|
| `GET /api/v1/o/<org>/journals` | Entries newest first (date, number): `id`, `number` (`JE-000042`), `date`, `type`, `status`, `narration`, `source` (`type`, `id`), `book_scope`, `total` (Σ debits), `lines` (count), `reversal_of` / `reversed_by` (`id`, `number`); `count`, `next_offset`. Filters: `status` (comma-separated; default posted + reversed), `from`, `to`, `type`, `source_type` + `source_id` (one document's entries), `account` (public id: entries with a line on it), `book` (`accounting` / `tax`: entries in that book), `q` (narration, or a number `JE-000042` / `42`); `limit` 1–200 (50), `offset`. A bad filter is a 400 naming it |
| `GET /api/v1/o/<org>/journals/<id>` | The entry plus every line (`line`, `account` `{id, code, name}`, `debit`, `credit`, `book`, `contact` `{id, name}`, `description`, `tax_code`, `tracking`), `books` (debit and credit totals of each book it touches), `posted_by`, `posted_at` and `audit` (action, by, at — posted, reversed…) |

Amounts are strings with two decimals. Permission `accounting.journals.view` (risk low; the
accounting roles have it); feature `accounting.journals.read` (402 outside the package); another
organisation's journal is a 404; documented in the OpenAPI schema (`journals_list`,
`journals_get`). Tenant sweep factory `ledger.JournalEntry` posts a journal through the service.
Read-only: nothing writes entries but the posting service.

## Trial balance per book (C-02-T11)

`numo9.ledger.trial_balance.trial_balance(book, as_of=None, include_zero=False) → TrialBalance` for
the active organisation:

- `book` is required: `accounting` (lines `both` + `accounting`) or `tax` (lines `both` + `tax`);
- posted and reversed entries only (a reversal and its original net to zero); drafts and entries
  awaiting approval never count; `as_of` limits to entries dated on or before it;
- one grouped query on the organisation's lines (`(organisation, account, book)` index) joined to
  the entries for status and date; account code and name from a second small query;
- rows (`TrialBalanceRow`: account, code, name, type, `debit`, `credit`, `balance` = debit − credit,
  `debit_balance`/`credit_balance` for the report columns) in code order; accounts whose debits
  equal their credits are left out unless `include_zero`;
- `total_debit`, `total_credit`, `total_balance` and `balanced`: every entry balances in each book
  it touches (C-02-T06), so each book's trial balance sums to zero.

## Tests

| Task | Tests |
|---|---|
| T02 | `tests/test_ledger_journal_models.py` |
| T04 | `tests/test_ledger_append_only.py` |
| T05 | `tests/test_ledger_sequence.py` (incl. threads on real connections) |
| T06 | `tests/test_ledger_validation.py` (incl. Hypothesis) |
| T07 | `tests/test_ledger_periods.py` |
| T08 | `tests/test_ledger_post_journal.py` |
| T09 | `tests/test_ledger_journal_states.py` (every pair of states) |
| T10 | `tests/test_ledger_reverse.py` (incl. two threads reversing at once) |
| T12 | `tests/test_ledger_post_storm.py` |
| T14 | `tests/test_ledger_write_contract.py` (fixture `tests/fixtures/ledger_writes/direct_write.py.txt`) |
| T15 | `tests/test_ledger_journals_api.py` (+ `tests/test_tenant_sweep.py`) |
| T11 | `tests/test_ledger_trial_balance.py` (incl. Hypothesis, cumulative ledger) |
| T13 | `tests/test_ledger_posting_property.py` — 10,000 Hypothesis examples: random valid journals (1–3 books, 2–8 lines, 0.01–10,000,000,000.00) are posted and each book's trial balance sums to zero; random invalid ones (11 defects: too few lines, a cent off, float, third decimal, negative, both/no side, unknown book, archived/parent/foreign account) are rejected with the defect's code and write nothing (no entry, line or number). About 4–5 minutes; `NUMO9_PROPERTY_EXAMPLES=500` for a quick local run |
| T17 | `tests/test_ledger_trial_balance_performance.py` — 100,000 posted lines (10,000 entries × 10 lines over 40 accounts, three book groups) plus 20,000 lines of another organisation, inserted with `generate_series` the engine's way (drafts, lines, then Posted with consecutive numbers): the accounting and tax trial balances each answer in < 1 s (about 0.1 s here), balanced; a half-year as-of report too |

`tests/ledger_helpers.post_for_test(spec, reversal_of=None, audit=True)` posts the way the engine
will (validate → lines while draft → number → Posted, one transaction) until `post_journal`
(C-02-T08) existed; it stays as a fast fixture for the property and performance tests (`audit=False`), never production code.

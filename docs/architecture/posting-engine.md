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
| T11 | `tests/test_ledger_trial_balance.py` (incl. Hypothesis, cumulative ledger) |
| T13 | `tests/test_ledger_posting_property.py` — 10,000 Hypothesis examples: random valid journals (1–3 books, 2–8 lines, 0.01–10,000,000,000.00) are posted and each book's trial balance sums to zero; random invalid ones (11 defects: too few lines, a cent off, float, third decimal, negative, both/no side, unknown book, archived/parent/foreign account) are rejected with the defect's code and write nothing (no entry, line or number). About 4–5 minutes; `NUMO9_PROPERTY_EXAMPLES=500` for a quick local run |

`tests/ledger_helpers.post_for_test(spec, reversal_of=None, audit=True)` posts the way the engine
will (validate → lines while draft → number → Posted, one transaction) until `post_journal`
(C-02-T08) exists; it is a test fixture, never production code.

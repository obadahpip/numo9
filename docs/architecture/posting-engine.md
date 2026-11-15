# Posting engine (C-02)

| | |
|---|---|
| **Deliverable** | C-02 · Journal posting engine, Phase 0 (component C — General ledger) |
| **Branch** | `feature/C-02-posting-engine` |
| **Decision** | [ADR-0003 — Posting engine and book dimension](../adr/0003-posting-engine-and-book-dimension.md) |
| **Code** | `backend/numo9/ledger/` (models: `JournalEntry`, `JournalLine`, `JournalSequence`; `sequence`; migration `0004_journal_append_only`) |
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

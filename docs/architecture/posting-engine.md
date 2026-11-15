# Posting engine (C-02)

| | |
|---|---|
| **Deliverable** | C-02 · Journal posting engine, Phase 0 (component C — General ledger) |
| **Branch** | `feature/C-02-posting-engine` |
| **Decision** | [ADR-0003 — Posting engine and book dimension](../adr/0003-posting-engine-and-book-dimension.md) |
| **Code** | `backend/numo9/ledger/` (models: `JournalEntry`, `JournalLine`) |
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

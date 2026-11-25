# Find & recode with undo (C-07)

Bulk recoding of posted journal lines — account, tax code, tracking, contact — without ever
editing a posted entry (ADR-0003, append-only ledger). Closes gap 35 of the Xero teardown.

## Pieces

| Module | Task | What it does |
|---|---|---|
| `ledger/recode_query.py` | C-07-T02 | Conditions (`{match, conditions: [{field, op, value}]}`) → an ORM filter over `JournalLine`, scoped to the organisation's partition |
| `ledger/recode_exclusions.py` | C-07-T03 | Locked / closed / filed periods, void documents, superseded revisions, reversals, system journals → excluded with a reason code; apps register their checks |
| `ledger/recode_preview.py` | C-07-T04, T06 | Before / after per line, totals per book (must be unchanged), account movements, tax impact; each line's `fingerprint` |
| `ledger/recode_execute.py` | C-07-T05, T06 | Draft batch → run: per entry, under a row lock, `reverse()` + `post_journal(caller="recode")` with the new coding, documents repointed to the re-post, one `RecodeLineChange` per line; > 200 lines as the job `numo9.ledger.recode`; changed lines are conflicts |
| `ledger/recode_undo.py` | C-07-T07 | Undo latest first: reverse each live re-post, post it again with the coding `before`; refused with the blocking entries when a period is locked, closed or filed, or a later batch recoded the lines |
| `ledger/recode_report.py` | C-07-T08 | The batch's audit report as CSV / XLSX / PDF (one row per `RecodeLineChange`) |
| `ledger/recode_api.py` | C-07-T09 | `/api/v1/o/<org>/recode/` — search, preview, execute, batches, undo, report; permission `accounting.recode`, feature key `accounting.recode.write` |
| `frontend/src/accounting/recode/` | C-07-T10 – T13 | Condition builder, results grid (select all across pages, Excluded tab), preview diff + confirm, progress, history with Undo and reports |

## Data

`RecodeBatch` — the search (`criteria`), the new coding (`changes`), the chosen lines
(`selection`, with fingerprints; `null` = every line found), status (`draft → running →
completed | failed → undone`), counts, `problems` (entries not recoded and why), the background
job, who ran / undid it and when.

`RecodeLineChange` — one per recoded line: the original entry and line, coding `before` / `after`
(public ids), the amounts (unchanged), the fingerprint, the reversal and the re-post — and, once
undone, the undo reversal and the restored entry.

## Rules

- **Amounts never change.** The preview raises if debits or credits would differ; each re-post
  copies the original's lines and amounts, only the chosen lines' coding changes.
- **One transaction per entry.** The entry row is locked (`SELECT … FOR UPDATE`), reversed on its
  own date and posted again on that date; a posting refused (a rule of the new account, a lock
  set meanwhile) leaves that entry as it was and is listed in `problems`.
- **No approval gate, no cash guard** for re-posts (`caller="recode"`): the entry posted already.
  Account flags (required contact / tracking / attachment), locks, closed periods and the tax lock
  apply as to any posting.
- **Optimistic re-validation** (T06): a chosen line whose fingerprint (entry state, coding,
  amounts) differs at execute, or that the search no longer finds, is a conflict.
- **Documents follow the re-post**: every model with a one-to-one `journal_entry` to the ledger
  (invoices, credit notes, bills, supplier credits, bank transactions) is repointed, so voiding a
  document reverses the live entry.
- **Undo** follows each line down the chain (a later batch undone in between) to the entry that
  carries it now.

## Performance (T14)

`tests/test_recode_performance.py`: 10,000 lines (1,000 entries) recoded among 110,000 posted
lines in about 90 s locally (budget 120 s). The posting validator looks up the parents of all a
journal's accounts in one query (`validate_journal`), which every posting benefits from.

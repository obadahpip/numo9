# Finding and recoding transactions

Go to **Accounting › Find and recode** (`/o/<organisation>/accounting/recode`). You need the
permission *Find and recode posted transactions in bulk, and undo a recode* — owners, admins and
your accountant (an accountant or accountant delegate) have it.

## 1. Find the lines

Build the search on the left: choose **Find lines matching all conditions** or **any
condition**, then add conditions — type, status, account, bank account, date (on, before, after,
between), amount (equals, more than, at least, less than, at most, between), tax code (is, is
one of, is empty), entered by, contact (is, is empty), journal number, reference (text in the
narration or the line description), tracking (category and option) and book (both, accounting,
tax). Each value box fits its field: dates open a date picker, amounts take numbers, accounts are
chosen from your chart.

Select **Find lines**. The summary above the results reads, for example, *500 lines · 3 accounts
· 12 excluded*.

## 2. Choose the lines

Tick lines one by one, tick the box in the header to choose the page, then **Select all 500
lines** to choose every page. With nothing ticked, the recode applies to every line found.

The **Excluded** tab lists the lines that can't be recoded, each with the reason:

| Reason | What it means |
|---|---|
| Locked | The date is on or before a lock date that applies to you (the general ledger's, or the module's: sales, purchases, bank, payroll) |
| Closed period | The date is inside a closed fiscal year |
| Filed period | The line carries a tax code (or the recode changes tax codes) in a filed GST/HST or QST period — a filed return can't move |
| Void document | The entry of a void invoice, credit note or bill |
| Revised document | An earlier posting of a document that was revised since: only its current revision is recoded |
| Reversed | The entry was reversed, or reverses another entry |
| System journal | A closing, payroll or depreciation journal: its own module owns its coding |

## 3. Choose the new coding and preview

Under **New coding**, choose any of: the new account, the new tax code (or *Remove the tax
code*), a tracking category and option, the new contact (or *Remove the contact*). A field left
empty keeps its value.

Select **Preview the recode**. The preview shows every line **before and after**, the changed
values marked, and the debits and credits of each book — the same before and after: a recode
never changes an amount. When a tax code changes, the preview shows how much the tax those lines
carry changes by; you confirm it before the recode runs.

## 4. Recode

Name the recode if you like, then select **Recode … lines**. The dialog gives the numbers: the
entries reversed and posted again, the debits and credits that stay the same, the lines left out.

Each affected entry is **reversed and posted again** on its own date with the new coding, in one
step per entry — the books keep the full history (append-only). The documents behind the entries
(an invoice, a bill, a bank transaction) follow the new entry, so voiding one later still works.

More than 200 lines run in the background: a progress note shows *Recoding 240 of 500 lines…*
until it finishes. If someone changed one of your lines between the preview and the recode (they
recoded or reversed it), that line is left as it is and listed as *not recoded* — preview again
to include it.

## 5. History, report and undo

**Recode history** lists every recode with who ran it and when, its lines and status, and its
audit report as CSV, Excel or PDF — one row per recoded line with the coding before and after
and both journal numbers.

**Undo** puts every line back the way it was (the re-posted entries are reversed and posted again
with the old coding). It is available while every period the recode touched is open. When it
isn't, the button is disabled and the reason is shown next to it — the entries in a locked,
closed or filed period. A line recoded twice is undone latest first: undo the later recode before
the earlier one.

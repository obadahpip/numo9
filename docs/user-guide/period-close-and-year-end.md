# Closing periods and the fiscal year

Go to **Accounting › Period close** (`/o/<organisation>/accounting/period-close`).

## The timeline

Each module — general ledger, sales, purchases, bank, payroll and sales tax — has a pill per
month of the fiscal year:

- **Closed** — the month was closed: nothing dated in it can be posted in that module, by anyone;
- **Locked** — a lock date covers it (Settings › Lock dates) without a close;
- **Open**.

Use the arrow keys to move between months, and select one to see its checklist.

## Before closing: the checklist

The checklist counts what is still open in the month, with a link to the list that fixes each:
drafts dated in the month, documents waiting for approval, GST/HST or QST periods ended and not
filed, and exceptions — recurring journals skipped and automatic reversals that couldn't be
posted. The counts don't stop you closing.

## Close a month

Select **Close** on the month. Periods close in order: you can't close May once June is closed.
Closing moves the module's lock date to the last day of the month for everyone, advisers
included. A recurring journal or an automatic reversal due in a closed month isn't posted: it
shows as an exception on the checklist.

## Close the fiscal year

**Close the fiscal year** posts a closing journal per book — accounting and tax — dated the last
day of the year: every revenue and expense account goes to zero and the year's profit or loss to
**Retained earnings** (each book with its own net income when they differ). The general ledger is
closed to that day. A year is closed once: running it again is refused.

## Reopen

Only an adviser (the organisation's accountant) can reopen, with a reason kept in the audit log,
starting with the latest close. Reopening restores the lock dates as they were before the close;
reopening the fiscal year also reverses its closing journals.

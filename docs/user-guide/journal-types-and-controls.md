# Manual journals: types and controls

A manual journal moves amounts between accounts when no invoice, bill or bank transaction does
it for you: an accrual, a correction, a reclassification, a year-end adjustment. This page
explains the journal types you can choose and the checks Numo9 runs before a journal is posted
(C-03).

Open **Accounting → Journals → New manual journal** (or press ++n++ then ++j++).

## The screen

| Part | What it does |
|---|---|
| Date | The journal's accounting date. It must be in an open period (after the lock date). |
| Narration | What the journal is for. It shows in the ledger and in reports. |
| Reverse automatically on | Optional. Numo9 posts the reversing journal by itself on that date (see [Automatic reversal](#automatic-reversal)). |
| Journal type | General, Adjusting, Reclass or Tax adjustment (see [Journal types](#journal-types)). |
| Supporting documents | Drop a receipt or invoice, or choose a file. Outlined in red when the journal needs one. |
| Lines | Account, debit, credit, description and — when shown — contact. A line holds a debit **or** a credit. |
| Post journal / Save as draft | Post now, or keep a draft to finish later. |

As you type, Numo9 asks the server what it would say about the journal. Problems are listed
under the lines **before** you post, so you never lose your work to a refusal.

## Journal types

| Type | Use it for | Who sets it |
|---|---|---|
| **General** | Everyday entries that aren't one of the other types. The default. | You |
| **Adjusting** | Period-end adjustments: accruals, prepayments, corrections found during review. | You |
| **Reclass** | Moving an amount from one account to another without changing the total. | You |
| **Tax adjustment** | Entries for the **tax book only** (two-book organisations). | You |
| Closing | The year-end close. | The year-end process only |
| Payroll | Payroll postings. | The payroll module only |
| Depreciation | Depreciation runs. | The fixed-asset module only |

The last three are *system types*: they are never offered in the picker, and a journal of a
system type posted by anyone but its process is refused (`ledger.journal.system_type`).

**Tax adjustment** journals have two extra rules:

- every line goes to the tax book (`ledger.journal.tax_adjustment_book`);
- no line may be on a bank account (`ledger.journal.tax_adjustment_bank`).

## Contacts on lines

Each line can name a contact (a customer or a supplier). The contact feeds the customer and
supplier sub-ledger views, so a journal on Accounts receivable can say *whose* balance it changes.

- The **Contact** column is hidden by default. Use **Show contact column** to add it.
- When you choose an account that **requires a contact** (an account setting in the chart of
  accounts, e.g. Accounts receivable), the column appears by itself and the cursor moves to that
  line's contact. The cell says *This account needs a contact.* until you pick one.
- While such an account is on a line, the column stays: **Hide contact column** is disabled.

## Controls before posting

Numo9 refuses or warns about a journal for these reasons. Every message names the line, the
account or the amount concerned.

### Account settings

Accounts in the chart of accounts can require more than an amount:

| Account setting | A line on that account needs | Code |
|---|---|---|
| Require contact | a contact on the line | `ledger.journal.contact_required` |
| Require tracking | a tracking category | `ledger.journal.tracking_required` |
| Require attachment | a document attached to the journal | `ledger.journal.attachment_required` |

### Expense journals

Your organisation can ask for more on manual journals that touch an **expense** account. Both
settings are off by default and every change is recorded in the audit log:

| Organisation setting | When it is on | Code |
|---|---|---|
| `journal_expense_requires_attachment` | an expense journal without an attachment is refused | `ledger.journal.expense_attachment_required` |
| `journal_expense_requires_contact` | every expense line needs a contact | `ledger.journal.expense_contact_required` |

When a document is needed, the drop zone is outlined in red, **Post journal** is disabled and its
tooltip says *Attach the supporting document first.* Saving a draft is still allowed.

### Bank or cash below zero

A journal that would take a bank or cash account (chequing, savings, petty cash…) **below zero**
is caught before it posts. Numo9 checks the balance:

- at the end of the journal's date, **and**
- on every later day up to today, counting entries already dated after the journal.

A backdated journal can push a past day below zero even when today's balance is positive — that
day is the one shown. The bank line gets a chip, for example *Petty Cash would be −994.17 on
15 Jun 2026*.

| You are | What happens |
|---|---|
| Not an adviser | The journal is **blocked**: *A journal can't take a bank or cash account below zero.* Ask an adviser, or record the missing deposit first. |
| An adviser | A dialog asks for a **reason of at least 10 characters**. The journal posts with the reason, which is stored with your name and the time and shown in the audit log. |

Journals posted by Numo9 itself (scheduled jobs) are not subject to this check.

### Approval

When your organisation sets a journal approval threshold, a journal at or above it must be
submitted and approved before it posts. The approver can never be the person who created the
journal, and their approval limit must cover the journal's total.

## Automatic reversal

Set **Reverse automatically on** to have Numo9 post the reversing journal on that date — useful
for accruals you will replace with the real bill next month.

- The date must be **after** the journal's date (`ledger.journal.auto_reverse_before`).
- It must be in an open period; a date on or before the lock date is refused when you save
  (`ledger.journal.auto_reverse_locked`).
- The reversal is posted exactly once, even if the background job runs again, and appears in the
  audit log as posted by the scheduled job.

## Languages

Every label, message and error on this screen is available in English (Canada) and French
(Canada). Error codes stay the same in both languages, so support can find a message whichever
language you work in.

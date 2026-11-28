# Bank accounts without feeds

F-01-T17 · Deliverable F-01 (gap-27). In Numo9 a bank, credit-card or cash account works the
moment you add it: no bank feed, no statement import, no reconciliation and no plan upgrade is
needed to record money in and out, and nothing else is blocked while you have none. Feeds and
statement imports (F-02) and reconciliation (F-05) are optional extras that check the books
against the bank — they never gate them. The decision is
[ADR-0007](../adr/0007-bank-accounts-never-depend-on-a-feed.md).

## 1. Add the account

Go to **Banking** (`/o/<organisation>/banking`) and select **Add account** (or press `N` `A`
anywhere). The side sheet asks four things:

| Field | What to enter |
|---|---|
| Type | Chequing, Savings, Credit card, Line of credit, Loan, Cash / petty cash or Clearing. The help under each type says what it is for. |
| Name | How the account is called everywhere, e.g. *TD Business Chequing*, *Visa Business*, *Petty Cash*. Unique in the organisation. |
| Institution | The bank or card issuer (Canadian banks are suggested), optional. |
| Currency | CAD by default. It can't be changed once the account has transactions. |

Select **Add account**: *TD Business Chequing is ready.* — with **Record a transaction** as the
next step. Numo9 also creates the account in your chart of accounts, typed from the account type:

| Type | In the chart of accounts | Codes |
|---|---|---|
| Chequing, Savings, Cash / petty cash, Clearing | Current asset (bank) | 1000–1099 |
| Credit card, Line of credit | Current liability | 2100–2199 |
| Loan | Non-current liability (or current, when you say it is repaid within a year) | 2700–2799 |

You can add the last four digits of the account number later; they are stored encrypted and
always shown masked (•••• 4821).

## 2. Record money in and out straight away

- **Spend money** (`N` `S`) — paying a supplier, a card purchase, cash out of the till. Choose the
  bank account, the date, optionally the contact and a reference, whether amounts include tax,
  then the lines: account, description, amount and tax code. Only purchase tax codes are offered,
  and the account's default code is filled in (for example *HST on purchases*).
- **Receive money** (`N` `R`) — money in that isn't an invoice payment: the owner's deposit, a
  refund, interest. Only sales-side tax codes are offered.
- A credit-card payment from chequing is a **transfer** between two of your accounts, not spend
  money (the transfer screen comes with the transfers deliverable, F-06).

Each transaction posts a balanced journal at once: a spend of 113.00 including HST on office
supplies posts Dr Office supplies 100.00 / Dr GST/HST receivable 13.00 / Cr the bank 113.00. The
usual journal rules apply — lock dates, required contacts or attachments set on the account — and
a spend that would take a bank or cash account **below zero** is stopped with the amount it is
short ([Bank or cash below zero](journal-types-and-controls.md#bank-or-cash-below-zero)): record
the money that came in first.

## 3. See it in the reports

The balance on each account card is the **ledger balance**: the posted transactions of its
account in the chart, the same figure as the trial balance and the **Balance Sheet** (a bank
account under current assets, a card or line of credit under current liabilities, shown as
*owed*). It is never typed in. Open an account to see its transactions with a running balance;
the last row's balance is the ledger balance. You can export the list as CSV or XLSX.

## Reconciliation is optional

Every card shows **Not reconciled — optional** until you choose to reconcile. You can type the
balance of your last bank statement and its date on the account: it is shown beside the ledger
balance so a difference stands out, and nothing depends on it. No screen, report, filing or
action waits for a feed, an import or a reconciliation.

## No bank account yet?

An organisation without any bank account sees **Add your first bank account** on Home and on
Banking — a reminder, not a gate: you can still post journals, invoices and bills. Dismiss it and
it stays hidden for 7 days (for you only).

## Archiving instead of deleting

An account with transactions can't be deleted (*has 1 transaction — archive instead*): archive it.
An archived account disappears from the pickers on new transactions but stays in the reports and
its history; it can be restored. Renaming the account renames its chart account too; the audit
log keeps the old and the new name.

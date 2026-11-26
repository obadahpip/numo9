# Entering conversion balances

Go to **Accounting › Conversion balances** (`/o/<organisation>/accounting/conversion`). Xero's
old address (`Setup/Welcome/EditConversionBalances.aspx`) lands here too.

Conversion balances are where your books start in Numo9: the balances of your old books at the
**conversion date** and the customer invoices and supplier bills still open that day. You enter
them once, in a guided wizard, and finalise them: one opening journal is posted.

## The steps

The wizard has six steps, shown at the top: **Conversion date → Bank and cash → Open invoices →
Open bills → Other balances → Review and finalise**. **Save and continue** saves the step and
moves on; every step is saved as you go, so you can leave and come back later — the wizard opens
on the step you were at. Select any step at the top to go back to it.

### 1. Conversion date

The first day your books are kept in Numo9 — usually the day after the last closed period in
your old system (for a calendar year: 1 January). Balances are as at the day before. You can
change the date until you finalise.

### 2. Bank and cash

Enter each bank and cash account's balance from its statement at the day before the conversion
date. An overdrawn account is a credit: it is allowed, and flagged on the Review step so you can
verify the statement.

### 3 and 4. Open invoices and open bills

Enter each invoice still open, and each bill still unpaid, **one per row**: customer (or
supplier), number, date, due date, total and — for a document partly paid before the conversion
date — what was **still owed**. You can **paste the rows from a spreadsheet** (copy the cells,
then paste into the first cell of the grid; a header row is skipped). **Verify the rows** checks
every row without saving; **Add documents** saves them all, or none when a row has a problem
(the problem is shown on its cell and listed under the grid).

These documents are real invoices and bills, marked as opening balances: they appear in aging,
statements and reminders and are paid like any other — but they post nothing themselves. Their
total must equal the **Accounts receivable** (invoices) and **Accounts payable** (bills) balance
you enter on the next step. An invoice keeps its number from your old system; a bill keeps the
supplier's invoice number and takes an `OB-0001` number of its own. Until you finalise, a
document can be removed; afterwards it can't be voided (see *Corrections* below).

### 5. Other balances

Every other balance of your old trial balance: Accounts receivable and payable, other assets,
loans, share capital, retained earnings… For an account that requires a contact (a shareholder
loan), choose the contact. Your accountant can also import the whole trial balance from a CSV or
Excel file (column mapping, with a dry run that lists the problems row by row).

If you convert at the start of a fiscal year and your trial balance includes revenue and expense
accounts, their net is opened to **Retained earnings** (the new year starts at zero). For a
mid-year conversion they are opened to their own accounts, so the year-to-date figures are
complete.

### 6. Review and finalise

The review shows the receivable and payable controls against their open documents, and warns
when **no equity** was entered (no share capital, no retained earnings — unusual for an existing
business) or when a bank account opens overdrawn.

## The difference meter

A bar stays at the bottom of every step: **Debits · Credits · Difference**, updated as you type.
**Finalise** is unavailable — and says why, next to the figures and on the button's tooltip —
while:

- the difference isn't 0.00 ("The balances are out by 12.50…");
- Accounts receivable or payable doesn't equal its open documents (the account and both figures
  are named);
- an account that requires a contact has none, or nothing was entered.

Nothing is plugged: unlike Xero, Numo9 never pushes a difference to a "historical adjustment".
If you must finalise with an amount you can't explain yet, add it yourself on the **Conversion
balances suspense** account — it stays visible and is flagged for review until it is cleared.

## Finalise

**Finalise** asks for confirmation, then posts **one opening journal** (type *Opening balance*,
journal type Adjusting) dated the conversion date, with Accounts receivable and payable split by
customer and supplier. Afterwards the balances and documents can't be edited.

**Lock balances** (on the Review step) also moves the lock dates of the general ledger, sales and
purchases to the day before the conversion date, for everyone except advisers — so nothing is
posted before your books start. A later lock already set isn't moved back; every change is in the
lock dates' history.

## Corrections

A balance found wrong after finalising is corrected by your **adviser** (the organisation's
accountant) with a **correcting opening journal**, with a reason: it is dated the conversion
date, linked to the conversion, and the original opening journal is never changed.

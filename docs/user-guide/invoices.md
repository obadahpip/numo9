# Creating and approving invoices

An invoice is written as a **draft**, then **approved**: approval gives it its number and posts
it to the ledger. A posted invoice isn't edited — it is emailed, paid, copied, or voided.

Open **Sales → New invoice** (`/o/<organisation>/sales/invoices/new`, or press **N** then **I**
anywhere). You need *Create and edit draft invoices* (`sales.invoices.write`) to write one and
*Approve, post and void invoices* (`sales.invoices.approve`) to approve or void it.

## Writing the invoice

| Field | What it does |
|---|---|
| Customer | Who you invoice: their address, language and payment terms come with them |
| Invoice date | The date the invoice posts on — and the date the lock dates and the GST/HST period are checked against |
| Due date | Leave it empty to use the customer's payment terms |
| Reference | The customer's purchase order or your own reference |
| Amounts are | Tax exclusive, tax inclusive, or no tax |

The lines work like every document grid: an item or a description, the quantity, the unit
price, a discount (`10%` or an amount), the revenue account and the tax code. The first line
starts on your first revenue account and each line's tax code comes from the customer and the
account (the dot shows a code you changed). The totals show the tax of each component (GST, HST,
PST, QST) separately.

**Attachments** — attach a signed purchase order, a timesheet or any file: it stays with the
invoice (it isn't emailed with it).

A first invoice takes four steps: choose the customer, describe the line, type its price,
**Approve**.

## The period ribbon

Above the form, the ribbon says what the invoice's date falls in:

- **Open period** — it can be approved;
- **Locked** — the date is on or before the sales (accounts receivable) lock date; approving is
  refused and the message names the lock: *"INV-0007 can't be approved: it is dated 15 Mar 2026,
  on or before the Sales and accounts receivable lock date (31 Mar 2026, everyone)."*;
- **GST/HST period … is filed** — the date is in a filed return's period; approving is refused
  with the period and its confirmation number. Date the invoice in an open period (its tax then
  goes on that return), or have it posted as a late adjustment of the filed period.

## The action bar

| Status | Actions |
|---|---|
| Draft | Save draft, Approve (or **Submit for approval** when your organisation's approval rule applies), Preview posting, Delete draft |
| Awaiting approval | Approve and post (someone other than the person who submitted it), Preview posting |
| Approved, Sent | Email, PDF, Copy, Copy to quote, Void, Preview posting |
| Partially paid, Paid | Email, PDF, Copy, Copy to quote, Preview posting |
| Void | PDF, Copy, Preview posting |

**Preview posting** opens the journal the invoice posts: Accounts receivable debited, each revenue
account and **each tax control account** (GST/HST payable, PST payable, QST payable) credited
separately, with the totals. What the preview shows for a draft is exactly what approval posts;
on a posted invoice it shows the posted journal.

**Approve** saves the draft first, then posts it. When the customer is over their credit limit
the editor says so; in block mode an override must be approved first.

**Void** reverses the invoice's journal on the void date you choose (the invoice's own date when
left empty) and keeps the number — numbers are never reused. An invoice with payments can't be
voided.

**Copy** makes a new draft with the same customer and identical lines, dated today; **Copy to
quote** makes a quote of it.

# Bills and the purchases overview

A bill records what a supplier invoiced you. Entering it doesn't touch the ledger; **approving**
it posts it to accounts payable (AP) and to the GST/HST you can recover (input tax credits, ITC).

## The purchases overview

**Purchases** (`/o/<organisation>/purchases`) is the same overview page as Sales: one layout, one
set of rules.

- **Status tiles** — *Draft*, *Awaiting approval*, *Awaiting payment* and *Overdue*, each with the
  number of bills and their amount. Drafts and bills awaiting approval count their total; posted
  bills count what is still owed (the total less any holdback still held and the payments).
  Click a tile to open the bills list on the tab of the same name: the tab shows the same count,
  because both come from the same query.
- **Overdue** means awaiting payment (or partially paid), with a due date before **today where
  your organisation is** (its time zone, Settings → General) and something still owed. The line
  under the tiles names the date used.
- **Money going out** — what you owe by age of the due date: *Current* (not due yet, or no due
  date), *1–30 days*, *31–60 days*, *61–90 days* and *Over 90 days* past due. The bar darkens with
  age, and every bucket is named with its amount below it.
- **Suppliers you owe the most** — the five largest open balances, with the overdue part.

Each card loads on its own. If one can't be loaded, it says which one and why, offers **Try
again**, and shows a **reference** (for example `Reference: web-5f1c9e2a…`): give it to support
if the problem keeps happening. The rest of the page keeps working. A new organisation sees `0`
and `$0.00` everywhere, never a blank, and a link to enter its first bill.

## The bills list

**Purchases → Bills** has a tab per status, each with its count: *All*, *Draft*, *Awaiting
approval*, *Awaiting payment* (partially paid bills included), *Overdue*, *Paid* and *Void*.
Search finds a bill by its number, the supplier's name, the supplier's invoice number or the
reference. Long lists come 50 bills a page, newest first. Click a number to open the bill.

## Entering a bill

**New bill** opens the editor beside the supplier's document: drop the PDF or picture on the left
(or start from the documents inbox with **Create a bill**) and type the bill on the right without
leaving the page.

- **Supplier invoice number** — checked as you type. A number the supplier already used on
  another bill shows *Already used on BILL-0042 (12 Sep 2026)* with a link to that bill, and the
  bill can't be saved with it. Two different suppliers may use the same number. Your organisation
  can require the number before a bill is approved (an organisation setting).
- **Possible duplicates** — a bill from the same supplier, for an amount within 1 % and dated
  within 10 days, is listed as a warning. It is only a warning: review it before approving.
- **Lines** — the shared document grid with the purchase accounts (expenses, assets, cost of goods
  sold) and the purchase tax codes. Meals and entertainment codes recover only part of the tax:
  the recoverable part goes to ITC and the rest to the expense.
- **Holdback** (construction) — an amount or a percentage of the total, held back from what is
  payable now.
- **From a purchase order** — a bill created from a PO or a goods receipt is filled with what was
  received and isn't billed yet; the match panel shows each line green (matches), amber (within
  tolerance) or red (doesn't match). A red line needs an approver to choose **Approve with
  variance**, which is recorded with their name.

## Approval

**Submit for approval** sends the bill to the right people: your organisation's routing rules
choose the approver group by amount and department, and the bill says why ("Routed to Finance
approvers (amount over $2,000.00)"). With no rule, anyone whose bill approval limit covers the total can
approve it. The bill appears in their approvals inbox.

Approving posts: Dr the expense or asset accounts, Dr ITC receivable (the recoverable tax, only
when your organisation is GST/HST registered on the bill date), Dr the expense for tax you can't
recover, Cr accounts payable, and Cr holdback payable for any holdback. A bill takes its number
(`BILL-0001`) when it is approved.

## Releasing a holdback

**Release holdback** on a posted bill moves all or part of the amount held back to what is
payable now (Dr holdback payable / Cr accounts payable), on the date you choose.

## Correcting a posted bill

A posted bill isn't edited. **Void** it with a date and a reason: its journal is reversed on that
date and it shows on the *Void* tab. A date before a lock date is refused, naming the lock date.

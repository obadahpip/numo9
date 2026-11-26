# Purchase orders and goods receipts

A purchase order (PO) records what you ordered from a supplier. It never posts to the ledger: it
is a **commitment** until the bill arrives.

## Statuses

Draft → Awaiting approval → Approved → Partially received → Received → Billed, or Closed /
Cancelled. A PO takes its number (`PO-0001`) when it is approved.

**Purchases → Purchase orders** lists them with one tab per status — All, Draft, Awaiting
approval, Approved, Partially received, Received, Billed, Closed, Cancelled — each with its
count; the search box (number, reference or supplier) narrows the tabs and their counts alike.
From a row: **Receive** (approved or partially received POs) and **Create bill** (approved,
partially received or received POs).

## Writing a purchase order

**New purchase order** (or press **N** then **P** anywhere): choose the supplier, the order date
and a reference, then the lines on the same grid as bills — accounts are limited to expense,
asset and cost-of-sales accounts and tax codes to purchase codes. The **Delivery** block says
where and when to deliver: *Deliver to* (the address), *Attention*, *Delivery date* and
*Instructions*; it prints on the PO.

Under the totals, the **approval limit indicator** compares the total with your purchase-order
approval limit as you type:

- "Within your approval limit of $5,000.00" — the main button is **Approve**;
- "$6,000.00 is above your approval limit of $5,000.00" — the main button is **Submit for
  approval**;
- "You have no purchase order approval limit" — **Submit for approval** too.

**Cancel order** cancels a PO; one with receipts or bills is **closed** instead (what arrived and
what was billed stay on record; the outstanding quantities are dropped). **Close order** closes a
received PO.

## Approval

Each person approves POs up to their **purchase-order approval limit** (Settings → Users and
roles → Approval limits). Within your limit, **Approve** approves at once; above it — or with no
limit — the PO goes to **Awaiting approval** and appears in the approvals inbox of the people
whose limit covers it. Nobody approves a PO they wrote or submitted.

If an approved PO is edited and its total goes **up**, it goes back to Awaiting approval (it keeps
its number). Lowering the total keeps it approved.

## Receiving

**Receive goods** (on the PO, or **Receive** in the list) opens the receive screen: per line the
quantity ordered, received so far and outstanding, and a large *Receiving now* field. Type the
quantity and press **Enter** to move to the next line; Enter on the last line records the
receipt (a barcode scanner that types a quantity and Enter works the same way). **Receive
everything outstanding** fills every line. Set the date received and a note (packing slip,
damage) above the table.

A line typed beyond what was ordered says so at once ("2 more than ordered"). Received 6 of 10
leaves 4 outstanding and the PO is **Partially received**; once every line is in, it is **Received**. Receiving more than ordered is
allowed up to the **over-receipt tolerance** (a % of the ordered quantity, in the organisation
settings). Beyond it, the organisation chooses: *warn* (you confirm and it is received) or
*block* (refused). With *warn*, the screen lists the lines over the tolerance and **Receive
anyway** records the receipt.

A receipt entered by mistake is **reversed** with a reason: its quantities come off the PO and the
outstanding quantities are back. The reversed receipt stays in the history.

Items aren't stock-tracked yet: receipts record the quantities on the PO; stock follows when
inventory arrives.

## Billing and the 3-way match

**Create bill** makes a draft bill of what was **received and isn't billed yet** (for a PO with
nothing received at all — services — what was ordered), at the PO's prices, accounts and tax
codes, and opens it.

Each bill line from a PO is matched three ways — what was **ordered**, what was **received** and
what is **billed** (this bill plus the other bills on the line), at the bill's price against the
PO's:

| Result | When |
|---|---|
| Green — *Matches* | Billed no more than ordered and received, at the PO's price |
| Amber — *Within tolerance* | More than ordered or received, or another price, within the tolerance |
| Red — *Doesn't match* | Beyond the tolerance — e.g. a bill for 12 against a PO for 10 |

The tolerances are in the organisation settings: **match quantity tolerance** and **match price
tolerance** (a percentage; empty = the over-receipt tolerance). An amber or red line needs an
approver to **Approve with variance**. A bill entered before the goods arrive is allowed: the
match says *nothing received yet: match pending the receipt*.

## Sending to the supplier

An approved PO is emailed to the supplier's people marked *Include in emails* with the PO
attached as a PDF (Letter, your branding, the delivery block, tax per component), in the
supplier's language.

## Commitments

**Commitments** (from the purchase order list) shows the value ordered and not yet billed, before
tax — by account, by supplier or by month of the PO, optionally between two PO dates — with the
number of open POs and lines per row and the total. Drafts, POs waiting for approval and billed,
closed or cancelled POs aren't commitments. The *Budget* column fills in when budgets arrive.

**Export CSV** and **Export Excel** download exactly what is on screen: the same grouping and
dates, the same rows in the same order, and the total.

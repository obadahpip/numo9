# Purchase orders and goods receipts

A purchase order (PO) records what you ordered from a supplier. It never posts to the ledger: it
is a **commitment** until the bill arrives.

## Statuses

Draft → Awaiting approval → Approved → Partially received → Received → Billed, or Closed /
Cancelled. A PO takes its number (`PO-0001`) when it is approved.

## Approval

Each person approves POs up to their **purchase-order approval limit** (Settings → Users and
roles → Approval limits). Within your limit, **Approve** approves at once; above it — or with no
limit — the PO goes to **Awaiting approval** and appears in the approvals inbox of the people
whose limit covers it. Nobody approves a PO they wrote or submitted.

If an approved PO is edited and its total goes **up**, it goes back to Awaiting approval (it keeps
its number). Lowering the total keeps it approved.

## Receiving

Record each delivery against the PO's lines: received 6 of 10 leaves 4 outstanding and the PO is
**Partially received**; once every line is in, it is **Received**. Receiving more than ordered is
allowed up to the **over-receipt tolerance** (a % of the ordered quantity, in the organisation
settings). Beyond it, the organisation chooses: *warn* (you confirm and it is received) or
*block* (refused).

A receipt entered by mistake is **reversed** with a reason: its quantities come off the PO and the
outstanding quantities are back. The reversed receipt stays in the history.

Items aren't stock-tracked yet: receipts record the quantities on the PO; stock follows when
inventory arrives.

## Sending to the supplier

An approved PO is emailed to the supplier's people marked *Include in emails* with the PO
attached as a PDF (Letter, your branding, the delivery block, tax per component), in the
supplier's language.

## Commitments

The commitment report shows the value ordered and not yet billed, before tax — by account, by
supplier or by month of the PO. Drafts, POs waiting for approval and billed, closed or cancelled
POs aren't commitments.

# Quotes

A quote tells a customer what the work will cost before you do it. The customer opens it from a
link — without an account — ticks the options they want, types their name (and signs, if they
like) and accepts. An accepted quote becomes an invoice with the same lines.

Open **Sales → Quotes** (`/o/<organisation>/sales/quotes`) for the list, or **New quote**
(press **N** then **Q** anywhere). You need *See quotes and their PDF* (`sales.quotes.view`) to see
quotes and *Create, edit and send quotes, and turn accepted quotes into invoices*
(`sales.quotes.manage`) for everything else.

## Statuses

One set of statuses is used everywhere — the list tabs, their counts, the filters and the
overview:

| Status | Meaning |
|---|---|
| Draft | Being written; only a draft is edited or deleted |
| Sent | Emailed or marked sent; it has a link the customer can open |
| Viewed | The customer opened the link (shown under the **Sent** tab) |
| Accepted | The customer accepted it (or you recorded that they did) |
| Declined | The customer declined it, with their reason if they gave one |
| Expired | Its expiry date passed before anyone accepted it |
| Invoiced | It was turned into an invoice |

A quote expires at the **end of its expiry day in your organisation's time zone**: accepting at
23:59 on the expiry day works, at 00:00 the next day it doesn't. A job moves sent and viewed
quotes past their date to Expired every hour.

## Writing the quote

| Field | What it does |
|---|---|
| Customer | Who the quote is for |
| Quote date | The date on the quote |
| Expiry date | Required; 30 days after the quote date unless you change it |
| Reference, Title, Summary | Shown on the quote and its PDF |
| Amounts are | Tax exclusive, tax inclusive, or no tax |
| Deposit on acceptance | None, a fixed amount, or a percentage of the **accepted** total |

The lines are the same grid as invoices (description, quantity, unit price, account, tax code,
tax amount, amount), with three more columns:

- **Optional** — the customer may add this line. It starts unticked: it isn't in the total until
  the customer ticks it.
- **Alternative group** — type a group name (for example *Wood*) on two or more lines, or pick a
  group already used: the customer chooses **one** line of the group. A line is either optional
  or in a group, not both.
- **Included** — which optional lines and which alternative the quote starts with. Choosing an
  alternative unticks the others of its group.

The totals count only the lines that are included: every plain line, the optional lines ticked
and one line of each alternative group (a group with none chosen adds nothing).

## Sending and the customer's page

| Status | Actions |
|---|---|
| Draft | Save draft, Email to customer, Mark as sent, PDF, Copy, Delete draft |
| Sent, Viewed | Email to customer, Copy link, Withdraw links, Mark accepted, Mark declined, Revise, PDF, Copy |
| Accepted | Convert to invoice, Revise, PDF, Copy |
| Declined, Expired | Revise, PDF, Copy |
| Invoiced | PDF, Copy |

**Email to customer** sends the PDF and a link to the customer's people marked *include in
emails*. **Mark as sent** makes the link without an email: use **Copy link** to share it.
**Withdraw links** stops every link of the quote from working.

The customer's page (`/q/…`) works on a phone: the lines, a checkbox for each optional line, a
choice for each alternative group, and the totals and deposit, updated as they choose. To accept
they type their full name — that is their signature — and may also draw one. Numo9 keeps the
evidence: the name typed, the drawn signature, the IP address and browser, the options chosen and
the PDF of the quote as accepted with its SHA-256 fingerprint. Accepting twice keeps the first
acceptance. They can also decline, with a reason.

A quote that can't be accepted says why and the **Accept** button is disabled: *expired* (with
"Ask … for a new quote"), *revised* (a newer version replaces it), already accepted, declined or
invoiced.

## Changing a sent quote

A sent quote isn't edited and an accepted quote never changes: **Revise** makes a new draft
version (a new number) that supersedes it. The old link then tells the customer the quote was
revised.

## Deposits

When a quote asks for a deposit, accepting it creates a **draft deposit invoice**: one line,
"Deposit for quote QU-0001 (30 %)", on your *Customer deposits* account, for the percentage of
the total the customer accepted (or the fixed amount — never more than the total), due the day of
acceptance. Approve and send it like any invoice; until then nothing is posted, and your approval
rule and lock dates apply.

## Converting to an invoice

**Convert to invoice** makes a draft invoice from an accepted quote: the lines that count — the
options the customer chose — copied **identically** (description, quantity, price, discount,
account, tax code, amounts). When there is a deposit invoice that wasn't voided, one more line
deducts it: "Less deposit, invoice INV-0042", minus the deposit, on the Customer deposits
account, without tax — so the invoice charges the full tax of the work and its total is the quote
total less the deposit. The quote becomes **Invoiced** and links to the invoice.

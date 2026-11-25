# Tax reports (G-05)

Five reports that always tie to the ledger, on every package with Tax (feature key
`tax.reports.read`, closing gaps 54 and 49 — Xero's *Taxes and balances* has no tax report).
They run in the K-01 report engine (`/o/<org>/reports/<slug>`), with tax presets, drill-down on
every figure and exports (PDF / XLSX / CSV) equal to the screen.

## Source: posted tax lines (G-05-T02)

Every posting that carries tax writes one **tax line per line and component**
(`tax.TaxLine`): the journal entry and line, the date (the tax point: the entry's date), the
side (sales / purchase), the tax code, the component (GST, HST, QST, PST) and its rate, the
**basis** (the net amount taxed), the **tax**, the **recoverable** part (ITC / ITR, purchases)
and the **non-recoverable** part (added to the cost: restricted ITCs, PST on purchases), and the
flags read by the audit report. Amounts are signed: a credit note or a reversal is negative.

- A reversal copies its original's tax lines with the opposite sign; a revised document (D-03b)
  is a reversal and a re-post, so a revision **across periods** shows as the difference in the
  later period, and within one range the superseded pair nets to zero. Lists hide superseded
  pairs inside the range (`current_only`): only the current revision is listed.
- Manual journals with a tax code but no calculated tax, and any journal that posts to a tax
  control account directly, are **journal-source** tax lines: listed in the audit report and in
  the tie-out's *Journals affecting tax accounts* (an exception).

## Parameters (every report)

| Parameter | Values | Default |
|---|---|---|
| `date_from`, `date_to` | a range | the current filing period |
| `period` | a filing period (sets the range) | — |
| `basis` | `settings` (G-06), `accrual`, `cash` — an explicit override per run | `settings` |
| `kind` | `all`, `gst_hst`, `qst`, `pst` | `all` |
| `side` | `all`, `sales`, `purchase` | `all` |

**Cash basis** (G-05-T03): a document's tax is recognised in proportion to the payments
dated in the range (a 50 % paid invoice reports 50 % of its tax); journal-source lines count on
their date.

## 1. Tax summary by code and component (G-05-T04)

Rows: component (section) → tax code. Columns: **Basis**, **Tax**, **Recoverable**,
**Non-recoverable**. Sections for sales (tax collected) and purchases (ITCs / ITRs). Totals per
component and side, then *Net tax* (collected − recoverable) per component. Each figure drills
to the tax detail filtered to that code and component.

## 2. Tax detail by document (G-05-T05)

One row per document (or journal) in date order: date, document type and number (link to the
document), contact, code, component, basis, tax, recoverable, non-recoverable. Grouped by
component; totals equal the summary's.

## 3. Tax audit report (G-05-T06)

One row per tax line: posting date, journal number, line, account, code, component, rate, basis,
tax, the person who posted it — with **flags** as chips:

| Flag | When |
|---|---|
| `override` | the document line's tax code was changed from the default (G-02) |
| `late_adjustment` | posted into a filed period, carried by the next return (G-03-T08) |
| `journal_source` | a manual journal or a journal hitting a tax control account |
| `restricted_itc` | part of the ITC / ITR is not claimable (meals 50 %…) |
| `superseded` | a revised document's earlier revision or its reversal |

## 4. ITC / ITR detail (G-05-T07)

Purchases only. One row per document line: tax, **recoverable**, **non-recoverable** and the
restriction (e.g. *Meals 50 %*). Totals per component; the recoverable total is the return's
line 106 (ITCs) / QST ITRs.

## 5. Tax-to-GL tie-out (G-05-T08)

Per control account (GST/HST payable, GST/HST receivable, QST payable, QST receivable, PST
payable): the **GL movement** in the range (credits − debits for payables, debits − credits for
receivables), the **report total** of the matching tax lines, and the **difference**. A
difference of 0.00 is a green *Ties to GL*; otherwise the card is red with the difference and the
section **Journals affecting tax accounts** names every journal that posted to a control account
without tax lines (number, date, narration, amount, a link). Always on accrual basis (the GL is).

## Exports (G-05-T11)

PDF (Letter, 1-inch margins), XLSX and CSV hold exactly the rows, columns and totals of the
screen for the same parameters (the K-01 exporters).

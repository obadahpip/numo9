# ADR-0006: Posted invoices are edited as revisions (101 → 101-1), by reversal and re-post

| | |
|---|---|
| **Status** | accepted (2026-11-25, on merge) |
| **Date** | 2026-11-25 |
| **Deciders** | Obadah Abu Odeh (Gray Matter AI / PYDUSK AI SOLUTIONS LTD.); Profitex (client decision 5) |
| **Deliverable / task** | D-03b-T01 (the phase plan calls this "ADR-002"; 0002 was already taken) |

## Context and problem statement

In Xero an approved invoice can only be voided and re-created, which loses its number, its
payments and its history. The client wants an approved or sent invoice to be **editable**
(Phase 1 plan, card D-03b). After D-03a an approved invoice is immutable: it has a number, a
posted journal and possibly payments, emails and a filed GST/HST period behind it. We need one
design for how an edit is stored, numbered, posted and reported, before the 25 tasks of D-03b
build on it.

## Decision drivers

- The ledger is append-only: posted journal lines are never updated (ADR-0003).
- Every figure must be traceable: who changed what, when and why, with old and new values.
- Reports must never show two versions of one invoice, nor a half-applied edit.
- A filed GST/HST return never changes (G-03): an edit dated in a filed period must not alter it.
- Two people editing the same invoice must not lose each other's change.
- The customer keeps one invoice number they recognise.

## Considered options

1. **Revisions by reversal and re-post** — each save of a posted invoice creates an
   `InvoiceRevision`; the previous revision's journal is reversed and the new one posted in the
   same transaction.
2. **Void and re-create** (Xero's way) — the edit voids 101 and issues 102.
3. **Edit in place with a delta journal** — update the invoice rows and post only the
   difference.
4. **Credit note and new invoice** — every edit issues a credit note for 101 and a new invoice.

## Decision outcome

**Chosen option:** "Revisions by reversal and re-post", because it is the only option that keeps
the invoice number, keeps the ledger append-only and leaves a complete, readable trail.

### The model

- `sales.InvoiceRevision` (invoice, `revision` 0, 1, 2…, `number_display`, `snapshot` of header
  and lines with totals, `reason`, `created_by`, `journal_reversal`, `journal_post`,
  `superseded_at`). Revision 0 is created at first approval, so every posted invoice has a
  current revision; `Invoice.current_revision` points at the latest.
- The invoice rows (`sales_invoice`, `sales_invoiceline`) always hold the **current** revision.
  Older revisions are read from their snapshots and are never edited.
- `Invoice.version` (an integer) increases with each revision and is the optimistic-concurrency
  token.

### Numbering

- The invoice keeps its number. Revision *n* ≥ 1 is shown as `<number>-<n>`: 101, 101-1, 101-2.
- The suffix is allocated inside the posting transaction, under the row lock on the invoice, so
  two saves can never get the same suffix. The numbering sequence (A-05) is not consumed.
- Lists, statements and search find the invoice by 101 and by 101-1.

### Posting

One database transaction per revision:

1. Lock the invoice (`SELECT … FOR UPDATE`) and compare `version` with the editor's; a mismatch
   is a **conflict** (HTTP 409), nothing is written.
2. Validate the change (D-03b-T05): the reason is required; the currency never changes; the
   contact changes only while no payment is allocated.
3. Check the locks on the invoice date: the AR lock and general-ledger lock refuse; the Tax lock
   is the filed-period rule below.
4. Reverse the previous revision's journal (C-02 `reverse`) and post the new revision's journal
   (`post_journal`), both dated the invoice date and both linked to the revision. A change of
   description only is still a reversal and a re-post (the two net to zero): one rule, no special
   case.
5. Store the snapshot, allocate the suffix, set `current_revision`, mark the previous revision
   `superseded_at`, write the audit event (D-03b-T15) with field diffs, the reason and the two
   journal ids, and emit `invoice.revised` (T17).
6. Payments stay allocated; if they now exceed the total, the excess becomes customer credit
   (D-05).

A failure at any step rolls the whole transaction back: there is never a reversed invoice
without its re-post.

### Filed-period rule

When the invoice date is inside a **filed** GST/HST (or QST) period, the Tax lock refuses the
revision, naming the period, unless the person chooses **late adjustment**. Then the reversal and
the re-post are posted as late adjustments (G-03-T08): the filed return is unchanged, and the
difference in net tax is reported on the next open period — an increase on line 104, a decrease
on line 107 — and listed on that return. The reversal and the re-post are netted, so only the
difference is carried (1,130.00 → 1,017.00 carries 13.00 on line 107).

### Reports

Every report reads the current revision through one query layer (`InvoiceCurrent`, T12): AR
aging, statements, reminders and the tax report. Because the superseded revision's journal is
reversed, ledger-based reports are right by construction; the query layer is for document-based
ones. A lint rule forbids reports from reading `InvoiceLine` directly.

### Documents

The PDF of revision *n* ≥ 1 is stamped "Revision *n* of invoice 101 — supersedes the version
issued on <date>"; the PDF of a superseded revision is watermarked "Superseded" (T14). The public
link always opens the current revision and says the invoice was revised (T23).

### Consequences

- Good: the number, the payments, the emails and the history stay with the invoice.
- Good: the ledger stays append-only; the trial balance is right after every transaction.
- Good: a filed return is never altered by an edit.
- Bad: each edit adds two journals, which lengthens the general ledger. Mitigation: both are
  linked to the revision, typed as system journals, and can be folded in the ledger view.
- Bad: snapshots duplicate data. Mitigation: they are small JSON documents and are the only
  record of superseded revisions.
- Bad: reports must use the query layer. Mitigation: the lint rule and the 1,000-run property
  test (T13: AR control = Σ open current revisions).

### Confirmation

- Golden scenario (T24): 101 at 1,130.00 revised to 1,017.00 gives 101-1, AR −113.00, two linked
  journals, tax report 1,017.00, 101 superseded.
- Property test (T13), concurrency test (T06), fault-injection test (T07), PDF snapshots (T14).

## Pros and cons of the options

### Void and re-create

- Good: simplest to build; nothing new in the ledger model.
- Bad: the customer's invoice number changes; payments must be re-allocated by hand; emails and
  history stay on a voided document. This is the Xero behaviour the client asked to replace.

### Edit in place with a delta journal

- Good: one journal per edit; a shorter ledger.
- Bad: the delta must be worked out per account, tax component, tracking and book, and a wrong
  delta is hard to see; the original journal no longer describes any document; a description-only
  edit leaves no ledger trace. Rejected for traceability.

### Credit note and new invoice

- Good: uses documents accountants already know.
- Bad: three documents for one correction and a new number for the customer; statements and
  aging show the noise. Credit notes stay available (D-06) for real credits.

## More information

Phase 1 plan, card D-03b · ADR-0003 (posting engine) · G-03-T08 (late adjustments) ·
`docs/specs/gst-hst-return-line-mapping.md`.

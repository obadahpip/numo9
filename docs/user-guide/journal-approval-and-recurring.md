# Manual journals: editor, approval and recurring journals

This page covers the journal editor, approval of manual journals and recurring journals (C-04).
Journal types, contacts on lines and the controls Numo9 runs before posting are in
[Manual journals: types and controls](journal-types-and-controls.md).

## The editor

**Accounting → Journals → New manual journal** (++n++ then ++j++).

- **Account** — type part of the code or the name ("5400", "rent") and pick it. Only accounts a
  journal may post to are offered; accounts with sub-accounts are headings only.
- **Debit / Credit** — a line holds one or the other; typing one clears the other.
- **Difference meter** — under the lines: *Balanced* in green, or *Out of balance by $12.50*.
  **Post journal** stays disabled until the difference is $0.00.
- **Tab** past the last cell of the last line adds a line and moves to its account.

### Actions

The buttons depend on the journal's state and on what you may do:

| State | Actions |
|---|---|
| New | Save as draft · Submit for approval · Post journal |
| Draft | Post journal · Submit for approval · Copy journal |
| Awaiting approval | Approve and post · Send back (an approver who didn't write it) · Withdraw (its author) · Copy journal |
| Posted | Copy journal · Reverse journal |
| Reversed | Copy journal |

**Copy journal** opens a new journal with the same type, narration and lines. **Reverse journal**
posts a new journal with debits and credits swapped, on the date you choose (it must be in an open
period). Journals posted by invoices, bills, payroll and other modules are changed in their own
module, so they offer neither.

## Approval

Your organisation can require approval of manual journals at or above an amount (organisation
settings, *journal approval threshold*; empty means never).

- A journal at or above the threshold can't be posted directly: **Submit for approval** sends it
  to an approver. Posting it anyway is refused (*Approval required*).
- The approver must **not** be the person who wrote or submitted it — the server refuses it
  whatever the screen shows (`ledger.journal.self_approval`).
- The approver's **approval limit** for journals (Settings → Users and roles → Approval limits)
  must cover the journal's total: a limit of 5,000.00 can't approve 5,000.01. The refusal names
  the people who can (`approval.limit_exceeded`).
- **Approve and post** posts the journal as the approver; every posting rule still applies (lock
  dates, cash below zero…).
- **Send back** returns it to draft with a reason (at least 3 characters) shown to the author.
- **Withdraw** lets the author take it back to draft.

Approvers and authors are notified at each step.

### The approvals inbox

**Approvals** (`/o/<organisation>/approvals`) lists everything waiting for approval that you may
approve, and what you submitted yourself:

- the limit indicator shows *Your limit $5,000.00*;
- each item shows its amount, date and who submitted it; items above your limit say *Above your
  limit*; your own say *You created this* and have no Approve button;
- the side panel previews the selected item's lines;
- keyboard: ↑/↓ choose, **A** approves, **R** sends back (a reason is asked).

## Recurring journals

**Accounting → Journals → Recurring** (`/o/<organisation>/accounting/journals/recurring`) keeps
journals that repeat: rent, accruals, amortisation.

| Field | Meaning |
|---|---|
| Name, narration, type | As on a manual journal; the narration goes on every journal |
| Repeat every … weeks / months / quarters / years | The schedule |
| Starts on / Ends on | The first possible date and the last (optional) |
| Each time | *Save a draft* or *Post the journal* |
| Lines | Account, debit, credit, description — they must balance |

- **Next 6 dates** under the schedule are worked out by the same code that creates the journals,
  so they are exactly what will happen.
- **End of month**: a schedule starting on the 31st falls on the last day of shorter months —
  28 (or 29) February, 30 April — and back on the 31st when the month has one.
- A new recurring journal starts **from today**: a start date in the past doesn't post the months
  already gone.
- Numo9 creates each occurrence **once**, on its date in your organisation's time zone, even if the
  background job runs twice.
- If a date is **locked** (before the lock date, or in a closed period) that occurrence is
  **skipped**, never posted on another date; *Last runs* shows it with the reason.
- With *Post the journal*, an occurrence at or above the approval threshold is submitted for
  approval on behalf of the person who set the recurring journal up.
- **Pause** stops new occurrences; **Resume** continues from the next date to come. Editing the
  lines or schedule makes a new version; each journal records the version it came from.

## Languages

Every label and message on these screens is available in English (Canada) and French (Canada).

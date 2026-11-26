# Recurring invoices

A recurring invoice is an invoice set up once that Numo9 creates on a schedule — a monthly
retainer, a subscription, rent. Open **Sales → Recurring invoices**
(`/o/<org>/sales/recurring-invoices`). Recurring invoices come with every package that has
invoices.

## Setting one up

**New recurring invoice** opens the template editor: the invoice editor's header and lines,
then the schedule.

- **Name** — for you only (the list and the notifications use it).
- **Customer**, **Reference**, **Amounts are** and the **lines** — the same grid as an invoice:
  item, description, quantity, unit price, discount, account and tax code.
- **Placeholders** — in the reference, the notes and the line descriptions, these are filled in
  on each invoice, in the customer's language:

  | Placeholder | English | French |
  |---|---|---|
  | `{{month}}` | October | octobre |
  | `{{year}}` | 2026 | 2026 |
  | `{{period_start}}` / `{{period_end}}` | 1 Oct 2026 | 1 oct. 2026 |

  The month and year are those of the period the invoice bills. A name Numo9 doesn't know
  (`{{montth}}`) is left as typed and flagged under the placeholders.
- **Schedule** — repeat every N weeks, months, quarters or years from **First invoice on**,
  optionally up to **Last invoice by**. A schedule on the 29th, 30th or 31st falls on the last day
  of shorter months (31 January, 28 February, 31 March). The panel lists the next 6 invoice dates,
  as the scheduler will create them. Each invoice is due by the customer's payment terms.
- **On each date**:
  - *Save as a draft* — the invoice waits in Drafts for you to check and approve;
  - *Approve* — the invoice is approved and posted, and gets its number;
  - *Approve and send* — it is also emailed to the customer's people marked *Include in emails*,
    with the PDF.

  Approving on a schedule needs the right to approve invoices (and to send them, for *Approve and
  send*). When the invoice needs approval (the organisation's approval threshold, or your
  approval limit), it goes to *Awaiting approval* instead.
- **Prorate a partial first or last period by days** — with **Service starts** and/or **Service
  ends**, a period the service covers only in part is charged for the days covered, line by line:
  service from 17 October in a 1–31 October period is 15 of 31 days, so a $310.00 line becomes
  $150.00. A period that ends before the service starts is skipped; the schedule ends with the
  period that holds the service end.

A schedule that started in the past starts from today: the months before the template existed
aren't invoiced. **Save** — changes apply to the next invoices only; invoices already created
don't change.

## Preview next invoice

Beside the totals, **Preview next invoice** shows the next invoice exactly as it will be created:
its date and due date, the reference, notes and line descriptions with the placeholders filled
in, the period billed, the proration and the totals. **For** previews any of the next dates. If
that date would be skipped (below), the preview says why.

## The list and the history

The list shows each recurring invoice's schedule, mode, **next run**, **last run**, status
(*Active*, *Paused*, *Ended*, also the tabs) and how many invoices it created and dates it
skipped. Open one and choose **Generated invoices** for its history: every date, newest first,
with the invoice it created (number, status, total) or why it was skipped.

## Pause, skips and the end of a schedule

- **Pause** stops a recurring invoice: its dates are recorded as skipped (*paused*) until you
  **Resume** it, and resuming starts again from today — the paused months aren't invoiced.
- A date is **skipped**, never moved to another date, when it falls on or before a lock date for
  sales (or the general ledger), or in a closed period, or when the customer is archived. You're
  notified (in the app, and by email per your preferences) with the reason, and the history shows
  it.
- If the invoice was created but couldn't be approved (a line without an account, a credit limit)
  it stays a draft; if it was approved but couldn't be emailed (nobody to send it to) it stays
  approved. Either way you're notified and the history shows the reason.
- When the schedule has no more dates (its last invoice date, or the service end), the recurring
  invoice is *Ended* and you're told once.

Notifications go to the person who set the recurring invoice up, or to the organisation's owners
and admins when that person is no longer a member.

## How exactly once is guaranteed (for support)

The scheduler runs every hour and creates each organisation's due invoices on the organisation's
own date (its time zone). Each date of each recurring invoice is recorded once (a row unique per
recurring invoice and date): two workers, a restart or a rerun of the job never create a second
invoice for the same date. A worker that stops half-way leaves nothing behind, and the next run
creates the invoice once.

Support can replay the dates of a day — for example after the workers were down:

```
python manage.py replay_ticks --date 2026-10-31 [--to 2026-11-02] [--org <organisation id>] \
    [--kind invoices] [--dry-run]
```

A date that already ran is listed as *already ran* and creates nothing; a date the scheduler
missed is created now, once. `--dry-run` only lists. Dates before a recurring invoice existed are
never replayed.

Every created and skipped date is in the recurring invoice's history (audit log:
*sales.recurringinvoicetemplate.generated*, *.skipped*, *.ended*).

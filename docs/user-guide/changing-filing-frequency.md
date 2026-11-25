# Changing your GST/HST filing frequency

Numo9 keeps one set of **filing periods** for each GST/HST (RT) and QST registration. Every day
from the registration's start to its end belongs to exactly one period, and a period that is
filed never changes. You can change how often you file, add a one-off period that doesn't follow
the cycle, and see every change that was made.

Open **Settings → Tax**, choose the registration, then **Filing periods**. You need the
permission *Add, version, archive and restore tax codes and rates* (`tax.manage`) to change
anything; everyone who can see tax codes can see the periods.

## The timeline

Each block is one period, in date order:

| Colour | Meaning |
|---|---|
| Green | Filed (or paid) |
| Blue | Open — nothing is due yet |
| Amber | Due soon — the return is due within 14 days |
| Red | Overdue — the due date has passed and the return isn't filed |

Point at a block (or move to it with the Tab key) to see its dates, its number, and the return and
payment due dates. An asterisk means the due date was moved to the next business day because the
usual date falls on a weekend or a statutory holiday. A marker above the timeline shows where
each filing frequency takes effect.

Numo9 keeps 24 months of periods ahead and updates "due soon" and "overdue" every night. The
organisation's owners and admins are notified once when a return becomes due soon and once when
it becomes overdue.

## Change the frequency

1. Select **Change frequency**.
2. Choose **Monthly**, **Quarterly** or **Annual**.
3. Enter the date the new frequency **takes effect** — its first day.
4. Enter the **CRA or Revenu Québec approval reference** (and its date). It is required when the
   change doesn't start on the first day of your financial year.
5. Select **Preview**. Numo9 shows the periods that will be removed, added and shortened. Nothing
   is saved yet.
6. Select **Confirm change**. Exactly the previewed periods are created.

What to expect:

- Filed periods are never touched. The new frequency can't start inside a period that is already
  filed — choose a date after it.
- If the date falls inside an open period, that period is shortened to end the day before, and
  the new frequency starts on the date. For example, quarterly to monthly from 1 July keeps
  January–March and April–June and creates July, August, September… as monthly periods.
- Annual to quarterly from 15 May gives a short period 1 January–14 May, then 15 May–30 June,
  then full quarters.
- Your invoices and bills don't move. A document belongs to the period that contains its date.

## Add an out-of-cycle period

Use this for a return that covers unusual dates, such as 1 January to 15 March after a change of
year end.

1. Select **Add out-of-cycle period**.
2. Enter the start and end dates and why (the note is kept in the history).
3. Select **Preview**. Unfiled periods it overlaps are removed, and the regular periods restart
   the day after it ends — after 1 January–15 March, quarters run 16 March–15 June,
   16 June–15 September, and so on, until the next frequency change.
4. Select **Add period**.

An out-of-cycle period can't overlap a filed period. While it isn't filed you can remove it from
the timeline; the regular periods are then put back.

## Frequency history

Under the timeline, **Frequency history** lists every frequency the registration has had: the
date it took effect, who recorded it and when, and the approval reference. Each change is also in
the audit log of the registration.

## Messages you may see

| Message | What to do |
|---|---|
| "A change during the financial year needs the CRA or Revenu Québec approval reference." | Enter the reference from the approval letter, or choose the first day of your financial year. |
| "… is inside the filed period …: a filed period can't change." | Choose a date after the filed period ends. |
| "The period overlaps the filed period …" | Choose dates after the filed period. |
| "A filing frequency already takes effect on …" | A change was already recorded for that date. |

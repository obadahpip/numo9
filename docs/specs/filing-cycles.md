# GST/HST and QST filing cycles — rules specification (G-03a-T01)

Status: **draft for client sign-off.** This page is the contract for the filing-cycle engine
(G-03a-T03…T18): the reporting periods of each sales-tax registration, their due dates, the
instalment dates of annual filers, and what a frequency switch or an out-of-cycle period does.
Amounts, return lines and filing itself are G-03 / G-09; this engine only decides **which
period a date belongs to and when it is due**.

## 1. Registrations that file

| Registration (A-05 `TaxRegistration.type`) | Return | Authority |
|---|---|---|
| `rt` — GST/HST program account | GST/HST return (GST34) | CRA |
| `qst` — Quebec QST number | QST return (FPZ-500) | Revenu Québec |

A registration files from its `effective_from` (the registration start) to its `effective_to`
(the stop date) or open-ended. PST/RST numbers (BC, SK, MB) and the BN, RP and RC accounts have
no periods here.

## 2. Frequencies (`FilingCycle`)

A registration has one or more **filing cycles**, each effective from a date until the next one:

| Frequency | Period | Anchor |
|---|---|---|
| `monthly` | a calendar month | — |
| `quarterly` | a **fiscal** quarter: three months from the financial year start (A-05 `fye_month` / `fye_day`); a 31 March year end gives Apr–Jun, Jul–Sep, Oct–Dec, Jan–Mar | financial year end |
| `annual` | the financial year | financial year end |

A cycle stores: frequency, `effective_from`, the CRA / Revenu Québec **approval reference** and
date, a note and its author. Cycles of a registration are unique by `effective_from`.

## 3. Periods (`FilingPeriod`)

- The periods of a registration cover **every day** from the registration start to its stop date
  (or 24 months ahead when open-ended, rolled forward nightly — G-03a-T17) **exactly once**: no
  gaps, no overlaps (enforced in the database with a `daterange` exclusion constraint).
- Kinds: `regular` (a whole period of the cycle), `stub` (a partial regular period — the
  registration starting mid-period, a switch taking effect mid-period, a stop date), `custom`
  (an out-of-cycle period entered by the accountant, §6).
- Status: `open` → `closed` (the period has ended) → `filed` (the return is filed, G-03) →
  `paid`. **Filed and paid periods are immutable**: never deleted, moved or regenerated.
- Each period has a sequence number within its registration (1, 2, 3… in date order).

## 4. Due dates

| Frequency | Return due | Payment due |
|---|---|---|
| Monthly, quarterly | one month after the period end (the last day of that month when the period ends on a month end: Q3 ending 30 Sep → 31 Oct) | same as the return |
| Annual — corporations and other registrants | three months after the year end (31 Dec → 31 Mar) | same as the return |
| Annual — individuals with business income and a 31 Dec year end | **15 June** | **30 April** |

The individual rule is **data** (a due-date rule keyed by business structure and frequency), so
another authority's rule can be added without code.

**Holiday roll.** A due date on a Saturday, Sunday or public holiday moves to the **next business
day** (CRA and Revenu Québec practice: a return or payment received then is on time). Holidays
are data (`HolidayCalendar`): federal statutory holidays plus the holidays of the province of the
registration (Quebec for QST), by year; 2026 and 2027 are loaded, later years added each autumn.

## 5. Instalments (annual filers)

An annual filer whose net tax for the previous year was $3,000 or more pays **quarterly
instalments**, each due **one month after the end of each fiscal quarter** (rolled like due
dates). The engine produces the four dates for each annual period; the amount is a placeholder
filled by G-09 (the lesser of the prior-year and current-year methods).

## 6. Changes

**Frequency switch** (a new cycle):

1. The effective date may not fall **inside a filed (or paid) period** — refused.
2. A mid-year switch (effective date not the financial year start) needs the **approval
   reference** — refused without it (HTTP 422). The engine **warns** (does not refuse) when the
   effective date is not a financial year start.
3. Only **unfiled** periods from the effective date on are deleted and regenerated; an open
   period crossing the effective date is **split** into a stub ending the day before and the new
   cycle's periods from the effective date. Tax postings are never moved: they belong to a period
   by their date (`period_for`, G-03a-T14).
4. Every change is previewed (removed / added / changed periods) before it is saved, and kept in
   the change history.

**Out-of-cycle (custom) period** — e.g. 1 Jan–15 Mar:

1. It may not overlap a filed or paid period.
2. Unfiled periods it overlaps are removed; the regular periods **realign from the day after its
   end**: with a 1 Jan–15 Mar custom period, quarters run 16 Mar–15 Jun, 16 Jun–15 Sep… until the
   next cycle change (or a later custom period) re-anchors them.
3. A custom period can be deleted only while unfiled with no locked tax postings; the regular
   periods are regenerated over its dates.

**Horizon** — an open-ended registration has periods 24 months ahead; the period containing the
24-month date is generated whole (the horizon never cuts a period into a stub). The nightly job
(`numo9.tax.roll_filing_periods`, G-03a-T17) rolls them forward, marks a period **due soon** in
the 14 days before its return is due and **overdue** after, and emits each change once.

## 7. Edge cases the tests cover

Switch on the 1st vs mid-month · annual → quarterly mid-year (a stub) · two switches in a year ·
a switch back · financial year ending 31 March · 29 February · a registration starting
mid-month · deleting a custom period · a due date on a long weekend.

## Sign-off

| Role | Name | Date |
|---|---|---|
| Client's accountant | | |
| Product owner | | |

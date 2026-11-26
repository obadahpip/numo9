# Assurance (K-09) — wireframes

K-09-T02 · Deliverable K-09. Low-fidelity frames for the exceptions engine: the Assurance page,
a finding's detail, the proposed-fix drawer, rule settings and the activity heatmap. They follow
the rule catalogue ([Assurance rules](../../specs/assurance-rules.md)), the Phase 0 wireframe
conventions ([Phase 0 wireframes](../wireframes.md): 1440 px desktop frame, `@numo9/ui`
components only, red numbered markers) and the "no banners in work screens" rule. Sample data is
the teardown organisation REFINED (Ontario, CAD). Sign-off = merging the PR.

Route: **Accounting › Assurance** (`/o/<org>/accounting/assurance`), tabs *Findings* ·
*Rule settings* · *Activity*. The nav item carries the badge "open critical + warning" (K-09-T24).

## A1. Assurance page — findings

```
┌ Accounting › Assurance ───────────────────────────────────────────────────────────── [Run checks] ①┐
│ [Findings] [Rule settings] [Activity]                                   Last run 26 Nov 2026 09:14 │
│ ┌─ Assurance score ─────────┐ ┌ Critical ┐ ┌ Warning ┐ ┌ Info ┐ ┌ Acknowledged ┐                  ②│
│ │   38 / 100                │ │    4     │ │   11    │ │  2   │ │      1       │                   │
│ │ ▁▁▁▁▁▁▁▁▁▁░░░░░░░░░░░░░░░ │ └──────────┘ └─────────┘ └──────┘ └──────────────┘                   │
│ └───────────────────────────┘                                                                      │
│ Severity: (All) (Critical 4) (Warning 11) (Info 2)   Status: (Open ▾)   Search [ rule, account… ] ③│
│ ▼ Negative cash or bank balance · critical · 1                                                   ④│
│   Petty Cash went below zero: −994.17 on 15 Jun 2026 (today −994.17).           −994.17           │
│   Cash on hand can't be negative: money was spent from it that was never put in.                   │
│   [View source] [Propose fix] [Acknowledge] [Mark false positive]                                ⑤│
│ ▼ Manual journal posts to a bank or cash account · warning · 2                                     │
│   Journal 1 (3 Jun 2026) posts 417.22 to Petty Cash.                             417.22           │
│   Journal 2 (15 Jun 2026) posts 576.95 to Petty Cash.                            576.95           │
│ ▶ Expense journal without a contact · warning · 2                                                  │
│ ▶ Expense journal without an attachment · warning · 2                                              │
│ ▶ Exempt code on a normally taxable account · warning · 5                                          │
│ ▶ Backdated posting · warning · 1                                                                  │
│ ▶ GST/HST registration without a Business Number · critical · 1                                    │
│ ▶ No lock date · warning · 1 …                                                                     │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Run checks | Starts a full run (background job, job tray); the page refreshes when it ends. Needs *manage* |
| 2 | Score card and counts | Score 0–100 (weighted by severity), counts of open findings by severity and the acknowledged ones; a count is a filter shortcut |
| 3 | Filters | Severity chips (one or several), status (open, acknowledged, resolved, false positive), text search over rule name, subject and explanation |
| 4 | Grouped list | One group per rule, critical first, with the count; groups open/close; each item shows the plain-language explanation with its numbers and the amount right-aligned |
| 5 | Actions | View source (the journal, account, bill, contact or settings page), Propose fix (only when the rule has a fix), Acknowledge, Mark false positive (asks for a reason, required) |

Empty state: "No open findings — the last run found nothing to check." with *Run checks*.
Error state: inline message with *Retry* (no banner).

## A2. Finding detail

```
┌ Finding · Negative cash or bank balance ──────────────────────────── critical · Open ┐
│ Subject   Petty Cash (1000)                                       [View account]     │
│ Why       Petty Cash went below zero: −994.17 on 15 Jun 2026 (today −994.17).        │
│ Numbers   Lowest −994.17 on 15 Jun 2026 · Today −994.17 · First negative 3 Jun 2026 │
│ Seen      First 26 Nov 2026 09:14 · Last 26 Nov 2026 09:14                          │
│ History   26 Nov 09:14 Opened by the nightly run                                     │
│           26 Nov 10:02 Fix drafted by Sam Patel — Draft journal (Dr 1000 / Cr 2900)  │
│ [Propose fix] [Acknowledge] [Mark false positive]                                    │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Header | Rule name, severity badge (text + colour, never colour alone), status |
| 2 | Numbers | Every value the rule used (`details`), formatted in the organisation's locale |
| 3 | History | The finding's audit events (opened, reopened, acknowledged, false positive + reason, fix drafted, resolved) |

## A3. Proposed-fix drawer

```
                                   ┌ Proposed fix ─────────────────────────────── ✕ ┐
                                   │ Why this entry                                  │
                                   │ Petty Cash is −994.17 and no other bank account │
                                   │ has the money: the owner most likely paid       │
                                   │ personally, so the entry credits Shareholder    │
                                   │ Loan.                                           │
                                   │ Date [03 Jun 2026]  Narration [Fund petty cash] │
                                   │ ┌ Account ───────────────┬ Debit ──┬ Credit ──┐  │
                                   │ │ 1000 Petty Cash        │ 994.17  │          │  │
                                   │ │ 2900 Shareholder Loan  │         │ 994.17   │  │
                                   │ └────────────────────────┴─────────┴──────────┘  │
                                   │ Totals 994.17 / 994.17 · balanced                │
                                   │ Other option: transfer from Chequing (if funded) │
                                   │ [Cancel]             [Create draft journal]      │
                                   └─────────────────────────────────────────────────┘
```

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Reasoning | The rule's explanation of the proposed entry (why these accounts, this amount, this date) |
| 2 | Editable grid | The C-04 LineGrid: accounts, debit, credit, description; totals and the unbalanced message as on the journal screen |
| 3 | Create draft journal | Creates a **draft** (never posted) linked to the finding and opens it in Journals › Draft; posting it later resolves the finding |
| 4 | Recode-tax fixes | For EXEMPT_ON_TAXABLE_ACCOUNT the drawer shows the prefilled find & recode search and suggested tax code with *Open in Find & recode* instead of a grid |

## A4. Rule settings

```
┌ [Findings] [Rule settings] [Activity] ────────────────────────────────────────────────────────────┐
│ Rule                                         On   Severity      Parameters                        │
│ Negative cash or bank balance               [●]  [Critical ▾]  Fix source [Auto ▾] Loan acct [2900]│
│ Backdated posting                           [●]  [Warning ▾]   Days [ 7 ]                          │
│ Round amount journal                        [●]  [Info ▾]      Threshold [1,000.00] Multiple [100] │
│ Weekend posting                             [○]  [Info ▾]      Holidays [ ] Province [ ]           │
│ …                                                                                                  │
│                                                                    [Reset to defaults] [Save]   ① │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Save | Validates each parameter against the rule's schema (type, min, max, choices) inline; saved changes apply on the next run ("Changes apply on the next run") and are audited |

## A5. Activity heatmap

```
┌ [Findings] [Rule settings] [Activity] ─────────────────────────────────────────────┐
│ Activity in the last 12 months (audit log)        Person [Everyone ▾]              │
│      Dec  Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov                   │
│ Mon  ░░░░ ░░░░ ░░░░ ░░░░ ░░░░ ░░░░ ░▓░░ ░░░░ ░░░░ ░░░░ ░░░░ ▒░░░                   │
│ …                                                                                  │
│ Sun  ░░░░ ░░░░ ░░░░ ░░░░ ░░░░ ░░░░ ░█░░ ░░░░ ░░░░ ░░░░ ░░░░ ░░░░                   │
│ Less ░ ▒ ▓ █ More                               [Show as table]                    │
│ People: Dana Lee 0 · Tarik Dugmag 12 (last 15 Jun 2026) · Sam Patel 4              │
└────────────────────────────────────────────────────────────────────────────────────┘
```

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Calendar grid | One square per day in the organisation's time zone, shade by count; tooltip "15 Jun 2026 · 12 actions"; counts equal the audit log |
| 2 | Table alternative | Date, person, count (accessible equivalent, keyboard reachable) |
| 3 | People | Totals per person and their last activity — a dormant administrator stands out |

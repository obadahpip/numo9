# K-05 — Organisation dashboard wireframes

K-05-T01 · Deliverable K-05 (Phase 1, Reporting core). Low-fidelity frames for the organisation
home `/o/<organisation>/home`: the default layout per role, the widget library, the empty and
error states, the mobile layout and the chart rules. They follow the K-05 card of
`docs/phase_plans/Phase_1_Core_Books.md` (gaps 4 and 60) and the conventions of
[Phase 0 wireframes](../wireframes.md): red numbered markers in the frames are annotations, the
table under each frame is the legend, sample data is Canadian (Ontario organisation, CAD,
GST/HST). Screens are built from `@numo9/ui` only. Sign-off = merging the pull request.

Principles fixed here (binding for K-05-T02 … T11):

- **The true position at a glance, no advertising.** There is no ad, app-store or "upgrade" widget,
  ever (gap-04). Bank & cash balances are on the default layout of every role that may see bank
  accounts (Xero hides them by default).
- **Same numbers as the reports.** Every figure is computed by the report service that produces it
  and links to that report, filtered the same way.
- **Zero is a number.** Empty data shows `0` / `$0.00` and an actionable empty state; a chart axis
  shows `$0`, never "—k" (gap-60).
- **Independent widgets.** Each widget loads, fails and retries on its own; one failure never blanks
  the page. Widget errors name what failed, offer **Try again** and show the request reference
  (the D-09-T10 card error).
- **Personal layout, role defaults.** A person's layout (which widgets, their order, their
  settings) is saved per person and organisation; a new person starts from their role's default.

## 1. Owner / admin — default layout (desktop, 12 columns)

```
+------------------------------------------------------------------------------------------+
| Numo9  Home  Sales  Purchases  Banking  Accounting  Reports  Tax      [Maple Fixtures v] |
+------------------------------------------------------------------------------------------+
| Home                                                  (1)[Customise dashboard]           |
| Maple Fixtures Ltd. · Data as of 2:14 p.m. (2)                                           |
|                                                                                          |
| +-- Bank & cash balances (3) -------------------+ +-- Cash in and out, 6 months (4) ----+ |
| | RBC Chequing   1001   $18,420.16  stmt $18,…  | |  $20k ┤        ▇                     | |
| | Visa ••4471    1010   ($2,310.00)  ⚠ (5)      | |  $10k ┤  ▇ ▆   ▇ ▆  ▆               | |
| | Petty cash     1015      $250.00              | |    $0 ┼──────────────────────────── | |
| | Total cash            $16,360.16              | |       Jun Jul Aug Sep Oct Nov       | |
| | [Bank accounts →]                             | |  ■ In  ■ Out      [Show as table]   | |
| +-----------------------------------------------+ +-------------------------------------+ |
| +-- Invoices owed to you (6) -------------------+ +-- Bills to pay (7) -----------------+ |
| | Awaiting payment 11 · $18,400.00              | | Awaiting payment 4 · $3,700.00      | |
| | Overdue           3 · $4,275.25 (red)         | | Overdue          3 · $2,700.00      | |
| | [████████▒▒▒▒░░  ] aging bar                  | | [██████▒▒░] aging bar               | |
| | Current 1–30 31–60 61–90 90+                  | | [Purchases overview →]              | |
| +-----------------------------------------------+ +-------------------------------------+ |
| +-- Tax and filing deadlines (8) ---------------+ +-- Profit and loss (9) --------------+ |
| | GST/HST Jul–Sep 2026  due 31 Oct  ● Overdue   | | Month to date  [MTD|YTD]            | |
| | GST/HST Oct–Dec 2026  due 31 Jan  ● Due soon  | | Income      $24,100.00              | |
| | [Tax registrations →]                         | | Expenses    $17,950.40              | |
| +-----------------------------------------------+ | Net profit   $6,149.60 [P&L →]      | |
| +-- Awaiting my approval (10) ------------------+ +-------------------------------------+ |
| | 2 bills · 1 invoice · 1 journal  [Inbox →]    | +-- Exceptions (11) ------------------+ |
| +-----------------------------------------------+ | Critical 1 · Serious 2 · Warning 5  | |
|                                                   +-------------------------------------+ |
+------------------------------------------------------------------------------------------+
```

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Customise dashboard | Opens edit mode (frame 5): add, remove, reorder (drag or keyboard), widget settings; saved per person; **Reset to my role's default** |
| 2 | Data as of | Time the figures were computed, in the organisation's time zone; each widget also shows its own when cached |
| 3 | Bank & cash | Every bank, credit-card and cash account **incl. petty cash** (F-01): ledger balance, statement balance when an import exists; total uses the K-02-T09 cash definition; many accounts scroll inside the card (max 8 rows visible) |
| 4 | Cash in and out | Bar chart (K-05-T08), 6 months by default (setting: 3 / 6 / 12); zero baseline, CAD axis (`$0`, `$10k`), legend + table fallback; bars link to the cash summary for the month |
| 5 | Negative cash | A negative balance shows in parentheses, `text-fg-danger` and a warning icon + "Negative balance" text (never colour alone), linking to the exceptions list filtered to the account |
| 6 | Invoices owed | Tiles Awaiting payment / Overdue from the D-09 sales query and the aging bar (shared `AgingBar`); each links to the invoices list tab |
| 7 | Bills to pay | Same pattern from the E-02 purchases overview query (`bills/overview`); links to the bills list tabs |
| 8 | Deadlines | G-03a filing periods (and payroll remittances later): next due periods, return due date, **Due soon** (≤ 14 days) / **Overdue** badges with icon + text; links to the registration's filing page. Org without the Tax product: frame 4, gated state |
| 9 | P&L snapshot | MTD / YTD toggle (setting); income, expenses, net from the K-02 P&L service; link opens the P&L with the same dates |
| 10 | Approvals | Counts per document type waiting for **me** (C-04 inbox counts); link to the inbox |
| 11 | Exceptions | K-09 counts by severity, each linking to the exceptions list filtered by severity; status colours reserved for severity |

## 2. Default layouts per role

Order is top-left to bottom-right (two columns on desktop). Widgets a role can't see because of
its permissions are never in its default; a person adding one later sees the permission
explanation in its place.

| Role (organisation) | Default widgets, in order |
|---|---|
| Owner, Admin | Bank & cash · Cash in and out · Invoices owed · Bills to pay · Deadlines · P&L snapshot · Awaiting my approval · Exceptions |
| Accountant (delegate, or a practice serving the organisation) | Bank & cash · Exceptions · Deadlines · P&L snapshot · Account watchlist · Invoices owed · Bills to pay · Awaiting my approval |
| Sales | Invoices owed · Awaiting my approval |
| Purchasing | Bills to pay · Awaiting my approval |
| Payroll, HR, Employee | Awaiting my approval · Deadlines |

## 3. Widget library

Shown in the **Add widget** drawer of edit mode (frame 5). Each entry: name, one-line description,
the product it needs, and **Add** (or "Already on your dashboard"). Nothing in the library sells
anything.

| Widget key | Name | Shows | Needs | Settings |
|---|---|---|---|---|
| `bank_cash` | Bank & cash balances | All bank, card and cash accounts incl. petty cash; ledger and statement balance; negative in red with exception link | Accounting (banking) | — |
| `cash_in_out` | Cash in and out | Money in / out per month, bar chart with table fallback | Accounting (banking) | Months: 3, 6, 12 |
| `invoices_owed` | Invoices owed to you | Awaiting payment, overdue, aging bar | Accounting (sales) | — |
| `bills_to_pay` | Bills to pay | Awaiting payment, overdue, aging bar | Accounting (bills) | — |
| `deadlines` | Tax and filing deadlines | Next GST/HST/QST return and payment due dates with due soon / overdue | Tax | — |
| `pnl_snapshot` | Profit and loss | Income, expenses, net profit | Core | Period: MTD, YTD |
| `account_watchlist` | Account watchlist | Balances of up to 10 chosen accounts | Core | Accounts (1–10) |
| `exceptions` | Exceptions | Open exceptions by severity | Core | — |
| `approvals` | Awaiting my approval | Documents waiting for my approval, by type | Core | — |

## 4. Empty, loading, error and gated states

```
+-- Bank & cash balances ----------------+  +-- Cash in and out, 6 months ----------+
|  No bank account yet                   |  |  $1 ┤                                 |
|  Add your bank account to see your     |  |  $0 ┼──────────────────────────────── |
|  balances here.                        |  |     Jun Jul Aug Sep Oct Nov           |
|  [Add bank account]  (1)               |  |  No money in or out in 6 months (2)   |
+----------------------------------------+  +---------------------------------------+
+-- Bills to pay ------------------------+  +-- Tax and filing deadlines -----------+
|  ░░░░░░░░░░░░  ░░░░░░  (3)             |  |  Deadlines need the Tax product (4)   |
|  ░░░░░░░░                              |  |  GST/HST and QST periods and due      |
+----------------------------------------+  |  dates come with Tax.  [See packages] |
+-- Profit and loss ---------------------+  +---------------------------------------+
|  ! Profit and loss couldn't be loaded  |
|  Something went wrong on our side and  |
|  nothing was changed. [Try again] (5)  |
|  Reference: web-5f1c9e2a7b3d4e10       |
+----------------------------------------+
```

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Empty | `0` / `$0.00` wherever a number exists, plus one primary action that fixes the emptiness (Add bank account, New invoice, Enter a bill, Set up GST/HST) |
| 2 | Empty chart | Axis from `$0` with real tick labels (`$0`, `$1`), never "—k"; the caption says there was no activity; the table fallback lists the months with `$0.00` |
| 3 | Loading | Skeleton per widget in its final size (no layout jump); the page never waits for the slowest widget |
| 4 | Gated | Widget whose product the organisation doesn't have: names the product and what it brings, link to the package page; the API answers the gate (402 info), not an error |
| 5 | Error | Card error of D-09-T10: what failed, why, **Try again** (only this widget reloads), reference id |

## 5. Edit mode — customise, reorder, add/remove

```
+------------------------------------------------------------------------------------------+
| Home — customising                         [Add widget] [Reset to default] [Done] (1)    |
| +-- ⠿ Bank & cash balances  [⚙] [✕] ----+ +-- ⠿ Cash in and out  [⚙] [✕] ----------+     |
| |  (content dimmed)                     | |  Months  (•) 6  ( ) 3  ( ) 12  (3)     |     |
| +---------------------------------------+ +----------------------------------------+     |
| +-- ⠿ Invoices owed  [⚙] [✕] (2) -------+ +-- ⠿ Bills to pay  [⚙] [✕] -------------+     |
| live region: "Bank & cash balances moved to position 1 of 8" (4)                         |
+------------------------------------------------------------------------------------------+
```

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Toolbar | **Add widget** opens the library drawer (frame 3); **Reset to default** restores the role default after a confirm; **Done** saves (PUT layout) — saving failures keep edit mode with the error |
| 2 | Handle and remove | `⠿` drag handle (dnd-kit); keyboard: focus the handle, `Space` to lift, arrows to move, `Space` to drop, `Esc` cancels; `✕` removes (undo toast) |
| 3 | Settings | Per-widget settings inline (months, MTD/YTD, watchlist accounts), validated by the server |
| 4 | Announcements | Every move and removal is announced in a polite live region |

## 6. Mobile layout (360 px)

```
+--------------------------------+
| ☰  Home              [🔔] [DR] |
| Data as of 2:14 p.m.           |
| +-- Bank & cash balances ----+ |
| | RBC Chequing   $18,420.16  | |
| | Visa ••4471   ($2,310.00)⚠ | |
| | Petty cash        $250.00  | |
| +----------------------------+ |
| +-- Invoices owed -----------+ |
| | Overdue 3 · $4,275.25      | |
| | [███▒▒░] aging bar         | |
| +----------------------------+ |
| +-- Cash in and out ---------+ |
| | (chart, full width)        | |
| | [Show as table]            | |
| +----------------------------+ |
|  … one column, same order     |
| [Customise dashboard]  (1)     |
+--------------------------------+
```

| Marker | Region | Behaviour |
|---|---|---|
| 1 | One column | 1 column below 768 px, 2 from 768 px, 12-column grid (widgets 6 or 12 wide) from 1280 px; same order as desktop; customise uses the keyboard / move up-down buttons instead of drag on touch; no horizontal scroll at 360 px; charts keep their table fallback |

## 7. Chart rules (K-05-T08)

- Bar (cash in/out) and line (trends) charts from `@numo9/ui` `BarChart` / `LineChart`; one value
  axis only (never dual axis), **zero baseline**, recessive grid, CAD axis ticks (`$0`, `$5k`,
  `$1.2M`; fr-CA `0 $`, `5 k$`), at most two series with the fixed series order (blue, then
  amber) and a legend; values in tooltips and in the **Show as table** fallback (exact amounts,
  `$0.00` for empty months).
- An all-zero or empty series still draws the axis from `$0` with real tick labels — never
  "—k" or a blank chart (gap-60).
- Negative months go below the zero line; the axis includes them.

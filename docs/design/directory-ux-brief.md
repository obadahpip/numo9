# Organisation directory — UX research brief (V-01-T01)

Deliverable V-01 · Phase 0. The accountant's home: every organisation assigned to the practice in one
dense, searchable list. Wireframes: [frame 2](wireframes.md#2-organisation-directory-practice-workspace)
(the directory) and frames 14–16 below (states, saved views and column chooser, go to organisation).

## 1. Who and why

| Person | Situation | What they need from the directory |
|---|---|---|
| Practice admin (firm owner) | 300–2,000 client organisations, several staff | See every client; find one in a keystroke; spot trials ending, unfiled returns, overdue items |
| Accountant / bookkeeper | 20–200 assigned clients, works client by client all day | Only *their* clients; open the next one fast; a personal view per task ("Payroll clients", "QC monthly filers") |
| Reviewer, payroll specialist | Works across a subset (review queue, payroll only) | Filter by package/payroll; same list, read-only actions |

Client decision 3 (project plan §1): accountants group and search the organisations they manage with
easy search and edit. Xero offers a plain organisation switcher list (teardown); there is no directory,
no saved filter and no column choice — so this screen is *beyond Xero*, with gap #6's pattern (saved
filters, column chooser) applied.

## 2. Research inputs and findings

| Source | Finding | Design response |
|---|---|---|
| Xero teardown (org switcher, practice pages) | One alphabetical list; no BN, province, package or status; no keyboard path | Dense table with the columns accountants scan for; `/`, `↑/↓`, `Enter`, `Ctrl/⌘+K` |
| Teardown gaps #1/#6 (two grid generations, no saved filters) | Every list behaves differently | The one `@numo9/ui` DataGrid (A-10-T10); views are named grid states |
| Client notes (Québec clients) | Names typed without accents ("Erable" for "Érable"); BN typed with spaces | Accent-insensitive search (`unaccent`), BN matched digits-only ("123 456" → `123456789`) |
| Phase 0 plan, V-01 rules | 2,000 organisations, < 300 ms p95; only assigned organisations; facets over the visible set | Server-side search on a denormalised summary; counts computed after access scoping |
| Accessibility baseline (A-10-T19) | Grids must expose table semantics and sort state | `role="grid"`, `aria-sort`, live result count, every action reachable without a mouse |

Assumptions recorded (no user interviews were possible inside this task): the persona tasks above
come from the client's notes and the project plan; the walkthrough with the project lead confirms
or corrects them before Phase 0 UAT.

## 3. Top tasks (in order of frequency) and how the screen serves them

1. **Open a known organisation** — `Ctrl/⌘+K` anywhere → type part of the name or BN → `Enter`
   (frame 16). In the directory: `/` focuses search, `↓` enters the rows, `Enter` opens,
   `Ctrl/⌘+Enter` opens in a new tab.
2. **Work a segment** — filter chips + Filters panel (package, status, province, fiscal year end,
   GST/HST cycle, payroll, overdue items, unfiled returns, archived) with counts; save as a view.
3. **Return to a segment tomorrow** — saved views rail; a default view opens first; views are stored on
   the server, so they follow the user to another browser (logout/login keeps them).
4. **Scan for problems** — columns Overdue / Unfiled / Status ("Trial 12 d", "Paid", "Demo",
   "Read-only") sortable; later deliverables (V-04 dashboards) drill into the directory with filters.

## 4. Layout decisions

- **Rows 40 px** (design token `size.row.compact` + padding), sticky header, virtualised body so 2,000
  rows scroll at 60 fps; density toggle kept from DataGrid.
- **Left rail = saved views** (personal). Each view has a menu: Update with changes, Rename, Set as
  default, Delete (confirmation). "Save current view" at the bottom. A changed view says "(changed)".
- **Search box** with placeholder "Search name, BN, owner, tag…" and the `/` hint; matches are
  highlighted with `<mark>` in the Organisation and BN cells.
- **Filters** as chips for the active filters (each removable) and a Filters panel that lists each
  option with its count. Counts are computed with every *other* filter applied, so choosing an option
  narrows the list to exactly the number shown next to it. Options with 0 stay visible, dimmed.
- **Column chooser** — the shared `@numo9/ui` component: show/hide plus reorder (drag handle, or
  `Alt+↑/↓` on the focused item). The record name column cannot be hidden. Order and visibility are
  part of the view.
- **Row actions**: Open, Open in new tab (menu on each row, keyboard reachable).
- **Archived organisations** (cancelled subscriptions) are hidden by default; "Show archived" in the
  Filters panel.

## 5. States (frame 14)

| State | Content |
|---|---|
| First run (no organisations) | Illustration, "Your practice has no organisations yet", actions **Create organisation** (primary) and **Open demo** |
| No results | "No organisations match", what was searched, **Clear search and filters**; hint about archived |
| Loading | Skeleton rows in the grid's row height; "Loading organisations" for screen readers |
| Error | "The directory didn't load", **Try again** (search and filters kept), **Report problem** |

## 6. Microcopy (en-CA; fr-CA in the catalogues)

Organisation (never "Organization"), Province, Fiscal year end (FYE), GST/HST cycle, Business Number
(BN), Trial — *n* days left ("Trial 12 d" in the chip), Paid, Demo, Read-only, Archived. Counts are
formatted with the user's locale ("2,000" / "2 000").

## 7. Accessibility

- Grid: `role="grid"`, `aria-rowcount` (all results), `aria-rowindex`, header buttons with `aria-sort`.
- Result count announced in a polite live region after each search ("143 of 2,000 organisations").
- Filters panel: each dimension is a `fieldset` with a `legend`; counts are part of the checkbox label.
- Go to organisation: dialog with combobox + listbox semantics; Esc closes and returns focus.
- Target: axe 0 violations on every state (V-01-T15).

## 8. Out of scope here (later deliverables)

Groups and tag management (V-02; the tag column and filter read V-02's tags), bulk selection and bulk
actions (V-03), dashboards (V-04), staff assignment (V-05).

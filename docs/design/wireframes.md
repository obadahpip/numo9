# Phase 0 wireframes

A-10-T02 · Deliverable A-10. Low-fidelity wireframes for the Phase 0 screens: the application shell,
the organisation directory, settings, contacts, chart of accounts, journal and the platform console.
They follow the information architecture and screen inventory of the Phase 0 plan (§3.2, §3.3) and
use the brand tokens from [Brand tokens](brand-tokens.md).

- Files: `docs/design/wireframes/*.svg` (1440 × 900 desktop frames; the shell also at 360 px).
  SVG imports into Figma as editable layers (drag the file onto the canvas), so the wireframes become
  the starting frames of the Figma file.
- Red numbered markers are annotations; the legend for each screen is below.
- Sample data is Canadian (Ontario organisation, CAD, GST/HST, Postal code `M5V 2T6`).
- Wireframes fix **layout, content and behaviour**, not final visuals. Components are the ones listed
  in A-10-T05 … T12; screens are built from `@numo9/ui` only.

## Walkthrough checklist (project lead)

| # | Screen | Built in | What to approve |
|---|---|---|---|
| 1 | Application shell (desktop, mobile) | A-10-T05 | Regions, nav order, org switcher position, job tray and notifications placement, mobile drawer |
| 2 | Organisation directory | V-01 / A-10-T10 | Saved views rail, search + filter chips, bulk bar, grid columns |
| 3 | Settings (General) | A-05 | Settings left nav with deep links, sectioned form, sticky save bar |
| 4 | Contacts list | B-01 | Role tabs with counts, grid columns, empty state |
| 5 | Chart of accounts | C-01 | Tree grid, type badges, GIFI column, health-check panel |
| 6 | Journal (basic) | C-02 / A-10-T11 | Header fields, LineGrid, totals, unbalanced message, post shortcut |
| 7 | Platform console | U-06 | Console nav, KPI tiles incl. founding counter, organisations grid |
| 8 | Package editor (console) | U-02-T09 | Product cards, limits, founding switch, live pricing-card preview, empty/error states |
| 9 | Price timeline + schedule dialog (console) | U-02-T10 | Versions per interval, today marker, "N subscriptions affected" dialog, overlap error |
| 10 | Promo codes (console) | U-02-T11 | Usage bar, create dialog, expire action, empty/error states |
| 11 | Contacts list with role tabs | B-01-T14 | Six role tabs with counts, title per tab, saved views, search, column chooser, bulk bar, archive |
| 12 | Contact form + live duplicate panel | B-01-T15, T16 | Section anchors, role chips, people, Canadian/foreign address, currency, credit warn/block, defaults, duplicate panel |
| 13 | Merge contacts dialog | B-01-T17 | Field chooser per row, "what moves" preview, alias, one-step merge, currency refusal |
| 14 | Organisation directory states | V-01-T14 | First-run empty state (Create organisation / Open demo), no results, loading skeleton, error with retry |
| 15 | Directory saved views, filters, column chooser | V-01-T11, T12 | Saved views rail and item menu, filters panel with counts, column chooser with reorder |
| 16 | Go to organisation (`Ctrl/⌘+K`) and keyboard map | V-01-T13 | Dialog search (name, BN with spaces), keys for the directory |
| 17 | Import contacts — 1 Upload | B-03-T12, T13 | Drop zone (CSV/XLSX, 25 MB, encodings), contacts vs people, saved mapping, template download, matching rules in plain language |
| 18 | Import contacts — 2 Map columns | B-03-T03, T12 | Auto-suggested field per column with sample values and match confidence (EN/FR headers), match keys (External ID → number → opt-in BN, never name), save mapping |
| 19 | Import contacts — 3 Review (dry run) | B-03-T07, T12 | Counts (new / updated / unchanged / errors), filter tabs, per-row action and changed fields, duplicates within the file, errors CSV |
| 20 | Import contacts — 4 Import | B-03-T08, T12 | Background job with progress, job tray, result with links, re-import = 0 changes, failure and retry |
| 21 | Groups & tags — group tree | V-02-T09 | Left-rail tree with counts, New group, drag to move, keyboard "Move to…" (max depth 5), organisations of the group with group and tag columns |
| 22 | Tag picker | V-02-T10 | Type-to-filter, apply/remove, type-to-create, 12-colour palette named (never colour alone), unique names per practice |
| 23 | Group staff panel + delete-group dialog | V-02-T07, T11 | Staff and role per group, inherited access shown, add/remove, delete dialog with affected organisations and staff counts |
| 24 | Contact activity timeline | B-02-T10 | Activity tab, type filter chips, newest first, amounts in the contact's currency, rows open their record |
| 25 | Statement preview and send | B-02-T05, T06, T11 | Outstanding/Activity, as-at date, language, Letter preview with aging, send dialog, history |
| 26 | Supplier statement reconciliation | B-02-T07, T08, T12 | Difference summary, two columns with auto-match, manual match and notes, import of their lines |

## 1. Application shell

![Application shell, desktop](wireframes/01-shell-desktop.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Brand mark | Links to the current organisation's Home (or the practice directory in `/p/…`) |
| 2 | Org switcher + practice badge | Shows the active organisation; menu lists the 5 recent organisations, a search box and "Open directory" (A-01-T14). The badge names the acting practice |
| 3 | Top navigation | Task-first modules that exist in Phase 0: Home · Contacts · Accounting · Documents · Settings. Active item: yellow text and underline on black. Later phases add Sales, Purchases, Banking, Tax, Payroll, Inventory, Reports |
| 4 | Search / quick-create | Command palette `Ctrl/⌘+K` (A-09); "+ Create" opens quick-create with shortcuts (`N I`, `N C`, `N J` …) |
| 5 | Job tray · notifications · help · user menu | Job tray icon (background jobs), bell (`Shift+N`), help/shortcuts (`?`), avatar menu (Profile, Preferences, Log out) |
| 6 | Breadcrumbs | Organisation › module › page; every crumb is a link; trial chip ("Trial — 23 days left") sits at the end of this bar |
| 7 | Content | Module screen; no promotional banners inside working screens (gap 12) |
| 8 | Job tray panel | Running and recent jobs with progress |
| 9 | Notification centre | Drawer, grouped by day, mark as read |

![Application shell, mobile 360 px](wireframes/02-shell-mobile.svg)

Below 1024 px the top navigation collapses into a menu button (44 × 44 px) that opens a drawer with
search, the module list and the practice links; the org switcher truncates the name; the bell and
user menu stay visible. No horizontal scroll at 360 px.

## 2. Organisation directory (practice workspace)

![Organisation directory](wireframes/03-directory.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Saved views rail | Personal and shared views; selected view highlighted |
| 2 | Search + filter chips | Search name, BN, owner, tag (`/` focuses); chips: Package, Status, Province, Fiscal year end, GST cycle, Group |
| 3 | Grid settings | Column chooser, density (comfortable/compact), save view |
| 4 | Bulk bar | Appears when rows are selected: Add to group, Tags, Assign staff, Message, Export |
| 5 | DataGrid | Virtualised; columns Organisation, BN, Province, Package, Status, FYE, Overdue, Assigned; `Space` select, `Enter` open, `B` bulk bar |

States: first-run empty state ("Create your first organisation" + "Open a demo"), no results, loading
skeleton, error with retry.

## 3. Settings — General

![Settings, General](wireframes/04-settings.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Settings navigation | Deep links `/o/:org/settings/{general, registrations, lock-dates, users-roles, email-domain, subscription, numbering, custom-fields, audit-log}`; each module's gear links its own section (gap 3) |
| 2 | Sticky save bar | Appears on first change: "You have unsaved changes", Discard, Save settings (`⌘S`); leaving with unsaved changes asks first |

Form uses Province picker and Postal code input; "On this page" anchors on wide screens.

## 4. Contacts

![Contacts](wireframes/05-contacts.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Role tabs | All contacts / Customers / Suppliers with counts; the page title follows the tab (gap 19) |
| 2 | DataGrid | Name, Role, Email, Phone, Province, Balance owing, Overdue |
| 3 | Empty state | Explains the next step with two actions: New contact, Import contacts |

## 5. Chart of accounts

![Chart of accounts](wireframes/06-chart-of-accounts.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Tree grid | Headers (Assets, Liabilities, Equity, Revenue, Expenses) collapse; columns Code, Name, Type badge, GIFI, Tax default, Balance; archived toggle |
| 2 | Health check | Accounts without a GIFI code, unreconciled bank accounts, duplicates |

`N A` creates an account.

## 6. Journal (basic, C-02 test path)

![Journal](wireframes/07-journal.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Header | Date (forgiving input, displayed `26 Oct 2026`), Narration, Book (Both / Tax / Management), Number (auto) |
| 2 | LineGrid | The shared document line editor (A-10-T11): account picker, description, tax, debit, credit; arrows move, `Enter` on the last row adds a line, drag to reorder |
| 3 | Balance message | Names both totals and the difference (§3.5 microcopy); Post is disabled until the difference is $0.00 |

`⌘Enter` posts; the posted journal gets its number and a "Reverse" action.

## 7. Platform console

![Platform console](wireframes/08-console.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | KPI tiles | MRR, active organisations, trials, founding offer counter ("786 of 1,000") |
| 2 | Charts | Trial funnel and churn; empty data renders as 0, never "—k" |
| 3 | Organisations grid | Organisation, Practice, Package, State, Founding #, MRR |

Console navigation: Metrics, Practices, Organisations, Products, Packages & prices, Promo codes,
Founding offer, Demo manager, Feature flags, Impersonation log, Jobs.

## 8. Package editor (U-02-T01)

U-02 adds three console frames: the package editor, the price timeline with its schedule dialog and
the promo-code list. Sample data: a "Growth" package (names are client data, entered by the
Platform Owner — never code).

![Package editor](wireframes/09-package-editor.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Header actions | Status chip (Draft / Active / Retired); History (record history drawer, audit A-04); Save draft; Activate package (draft → active) or Retire package (active → retired). Activating with no product is refused with a message, never a disabled button without reason |
| 2 | Product cards | One card per sellable product (main and active companion apps) with a switch; planned companion apps are greyed and can't be switched on; Practice and Client portal are free and part of every package (not toggled) |
| 3 | Limits | Organisation users (number or Unlimited); practice users are never counted |
| 4 | Founding offer | Switch: the package is eligible for the founding-1,000 offer (U-08) |
| 5 | Live preview | The public pricing card exactly as the website (Q-01) will show it, from the unsaved form: name, description, monthly/annual toggle, current price, products, user limit, founding badge |
| 6 | States | Empty list (first package), refused activation, field errors under each field (the API's field form) |

Retired package: a notice says it is hidden from sign-up and how many organisations keep their
subscription. Delete is offered for drafts only and is refused while anyone subscribes (retire instead).

## 9. Price timeline and schedule dialog (U-02-T01)

![Price timeline](wireframes/10-price-timeline.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Timeline per interval | Monthly and Annual rows; each price version is a bar from its start date to the next version's start (no end = open); the version in force today is highlighted |
| 2 | Today marker | Red line with today's date; versions after it are "Scheduled" and can be deleted until they start |
| 3 | Schedule a price change | Interval, new price (CAD, before GST/HST), start date (today or later) |
| 4 | Impact | "N subscriptions affected at their next renewal" — the count comes from the API for the chosen package, interval and date; renewals before the date keep the old price; grandfathered subscriptions never change |

A started price is never edited (Stripe prices are immutable): a change is always a new version.
Two versions can't overlap; the API's error is shown in the dialog.

## 10. Promo codes (U-02-T01)

![Promo codes](wireframes/11-promo-codes.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | New promo code | Opens the create dialog |
| 2 | Usage bar | Redemptions ÷ maximum ("7 of 10"); no maximum → "3 · no limit" |
| 3 | Status and Expire | Active / Used up / Expired; Expire ends an active code now (redemptions already made are kept) |
| 4 | Create dialog | Code (case-insensitive, unique), percent or fixed amount (CAD), duration (once, number of months, forever), maximum uses, expiry date, package restriction (empty = every package) |
| 5 | States | Empty list, field error (code taken), load failure, refusal for anyone without `platform.catalogue.manage` |

## 11. Contacts list with role tabs (B-01-T01)

B-01 adds three frames: the contacts list with every role tab, the contact form with the live
duplicate panel and the merge dialog. They extend frame 4 (A-10-T02), which showed only All /
Customers / Suppliers. Sample data is Canadian (Ontario and Quebec contacts, CAD and one USD
contact); contact numbers use the `C-0001` pattern.

![Contacts list with role tabs](wireframes/12-contacts-list-roles.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Role tabs | All contacts · Customers · Suppliers · Contractors · Agencies · Archived, each with its count. The page title, the browser tab title, the breadcrumb, the intro line and the primary button follow the tab ("Customers", "New customer") — gap-19. Roles are set on the contact, never inferred from transactions, so a new customer appears under Customers at once. Employees are reached from People/HR, not a tab here |
| 2 | Saved views | Personal and shared views (filters, columns, sort) per tab |
| 3 | Search, filter chips, column chooser | Search name, email, BN, tax ID, contact number (`/` focuses; accents ignored: "erable" finds "Érable"); chips Province, Currency, Credit mode; Columns and Save view |
| 4 | DataGrid | Number, Name, Roles, Email, Province, Currency, Credit limit (with warn/block), Balance owing; `Enter` opens; row actions Open, Edit, Archive, Merge with… |
| 5 | Bulk bar | Archive, Merge (exactly two selected), Export, Add role |
| 6 | States | Empty tab explains the role and offers New / Import; Archived tab: archived contacts keep their history and can be restored (archive = soft delete, never a hard delete) |

## 12. Contact form and live duplicate panel (B-01-T01)

![Contact form with duplicate panel](wireframes/13-contact-form.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | On this page | One page with section anchors: Details, People, Addresses, Financial, Sales defaults, Purchase defaults, Tax & compliance, Portal, Custom fields; the current section is highlighted while scrolling |
| 2 | Role chips | Customer, Supplier, Employee, Contractor, Government agency; at least one is required ("Choose at least one role.") |
| 3 | Details | Display name (required), contact number (next from the sequence, editable, unique), legal name, language (EN/FR for documents), Business Number (9 digits, check digit), Tax ID |
| 4 | Possible duplicates panel | Appears within 300 ms after typing stops (debounced) on display name, email, BN or tax ID: name similarity ≥ 60 % (accents and case ignored) or an exact email / BN / tax ID match; each row says why it matched and offers Open, Merge…, Ignore. A warning, never a block: same name in another province is shown, saving is still allowed. Announced once to screen readers (`role="status"`) |
| 5 | People | Unlimited people; one primary (★); "include in emails" per person |
| 6 | Addresses | Billing and shipping (shipping "Same as billing" by default). Canada: Province dropdown (13) and Postal code `A1A 1A1` checked against the province; other countries: Region and Postal code as free text. The province's tax hint is shown (QC → GST + QST, ON → HST 13 %) and resolved to a tax code by G-02 |
| 7 | Financial | Currency (ISO 4217, CAD by default), credit limit with Warn / Block segmented control and its explanation, statement preference |
| 8 | Defaults and compliance | Sales/purchase account, payment terms (master list), amounts are; T4A flag; exemption certificate (file, number, expiry); portal access; custom fields defined in Settings (text, number, date, select; up to 30) |
| 9 | Sticky save bar | "You have unsaved changes", Cancel, Save contact (`⌘S`); field errors under each field |

## 13. Merge contacts dialog (B-01-T01)

![Merge contacts dialog](wireframes/14-contact-merge.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Keep / merge in | The contact to keep is chosen first (the older one by default); the columns can be swapped |
| 2 | Field chooser | One row per field with a radio per side; roles can be kept as the union of both |
| 3 | What moves | Counts of every record that points at the merged contact (invoices, bills, credit notes, journal lines, people, attachments) from the merge registry; the merged contact number stays as an alias; its history shows on the kept contact |
| 4 | Refusal | Contacts in different currencies can't be merged (message names both currencies); other refusals the same way, never a disabled button without reason |
| 5 | Merge | Runs in one transaction: if any step fails nothing changes; the merge is in the audit log |

## 14. Organisation directory states (V-01-T01)

UX brief: [Organisation directory — UX research brief](directory-ux-brief.md).

![Organisation directory states](wireframes/15-directory-states.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | First run | The practice has no organisations: "Create organisation" (primary, focused first) and "Open demo" |
| 2 | No results | Says what was searched and filtered; "Clear search and filters"; archived organisations are hidden unless "Show archived" is on |
| 3 | Loading | Skeleton rows at the grid's row height; "Loading organisations" in the live region |
| 4 | Error | "The directory didn't load", Try again (keeps the search and filters), Report problem |

## 15. Directory saved views, filters with counts, column chooser (V-01-T01)

![Directory saved views, filters and column chooser](wireframes/16-directory-views-columns.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Saved views rail | The user's own views, stored on the server (they follow the user after logout/login and on another device); one can be the default; item menu: Update with changes, Rename, Set as default, Delete. A view with unsaved changes reads "(changed)" |
| 2 | Filters panel | Package, Status, Province, Fiscal year end, GST/HST cycle, Payroll, Overdue items, Unfiled returns, Show archived. Each option shows the number of organisations the list would show with that option added (every other filter applied); zero options stay, dimmed |
| 3 | Column chooser | Shared `@numo9/ui` component: show/hide and reorder (drag handle or `Alt+↑/↓`); the Organisation column always stays; order and visibility are saved in the view |

## 16. Go to organisation and keyboard map (V-01-T01)

![Go to organisation and keyboard map](wireframes/17-org-goto.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Go to organisation | `Ctrl/⌘+K` anywhere in the app; the same search as the directory (accent-insensitive name, BN with or without spaces, owner, tag); matches highlighted; `Enter` opens, `Ctrl/⌘+Enter` opens in a new tab, `Esc` closes and returns focus |
| 2 | Keyboard map | `/` search, `↓` into the rows, `↑/↓ PgUp/PgDn Home/End` move, `Enter` open, `Ctrl/⌘+Enter` new tab, `F` filters panel, `Ctrl/⌘+K` go to organisation |

## 17. Import contacts — step 1, Upload (B-03-T01)

B-03 adds a four-step wizard (Upload → Map columns → Review → Import) reached from the contacts list
(Import in the bulk bar and in the empty state, frame 11) and, with the same frames and other field
names, from the chart of accounts (C-01-T13). Every step shows the step bar; Back keeps what was
chosen; nothing is saved before the last step. Sample file: a Quebec client list exported from an
old system with French headers, saved in Windows-1252.

![Import contacts, step 1: upload](wireframes/18-import-upload.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Step bar | Four steps, the current one in black, finished ones with a check; steps can't be skipped. The live region announces "Step 1 of 4, Upload" |
| 2 | Drop zone | Drag and drop or Choose file (keyboard: `Enter`/`Space`); `.csv` and `.xlsx`, up to 25 MB (A-06 limit); the encoding is detected (UTF-8, UTF-8 with BOM, Windows-1252) — never asked |
| 3 | File contents | Contacts (one row per contact) or People at contacts (one row per person, linked by contact number or External ID, no limit per contact — B-03-T09) |
| 4 | Saved mapping | "Detect from the file's headers" by default; a saved mapping of the organisation is chosen automatically when the headers are the same; the list shows how often each was used |
| 5 | Template and rules | Download the CSV or Excel template (headers = the mapping fields, B-03-T13); the matching rules in plain words: External ID, then contact number, never the name; blank cells leave fields unchanged; `__CLEAR__` empties a field; formulas import their values |
| 6 | Errors | Wrong type, empty file, too large, no header row: the message says what to do ("Save it as .csv or .xlsx and try again"); Next stays enabled and explains on click rather than being disabled without a reason |

## 18. Import contacts — step 2, Map columns (B-03-T01)

![Import contacts, step 2: map columns](wireframes/19-import-map.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Step bar | As frame 17; the subtitle summarises the file: name, rows, columns, detected encoding, header row |
| 2 | Columns | One row per column of the file, in file order, with the first three non-empty sample values |
| 3 | Numo9 field | A select per column, pre-filled by auto-suggest (B-03-T03): English and French field names and synonyms, accents and case ignored ("Courriel" → Email, "NE" → Business Number, "Code postal" → Billing postal code); "Don't import" when nothing fits |
| 4 | Match confidence | Exact / Exact (FR) for a known header, Similar for a fuzzy match (to check), You chose after a manual change, No match. Similar matches are listed first in the screen-reader summary |
| 5 | Match keys and required fields | Rows match existing contacts by External ID, then contact number; Business Number only when switched on, and only when the first two are empty; never by name, so a renamed contact is updated (gap-21). Display name must be mapped |
| 6 | Save this mapping | Name the mapping; stored per organisation and entity (`ImportMapping`); the next file with the same headers maps itself |
| 7 | Validation | A field can be mapped from one column only; the message names both columns and the field |

## 19. Import contacts — step 3, Review the dry run (B-03-T01)

![Import contacts, step 3: review the dry run](wireframes/20-import-review.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Step bar | "A dry run: nothing has been saved yet" |
| 2 | Counts | New, Updated, Unchanged, Errors — each count opens its tab; New + Updated is the number the Import button shows |
| 3 | Within the file | Duplicates inside the file (same External ID or contact number on two rows): every copy is an error naming the other rows |
| 4 | Tabs, search, errors CSV | Filter by action; search by row number, name or number; Download errors gives a CSV with the row number, the column and the reason |
| 5 | Rows | Row number, action chip, contact (name and number), how it matched, and each changed field as "before → after"; formatted values (postal code spacing) are shown as such; `__CLEAR__` shows as "cleared" |
| 6 | Errors | One plain-language reason per row (province/postal code mismatch, unknown currency, invalid email, BN check digit, duplicate in file) — B-03-T04 validators |
| 7 | Blank cells | States that blank cells changed nothing (non-destructive updates, gap-21) |
| 8 | Import | "Import N rows" (new + updated); rows with errors are skipped, never half-imported |

## 20. Import contacts — step 4, Import (B-03-T01)

![Import contacts, step 4: import progress and result](wireframes/21-import-result.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Step bar | Final step; leaving the page doesn't stop the import |
| 2 | Progress | Background job (A-08) with rows done / total and time left; percentage in a polite live region; each row is its own transaction |
| 3 | Job tray | The same job in the job tray; the bell notifies when it finishes (A-07) |
| 4 | Result | Created / updated / unchanged / skipped counts; every change is in the audit log with the file name and row number |
| 5 | Next actions | Open the created or updated contacts (filtered list), download the errors CSV, import another file. Re-importing the same file shows 0 new and 0 updated (gap-21) |
| 6 | Failure | If the job stops, the message says which rows were saved; Try again re-runs the dry run so saved rows show as unchanged |

## 21. Groups & tags — group tree (V-02-T01)

![Groups and tags — group tree](wireframes/22-groups-tree.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | New group | Creates a group at the top level or, with a group selected, inside it; name required, unique among its siblings |
| 2 | Tree | Practice-scoped groups with organisation counts ("All organisations" and "No group" are views, not groups); drag a group onto another to move it with its sub-groups; a group can't go inside itself; depth 5 at most |
| 3 | Move to… | The keyboard alternative to dragging: search groups, `↑/↓` choose, `Enter` move, `Esc` cancel; the current parent is marked; refused moves say why (depth 5, inside itself) |
| 4 | Organisations of the group | The directory grid (V-01) filtered to the group, with Groups and Tags columns; an organisation can be in several groups |

## 22. Tag picker (V-02-T01)

![Tag picker](wireframes/23-tag-picker.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Search | Opens from "+ Tag" on a row (or the bulk bar); typing filters the practice's tags; `Space` toggles one |
| 2 | Create | When no tag has the typed name: "Create tag “…”" — created and applied in one step (`Enter`) |
| 3 | Colour | 12 accessible colours, each with its name; a tag always shows its name next to the colour (never colour alone); names are unique per practice, case and accents ignored |

## 23. Group staff panel and delete-group dialog (V-02-T01)

![Group staff panel and delete-group dialog](wireframes/24-group-staff.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Group staff | Staff assigned to a group can open every organisation in it and its sub-groups, including organisations added later; one role per person per group |
| 2 | Inherited access | "Access comes from" names the group that grants it; inherited rows (from a parent group) are changed on that group |
| 3 | Delete group | Practice admins only; the dialog counts what changes — organisations leaving the group (they stay in the practice), sub-groups moving up, staff assignments removed and the organisations people lose access to (those they can't reach another way); typed confirmation |


## 24. Contact activity timeline (B-02-T01)

![Contact activity timeline](wireframes/25-contact-timeline.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Activity tab | One timeline per contact: documents, payments, emails, notes and changes, newest first |
| 2 | Type filter | Chips per kind of event ("All" by default); search within the timeline |
| 3 | Rows | Date, event, reference, amount (contact's currency, blank when none), who; each row opens its record |

## 25. Statement preview and send (B-02-T01)

![Statement preview and send](wireframes/26-statement-preview.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Options | *Outstanding* (as at a date) or *Activity* (a date range with opening balance); language defaults to the contact's |
| 2 | Preview | Exactly the PDF: Letter 8.5 × 11 in with 1 in margins, organisation and contact addresses, lines, aging buckets (Current, 1–30, 31–60, 61–90, 90+), amount due in the contact's currency |
| 3 | Send | Email to the contact's billing person with the PDF attached (A-07); subject and body in the contact's language |
| 4 | History | Every statement sent (date, type, recipients, who); it also appears on the activity timeline |

## 26. Supplier statement reconciliation (B-02-T01)

![Supplier statement reconciliation](wireframes/27-supplier-reconciliation.svg)

| Marker | Region | Behaviour |
|---|---|---|
| 1 | Summary | Their balance, ours, the difference and what explains it (their lines without a bill, bills not on their statement) |
| 2 | Two columns | Their statement lines and our bills side by side; auto-match by invoice number, then by amount within ±3 days; unmatched highlighted |
| 3 | Manual match | Select one line on each side and match; notes on a line; the difference updates at once |
| 4 | Import | Their statement from CSV/XLSX with a column mapping (date, invoice number, amount, reference) or typed lines; lines added = rows in the file |

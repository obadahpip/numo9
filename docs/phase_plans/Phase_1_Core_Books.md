# NUMO9 — PHASE 1 · Core Books — Implementation Plan

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | 1 — Core Books (walking skeleton of real bookkeeping) |
| **Weeks** | Week 2 from kickoff |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment) |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §1, §2, §3 (Components C, D, E, F, G, K), §4 gap matrix, §5.2–§5.4, §6 · Project_Phases.md (Phase 1) · Quotation GMA-PFX-2026-003 §4–§5 · Agreement GMA-PFX-2026-003-A §06–§07 · xero_teardown.md §1–§9 · AI Coding Agent — Mandatory Engineering Workflow (Rules 1–11) |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE, applied to the phase, to every deliverable (one Git branch each) and to every atomic task |

---

## 0. How to use this file

- Every deliverable below (same ID as Project_Phases.md) is **one Git branch** `feature/<ID>-<short-name>` cut from `main`.
- Every deliverable is decomposed into **atomic tasks** (`<ID>-T01`, `<ID>-T02` …), each sized for a focused 1–2 hour session, independently testable (mocks/fixtures allowed), and ordered by dependency.
- Each atomic task runs its own cycle: **UNDERSTAND** (re-read the card, inspect existing code) → **PLAN** (restate expected behaviour + acceptance) → **BUILD** (smallest working piece) → **TEST** (run, compare with acceptance, edge cases, regression) → **IMPROVE** (only after green).
- A task is complete only when its acceptance is **observed**; a deliverable only when every task and the deliverable acceptance criteria pass; the phase only when the **exit demonstration** is observed on staging (Agreement §07).
- Part 1 of this file covers sections 0–5 for the whole phase and the cards for Components **C, D, E**. Cards for **F, G, K** and sections 7–12 follow in Part 2.

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase (outputs of Phase 0)

| Area | Already built and verified in Phase 0 | Used by Phase 1 for |
|---|---|---|
| Repository & infra (S-01, S-02, S-03, S-06 baseline) | Monorepo `backend/ frontend/ mobile/ infra/ docs/`, GitHub Actions CI, dev/staging/prod, Docker Compose + Caddy, Canadian region, TLS/CSP, partitioned posting/audit tables, per-org rate limits | Every branch; partitioned `ledger_journalline` |
| Tenancy (A-01) | `Practice`, `PracticeMember`, `Organisation`, `OrganisationMember`, `PracticeAssignment`; `OrgOwnedModel`; scoped manager; router sweep | All new models inherit `OrgOwnedModel`; every new endpoint registered in the sweep |
| Auth & RBAC (A-02, A-03) | Sessions, 2FA, roles, custom roles, **approval limits per user** (`ApprovalLimit(user, document_type, max_amount)`), permission catalogue lint | Approval of JEs, bills, POs; self-approval prohibition |
| Audit (A-04) | Append-only `AuditEvent` with field diffs, global viewer | Every state change in Phase 1 emits an audit event |
| Settings & locks (A-05) | `OrganisationSettings` (Province, BN, RT/RP/RC, QST, FYE, TZ, numbering, default terms), **per-module `LockDate`** (GL/AR/AP/Bank/Payroll/Tax) | Every posting checks the module lock |
| Files (A-06) | `Document` storage, preview, virus-scan hook, inbound email per org | Attachments on JEs, invoices, bills, expense claims |
| Notifications/email (A-07) | Branded templates, EN/FR variants, bounce flag, custom sending domain | Invoice/quote/reminder/statement emails |
| Jobs (A-08) | Celery + Redis + beat, idempotency keys, job dashboard | Recurring invoices/bills/JEs, reminders, statement runs, exceptions scans |
| Search (A-09) | Global search index + quick-create palette | New record types registered (quotes, invoices, bills, POs, journals, bank txns) |
| Design system (A-10) | `@numo9/ui`: `DataGrid`, `DocumentLineGrid` (shell), `Form`, `Picker`, `DatePicker`, `MoneyInput`, `EmptyState`, `StatusBadge`, `Drawer`, `CommandPalette`, i18n lint, visual regression | All Phase 1 screens; `DocumentLineGrid` becomes the shared sales/purchase grid in D-01 |
| SaaS (U-01…U-08) | Feature keys, entitlement engine (402 + explicit gating), Stripe billing, trial, demo, founding counter | Feature keys `accounting.*`, `tax.*`; demo seed extended with Phase 1 data |
| Workspace (V-01…V-05) | Organisation directory, groups/tags, bulk actions, cross-org dashboard shell | V-04 tiles start receiving real counts (unreconciled, unfiled returns, approvals) |
| Contacts (B-01…B-03) | `Contact` with roles, Province, default accounts/tax, `PaymentTerms` master, credit limit warn/block, currency, statement prefs | Default terms, tax, credit checks on every document |
| Ledger (C-01, C-02) | `Account` (types, sub-accounts, GIFI, require-contact/tracking/attachment flags), Canadian template with separate GST/HST/ITC/PST/QST controls; `JournalEntry`/`JournalLine` posting engine (balanced, atomic, append-only, `reverse()`, states, `book` dimension, gap-free sequence) | Every Phase 1 posting goes through `PostingService.post()` only |

Nothing in Sales, Purchases, Banking, Tax or Reporting exists yet. There is no production code that creates documents; the ledger can only receive journals through the C-02 service API.

### 1.2 Problem definition — the seven questions for Phase 1

1. **Who uses it?** Accountants (practice members) keeping the books of assigned organisations; Organisation Owners/Admins issuing invoices and paying bills; Sales clerks (quotes, invoices), Purchasing (POs, receipts, bills), Approvers (with amount limits), Employees (expense claims); the System (recurring documents, reminders, exceptions scans, filing-period generation).
2. **Desired outcome?** A paying organisation runs real books: issues quotes and invoices (and **revises a posted invoice to 101-1**), receives payments, raises POs, receives goods, enters and pays bills (EFT/cheque) with early-payment discounts, spends and receives money from a **never-locked bank account**, applies correct Canadian sales tax automatically, switches GST/HST filing cycle and files an out-of-cycle period, and reads a correct P&L, Balance Sheet, TB and aging — with the exceptions engine clean.
3. **Inputs?** Contacts, items (untracked/service in Phase 1; tracked stock arrives in Phase 2), document lines, dates, payment terms (incl. 2/10 net 30), bank statement files (CSV/OFX/QFX/QBO/XLSX), bank rules, tax registrations and filing-cycle settings, approval limits, attachments, manual journals, recode criteria, conversion balances.
4. **Outputs?** Posted balanced JEs; branded PDFs (quote, invoice + revision stamp, credit note, PO, statement, remittance); emails; AR/AP sub-ledgers; payment allocations; CPA 005 EFT files, cheque prints, positive-pay files; bank register and reconciliation reports; GST/HST return worksheets per period; tax reports; P&L, BS, Cash Flow (indirect + direct), TB, GL, Journal report, Equity, AR/AP aging and control reconciliation; dashboard; exceptions list with draft correcting entries; audit events.
5. **Business rules?** Double entry through C-02 only; ledger append-only (corrections = reversal + re-post); invoice revision = reverse + re-post in **one transaction**, suffix `-n`, filed-period rule; module lock dates and closed periods refuse postings naming the lock; approval limits per user, approver ≠ creator; pickers filtered by document side (sales vs purchase) and account type; effective-dated tax codes, place of supply from contact Province + registrations; zero-rated ≠ exempt ≠ out-of-scope; partial ITC %; due date required (default from terms); supplier invoice number unique per supplier; credit limit warn/block; negative cash/bank warn or block per setting; reconciliation never blocks; every money total uses `Decimal` and numeric(18,2) with banker's-safe rounding per line then document; CAD base currency (multi-currency arrives Phase 2 — fields reserved).
6. **What could go wrong?** AR drift after revisions; double posting on retries or concurrent approval; recurring jobs creating duplicates after worker restart; numbering collisions; tax rounding differences between line and document; wrong period after cycle switch; documents dated in filed periods; reminders sent for paid/disputed invoices; duplicate bank lines on re-import; rules applied in wrong order; partial receipts mis-stating stock commitments; cheque void not reversing payment; discount taken outside window; overpayments lost; lock bypass through recode; report performance on large GLs; time-zone off-by-one at period end; silent UI failures (the Xero "Unable to load" card).
7. **Smallest useful implementation?** Invoice (D-01 grid + D-03a) → payment (D-05) → spend money from a feed-less chequing account (F-01) → GST/HST code defaulted from Province (G-01/G-02) → P&L and BS (K-01/K-02). Build in that order first (the "golden path"), then widen to quotes, revisions, POs, reminders, cycles and exceptions.

### 1.3 Restated objective

- **Currently:** Phase 0 gives tenancy, SaaS, contacts, a chart of accounts and a posting engine, but nobody can issue a document, pay a bill, use a bank account, charge tax or read a statement.
- **Change:** Build the Core Books — journals with controls, sales with editable invoices (revisions), purchases with POs/receiving/3-way match and credit terms, never-locked banking with import/rules/optional reconciliation, the Canadian tax engine with switchable filing cycles, the core report engine, the dashboard and the exceptions engine.
- **Why:** This is the walking skeleton (Plan §1.4 Q7) that lets Profitex run a real organisation early, and it closes 40+ of the 61 Xero gaps (§2 below).
- **Done means:** the exit demonstration runs on staging: *invoice 101 for 1,130.00 → revise to 1,017.00 as 101-1 (AR −113.00, two linked JEs) → receive payment → spend money from a new chequing account with no import → switch GST/HST from quarterly to monthly from 1 Jul and file an out-of-cycle stub period → P&L/BS correct, BS balances, exceptions engine clean* — and every Phase 1 deliverable's acceptance criteria are observed.

### 1.4 Assumptions & interpretations

1. Items in Phase 1 are **service / untracked** items (the minimal item record from H-01 is stubbed as `Item(code, name, sales_account, purchase_account, sales_tax_code, purchase_tax_code, is_tracked=False)`); stock quantities from E-01 receipts are recorded as **receipt quantities** and wired to stock movements when H-03/H-04 land in Phase 2 (the E-01 acceptance "stock +6" is verified with a `StockMovementSink` interface + test double in Phase 1 and re-verified against H-04 in Phase 2).
2. Currency is CAD only in Phase 1; `currency` and `fx_rate` columns exist (default CAD / 1.0) so R-02 needs no migration of document tables.
3. E-signature on quotes uses an in-house typed-name + drawn-signature + IP/timestamp evidence record (no paid provider) unless the client elects a provider.
4. SMS/WhatsApp reminder channels are **hooks** (`ReminderChannel` interface, email implemented, SMS/WhatsApp adapters stubbed) — provider fees are the client's.
5. CPA 005 EFT files are generated per bank-specific originator settings entered by the organisation; positive-pay uses a generic CSV plus RBC/TD/BMO/Scotiabank/CIBC presets.
6. The system **never files** GST/HST with CRA: it produces the worksheet, marks filed (with confirmation number typed by the accountant), locks the period. Payment arrives in Phase 4 (G-09).
7. Late-payment interest on overdue invoices in D-07 is a line added to the next statement/invoice; the full interest engine is FN-04 (Phase 2), which extends D-07/E-07.
8. "Reports follow the current revision" means every report query joins `Invoice.current_revision`; superseded revisions are visible only in history.

Open questions for the client (non-blocking; defaults above apply): preferred invoice numbering pattern (default `INV-0001` vs plain `101`), default reminder schedule wording, cheque stock vendor (layout default: cheque on top + 2 vouchers, Letter).

### 1.5 Client inputs required

| Input | Needed for | Due |
|---|---|---|
| Sample invoices, quotes, bills, statements (PDF) | PDF layout fixtures (D-03a), import mapping fixtures | Start of week 2 |
| CRA business numbers (RT) for fixtures | G-03 worksheet header, D-03a BN on PDF | Start of week 2 |
| Bank statement samples from their banks (CSV/OFX) | F-02 saved mappings | Start of week 2 |
| Cheque stock / bank originator IDs (test) | E-06 CPA 005 & cheque print | Mid week 2 |

---

## 2. BETTER THAN XERO — gap analysis for Phase 1

| Gap # | Teardown ref | What Xero does / fails to do | What Numo9 does instead (better) | Observable proof (test tag) |
|---|---|---|---|---|
| 1 | §0 | Two UI generations; invoice, bill, repeating editors use different grids | One `DocumentLineGrid` for quote, invoice, recurring, credit note, PO, bill, supplier credit | `gap-01`: visual snapshot of all 7 editors uses same component id |
| 4 | §1 | No bank balance widget; "—k" on empty charts; ad widget | Bank balances widget by default, zeros render "0", no ads | `gap-04` |
| 5 | §2.1 | "Online payments" card fails silently; "Expired" status inconsistent | Every card has retry + error report; one `QuoteStatus` enum used by overview, list tabs and filters | `gap-05` |
| 6 | §2.2 | Invoice approval paywalled; no Overdue / Credit-notes tab; no saved filters | Approval never gated; Overdue and Credit notes tabs; saved views + column chooser | `gap-06` |
| 7 | §2.3 | Sales tax picker lists purchase codes; account picker unfiltered | Pickers filtered by side and account type; server rejects mismatches too | `gap-07` |
| 8 | §2.3 | Expired rates (MB pre-2019) selectable on 2026 docs | Effective-dated rates; expired hidden and rejected server-side | `gap-08` |
| 9 | §2.3 | User picks 1 of 36 codes manually | Place-of-supply defaulting from contact Province + registrations | `gap-09` |
| 10 | §2.3 | Line discount only; no document discount; no 2/10 net 30 | Line + document discount; early-payment terms with automatic discount posting | `gap-10` |
| 12 | §2.3 | Due date empty, not required; banners push form down | Due date required, prefilled from terms; zero banners in editors | `gap-12` |
| 13 | §2.4 | Repeating editor legacy/disabled; no proration | Same grid; proration; never plan-gated | `gap-13` |
| 14 | §2.5 | Credit note silently redirects | Full credit-note page; any gating is explicit with reason | `gap-14` |
| 16 | §2.7 | Reminders overdue-only; no escalation/SMS/late fee | Before- and after-due steps, escalation, opt-out, late-fee line, channel hooks | `gap-16` |
| 17 | §2.9 | Quote: different date format, no tax column, no optional lines/deposit/e-sign | Shared grid with tax; optional lines; alternatives; deposit; e-signature | `gap-17` |
| 22 | §4.1 | Purchases overview legacy vs Sales overview modern | One `OverviewPage` pattern for both | `gap-22` |
| 23 | §4.2 | No supplier-statement reconciliation (B-02, Phase 0), no early-payment discount, no routing by amount/department | Discount capture (E-07); routing rules by amount/department (E-02) | `gap-23` |
| 24 | §4.3 | Bill grid lacks discount/tax amount/column chooser; no invoice-no. uniqueness; no holdback; no 3-way match | Shared grid; uniqueness at entry; holdback; PO–GRN–bill match | `gap-24` |
| 25 | §4.5 | No partial receipt/GRN; POs non-posting, no commitment report; no PO limits | Receiving statuses; commitment report; per-user PO limits | `gap-25` |
| 26 | §4.6–4.7 | Checks/Cheques spelling; no positive pay; no register void/stale | "Cheque" everywhere; positive-pay export; register with void/stale tracking | `gap-26` |
| 27 | §5.1 | Bank module plan-locked; only Credit card/Other types | Never-locked accounts, 7 types, set-up prompt | `gap-27` |
| 28 | §5.3 | Rules lack regex/not-contains/ranges/priority/preview | All present + history preview | `gap-28` |
| 33 | §5.8–5.9 | Journals bypass AP/ITC; no contact on lines; no negative-cash warning; no approval; no journal type | Journal types, contact per line, attachment/contact rules, negative-balance control, approval | `gap-33` |
| 35 | §5.11 | Recode has no undo | Batch undo within open period; lock respected and explained | `gap-35` |
| 36 | §5.12 | Assurance ignores journals; no SoD/round/weekend/duplicate checks | Exceptions engine with all rules | `gap-36` |
| 44 | §6.8 | Tax defaults "based on last"; config over 4 pages | Account/contact-based defaults; one tax page (G-06) | `gap-44` |
| 45 | §6.9 | All accounts Exempt; no zero-rated vs exempt; no partial ITC | Province-rate defaults; distinct types; partial ITC | `gap-45` |
| 47 | §6.11 | Unbalanced conversion silently pushed to "Historical Adjustment" | Finalisation blocked while difference ≠ 0.00, difference named | `gap-47` |
| 49 | §6.14 | Report basis vs tax basis on two pages | One basis setting, explicit override per report | `gap-49` |
| 53 | §8.2 | AI flags symptoms only | Exceptions engine drafts the correcting entry | `gap-53` |
| 54 | §9.1 | No sales-tax report; no indirect cash flow; no AR/AP control reconciliation; two report engines | All present in one engine | `gap-54` |
| 55 | §9.2 | Header prints a number; "–" on empty; future period unlabelled | Name validation; "No activity in this period"; "Year to date" label | `gap-55` |
| 56 | §9.3 | Negative cash as negative asset; no Liabilities section | Overdrawn bank reclassified to current liabilities; A/L/E always printed | `gap-56` |
| 57 | §9.4 | TB unsorted; YTD only | Sorted by code; opening/movement/closing | `gap-57` |
| 58 | §9.5 | Journal order direction missing | Sort direction control | `gap-58` |
| 59 | §9.6 | GL Exceptions flags nothing | Rule set catches the teardown scenario | `gap-59` |
| 60 | §9.7 | Closing bank balance ignores petty cash | Cash definition configurable (bank + cash types) | `gap-60` |

**Beyond-Xero additions in this phase**

- **Invoice revisions** 101 → 101-1 → 101-2 with ledger re-post, PDF stamp, history, portal badge (client decision 5).
- **Never-locked banking** — bank accounts are plain ledger accounts usable instantly (client decision 6).
- **Filing-cycle engine** — monthly/quarterly/annual with effective-dated switch, out-of-cycle stub periods, stop/restart (client decisions 11–12).
- **GST/HST return worksheet** lines 101–115 on every Tax package (Xero plan inspected had none).
- **Exceptions engine with draft correcting entries** (e.g. the REFINED petty-cash scenario → draft Dr 1000 / Cr 2900 994.17).
- **CPA 005 EFT, cheque register, positive pay** for Canadian banks.

**Xero strengths matched conceptually (original design, no copying):** keyboard quick-create, column chooser and saved views, find-and-recode with audit report (plus undo), bank rules with fixed + % allocation (plus regex/priority/preview), duplicate-bill review (plus entry-time uniqueness), report layout editor with Draft/Published versions.

**[EXTRA] improvements beyond the gap report (inside Schedule A scope)**

- [EXTRA] **Live posting preview** drawer on every document: shows the exact JE (Dr/Cr, tax split, book) *before* approval — accountants see what will hit the ledger.
- [EXTRA] **Revision diff view**: side-by-side line diff between 101 and 101-1 with amount/tax deltas highlighted.
- [EXTRA] **Smart due-date chips** (Net 15/30/45/60, EOM, 2/10 net 30) driven by the terms master, plus "due in N days" helper text.
- [EXTRA] **Duplicate-document guard** on invoices too (same contact + amount + date within 7 days → soft warning).
- [EXTRA] **Undo toast (10 s)** for non-posting actions (delete draft line, archive rule, dismiss exception) instead of confirm dialogs.
- [EXTRA] **Paste-from-spreadsheet** into any document grid (tab-separated rows → lines, with validation per cell).
- [EXTRA] **Bank "spend money" from receipt photo** linking A-06 document to the transaction in one step.
- [EXTRA] **Period-status ribbon** on every editor: "GST period Jul 2026 — open / filed / locked" so the user knows before saving.
- [EXTRA] **Explain-this-number** drill on every report cell (source journals + filter chips).
- [EXTRA] **Approval inbox** unified across JEs, bills, POs, expense claims, with one-key approve/reject and limit indicator.

---

## 3. UI/UX DESIGN PLAN (senior UI/UX lead view)

### 3.1 UX principles applied in Phase 1

1. **Task-first layouts** — every editor shows the fields needed to finish the job above the fold; optional fields behind "More details" (progressive disclosure). No banners inside editors (Gap 12).
2. **One grid, one behaviour** — the same `DocumentLineGrid` (keyboard model, column chooser, paste, totals panel) for all documents; learn once, use everywhere (Gap 1).
3. **Explain before you post** — posting preview drawer and period-status ribbon; every block/warn message names the cause and the fix.
4. **No silent failures, no silent redirects** — every load error shows a retry with a reference id; every gated feature shows "Included in package X — Manage package" (U-03).
5. **Forgiving inputs** — money inputs accept `1,130`, `1130.00`, `$1 130,00`; dates accept `26/10`, `oct 26`, `+7`; pickers search by code, name and alias; tax and account auto-filled with visible "why" tooltip ("HST 13 % — customer in ON").
6. **Undo over confirm** where the action is reversible and non-posting; confirm dialogs only for posting/voiding/filing, and they state consequences in numbers ("This reverses JE 1045 and posts JE 1046; AR for Acme changes by −113.00").
7. **Keyboard-first for accountants** — `N I` new invoice, `N B` bill, `N J` journal, `N S` spend money, `Ctrl+Enter` save, `Ctrl+Shift+Enter` approve, `/` search, `J/K` row navigation in lists, `?` shortcut sheet; every shortcut shown in tooltips and the palette.
8. **Status clarity** — one status model per document type, same colours everywhere (Draft grey, Awaiting approval amber, Approved/Awaiting payment blue, Overdue red, Paid green, Revised purple badge, Void struck-through).
9. **Accessibility** — WCAG 2.1 AA: contrast ≥ 4.5:1, focus rings, grid fully operable by keyboard with ARIA grid roles, live regions for totals and errors, no colour-only status.
10. **Localisation-ready** — every string an ICU key (en-CA now, fr-CA keys created), layouts tested at +30 % string length, Canadian spelling (cheque, organisation, Province, Postal code), one date format per locale (`26 Oct 2026` en-CA), Letter page with inch margins on PDFs.
11. **Responsive** — editors usable at 1280 px and down to tablet (768 px: grid collapses to stacked line cards); lists usable on phone.
12. **Speed budgets** — list first paint < 1 s, editor interactive < 1.5 s, totals recalculation < 50 ms, optimistic UI for line edits.

### 3.2 Information architecture added in Phase 1

```
Top bar: [Org switcher] Home · Sales · Purchases · Banking · Accounting · Tax · Reports · Contacts   [+ Create] [Search /] [Approvals ●] [Bell] [Avatar]
Sales      → Overview · Quotes · Invoices · Recurring invoices · Credit notes · Payments received · Reminders & statements · Sales settings
Purchases  → Overview · Purchase orders · Receipts (GRN) · Bills · Recurring bills · Supplier credits · Expense claims · Batch payments · Cheques · Purchases settings
Banking    → Accounts · Transactions (spend/receive/transfer) · Import statement · Rules · Reconcile · Banking settings
Accounting → Chart of accounts · Journals (manual/recurring) · Find & recode · Conversion balances · Period close · Exceptions · Accounting settings
Tax        → Tax codes · Returns (GST/HST periods) · Filing cycles · Tax reports · Tax settings (one page)
Reports    → All reports · Favourites · Drafts · Published · Custom
Approvals  → Unified inbox (JEs, bills, POs, expense claims, invoices if rule on)
```
Settings deep-link per module (Gap 3): "Sales settings" opens `/settings/sales`, never a generic hub.

### 3.3 Screen inventory

| Screen | Primary user | Purpose | Key components | States | Keyboard shortcuts |
|---|---|---|---|---|---|
| Manual journal editor | Accountant | Create/post journals by type | `Form`, `DocumentLineGrid` (journal mode: Dr/Cr), `ContactPicker` per line, `AttachmentDrop`, `PostingPreview`, `PeriodRibbon` | draft / awaiting approval / posted / reversed / blocked-by-lock / negative-cash warning | `N J`, `Ctrl+Enter`, `Ctrl+Shift+Enter`, `Alt+R` add reversal date |
| Journals list | Accountant | Find, filter, bulk approve | `DataGrid`, tabs (All/Draft/Awaiting/Posted/Reversed/Recurring), saved views | empty with "Create journal" CTA | `J/K`, `A` approve, `/` |
| Recurring journal template | Accountant | Schedule repeating JEs | `ScheduleBuilder` (rrule), preview of next 6 dates | paused / active / ended | — |
| Conversion balances wizard | Accountant | Opening TB + AR/AP by document | `Stepper` (Date → Bank → AR → AP → Other → Review), live difference meter | balanced / unbalanced (finalise disabled + named difference) / finalised (locked) | `Ctrl+Enter` next step |
| Period close | Accountant | Close module periods, year-end roll | `Checklist`, module lock toggles, reopen dialog with reason | open / closing / closed | — |
| Find & recode | Accountant | Bulk recode with preview/undo | `ConditionBuilder`, `DataGrid` with selection, diff preview, batch history with Undo | no matches / preview / done / undone | `Ctrl+A` select all results |
| Sales overview | Owner/Sales | Status tiles + money coming in | `OverviewPage` (shared with purchases), `StatTile`, `AgingBar`, `CardWithRetry` | empty org / loading skeleton / card error with retry | `N I`, `N Q` |
| Quote editor | Sales | Create/send quotes | `DocumentLineGrid` (quote mode: optional/alternative lines), `DepositField`, `ExpiryDate` | draft/sent/accepted/declined/expired/invoiced | `N Q`, `Ctrl+Enter` |
| Public quote page | Customer | View, choose options, accept/sign or decline | `PublicDocumentView`, `SignaturePad`, option toggles | open / expired (accept disabled with reason) / accepted | Tab order only |
| Invoice editor | Sales/Accountant | Create, approve, send, **revise** | `DocumentLineGrid`, `TermsChips`, `PostingPreview`, `RevisionBanner` (on edit of posted), `RevisionHistoryPanel` | draft/awaiting approval/approved/sent/partially paid/paid/revised/void/credit-limit warn or block/period filed | `N I`, `E` edit (starts revision), `Ctrl+Shift+Enter` approve, `P` PDF |
| Revision diff | Accountant | Compare 101 vs 101-1 | `DiffTable` with deltas | n/a | `←/→` switch revisions |
| Recurring invoice editor | Sales | Schedule invoices | same grid + `ScheduleBuilder`, placeholders `{{month}} {{year}}`, proration toggle | active / paused / ended | — |
| Receive payment | Owner/Accountant | Allocate to many invoices | `AllocationTable` (auto-allocate oldest first), overpayment → credit | balanced / unallocated remainder / overpayment | `Ctrl+Enter` |
| Credit note editor | Sales | Full page, apply or refund | same grid, `ApplyToInvoices` panel | draft / approved / applied / refunded | `N C` |
| Reminders & statements settings | Owner | Before/after-due schedule | `TimelineEditor` (-7, 0, +7, +14, +30 days), template editor with preview, channel toggles | off / on / partial (channel not configured) | — |
| Purchases overview | Purchasing | Same pattern as sales | `OverviewPage` | as sales | `N B`, `N O` |
| PO editor | Purchasing | Create/approve/send POs | same grid, delivery block, approval limit indicator | draft/awaiting approval/approved/partially received/received/billed | `N O` |
| Goods receipt (GRN) | Warehouse/Purchasing | Receive partial quantities | `ReceiptTable` (ordered/received/outstanding), barcode-ready input | partial / full / over-receipt warning | `Enter` next line |
| Bill editor | Purchasing/Accountant | Enter, match, route, approve | same grid, `SupplierInvoiceNo` with live uniqueness check, `HoldbackField`, `MatchPanel` (PO/GRN/bill), `AttachmentPreview` split view | draft/awaiting approval/awaiting payment/paid/duplicate-suspected/match-variance | `N B` |
| Expense claim | Employee | Submit receipts & mileage | `ReceiptCapture` (photo/drag), `MileageCalculator` (km × CRA rate), category picker | draft / submitted / approved / rejected / reimbursed | `N E` |
| Batch payment | Accountant | Pay many bills, EFT/cheque | `BillSelector` with discount-window badges, totals, `FileDownload` (CPA 005), cheque print preview | ready / file generated / sent / partially failed | — |
| Cheque register | Accountant | Track cheques | `DataGrid` with status (issued/cleared/void/stale), void action, positive-pay export | — | — |
| Approvals inbox | Approvers | Approve across modules | `InboxList`, limit indicator, side preview | empty "Nothing awaiting you" | `A` approve, `R` reject, `J/K` |

### 3.4 Key user flows (with targets)

1. **Create and send first invoice** (Owner, new org): `+ Create → Invoice` (1) → type customer name, pick (2) → tax and terms auto-filled from contact → type line item + amount (3) → `Approve & send` (4) → PDF preview → Send (5). Target ≤ 5 clicks / ≤ 60 s; zero manual tax selection.
2. **Revise a posted invoice (101 → 101-1)**: open invoice 101 → `Edit` → banner "Editing a posted invoice creates revision 101-1. The original stays in history." → change line → reason (required, chips: price correction / quantity / tax / other) → `Save revision` → confirmation shows deltas (AR −113.00, tax −13.00, two journals) → done. Target ≤ 6 clicks; concurrent editor gets "Someone saved revision 101-1 two minutes ago — reload to continue".
3. **Receive a payment against 3 invoices**: `Receive payment` → customer → amount → auto-allocate oldest first (editable) → bank account → Save. Overpayment shows "113.00 will be held as customer credit".
4. **PO → partial receipt → bill with 3-way match**: approve PO 10 units → `Receive` 6 → outstanding 4 shown → `Create bill from PO` prefilled with received qty → if bill qty 12 vs PO 10 → amber match variance panel with "Approve with variance (needs approver)" or "Edit bill".
5. **Pay bills in a batch with discount**: Batch payments → filter "Discount ends ≤ 3 days" chip → select → totals show discount captured → choose EFT → download CPA 005 → mark sent.
6. **Expense claim** (employee, mobile-responsive web): New claim → snap receipt → category → amount (tax auto-split) → submit. Approver cannot be submitter (button absent with tooltip reason).
7. **Recode 500 lines with undo**: Find & recode → conditions → select all → new account → preview diff (500 lines, totals unchanged) → Recode → batch row with `Undo` (enabled while period open).

### 3.5 Microcopy & error-message rules

- Plain language, cause + fix + where: *"This invoice is dated 15 Jun 2026, before the AR lock date (30 Jun 2026). Change the date to 1 Jul 2026 or later, or ask an adviser to move the lock."*
- Numbers in messages, not adjectives: *"Bill total 1,245.00 does not match PO-0042 received value 1,130.00 (difference 115.00)."*
- Never blame: *"We couldn't load online payments. Retry · Reference 7F3A"* (Gap 5).
- Revision language: "Revision 1 of invoice 101 — supersedes the version issued 26 Oct 2026".
- Gating: *"Recurring invoices are included in the Accounting product. Your package: Tax only. View packages."* Never a redirect.
- Canadian terms: GST/HST, ITC, cheque, Province, Postal code, vacation pay, organisation.
- Confirm dialogs state consequences and offer the safe default as the focused button.

### 3.6 Accessibility & usability test plan

| Usability task (5 accountants + 3 owners, moderated, staging) | Success metric |
|---|---|
| Create and send an invoice to an Ontario customer | ≥ 90 % complete in < 90 s; 0 wrong tax codes |
| Revise invoice 101 and explain what changed in the ledger | ≥ 80 % correctly state AR delta from the confirmation screen |
| Receive goods partially and create the bill | ≥ 80 % without help; 0 posting errors |
| Find why a journal was refused (lock date) | 100 % identify the lock from the message alone |
| Recode 50 lines then undo | ≥ 90 % succeed; SUS ≥ 75 |

Automated: axe-core on every screen in CI (0 serious/critical), keyboard-only Playwright scripts for the 7 flows above, Lighthouse accessibility ≥ 95 on editors, pseudo-locale (+30 %) visual snapshots.

---

## 4. TOOLS & TECHNOLOGY FOR PHASE 1

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| Backend core | Python 3.12, Django 5, DRF | Models, services, API | GMA core stack |
| Money & math | `decimal.Decimal` (context ROUND_HALF_UP), `django-money` (optional field helpers) | All amounts, tax rounding | numeric(18,2) DB columns; never float |
| Dates & schedules | `python-dateutil` (`rrule`, `relativedelta`), `zoneinfo` | Recurring documents, terms, filing periods, due dates | Org-local time zone for period ends |
| State machines | `django-fsm-2` (or hand-rolled transition service) | Document lifecycles (invoice, bill, PO, quote, JE) | Transitions emit audit events |
| Concurrency | PostgreSQL `SELECT … FOR UPDATE`, advisory locks, `django-concurrency`-style version column | Revision conflicts, numbering, approvals | Optimistic `version` on documents |
| Background jobs | Celery 5, Redis 7, `django-celery-beat`, idempotency key table (A-08) | Recurring invoices/bills/JEs, reminders, statement runs, exceptions scan, period generation | Exactly-once tick via unique (schedule_id, tick_date) |
| PDF | WeasyPrint (templates), `pypdf` (merge), headless Chromium fallback | Invoice/quote/credit note/PO/statement/remittance/cheque PDFs with revision stamp | Letter, inch margins |
| Email | Django email + transactional provider (Postmark/SES), Mailpit in dev | Sending documents and reminders | Bounces from A-07 |
| Bank files | `ofxparse`, `ofxtools`, `openpyxl`, `csv`, `chardet` | F-02 import (CSV/OFX/QFX/QBO/XLSX) | Saved bank mappings |
| EFT / cheques | Internal `cpa005` writer module + fixed-width validator; `reportlab` or WeasyPrint for cheque/MICR layout; MICR E-13B font | E-06 | Font licence check |
| Regex safety | `re2` (google-re2) or regex timeout guard | F-04 bank rules regex conditions | Prevent ReDoS |
| Search | PostgreSQL full-text + `pg_trgm` | Duplicate detection, global search registration, contact/item pickers | Already in A-09 |
| Reporting | SQL aggregates on partitioned lines, materialised balance snapshots per account/period, `django-pgviews` | K-01/K-02 under 3 s p95 | Read replica optional |
| Exports | `openpyxl`, `XlsxWriter`, CSV, WeasyPrint | Report/list exports | Export = on-screen rows |
| API docs | `drf-spectacular` (OpenAPI 3) | Every Phase 1 endpoint | Contract tests later (W-01) |
| Frontend | Next.js 15 App Router, TypeScript, React Query (TanStack Query), React Hook Form + Zod, Tailwind, `@numo9/ui` | All screens | One design system |
| Grid | TanStack Table + virtualisation (TanStack Virtual) inside `DocumentLineGrid` | Document lines, lists | Keyboard model + ARIA grid |
| Charts | Recharts or visx (via design-system wrappers) | Dashboard, aging bars | Zero renders "0" |
| Signature | `signature_pad` | Quote e-signature | Evidence record server-side |
| i18n | `react-intl` / FormatJS (ICU), Django gettext + ICU, i18n extraction CI | All strings | en-CA live, fr-CA keys |
| Design | Figma (component library mirror), FigJam (flows), Storybook 8 | Wireframes, component states | Every new component has stories |
| Testing — backend | pytest, pytest-django, factory_boy, Hypothesis, freezegun/time-machine, pytest-xdist, coverage.py | Unit/property/integration | ≥ 85 % on ledger, revisions, tax |
| Testing — frontend | Vitest, Testing Library, MSW (API mocks), Playwright (E2E + a11y), axe-core, Chromatic or Playwright snapshots (visual regression) | Components, flows | Keyboard-only flows |
| Performance | k6, `django-silk`/`django-debug-toolbar` (dev), `EXPLAIN ANALYZE` scripts, Lighthouse CI | Reports p95, list speed | Budgets in §3.1 |
| Quality | ruff, mypy (strict on `ledger`, `sales`, `purchases`, `tax`), import-linter (module boundaries), eslint, prettier, pre-commit, semgrep | Static checks | CI gate |
| Security | OWASP ZAP baseline, pip-audit, npm audit, gitleaks, Trivy (images), Bandit | Each PR / nightly | No high findings |
| Observability | Sentry (backend + frontend), structured logging (structlog), Prometheus metrics for job ticks | Error + job monitoring | Full S-04 in Phase 5 |
| Dev productivity | Docker Compose, Makefile targets (`make seed-phase1`, `make sweep`), Mailpit, MinIO, Stripe CLI (unchanged), ngrok for public quote links in dev | Local dev | — |
| Docs | MkDocs Material in `docs/`, ADR template (`docs/adr/ADR-002-invoice-revisions.md`) | Developer + user docs | ADR-002 written in D-03b |
| **Internal tools to build in Phase 1** | `make fixtures-phase1` (50 sales fixture documents, 50 purchase fixtures, REFINED teardown fixture org), `manage.py ledger_check` (TB = 0, AR/AP = control, AR = Σ open current revisions), `manage.py replay_ticks` (recurring job replay test), `manage.py recode_undo`, CPA 005 validator CLI, bank-file anonymiser, tax-matrix generator (all provinces × code types × 2026 dates), posting-preview API reused by UI and tests, revision property-test harness | Verification and support | Live in `backend/tools/` |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 objective

A paying organisation runs real Canadian books in Numo9: controlled journals, sales with editable posted invoices, purchases with receiving/3-way match and credit terms, never-locked banking, Canadian tax with switchable filing cycles, and correct core reports with an exceptions engine.

### 5.2 Level 2 components

| Component | Deliverables | Purpose |
|---|---|---|
| C — General Ledger & Journals | C-03, C-04, C-05, C-06, C-07 | Journal types and controls, manual/recurring/approval, conversion balances, period close, find & recode with undo |
| D — Sales | D-01, D-02, D-03a, D-03b, D-04, D-05, D-06, D-07, D-09 | Shared grid, quotes, invoices + revisions, recurring, payments, credit notes, reminders, overview |
| E — Purchases | E-01, E-02, E-03, E-04, E-06, E-07 | POs/GRN/3-way match, bills, recurring bills & supplier credits, expense claims, batch payments & cheques, early-payment discounts |
| F — Banking | F-01, F-02, F-04, F-05, F-06, F-07 | Never-locked accounts, import, rules, optional reconciliation, transfers, negative-balance controls |
| G — Tax Engine (core) | G-01, G-02, G-03, G-03a, G-03b, G-05, G-06 | Codes & rates, place of supply, GST/HST worksheet, filing cycles, stop/restart, tax reports, one tax settings page |
| K — Reporting (core) | K-01, K-02, K-03, K-05, K-09 | Report engine, statements, AR/AP reports, dashboard, exceptions engine |

Total: **37 deliverables**.

### 5.3 Dependency graph and execution order

```
Phase 0 (A, U, B, C-01, C-02)
   │
   ├── G-01 Tax codes ── G-02 Place of supply ── G-06 Tax settings page
   │        │
   ├── C-03 Journal types/controls ── C-04 Manual/recurring/approval ── C-05 Conversion ── C-06 Period close ── C-07 Recode+undo
   │        │
   ├── F-01 Never-locked accounts ── F-06 Transfers ── F-07 Negative controls
   │        │            └── F-02 Import ── F-04 Rules ── F-05 Reconciliation
   │        │
   ├── D-01 Shared grid (needs G-01/G-02) ──┬── D-03a Invoices ── D-05 Payments ── D-06 Credit notes
   │                                        │        └── D-03b Revisions (needs G-03 rules)
   │                                        ├── D-02 Quotes (→ convert to D-03a)
   │                                        ├── D-04 Recurring invoices
   │                                        ├── D-07 Reminders/statements (needs D-03a, D-05)
   │                                        ├── D-09 Sales overview & lists
   │                                        ├── E-01 PO/GRN/3-way ── E-02 Bills ── E-03 Recurring bills & supplier credits
   │                                        │                           ├── E-06 Batch payments & cheques (needs F-01)
   │                                        │                           └── E-07 Early-payment discount (needs D-05/E-06)
   │                                        └── E-04 Expense claims (needs E-02)
   │
   ├── G-03 GST/HST worksheet ── G-03a Filing cycles ── G-03b Stop/restart ── G-05 Tax reports
   │
   └── K-01 Report engine ── K-02 Statements ── K-03 AR/AP ── K-05 Dashboard ── K-09 Exceptions (needs C-03, F-07, G-01)
```

**Execution order** (‖ = can run in parallel by different engineers):

1. G-01 ‖ C-03 ‖ F-01
2. G-02 ‖ C-04 ‖ F-06 ‖ F-02
3. D-01 ‖ G-06 ‖ F-07 ‖ F-04
4. D-03a ‖ E-01 ‖ C-05 ‖ K-01
5. D-05 ‖ E-02 ‖ K-02 ‖ G-03
6. **Golden-path checkpoint**: invoice → payment → spend money → P&L/BS (smallest useful implementation demo)
7. D-06 ‖ E-03 ‖ G-03a ‖ F-05
8. D-03b (after G-03) ‖ E-04 ‖ G-03b ‖ K-03
9. D-02 ‖ D-04 ‖ E-06 ‖ C-06
10. D-07 ‖ E-07 ‖ G-05 ‖ C-07
11. D-09 ‖ K-05
12. K-09 (last: consumes all)
13. Phase exit demonstration on staging

---

## 6. PLAN — Deliverable cards with ATOMIC TASKS (Rule 3)

> Part 1 covers Components C, D and E. Components F, G and K continue in Part 2.

### 6.1 General Ledger & Journals (Component C)

### C-03 · Journal types, contacts on lines, negative-balance controls

- **Branch:** `feature/C-03-journal-types-controls`
- **Objective:** classify every journal by type, allow a contact on each line, enforce attachment/contact rules on expense journals, and warn/block journals that drive cash or bank negative.
- **Current behaviour:** C-02 posts balanced journals with a book dimension but no type, no line contact, no business controls.
- **Expected behaviour (better than Xero):** journal types General / Adjusting / Closing / Reclass / Tax-adjustment (tax book only) / Payroll / Depreciation (system types not user-selectable); optional contact per line feeding AR/AP sub-ledger views; per-organisation rules "require attachment" and "require contact" on journals touching expense accounts; a journal that drives any cash/bank account below zero is **blocked for non-advisers** and **warned for advisers** (reason required, stored); optional auto-reversing date creating the reversal on that date.
- **Gap #s closed:** 33 (with C-04, F-07).
- **Business rules:** tax-adjustment journals force `book = tax` on all lines and may not hit bank accounts; closing journals only by year-end process (C-06); account flags from C-01 (`require_contact`, `require_tracking`, `require_attachment`) enforced on journal lines; negative check uses ledger balance at journal date **and** at today (future-dated subsequent entries considered); reversal date > journal date and in an open period.
- **Edge cases:** journal hitting two bank accounts where one goes negative; backdated journal pushing a past balance negative but today's balance positive (warn — balance at journal date matters); attachment uploaded then deleted before posting; reversal date in a locked period; contact archived after posting.
- **UI/UX notes:** type selector as segmented control with description tooltips; per-line contact column hidden by default (column chooser) but auto-shown when an account requires contact; inline warning chip on the bank line "Petty Cash would be −994.17 on 15 Jun 2026"; adviser override dialog with reason textarea (min 10 chars); attachment drop zone in header with red outline when required.
- **Dependencies:** C-01, C-02, A-03 (adviser role), A-06 (attachments), A-05 (locks).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| C-03-T01 | Add `JournalType` enum + `journal_type` field on `JournalEntry` (default General), migration; system types flagged non-selectable | DB | C-02 | Migration applies/rolls back; existing JEs default to General | unit, migration test |
| C-03-T02 | Add nullable `contact` FK on `JournalLine` (org-scoped), index (org, contact) | DB | B-01, T01 | Line saves with contact from same org; other-org contact rejected | unit + sweep |
| C-03-T03 | `JournalPolicy` service: validate type rules (tax-adjustment ⇒ all lines `book=tax`, no bank accounts; closing only from C-06 caller) | BE | T01 | Tax-adjustment with bank line raises `JournalRuleError` naming the line | unit |
| C-03-T04 | Account-flag enforcement in `JournalPolicy`: `require_contact`, `require_tracking`, `require_attachment` per line | BE | T02 | Line on account with require_contact and no contact → error naming account | unit (parameterised) |
| C-03-T05 | Org settings: `journal_expense_requires_attachment`, `journal_expense_requires_contact` toggles (A-05 settings page section) | DB/BE | A-05 | Toggles persist, audited | unit |
| C-03-T06 | Expense-journal rule: if any line hits an Expense-class account and toggle on → attachment/contact required | BE | T04, T05 | Expense journal without attachment refused when on; accepted when off | unit |
| C-03-T07 | `CashBalanceGuard`: compute projected balance of each cash/bank account at journal date and at today including the journal | BE | C-02 | Fixture: Petty Cash 0 + journal Cr 417.22 → projected −417.22 detected | unit + property (random sequences) |
| C-03-T08 | Guard outcome by role: non-adviser → block; adviser → warn with mandatory reason stored in `JournalOverride(reason, user, at)` | BE | T07, A-03 | Non-adviser 409 with message; adviser posts with reason; override audited | unit + API |
| C-03-T09 | Auto-reversing date: field `auto_reverse_on`; Celery beat task posts `reverse()` on that date idempotently | BE | A-08 | Reversal created exactly once after worker restart; locked-period date rejected at save | integration (freezegun) |
| C-03-T10 | API: extend `/api/v1/journals/` serializer (type, line contact, auto_reverse_on, override_reason); permission & feature key `accounting.journals` | API | T01–T09 | OpenAPI shows fields; 402 when product absent; sweep passes | API tests |
| C-03-T11 | UI: journal type segmented control + descriptions; system types hidden | FE | T10 | Only selectable types shown; i18n keys exist | Vitest |
| C-03-T12 | UI: contact column in journal grid; auto-shown when account requires it | FE | T10, D-01 shell | Selecting require-contact account reveals and focuses contact cell | Vitest + Playwright |
| C-03-T13 | UI: negative-balance inline chip + adviser override dialog; block message for non-advisers | FE/UX | T08 | Teardown scenario shows "Petty Cash would be −994.17"; dialog requires reason | Playwright |
| C-03-T14 | UI: attachment-required state (red outline + message) and posting disabled until satisfied | FE | T06 | Post button disabled with tooltip reason | Playwright |
| C-03-T15 | Audit hooks: type change, override, auto-reversal posted | BE | A-04 | Audit viewer shows each event with diff | integration |
| C-03-T16 | Fixtures: REFINED teardown journals (417.22, 576.95) + negative-cash scenarios | QA | T07 | `make fixtures-phase1` loads them | fixture test |
| C-03-T17 | Docs: journal types & controls page (user guide) + i18n en-CA/fr-CA keys | DOC | T11–T14 | Docs page in MkDocs; missing-key gate green | CI |

- **Deliverable acceptance:** Petty Cash below zero is blocked for non-advisers and warned (with stored reason) for advisers; an expense journal without attachment is refused when the rule is on; tax-adjustment journals post to the tax book only.
- **Testing approach:** unit + Hypothesis property test (no sequence of non-adviser journals ends with negative cash), integration with posting engine, Playwright for UI states, tenant sweep, regression on C-02 concurrency test.
- **Risks & mitigations:** performance of projected-balance query on large ledgers → use per-account daily balance snapshot + delta; false positives on backdated entries → show both dates in message.

### C-04 · Manual, recurring and approval workflow

- **Branch:** `feature/C-04-journal-workflow`
- **Objective:** full manual journal UI, recurring journal templates and threshold-based approval where the approver is never the creator.
- **Current behaviour:** journals can be posted only through the service API; no UI, no recurrence, no approval.
- **Expected behaviour:** journal editor with line autocomplete (account by code/name, description memory, contact), Save draft / Submit for approval / Post; recurring templates (rrule) generating one draft or posted journal per period; approval required when total ≥ org threshold or user's A-03 limit is exceeded; approver ≠ creator enforced server-side; unified Approvals inbox.
- **Gap #s closed:** 33.
- **Business rules:** states Draft → Awaiting approval → Posted → Reversed (from C-02); a user whose approval limit < journal total cannot approve; recurring template stores lines, schedule, end date, mode (draft/post); generated journal dated on schedule date; if the period is locked, the occurrence is skipped and an exception raised (not silently posted elsewhere).
- **Edge cases:** template edited between ticks; schedule on 31st in February (use last day); worker restart mid-tick; approver removed from org while item waiting; creator tries to approve via API.
- **UI/UX notes:** spreadsheet-like Dr/Cr grid with running difference meter ("Out of balance by 12.50") and Post disabled until 0.00; `Tab` creates new line at end; "Copy journal", "Reverse journal" actions; recurring preview list "Next 6 dates"; Approvals inbox with limit indicator ("Your limit 5,000.00").
- **Dependencies:** C-03, A-03, A-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| C-04-T01 | `JournalApprovalPolicy` model fields on `OrganisationSettings`: `journal_approval_threshold` (nullable = never) | DB | A-05 | Threshold persisted, audited | unit |
| C-04-T02 | Approval service: `submit()`, `approve(user)`, `reject(user, reason)`; checks approver ≠ creator and `ApprovalLimit` | BE | C-02, A-03 | Self-approval raises; limit 5,000 cannot approve 5,000.01 | unit (parameterised) |
| C-04-T03 | Posting gate: `post()` refuses if approval required and not approved | BE | T02 | Direct post of above-threshold JE → 409 "Approval required" | unit + API |
| C-04-T04 | `RecurringJournalTemplate` model (lines JSON validated, rrule string, start/end, mode, next_run, paused) | DB | C-03 | Invalid rrule rejected; template saves | unit |
| C-04-T05 | Recurrence generator using dateutil rrule with month-end clamp; returns occurrence dates | BE | T04 | 31 Jan monthly → 28/29 Feb, 31 Mar | unit + Hypothesis |
| C-04-T06 | Celery tick task with unique (template_id, occurrence_date) idempotency row; locked period → skip + exception record | BE | T05, A-08 | Two workers / restart create exactly one JE per period | integration (concurrency) |
| C-04-T07 | API endpoints: `/journals/{id}/submit`, `/approve`, `/reject`, `/journals/recurring/` CRUD, `/journals/recurring/{id}/preview` | API | T02–T06 | OpenAPI documented; permissions `accounting.journals.approve` declared | API tests + sweep |
| C-04-T08 | Approvals inbox aggregation endpoint `/api/v1/approvals/` (JEs now; bills/POs/claims register later via `ApprovableRegistry`) | API | T07 | Lists only items user may approve; counts match | API test |
| C-04-T09 | UI: journal editor Dr/Cr grid with autocomplete, difference meter, keyboard model | FE | T07, D-01 grid | Post disabled while difference ≠ 0.00; `Tab` adds line | Vitest + Playwright |
| C-04-T10 | UI: actions bar (Save draft / Submit / Post / Copy / Reverse) with state-aware visibility | FE | T09 | Buttons match state matrix | Vitest (state table) |
| C-04-T11 | UI: recurring template editor with schedule builder + next-6-dates preview + pause/resume | FE/UX | T07 | Preview equals backend preview | Playwright |
| C-04-T12 | UI: Approvals inbox (list, side preview, `A`/`R` keys, limit indicator, empty state) | FE/UX | T08 | Approve via keyboard; self-created items show "You created this" with no approve button | Playwright + axe |
| C-04-T13 | Notifications: submit → approvers notified; approve/reject → creator notified (A-07) | BE | T02 | Emails/in-app delivered once | integration |
| C-04-T14 | Global search & quick-create registration for journals (`N J`) incl. narration indexing | BE/FE | A-09 | Searching "Ontario Corporation" returns the journal | integration |
| C-04-T15 | Tests: approval matrix (role × amount × creator) and recurrence replay | QA | T02–T06 | Matrix green in CI | pytest |
| C-04-T16 | Docs + i18n keys | DOC | T09–T12 | Missing-key gate green | CI |

- **Deliverable acceptance:** one recurring JE per period (verified after worker restart); self-approval impossible (UI and API); approval limit enforced.
- **Testing approach:** unit, concurrency integration (two Celery workers in CI), Playwright flows, security (API self-approval attempt), regression on C-02.
- **Risks:** duplicate ticks → idempotency row with unique constraint; template drift → generated JE stores template version.

### C-05 · Conversion balances

- **Branch:** `feature/C-05-conversion-balances`
- **Objective:** enter opening balances at a conversion date — TB plus open AR/AP by document — and refuse finalisation while unbalanced.
- **Current behaviour:** none; a new organisation starts from zero balances.
- **Expected behaviour (better than Xero):** guided wizard (Conversion date → Bank & cash → Open invoices → Open bills → Other balances → Review); AR/AP opening entered **per document** (creating `OpeningInvoice`/`OpeningBill` records so aging and payments work); live difference meter; **Finalise disabled while difference ≠ 0.00**, with the difference named and the accounts listed; no automatic "historical adjustment" plug; optional "lock balances" setting the GL lock at conversion date.
- **Gap #s closed:** 47.
- **Business rules:** conversion date = day after the last closed period in the old system; opening JE type Adjusting, dated conversion date − 1? (No: dated conversion date, flagged `is_opening`); AR control balance must equal Σ opening invoices, AP likewise; retained earnings computed from P&L accounts if entered as TB; editing after finalisation requires adviser + creates a correcting opening JE (append-only).
- **Edge cases:** opening invoice partially paid; credit balances in AR; negative petty cash at conversion (warn via C-03 guard); foreign-currency opening items (reserved, CAD only now); user enters P&L balances for a mid-year conversion (allowed, comparative YTD).
- **UI/UX notes:** stepper with progress, each step saves draft; difference meter sticky at bottom ("Debits 120,450.00 · Credits 120,437.50 · Difference 12.50 — Finalise unavailable"); import TB from CSV/XLSX with column mapping; open-document grids paste-friendly.
- **Dependencies:** C-02, C-03, B-01, D-03a/E-02 document models (opening variants), A-05 locks.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| C-05-T01 | `ConversionSession` model (conversion_date, status draft/finalised, created_by, finalised_by/at) one per org | DB | A-01 | Second active session refused | unit |
| C-05-T02 | `ConversionLine` (account, debit, credit) with validation (one side only) | DB | T01 | Both sides filled rejected | unit |
| C-05-T03 | `OpeningDocument` link: opening invoices/bills stored as `Invoice`/`Bill` with `is_opening=True`, no revenue posting | DB/BE | D-03a/E-02 models (stub) | Opening invoice appears in AR aging, posts nothing until finalise | unit |
| C-05-T04 | Difference calculator service incl. AR/AP control vs documents check | BE | T02, T03 | Returns difference and list of unbalanced accounts | unit + Hypothesis |
| C-05-T05 | Finalise service: refuses if difference ≠ 0.00 or control ≠ documents; posts one opening JE (`is_opening`) atomically | BE | T04, C-02 | Unbalanced → error naming difference; balanced → JE posted, session locked | unit + integration |
| C-05-T06 | Optional "lock balances": set GL/AR/AP lock at conversion date − 1 on finalise | BE | T05, A-05 | Lock set and audited | unit |
| C-05-T07 | Post-finalise correction flow: adviser creates correcting opening JE (no edits to original) | BE | T05 | Original JE unchanged; correction linked | unit |
| C-05-T08 | TB import (CSV/XLSX) with column mapping + dry-run report | BE | T02 | Mapping errors listed per row; dry-run writes nothing | integration |
| C-05-T09 | API `/api/v1/conversion/` (session, lines, documents, difference, finalise, import) + feature key `accounting.conversion` | API | T01–T08 | OpenAPI; sweep | API tests |
| C-05-T10 | UI: stepper wizard with saved progress per step | FE/UX | T09 | Leaving and returning resumes at step | Playwright |
| C-05-T11 | UI: sticky difference meter + disabled Finalise with reason tooltip | FE | T09 | Meter updates < 50 ms; tooltip names difference | Vitest |
| C-05-T12 | UI: open invoices/bills grids (paste-friendly) | FE | T09 | Paste 20 rows → 20 docs validated | Playwright |
| C-05-T13 | Fixtures: balanced and unbalanced conversion sets incl. REFINED (no opening equity) | QA | T05 | Both fixtures behave per acceptance | pytest |
| C-05-T14 | Exceptions hook: register "opening equity missing" signal for K-09 | BE | T05 | Signal emitted when no equity lines | unit |
| C-05-T15 | Docs + i18n | DOC | T10–T12 | Gate green | CI |

- **Deliverable acceptance:** conversion cannot be finalised while difference ≠ 0.00; the blocked state names the difference; AR/AP opening documents drive aging.
- **Testing:** unit, property test (random balanced sets always finalise; unbalanced never), integration, Playwright.
- **Risks:** users wanting a plug account → explain in UI that a suspense line can be added explicitly (visible, flagged by K-09), never automatic.

### C-06 · Period close and year-end

- **Branch:** `feature/C-06-period-close`
- **Objective:** close periods per module, roll retained earnings at year-end, reopen with reason.
- **Current behaviour:** module lock dates exist (A-05) but there is no close process, no year-end roll.
- **Expected behaviour:** Period close screen with checklist per month (unposted drafts, unreconciled lines (info only), open exceptions, unfiled tax periods); "Close module" sets that module's lock; year-end process creates a closing JE (P&L → Retained earnings) per book (accounting and tax separately), dated FYE; reopen requires adviser + reason and is audited; reopening a year reverses its closing JE.
- **Business rules:** closing JE type Closing, system-created; current-year earnings shown on BS until closed; postings into closed periods refused naming the lock (A-05); reopen only the latest closed period first (stack order) unless adviser forces.
- **Edge cases:** first year with conversion mid-year; postings arriving after close via recurring job (skipped + exception); two books with different NI; FYE change after closing (blocked).
- **UI/UX notes:** month timeline (Jan–Dec) with status pills per module; checklist items link to the screen that fixes them; reopen dialog shows consequences.
- **Dependencies:** C-03, C-04, A-05, C-02 book dimension.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| C-06-T01 | `PeriodClose` model (org, module, period_end, closed_by/at, reopened_by/at, reason) | DB | A-05 | Record per module per period | unit |
| C-06-T02 | Close service: sets module lock to period_end; validates no later period already closed out of order | BE | T01 | GL close Jun sets lock 30 Jun | unit |
| C-06-T03 | Checklist service: counts drafts, awaiting approval, unfiled tax periods, open exceptions for the period | BE | C-04 | Counts match fixture | unit |
| C-06-T04 | Year-end roll: per book, sum P&L accounts → closing JE to Retained Earnings dated FYE | BE | C-02 | Fixture NI 25,000 → RE +25,000; P&L accounts zero after FYE in BS view | unit + data validation |
| C-06-T05 | Reopen service: adviser only, reason required, reverses closing JE if year-end | BE | T02, T04 | Reopen audited; RE restored | unit |
| C-06-T06 | Recurring/auto jobs respect closed periods (skip + exception) | BE | T02, C-04-T06 | Tick into closed period produces exception, no JE | integration |
| C-06-T07 | API `/api/v1/period-close/` (timeline, checklist, close, reopen, year-end) | API | T01–T06 | OpenAPI; permissions `accounting.period_close` | API + sweep |
| C-06-T08 | UI: module × month timeline with status pills | FE/UX | T07 | Pills reflect API; keyboard navigable | Playwright + axe |
| C-06-T09 | UI: checklist panel with deep links; close and reopen dialogs with consequences text | FE | T07 | Links open the filtered list | Playwright |
| C-06-T10 | Fixtures: full-year fixture with known RE roll in both books | QA | T04 | Year-end roll correct on fixture | pytest |
| C-06-T11 | Docs + i18n | DOC | T08–T09 | Gate green | CI |

- **Deliverable acceptance:** posting into closed period blocked naming the lock; year-end roll correct on fixture in both books; reopen audited with reason.
- **Testing:** unit, data validation (NI = ΔRE), integration with recurring jobs, Playwright.
- **Risks:** closing JE double-created → unique (org, book, fye) constraint.

### C-07 · Find & recode with undo

- **Branch:** `feature/C-07-find-recode-undo`
- **Objective:** find transaction lines by conditions, recode account/tax/tracking/contact in bulk with preview, keep an audit report and allow batch undo.
- **Current behaviour:** none.
- **Expected behaviour (better than Xero):** condition builder (All/Any: type, status, account, bank account, date range, amount range, tax code, entered by, contact, document number/reference, tracking, book); results grid with select all; choose new values; **preview diff** (before/after per line + totals unchanged check + tax impact); execute as one `RecodeBatch` via reversal + re-post per affected document (append-only); history table with audit report download; **Undo** of the whole batch while every affected period is open; lock dates respected and explained per line.
- **Gap #s closed:** 35.
- **Business rules:** recode never changes amounts; changing tax code recalculates tax split → shown in preview, requires confirmation; lines in locked/filed periods excluded with reason; undo = reverse the recode JEs; recode of a revised invoice targets the current revision only.
- **Edge cases:** 10,000 matches (async job with progress); line recoded twice (undo order: latest first); lines changed by another user between preview and execute (re-validate, conflict list); tax recode in a filed GST period (excluded).
- **UI/UX notes:** two-pane: conditions left, results right; sticky summary "500 lines · 3 accounts · totals unchanged · 12 excluded (locked)"; excluded lines visible in a separate tab with reasons; Undo button with countdown-free availability while periods open.
- **Dependencies:** C-02, C-03, A-05, D-03a/E-02 documents, A-08 jobs.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| C-07-T01 | `RecodeBatch` and `RecodeLineChange` models (criteria JSON, before/after, status, undone_by/at) | DB | C-02 | Models migrate | unit |
| C-07-T02 | Query builder: conditions → ORM filter over `JournalLine` with org scope and indexes | BE | T01 | Each condition type returns expected lines on fixture | unit (parameterised) |
| C-07-T03 | Exclusion engine: locked/closed/filed periods, voided docs, superseded revisions → excluded with reason | BE | T02, A-05 | Excluded list with reason codes | unit |
| C-07-T04 | Preview service: before/after per line, totals unchanged assertion, tax impact recalculation | BE | T02, G-01 | Preview totals equal original totals | unit + Hypothesis |
| C-07-T05 | Execute service (Celery job for > 200 lines): per document reverse + re-post with new coding inside transaction; batch status/progress | BE | T04, A-08 | 500 lines → one batch, audit rows = 500 | integration |
| C-07-T06 | Optimistic re-validation at execute (version check); conflicts reported | BE | T05 | Line modified after preview reported as conflict, not recoded | integration |
| C-07-T07 | Undo service: reverse recode JEs in reverse order; refused if any period now locked (lists which) | BE | T05 | Undo restores every line's coding | integration + data validation |
| C-07-T08 | Audit report export (PDF/XLSX/CSV) per batch | BE | T05 | Export rows = batch changes | unit |
| C-07-T09 | API `/api/v1/recode/` (search, preview, execute, batches, undo, report) + permission `accounting.recode` (adviser roles) | API | T02–T08 | OpenAPI; sweep; non-permitted role 403 | API |
| C-07-T10 | UI: condition builder (All/Any, typed value inputs per field) | FE/UX | T09 | Builder serialises to API schema | Vitest |
| C-07-T11 | UI: results grid with select-all-across-pages, excluded tab | FE | T09 | Select all 500 across pages | Playwright |
| C-07-T12 | UI: preview diff + confirm dialog with numbers; progress toast for async | FE/UX | T09 | Diff shows per-line before/after | Playwright |
| C-07-T13 | UI: batch history with Undo + report download | FE | T09 | Undo button disabled with reason when period locked | Playwright |
| C-07-T14 | Performance test: 10,000-line recode under 2 min on staging-size data | QA | T05 | k6/pytest timing within budget | perf |
| C-07-T15 | Docs + i18n | DOC | T10–T13 | Gate green | CI |

- **Deliverable acceptance:** recode of 500 lines produces one audit batch; undo restores every line; locked lines excluded with reason.
- **Testing:** unit, property (recode then undo ⇒ identical coding), integration, performance, Playwright.
- **Risks:** large batches lock tables → chunked transactions per document, batch-level status.

### 6.2 Sales (Component D)

### D-01 · Shared sales document grid

- **Branch:** `feature/D-01-document-grid`
- **Objective:** one line-grid component and one calculation service used by quotes, invoices, recurring invoices and credit notes (and, in E-02, purchase documents).
- **Current behaviour:** `DocumentLineGrid` shell exists in the design system (A-10) with no business logic.
- **Expected behaviour (better than Xero):** columns Item, Description, Qty, Unit price, Line discount (amount or %), Account, Tax code, Tax amount, Amount; **document-level discount** (amount or %) allocated pro-rata to lines for tax; tax exclusive / inclusive / no tax; **account picker filtered** to Revenue/Other income/Sales types; **tax picker filtered** to sales codes effective on document date; required due date defaulted from terms; column chooser (per user, saved); paste from spreadsheet; drag reorder; posting preview; totals panel (Subtotal, Discount, tax per component GST/HST/PST/QST, Total).
- **Gap #s closed:** 1, 7, 10, 12, 17.
- **Business rules:** calculation in `DocumentCalculator` (backend authoritative; frontend mirror for instant feedback, server result wins); rounding per line to 2 dp then tax summed per component; inclusive mode back-calculates net; document discount never makes a line negative; mismatched side (purchase code or expense account) refused server-side with message.
- **Edge cases:** 100 % discount; zero-qty lines; inclusive tax with partial ITC (purchase side, E-02); rounding of 1/3 quantities; very long descriptions; expired tax code on an old draft when date moves forward (flag line, require re-pick).
- **UI/UX notes:** spreadsheet keyboard model (arrows, Enter down, Tab right, `Ctrl+D` duplicate line, `Ctrl+Backspace` delete line with undo toast); "why this tax" tooltip; tablet view collapses to line cards; totals live region for screen readers.
- **Dependencies:** A-10, C-01, G-01, G-02, B-01 (terms, defaults).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-01-T01 | Abstract models `DocumentBase` (contact, dates, terms, currency, tax_mode, doc_discount, totals, version) and `DocumentLineBase` | DB | A-01 | Abstract classes compile; concrete test model migrates | unit |
| D-01-T02 | Minimal `Item` stub (code, name, accounts, tax codes, is_tracked=False) pending H-01 | DB | C-01 | Item defaults flow into a line | unit |
| D-01-T03 | `DocumentCalculator` — exclusive mode: line net, line discount, tax per component, totals | BE | G-01 | 50 fixture documents match reference sheet to the cent | unit (fixtures) |
| D-01-T04 | Calculator — inclusive and no-tax modes | BE | T03 | Inclusive fixtures match; no-tax yields 0 tax | unit |
| D-01-T05 | Calculator — document discount pro-rata allocation (amount and %) with remainder cent on largest line | BE | T03 | Σ allocated = discount exactly | Hypothesis |
| D-01-T06 | Side validator: account type and tax code side per document type; effective-date check | BE | G-01, C-01 | Purchase code on sales line → 400 naming line; expired rate rejected | unit |
| D-01-T07 | Due-date resolver from terms master (Net N, EOM, day-of-next-month, 2/10 net 30) | BE | B-01 | All term types produce correct dates incl. month ends | unit + Hypothesis |
| D-01-T08 | Posting-preview service (lines → proposed JE incl. tax control accounts) | BE | T03, C-02 | Preview JE equals actual JE posted later (D-03a) | integration |
| D-01-T09 | API: `/api/v1/documents/calculate` (stateless) and `/posting-preview` | API | T03–T08 | p95 < 80 ms for 50 lines | API + perf |
| D-01-T10 | Frontend calculator mirror (TS) sharing fixture JSON with backend tests | FE | T03–T05 | Same 50 fixtures pass in Vitest | Vitest |
| D-01-T11 | Grid: columns, keyboard model, ARIA grid roles, add/duplicate/delete with undo toast | FE/UX | A-10 | Keyboard-only Playwright fills 5 lines | Playwright + axe |
| D-01-T12 | Filtered account and tax pickers (side + date aware, search by code/name, "why" tooltip) | FE | T06, T09 | Sales line shows no purchase codes/expense accounts | Playwright (`gap-07`) |
| D-01-T13 | Column chooser with per-user persistence; hidden-column note | FE | T11 | Choice persists across sessions | Playwright |
| D-01-T14 | Document discount control + totals panel (tax per component, live region) | FE | T10 | Totals equal server result after debounce | Vitest |
| D-01-T15 | Paste-from-spreadsheet (TSV) with per-cell validation highlighting | FE | T11 | Paste 20 rows from Excel → 20 lines, invalid cells flagged | Playwright |
| D-01-T16 | Tablet/stacked line-card layout ≤ 1024 px | FE/UX | T11 | Visual snapshot at 768 px | visual regression |
| D-01-T17 | Required due date field with term chips and "due in N days" helper | FE | T07 | Cannot save without due date; chips set dates | Playwright (`gap-12`) |
| D-01-T18 | Storybook stories for every grid state + Figma spec parity check | UX | T11–T17 | Stories published; design review signed | Chromatic |
| D-01-T19 | i18n keys (en-CA/fr-CA) + pseudo-locale layout check | FE | T11–T17 | Gate green; no clipping at +30 % | CI |

- **Deliverable acceptance:** no purchase codes/expense accounts on sales lines; expired rate unselectable; 50 fixtures match; same component used by every editor.
- **Testing:** fixture-driven unit (shared JSON), property tests, Playwright keyboard flows, visual regression, axe.
- **Risks:** front/back calculation drift → shared fixtures and server-authoritative totals.

### D-02 · Quotes

- **Branch:** `feature/D-02-quotes`
- **Objective:** quotes with optional lines, alternatives, deposit, e-signature acceptance, conversion to invoice and a consistent Expired status.
- **Current behaviour:** none.
- **Expected behaviour (better than Xero):** statuses Draft / Sent / Viewed / Accepted / Declined / **Expired** / Invoiced — same enum in overview, list tabs and filters; title & summary; optional lines (customer can tick) and alternative groups (choose one); deposit request (amount or %) creating a deposit invoice on acceptance; public link + portal acceptance with typed name + drawn signature, IP, timestamp, document hash; tax amount column and total tax line (shared grid); convert to invoice with identical lines (selected options only).
- **Gap #s closed:** 5, 17.
- **Business rules:** expiry date required (default org setting, e.g., 30 days); nightly job moves Sent/Viewed past expiry → Expired; expired cannot be accepted (public page shows reason and "Ask for a new quote"); accepted quote is immutable (new version = copy); conversion links quote ↔ invoice; deposit invoice credited against final invoice.
- **Edge cases:** acceptance at 23:59 on expiry day (org-local TZ); customer accepts twice (idempotent); quote revised after sending (new quote version, old link shows "superseded"); alternative group with none selected.
- **UI/UX notes:** quote editor = shared grid + "Optional" toggle per line and "Alternative group" picker; public page mobile-first, big Accept button, option toggles recalc totals live; signature pad accessible alternative (typed name only).
- **Dependencies:** D-01, D-03a (conversion), A-07 email, A-06 storage.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-02-T01 | `Quote`, `QuoteLine` (is_optional, alternative_group, selected) models + `QuoteStatus` enum shared | DB | D-01 | Migrates; enum exported to frontend | unit |
| D-02-T02 | Quote numbering `QU-0001` via org numbering service inside transaction | BE | A-05 | Concurrent creates → unique numbers | integration |
| D-02-T03 | Calculator extension: totals exclude unselected optional/alternative lines | BE | D-01-T03 | Totals change correctly with selection | unit |
| D-02-T04 | Lifecycle service (send, view tracking, accept, decline, expire, invoice) with transitions guarded | BE | T01 | Illegal transitions raise | unit (state table) |
| D-02-T05 | Expiry job (org-local midnight) moving to Expired | BE | A-08 | Quote expiring today accepted at 23:59 local; expired at 00:00 | integration (freezegun, TZ) |
| D-02-T06 | Public token link (signed, revocable) + view tracking | BE/API | T04 | Link works without login; revoked link 410 | API |
| D-02-T07 | Acceptance evidence record (typed name, signature PNG, IP, UA, hash of rendered PDF) | BE | T06, A-06 | Evidence stored; hash matches PDF | unit |
| D-02-T08 | Deposit: on acceptance create deposit invoice (D-03a) and link | BE | D-03a | Deposit invoice amount = % of accepted total | integration |
| D-02-T09 | Convert to invoice: copy selected lines identically; deposit applied as credit line | BE | D-03a | Line-by-line equality test | unit |
| D-02-T10 | PDF template (Letter, inches) with tax column and optional-line markers | BE | A-10 | PDF snapshot matches fixture | snapshot |
| D-02-T11 | API `/api/v1/quotes/` CRUD + actions; public `/q/{token}` endpoints; feature key `accounting.sales.quotes` | API | T01–T09 | OpenAPI; sweep (public endpoints excluded but token-scoped) | API |
| D-02-T12 | UI: quote editor (grid with Optional toggle, alternative group picker, expiry, deposit) | FE/UX | T11 | Create quote with 2 options in < 90 s | Playwright |
| D-02-T13 | UI: public quote page (option toggles, signature, accept/decline, expired state) | FE/UX | T11 | Expired quote shows reason; Accept disabled | Playwright + axe (mobile viewport) |
| D-02-T14 | UI: quotes list tabs All/Draft/Sent/Accepted/Declined/Expired/Invoiced with counts from same enum | FE | T11 | Tab counts = overview card counts (`gap-05`) | Playwright |
| D-02-T15 | Emails: send quote, accepted/declined notifications | BE | A-07 | One email per event | integration |
| D-02-T16 | Search registration + quick-create `N Q` | BE/FE | A-09 | Quote found by number/contact | integration |
| D-02-T17 | Docs + i18n | DOC | T12–T14 | Gate green | CI |

- **Deliverable acceptance:** accepted quote converts with identical lines; expired quote cannot be accepted; Expired status consistent in overview, list and filters.
- **Testing:** unit (state machine), TZ boundary tests, integration (deposit, conversion), Playwright public flow on mobile viewport.
- **Risks:** e-signature legal weight → evidence record + client confirms sufficiency; token leakage → signed tokens, expiry, revoke.

### D-03a · Invoices and posting

- **Branch:** `feature/D-03a-invoices`
- **Objective:** invoice lifecycle with numbering, branded PDF, attachments, copy and AR/revenue/tax posting.
- **Current behaviour:** none.
- **Expected behaviour (better than Xero):** statuses Draft → Awaiting approval (optional rule) → Approved → Sent → Partially paid → Paid (+ Void); **approval never plan-gated**; approval posts Dr AR / Cr Revenue / Cr GST/HST payable / Cr PST payable / Cr QST payable (separate control accounts) via C-02; branded PDF (Letter, inch margins, BN/RT and QST numbers printed, Canadian sample in theme preview); attachments; copy to new invoice/quote; credit-limit warn/block from contact; duplicate-invoice soft warning [EXTRA]; period-status ribbon; posting preview.
- **Gap #s closed:** 6 (approval never gated), 43 (one template system, Letter/inch, Canadian sample).
- **Business rules:** number allocated at approval (draft shows "Draft"); AR lock and GST filed-period checks at approval; void = reversal JE, keeps number; contact on credit-limit block requires approver override (A-03); invoice date in a period with no GST registration → out-of-scope default (G-03b).
- **Edge cases:** concurrent approval (one wins); approving with zero total; negative-total invoice (refuse — use credit note); contact archived; PDF render failure (retry, error surfaced).
- **UI/UX notes:** header (Contact, Issue date, Due date with chips, Reference, Amounts are), grid, totals, notes/terms, attachments; action bar: Save draft · Approve · Approve & send · ⋯ (PDF, Copy, Void); right drawer "Posting preview"; "Approve & send" opens email composer with PDF preview.
- **Dependencies:** D-01, C-02, G-01/G-02, B-01, A-06, A-07.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-03a-T01 | `Invoice`, `InvoiceLine` concrete models (from `DocumentBase`), status enum, `current_revision` nullable FK (filled in D-03b) | DB | D-01 | Migrates | unit |
| D-03a-T02 | Numbering service: allocate at approval inside posting transaction; pattern from settings | BE | A-05 | 1,000 concurrent approvals → no gaps/duplicates | integration (concurrency) |
| D-03a-T03 | `InvoicePostingService.approve()`: build JE via calculator, separate tax control accounts, post atomically | BE | C-02, D-01-T08 | Approval posts balanced JE equal to preview | integration |
| D-03a-T04 | Lock and period checks (AR lock, GST filed period) at approve/void with named messages | BE | A-05, G-03 | Pre-lock date refused naming lock | unit |
| D-03a-T05 | Optional approval rule (threshold / role) using A-03 limits; never product-gated | BE | A-03 | Threshold rule routes to Awaiting approval | unit |
| D-03a-T06 | Credit-limit check (warn/block) + override approval | BE | B-01 | Block mode refuses without override; warn returns warning | unit |
| D-03a-T07 | Void service: reversal JE, status Void, number retained, audit | BE | T03 | Void nets ledger to zero for the invoice | integration |
| D-03a-T08 | Duplicate-invoice soft warning (same contact + total ± 0 + date ± 7 days) [EXTRA] | BE | T01 | Warning returned, not blocking | unit |
| D-03a-T09 | PDF template engine (WeasyPrint): branding theme, Letter/inch, BN/RT/QST numbers, tax per component, terms, pay-advice | BE | A-10 | PDF matches fixture snapshot; theme preview uses Canadian sample | snapshot (`gap-43`) |
| D-03a-T10 | Copy to invoice/quote service | BE | T01, D-02 | Copy has identical lines, new draft | unit |
| D-03a-T11 | API `/api/v1/invoices/` CRUD + approve/send/void/copy/pdf; feature key `accounting.sales.invoices`; sweep registration | API | T01–T10 | OpenAPI; sweep green | API |
| D-03a-T12 | Email send with PDF attachment + "viewed" tracking pixel/link | BE | A-07 | Send logged; bounce flags contact | integration |
| D-03a-T13 | UI: invoice editor header + grid + totals + attachments | FE/UX | T11, D-01 | First invoice in ≤ 5 clicks | Playwright |
| D-03a-T14 | UI: action bar state matrix, posting preview drawer, period ribbon | FE | T11 | Preview matches posted JE | Playwright |
| D-03a-T15 | UI: email composer with PDF preview | FE | T12 | Send in one dialog | Playwright |
| D-03a-T16 | UI: credit-limit warning/block banners inside editor (not promotional) | FE/UX | T06 | Block shows "Request override" | Playwright |
| D-03a-T17 | Search registration (number, contact, reference, amount) + quick-create `N I` | BE/FE | A-09 | Invoice found by amount | integration |
| D-03a-T18 | Fixtures: 50 invoices across provinces + PDF fixtures from client samples | QA | T03, T09 | Fixtures load; posting matches expected | pytest |
| D-03a-T19 | Docs + i18n | DOC | T13–T16 | Gate green | CI |

- **Deliverable acceptance:** approving posts a balanced JE; PDF matches fixture; approval available on every package with Accounting.
- **Testing:** integration with posting engine, concurrency on numbering/approval, PDF snapshot, Playwright, sweep.
- **Risks:** PDF rendering speed → async render cache keyed by revision hash.

### D-03b · Invoice revisions (editable posted invoices)

- **Branch:** `feature/D-03b-invoice-revisions`
- **Objective:** let an approved/sent invoice be edited; each save creates revision 101-1, 101-2 … with reversal + re-post in one transaction, payment re-allocation, PDF stamp, history and reports following the current revision.
- **Current behaviour (Xero):** posted invoices can only be voided and re-created. In Numo9 after D-03a: invoices are immutable once approved.
- **Expected behaviour:** `Edit` on a posted invoice opens the editor in revision mode (banner, required reason); save creates `InvoiceRevision(n)` snapshot; prior JE reversed and new JE posted in the same DB transaction, both linked to the revision; allocated payments stay; if new total < paid, excess becomes customer credit; PDF stamped "Revision 1 of invoice 101 — supersedes the version issued on 26 Oct 2026"; history panel + diff view; AR aging, statements, reminders, tax reports read the current revision; revision dated in a filed GST period requires unlocking or carries a late-adjustment flag posting the tax difference into the next open period; void still available; portal shows latest with "Revised" badge and links to superseded versions.
- **Gap #s closed:** client decision 5 (beyond Xero); supports 54 (tax report correctness).
- **Business rules:** revision number allocated inside the posting transaction with row lock on the invoice; optimistic `version` check → second concurrent editor gets conflict; editing contact allowed only if no payments allocated; currency change not allowed; revision of a paid invoice allowed (credit created if reduced, AR increased if raised); ADR-002 records the design.
- **Edge cases:** revision after partial payment; revision raising the total above credit limit; revision that changes only description (still a revision — no JE delta? → reversal + re-post anyway for simplicity and traceability, JE delta zero); revision in AR-locked period (refused naming lock); revision when GST period filed and late flag chosen; recurring-generated invoice revised; deposit invoice revised.
- **UI/UX notes:** purple "Revised" badge + revision selector (101 · 101-1 · 101-2); diff view with deltas; confirm dialog stating "AR for Acme −113.00 · GST/HST −13.00 · Reverses JE 1045 · Posts JE 1046"; conflict dialog with "Reload" and "View their changes"; history panel timeline.
- **Dependencies:** C-02, D-03a, D-05, G-03 (filed-period rules), A-04.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-03b-T01 | ADR-002 "Invoice revisions" (model, posting, numbering, filed-period rule, alternatives rejected) | DOC | — | ADR merged in `docs/adr/` | review |
| D-03b-T02 | `InvoiceRevision` model (invoice, revision_no, number_display "101-1", snapshot JSON of header+lines, totals, reason, created_by, journal_reversal, journal_post, superseded_at) | DB | D-03a | Migrates; unique (invoice, revision_no) | unit |
| D-03b-T03 | Backfill: revision 0 created at first approval (D-03a hook) so every posted invoice has a current revision | BE/DB | T02 | All approved invoices have revision 0 and `current_revision` set | data migration test |
| D-03b-T04 | Revision builder: clone current revision into editable draft state (in memory / draft row) | BE | T02 | Clone equals current snapshot | unit |
| D-03b-T05 | Revision validator: allowed field changes, contact change only if no allocations, currency fixed, reason required | BE | T04 | Invalid changes refused with field errors | unit |
| D-03b-T06 | Concurrency: `SELECT … FOR UPDATE` on invoice + `version` compare; conflict error type | BE | T02 | Two simultaneous saves → one succeeds, other 409 conflict, no lost update | concurrency integration |
| D-03b-T07 | Posting: reverse previous revision JE + post new JE in one transaction; link both to revision | BE | C-02, T06 | GL shows two linked JEs; rollback leaves no partial state on failure injection | integration + fault injection |
| D-03b-T08 | Number suffix allocation inside the same transaction (101-1, 101-2) | BE | T07 | Sequential suffixes under concurrency | integration |
| D-03b-T09 | Payment re-allocation: keep allocations; if paid > new total move excess to customer credit (D-05 credit model) | BE | D-05 | Paid 1,130 → revised 1,017 → credit 113.00 | integration |
| D-03b-T10 | Lock rules: AR lock refuses; filed GST period → require unlock or `late_adjustment=True` | BE | G-03, A-05 | Filed period without flag refused naming period | unit |
| D-03b-T11 | Late-adjustment posting: tax difference posted into next open GST period (adjusting entry linked to revision) | BE | T10, G-03 | Tax report of filed period unchanged; next period shows delta | integration |
| D-03b-T12 | Reports read current revision: AR aging, statements, reminders, tax report query layer (`InvoiceCurrent` view) | BE | T07 | Tax report for period shows 1,017.00 only | integration |
| D-03b-T13 | Property test harness: 1,000 random edit/payment sequences; assert AR control = Σ open current revisions; TB = 0 | QA | T07–T12 | Property test passes in CI | Hypothesis |
| D-03b-T14 | PDF stamp: "Revision n of invoice 101 — supersedes the version issued on …"; superseded PDFs watermarked "Superseded" | BE | D-03a-T09 | Snapshot PDFs for 101 and 101-1 | snapshot |
| D-03b-T15 | Audit events: revision created with field diffs, reason, JE ids | BE | A-04 | Audit viewer shows old/new values | integration |
| D-03b-T16 | API: `POST /invoices/{id}/revisions`, `GET /invoices/{id}/revisions`, `GET /invoices/{id}/revisions/{n}/diff`, ETag/If-Match for version | API | T04–T12 | OpenAPI; 409 on stale If-Match; sweep | API |
| D-03b-T17 | Webhook/event `invoice.revised` emitted (consumed later by W-01, mobile) | BE | T07 | Event stored in outbox once per revision | unit |
| D-03b-T18 | UI: "Edit" on posted invoice → revision mode banner + reason chips + required reason | FE/UX | T16 | Banner text per §3.5; cannot save without reason | Playwright |
| D-03b-T19 | UI: confirmation dialog with AR/tax/JE deltas | FE/UX | T16 | Deltas equal server preview | Playwright |
| D-03b-T20 | UI: revision selector + history panel timeline + "Revised" badge on lists | FE | T16 | Badge on list rows; selector switches views | Playwright |
| D-03b-T21 | UI: diff view (line added/removed/changed, amount and tax deltas) [EXTRA] | FE/UX | T16 | Diff of 101 vs 101-1 highlights changed line | Playwright + axe |
| D-03b-T22 | UI: conflict dialog (Reload / View their changes) | FE/UX | T16 | Second editor sees dialog, no data loss of own input (copied to clipboard option) | Playwright (two contexts) |
| D-03b-T23 | Portal/public invoice link: always resolves to current revision; superseded link redirects with notice | BE/FE | T16 | Old link → current with "This invoice was revised" | Playwright |
| D-03b-T24 | Golden scenario fixture: 101 at 1,130.00 → 1,017.00 → assertions (AR −113.00, two JEs, tax 1,017.00, 101 superseded) | QA | T07–T14 | Scenario test green; used in exit demo | pytest + Playwright |
| D-03b-T25 | Docs: user guide "Revising an invoice" + i18n keys | DOC | T18–T23 | Gate green | CI |

- **Deliverable acceptance:** editing invoice 101 (CAD 1,130.00) to CAD 1,017.00 produces 101-1; AR for the contact changes by exactly −113.00; the GL has two linked JEs; the tax report reflects 1,017.00 only; 101 remains viewable and marked superseded; 1,000-run property test never leaves AR ≠ Σ open current revisions; concurrent edit → conflict, never lost update.
- **Testing:** unit (state machine), Hypothesis property test, concurrency test, fault injection, PDF snapshots, Playwright functional through UI and public link, regression on D-03a/D-05.
- **Risks & mitigations:** revision in filed period → G-03 late-adjustment rule; numbering collisions → suffix allocated under row lock; report drift → single `InvoiceCurrent` query layer used by every report (lint rule forbids reading `InvoiceLine` directly in reports).

### D-04 · Recurring invoices

- **Branch:** `feature/D-04-recurring-invoices`
- **Objective:** schedule invoices using the same grid, with placeholders, proration and auto-send or draft mode.
- **Current behaviour:** none (Xero: legacy, disabled on plan).
- **Expected behaviour:** `RecurringInvoiceTemplate` (contact, lines, schedule rrule, start/end, due-date rule, mode Draft / Approve / Approve & send, placeholders `{{period_start}} {{period_end}} {{month}} {{year}}`, proration flag for first/last partial period); generator creates exactly one invoice per occurrence; failures visible in job dashboard and template page; never product-gated within Accounting.
- **Gap #s closed:** 13.
- **Business rules:** idempotency on (template, occurrence_date); invoice number allocated at approval; proration = days in partial period / days in period × line amount, rounded per line; paused templates skip; locked period → occurrence skipped + exception; template changes apply to future occurrences only.
- **Edge cases:** worker restart mid-run; DST transitions; end date before next run; contact archived (skip + notify); email bounce on auto-send.
- **UI/UX notes:** template editor = invoice editor + schedule panel + "Preview next invoice" with placeholders resolved; list shows next run, last run, status; history tab of generated invoices.
- **Dependencies:** D-01, D-03a, A-08, A-07.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-04-T01 | `RecurringInvoiceTemplate` + lines models (version field) | DB | D-01 | Migrates | unit |
| D-04-T02 | Schedule engine reuse (C-04-T05 rrule, month-end clamp) + due-date rule | BE | C-04 | Occurrences correct incl. Feb | unit |
| D-04-T03 | Placeholder renderer (ICU-safe, locale-aware month names) | BE | T01 | `{{month}}` → "October" en-CA / "octobre" fr-CA | unit |
| D-04-T04 | Proration calculator for first/last partial period | BE | D-01-T03 | Fixture 15 of 31 days → 15/31 amount | unit + Hypothesis |
| D-04-T05 | Generator task with idempotency row + mode handling (draft/approve/approve&send) | BE | T02–T04, D-03a | Exactly one invoice per tick after restart | integration (two workers) |
| D-04-T06 | Skip rules (paused, ended, locked period, archived contact) with exception/notification | BE | T05 | Skips logged, owner notified | integration |
| D-04-T07 | API `/api/v1/recurring-invoices/` CRUD, pause/resume, preview, history | API | T01–T06 | OpenAPI; sweep | API |
| D-04-T08 | UI: template editor (grid + schedule panel + mode + proration) | FE/UX | T07 | Create monthly template in < 2 min | Playwright |
| D-04-T09 | UI: preview next invoice with resolved placeholders | FE | T07 | Preview equals generated invoice | Playwright |
| D-04-T10 | UI: list with next/last run, status, generated history tab | FE | T07 | Counts match | Playwright |
| D-04-T11 | Replay tool `manage.py replay_ticks` for support | OPS | T05 | Replaying a day creates nothing new | integration |
| D-04-T12 | Docs + i18n | DOC | T08–T10 | Gate green | CI |

- **Deliverable acceptance:** exactly one invoice per tick after worker restart; proration correct on fixtures; same grid as invoice editor.
- **Testing:** integration with concurrent workers, time-travel tests, Playwright.
- **Risks:** duplicate generation → unique constraint; time zone → org TZ for occurrence dates.

### D-05 · Payments received and allocation

- **Branch:** `feature/D-05-payments-received`
- **Objective:** record customer payments against one or many invoices, handle overpayments as credit, prepayments, and bank account selection.
- **Current behaviour:** none.
- **Expected behaviour:** `ReceivePayment` (contact, date, amount, bank/clearing account, reference, method); allocation table auto-allocates oldest-due first (editable); overpayment → `CustomerCredit`; prepayment without invoice → credit; posting Dr Bank / Cr AR (per allocation) / Cr Customer credit liability; unallocate/reallocate with audit; refund of credit (to bank).
- **Business rules:** allocations ≤ open balance of current revision; AR decreases by exactly the allocated amount; bank lock and AR lock checked; payment on Void invoice refused; early-payment discount (E-07) applied when inside window.
- **Edge cases:** payment in different order than due; partial cents; allocating credit to new invoice; deleting a payment that is reconciled (refuse — unreconcile first); payment dated before invoice (warn).
- **UI/UX notes:** single screen "Receive payment" also reachable from invoice ("Record payment" prefilled); allocation table with "Auto-allocate" and running unallocated amount; overpayment notice in plain language.
- **Dependencies:** D-03a, F-01, C-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-05-T01 | `CustomerPayment`, `PaymentAllocation`, `CustomerCredit` models | DB | D-03a | Migrates | unit |
| D-05-T02 | Allocation service (auto oldest-due, manual) with ≤ open balance validation | BE | T01 | Over-allocation refused | unit + Hypothesis |
| D-05-T03 | Posting: Dr bank / Cr AR / Cr customer credit; lock checks | BE | C-02, F-01 | AR decreases by exactly the payment | integration |
| D-05-T04 | Overpayment and prepayment → credit; apply credit to invoice later | BE | T02 | 113.00 credit created and applicable | integration |
| D-05-T05 | Unallocate/reallocate with audit; delete refused when reconciled | BE | T03, F-05 | Reconciled payment delete → 409 naming reconciliation | unit |
| D-05-T06 | Refund of customer credit to bank | BE | T04 | Refund posts Dr credit / Cr bank | integration |
| D-05-T07 | Invoice status updater (Partially paid / Paid) reading current revision | BE | D-03b-T12 | Status correct after revision + payment combos | unit |
| D-05-T08 | API `/api/v1/payments-received/` + `/allocate`, `/credits/` | API | T01–T07 | OpenAPI; sweep | API |
| D-05-T09 | UI: Receive payment screen with allocation table + auto-allocate | FE/UX | T08 | 3-invoice payment in < 45 s | Playwright |
| D-05-T10 | UI: "Record payment" from invoice (prefilled) + credit notice | FE | T08 | Prefill correct | Playwright |
| D-05-T11 | UI: customer credits list and apply/refund actions | FE | T08 | Apply credit reduces invoice balance | Playwright |
| D-05-T12 | Data validation: AR control = Σ open current revisions − credits on fixtures | QA | T03 | `ledger_check` passes | pytest |
| D-05-T13 | Docs + i18n | DOC | T09–T11 | Gate green | CI |

- **Deliverable acceptance:** AR decreases by exactly the payment; overpayment held as credit; reconciled payments protected.
- **Testing:** unit, property, integration, data validation, Playwright.
- **Risks:** allocation race on same invoice → row lock on invoice when allocating.

### D-06 · Credit notes

- **Branch:** `feature/D-06-credit-notes`
- **Objective:** full credit-note page (never a silent redirect) with apply-to-invoice or refund.
- **Current behaviour (Xero):** credit note page silently redirects on the inspected plan.
- **Expected behaviour:** `CreditNote` using shared grid (numbering `CN-0001`), from scratch or "Credit this invoice" (copies current revision lines); approval posts Dr Revenue / Dr tax payable / Cr AR; apply to one or more invoices or refund to bank; credit notes tab in invoice lists; any gating shown explicitly.
- **Gap #s closed:** 14.
- **Business rules:** applied amount ≤ invoice open balance and ≤ credit remaining; tax reverses in the period of the credit note date (G-03 rule); refund posts Dr AR-credit / Cr bank.
- **Edge cases:** credit note larger than invoice; credit note on revised invoice (targets current revision); credit in filed period (late adjustment rule like D-03b).
- **UI/UX notes:** same editor look as invoice, red "Credit note" header chip; apply panel lists open invoices of the contact.
- **Dependencies:** D-01, D-03a, D-05.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-06-T01 | `CreditNote`, lines, `CreditApplication` models | DB | D-01 | Migrates | unit |
| D-06-T02 | "Credit this invoice" builder (copy current revision lines) | BE | D-03b | Lines equal current revision | unit |
| D-06-T03 | Posting service (reverse revenue and tax, Cr AR) | BE | C-02 | Applying reduces balance and reverses revenue/tax | integration |
| D-06-T04 | Apply service (multi-invoice) with limits | BE | T03, D-05 | Over-application refused | unit |
| D-06-T05 | Refund service | BE | T03, F-01 | Refund posts correctly | integration |
| D-06-T06 | Filed-period handling (late adjustment flag) | BE | G-03 | Same rule as D-03b-T10 | unit |
| D-06-T07 | PDF template for credit note | BE | D-03a-T09 | Snapshot matches | snapshot |
| D-06-T08 | API `/api/v1/credit-notes/` + apply/refund; explicit 402 gating payload | API | T01–T07 | No redirect anywhere (`gap-14`) | API + Playwright |
| D-06-T09 | UI: credit note editor + apply panel | FE/UX | T08 | Apply to two invoices in one flow | Playwright |
| D-06-T10 | UI: Credit notes tab in invoices list | FE | T08 | Tab count = list | Playwright |
| D-06-T11 | Docs + i18n | DOC | T09 | Gate green | CI |

- **Deliverable acceptance:** full page reachable from list and quick-create; applying reduces balance and reverses revenue/tax.
- **Testing:** integration, Playwright, gap-14 test.
- **Risks:** tax period of credit → explicit rule documented in ADR-002 addendum.

### D-07 · Reminders and statements

- **Branch:** `feature/D-07-reminders-statements`
- **Objective:** before-due and after-due reminder schedules with escalation, opt-out, late-fee/interest line, channel hooks, and statement runs.
- **Current behaviour (Xero):** overdue-only email reminders, plan-gated.
- **Expected behaviour (better than Xero):** org-level schedule of steps (e.g., −7, 0, +7, +14, +30 days) each with template (EN/FR), channel (email now; SMS/WhatsApp adapters), minimum amount; escalation actions per step (notify owner/salesperson, put contact on credit hold); per-contact opt-out and per-invoice pause; disputed flag stops reminders; late-fee/interest option adds a line to the next statement or a separate fee invoice (rate as data; FN-04 extends in Phase 2); statement runs (outstanding / activity) for selected contacts, emailed in bulk.
- **Gap #s closed:** 16.
- **Business rules:** never remind paid, voided, disputed, or credit-covered invoices; reminders use current revision amount and link; one reminder per step per invoice (idempotent); sending window respects org TZ business hours.
- **Edge cases:** invoice revised between steps; partial payment (remind remaining balance); contact without email (skip + list); bounce (flag contact, stop channel).
- **UI/UX notes:** timeline editor with draggable steps, preview with real invoice data; reminder log per invoice; statement run wizard with preview.
- **Dependencies:** D-03a, D-03b, D-05, A-07, A-08, B-02 (statements).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-07-T01 | `ReminderSchedule`, `ReminderStep` (offset days, template, channel, min amount, escalation) models | DB | A-07 | Migrates | unit |
| D-07-T02 | `ReminderChannel` interface; email implementation; SMS/WhatsApp stub adapters | BE | A-07 | Stub records "would send"; email sends | unit |
| D-07-T03 | Eligibility engine (paid/void/disputed/opt-out/paused/min amount/credit-covered) | BE | D-05 | No reminder for paid or disputed | unit (parameterised) |
| D-07-T04 | Daily job: compute due steps per invoice, idempotency (invoice, step) | BE | T03, A-08 | Before-due reminder sent on schedule exactly once | integration (freezegun) |
| D-07-T05 | Escalation actions (notify user, credit hold flag on contact) | BE | T04, B-01 | Credit hold blocks new invoices in block mode | integration |
| D-07-T06 | Late-fee/interest line generator (rate, grace, min) appended to statement or fee invoice | BE | D-03a | Fee computed per fixture | unit |
| D-07-T07 | `disputed` flag on invoice + per-contact opt-out field | DB/BE | D-03a | Flag stops reminders | unit |
| D-07-T08 | Statement run service (bulk, outstanding/activity, PDF + email) reusing B-02 | BE | B-02 | Statement totals = AR aging for contact | integration |
| D-07-T09 | API `/api/v1/reminders/` schedule CRUD, preview, log; `/statement-runs/` | API | T01–T08 | OpenAPI; sweep | API |
| D-07-T10 | UI: timeline editor (before/after-due steps) with template preview | FE/UX | T09 | Add −7 step in < 30 s | Playwright |
| D-07-T11 | UI: invoice reminder log + pause/dispute controls | FE | T09 | Log shows sent/skipped with reason | Playwright |
| D-07-T12 | UI: statement run wizard (select contacts, preview, send) | FE | T09 | Bulk send 50 statements | Playwright |
| D-07-T13 | EN/FR reminder templates seeded | BE/DOC | T01 | Both languages render | snapshot |
| D-07-T14 | Docs + i18n | DOC | T10–T12 | Gate green | CI |

- **Deliverable acceptance:** no reminder for paid or disputed invoices; before-due reminder sent on schedule; statement total = aging.
- **Testing:** time-travel integration, parameterised eligibility, Playwright.
- **Risks:** spamming customers → idempotency + daily cap per contact.

### D-09 · Sales overview and lists

- **Branch:** `feature/D-09-sales-overview`
- **Objective:** one overview page pattern (shared with purchases), list tabs incl. Overdue and Credit notes, saved filters, column chooser, bulk actions, revision badge.
- **Current behaviour:** none (Xero: modern sales overview vs legacy purchases overview).
- **Expected behaviour:** `OverviewPage` component with status tiles Draft / Awaiting approval / Awaiting payment / **Overdue** (count + amount), money-coming-in aging bar, top customers owing, quotes card (same enum), cards with retry on error; invoice list tabs All / Draft / Awaiting approval / Awaiting payment / Overdue / Paid / Credit notes / Void; saved views; column chooser; bulk: approve, send, send statements, export, print; "Show deleted/voided"; Revised badge.
- **Gap #s closed:** 5, 6, 22.
- **Business rules:** tile counts come from the same query as list tabs (single `SalesListQuery`); overdue = due date < today (org TZ) and open balance > 0 on current revision.
- **Edge cases:** large lists (10k invoices) — server pagination; empty org — instructive empty state; failing card — retry + reference id.
- **UI/UX notes:** tiles clickable → filtered list; saved view chips; bulk action bar appears on selection; keyboard `J/K`, `X` select, `Shift+X` range.
- **Dependencies:** D-02, D-03a, D-03b, D-05, D-06, A-10.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-09-T01 | `SalesListQuery` (filters, tabs, sorting, counts) on current revisions | BE | D-03b | Counts per tab correct on fixture | unit |
| D-09-T02 | Overview aggregates (tiles, aging buckets, top owing, quotes by status) | BE | T01, D-02 | Tile counts = list counts | integration (`gap-06`) |
| D-09-T03 | Saved views model (per user, per list key) + API | DB/API | A-10 | View persists | API |
| D-09-T04 | Bulk actions service (approve/send/statements/export) as job with per-row result | BE | D-03a, D-07 | 200 invoices bulk-sent with per-row status | integration |
| D-09-T05 | API `/api/v1/sales/overview`, `/invoices?tab=` | API | T01–T04 | OpenAPI | API |
| D-09-T06 | Shared `OverviewPage` component (tiles, cards with retry, aging bar) in `@numo9/ui` | FE/UX | A-10 | Used by sales now, purchases in E-02 | Storybook |
| D-09-T07 | Sales overview screen | FE | T05, T06 | Tile click opens filtered list | Playwright |
| D-09-T08 | Invoice list tabs incl. Overdue & Credit notes, Revised badge, show voided toggle | FE | T05 | Tabs present; badge visible | Playwright |
| D-09-T09 | Column chooser + saved view chips + bulk action bar + keyboard selection | FE/UX | T03, T04 | Keyboard range-select and bulk send | Playwright + axe |
| D-09-T10 | Card error state with retry + reference id (no silent "Unable to load") | FE | T06 | Simulated 500 shows retry; retry recovers | Playwright (`gap-05`) |
| D-09-T11 | Performance: 10k invoices list p95 < 1 s | QA | T01 | k6 within budget | perf |
| D-09-T12 | Docs + i18n | DOC | T07–T10 | Gate green | CI |

- **Deliverable acceptance:** tile counts = list counts; Overdue and Credit notes tabs; saved views; card errors retry.
- **Testing:** integration, Playwright, performance.
- **Risks:** count drift → one query source.

### 6.3 Purchases (Component E)

### E-01 · Purchase orders, receiving and 3-way match

- **Branch:** `feature/E-01-po-receiving-match`
- **Objective:** POs with approval limits, partial goods receipts (GRN), PO/received/billed match and a commitment report.
- **Current behaviour (Xero):** POs non-posting; only "Billed" status; no receiving; no limits.
- **Expected behaviour:** PO statuses Draft / Awaiting approval / Approved / Partially received / Received / Billed / Closed / Cancelled; per-user PO approval limits (A-03); `GoodsReceipt` with lines (received qty per PO line, date, received_by, notes); outstanding = ordered − received; "Create bill from PO/receipt" prefilled with received-not-billed quantities; 3-way match per line (PO qty/price vs received qty vs billed qty/price) with tolerance settings (qty %, price %); variances flagged and require approver; commitment report (open PO value by account/supplier/period vs budget placeholder until K-04); receipts call `StockMovementSink` (test double in Phase 1, H-04 in Phase 2).
- **Gap #s closed:** 24, 25.
- **Business rules:** receiving > ordered warns (tolerance) or blocks; receipt of untracked items allowed (records quantity, no stock); PO is non-posting (commitments only); cancelling a partially received PO closes outstanding; approval limit by user and amount.
- **Edge cases:** multiple partial receipts; receipt reversal; bill before receipt (allowed with "received later" status, match pending); price change on bill; PO revised after approval (re-approval if total increases).
- **UI/UX notes:** PO editor = shared grid + delivery block; Receive screen with ordered/received/outstanding columns and big numeric inputs (barcode-ready); Match panel on the bill with green/amber/red per line.
- **Dependencies:** D-01 grid, A-03, B-01, E-02 (bill creation), H-04 interface.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| E-01-T01 | `PurchaseOrder`, `PurchaseOrderLine` models (from `DocumentBase`, purchase side) + status enum | DB | D-01 | Migrates | unit |
| E-01-T02 | PO numbering `PO-0001` + approval service using A-03 PO limits | BE | A-03 | Limit 5,000 cannot approve 5,001 | unit |
| E-01-T03 | Re-approval rule when approved PO total increases | BE | T02 | Increase → Awaiting approval | unit |
| E-01-T04 | `GoodsReceipt`, `GoodsReceiptLine` models; receipt service with tolerance rules | DB/BE | T01 | Receive 6 of 10 → 4 outstanding, status Partially received | unit |
| E-01-T05 | `StockMovementSink` interface + Phase-1 test double; receipt emits +qty | BE | T04 | Sink records +6 for tracked item fixture | unit |
| E-01-T06 | Receipt reversal | BE | T04 | Outstanding restored; sink −qty | unit |
| E-01-T07 | Match engine (PO vs GRN vs bill per line with qty/price tolerance) | BE | T04, E-02 | Bill 12 vs PO 10 flagged | unit (parameterised) |
| E-01-T08 | Commitment report query (open PO value by account/supplier/month) | BE | T01 | Report totals = open PO lines | integration |
| E-01-T09 | PO PDF + email to supplier | BE | D-03a-T09 | PDF snapshot | snapshot |
| E-01-T10 | API `/api/v1/purchase-orders/`, `/receipts/`, `/purchase-orders/{id}/match`, `/reports/commitments`; feature key `accounting.purchases.po` | API | T01–T09 | OpenAPI; sweep | API |
| E-01-T11 | UI: PO editor (shared grid purchase mode, delivery block, limit indicator) | FE/UX | T10 | PO created in < 90 s | Playwright |
| E-01-T12 | UI: Receive screen (ordered/received/outstanding, keyboard Enter-to-next, over-receipt warning) | FE/UX | T10 | Partial receipt flow passes | Playwright + axe |
| E-01-T13 | UI: PO list tabs incl. Partially received / Received; "Create bill" action | FE | T10 | Tabs counts correct | Playwright |
| E-01-T14 | UI: commitment report screen with export | FE | T10 | Export = screen | Playwright |
| E-01-T15 | Approvals inbox registration for POs | BE | C-04-T08 | PO appears for approver within limit only | integration |
| E-01-T16 | Docs + i18n | DOC | T11–T14 | Gate green | CI |

- **Deliverable acceptance:** receiving 6 of 10 leaves 4 outstanding and increases stock by 6 (sink in Phase 1; re-verified with H-04 in Phase 2); a bill for 12 against a 10-unit PO is flagged; PO limits enforced.
- **Testing:** unit, integration, Playwright, approval matrix.
- **Risks:** sink contract mismatch with H-04 → contract test kept for Phase 2.

### E-02 · Bills

- **Branch:** `feature/E-02-bills`
- **Objective:** bills on the shared grid with supplier invoice-number uniqueness, duplicate review, routing by amount/department, holdback and AP/ITC posting.
- **Current behaviour (Xero):** legacy bill grid without discount/tax columns; uniqueness only in a separate review; no holdback; approval plan-gated.
- **Expected behaviour:** statuses Draft / Awaiting approval / Awaiting payment / Partially paid / Paid / Void; shared grid (purchase side filters: expense/asset/COGS accounts, purchase tax codes, partial ITC % from G-01); **supplier invoice number unique per supplier at entry** (live check); duplicate review (same supplier + amount ± 1 % + date ± 10 days) as soft warning list; routing rules (amount bands × department/tracking → approver group); holdback (amount or %) posted to Holdback payable, released later; posting Dr Expense/Asset / Dr ITC receivable (recoverable part) / Dr Expense (non-recoverable part) / Cr AP / Cr Holdback; attachment split-view; bill from PO/receipt (E-01) with match panel; purchases overview using `OverviewPage`.
- **Gap #s closed:** 1, 22, 23, 24.
- **Business rules:** AP lock; approval limits; supplier invoice no. required (configurable) and unique; ITC only if org GST-registered at bill date; holdback released by "Release holdback" action creating a payable.
- **Edge cases:** same invoice number from two suppliers (allowed); credit card bill vs bill; bill in foreign currency (reserved); partial ITC on inclusive amounts; release partial holdback.
- **UI/UX notes:** left: document preview (PDF/image from attachment), right: bill form; uniqueness check shows inline "Already used on BILL-0042 (12 Sep 2026)" with link; match panel; routing explanation "Routed to Finance approvers (amount > 2,000)".
- **Dependencies:** D-01, E-01, G-01, A-03, A-06, D-09-T06.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| E-02-T01 | `Bill`, `BillLine` models (supplier_invoice_no, holdback fields, department/tracking) | DB | D-01 | Migrates; unique (org, supplier, supplier_invoice_no) where not void | unit |
| E-02-T02 | Live uniqueness endpoint `/bills/check-number` | API | T01 | Duplicate number blocked at entry | API (`gap-24`) |
| E-02-T03 | Duplicate-suspect finder (fuzzy amount/date) + review list | BE | T01 | Fixture duplicates surfaced | unit |
| E-02-T04 | Purchase-side calculator integration incl. partial ITC split | BE | D-01-T03, G-01 | 50 % meals: half tax to ITC, half to expense | unit |
| E-02-T05 | Posting service (AP, ITC, non-recoverable, holdback) | BE | C-02, T04 | Balanced JE matches preview | integration |
| E-02-T06 | Holdback release service | BE | T05 | Release posts Dr Holdback / Cr AP | integration |
| E-02-T07 | `ApprovalRoutingRule` (amount band, department → approver group) + evaluator | DB/BE | A-03 | Thresholds respected; explanation string returned | unit (parameterised) |
| E-02-T08 | Bill from PO/receipt + match panel data (uses E-01-T07) | BE | E-01 | Prefilled qty = received − billed | integration |
| E-02-T09 | Void & lock checks | BE | T05, A-05 | Pre-lock refused naming lock | unit |
| E-02-T10 | API `/api/v1/bills/` CRUD + approve/void/release-holdback; feature key `accounting.purchases.bills` | API | T01–T09 | OpenAPI; sweep | API |
| E-02-T11 | UI: bill editor split view (attachment preview + form) | FE/UX | T10 | Enter bill from PDF without leaving page | Playwright |
| E-02-T12 | UI: inline supplier-invoice-number check + duplicate warning panel | FE/UX | T02, T03 | Inline message with link | Playwright |
| E-02-T13 | UI: match panel (green/amber/red per line) + "Approve with variance" | FE | T08 | Variance requires approver | Playwright |
| E-02-T14 | UI: routing explanation and approvals inbox registration | FE/BE | T07, C-04-T08 | Bill appears for correct group | integration |
| E-02-T15 | UI: Purchases overview (shared `OverviewPage`) + bills list tabs | FE | D-09-T06 | Same component id as sales (`gap-22`) | visual regression |
| E-02-T16 | Search registration + quick-create `N B` | BE/FE | A-09 | Bill found by supplier invoice no. | integration |
| E-02-T17 | Fixtures: 50 purchase documents across provinces incl. partial ITC | QA | T04 | Fixtures match | pytest |
| E-02-T18 | Docs + i18n | DOC | T11–T15 | Gate green | CI |

- **Deliverable acceptance:** duplicate supplier invoice number blocked; approval thresholds respected; holdback posts and releases; partial ITC correct.
- **Testing:** unit, integration, approval matrix, Playwright, visual regression.
- **Risks:** false duplicate blocks → uniqueness per supplier only, fuzzy matches are warnings.

### E-03 · Recurring bills and supplier credits

- **Branch:** `feature/E-03-recurring-bills-supplier-credits`
- **Objective:** repeating bills and supplier credit notes using the same patterns as D-04 and D-06.
- **Current behaviour:** none.
- **Expected behaviour:** `RecurringBillTemplate` (reuse schedule engine, modes draft/approve); `SupplierCredit` (shared grid) applied to bills or refunded (receive money); reversal of expense/ITC on approval.
- **Business rules:** same idempotency as D-04; supplier credit ITC reversal in credit date's GST period; apply ≤ open balance.
- **Edge cases:** recurring bill with supplier invoice number pattern (`{{month}}-{{year}}`) to keep uniqueness; credit larger than bill.
- **UI/UX notes:** identical UX to sales counterparts (learn once).
- **Dependencies:** D-04 engine, D-06 pattern, E-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| E-03-T01 | `RecurringBillTemplate` + lines models | DB | E-02 | Migrates | unit |
| E-03-T02 | Generator reusing D-04 engine (shared `RecurringGenerator` base) | BE | D-04-T05 | Exactly one bill per tick after restart | integration |
| E-03-T03 | Supplier-invoice-no. pattern rendering for uniqueness | BE | T02, E-02-T01 | Generated numbers unique | unit |
| E-03-T04 | `SupplierCredit`, lines, `SupplierCreditApplication` models | DB | E-02 | Migrates | unit |
| E-03-T05 | Supplier credit posting (Dr AP / Cr expense / Cr ITC) | BE | C-02 | Balanced; ITC reversed | integration |
| E-03-T06 | Apply to bills + refund (receive money) | BE | T05, F-01 | Apply reduces bill balance | integration |
| E-03-T07 | API `/recurring-bills/`, `/supplier-credits/` | API | T01–T06 | OpenAPI; sweep | API |
| E-03-T08 | UI: recurring bill template editor (shared with D-04 components) | FE | T07 | Same components | Playwright |
| E-03-T09 | UI: supplier credit editor + apply panel | FE | T07 | Apply to 2 bills | Playwright |
| E-03-T10 | Docs + i18n | DOC | T08–T09 | Gate green | CI |

- **Deliverable acceptance:** parallel to D-04/D-06 (one bill per tick; applying credit reduces balance and reverses expense/ITC).
- **Testing:** integration, Playwright.
- **Risks:** duplicated logic → shared base classes enforced by import-linter.

### E-04 · Expense claims

- **Branch:** `feature/E-04-expense-claims`
- **Objective:** employees submit receipts and mileage, approvers approve, a reimbursement bill is created.
- **Current behaviour (Xero):** paid add-on.
- **Expected behaviour:** `ExpenseClaim` with lines (receipt image/PDF, date, merchant, category→account, amount incl. tax with automatic tax split, partial ITC by account), mileage lines (km × CRA per-km rate configurable by year, two-tier rate after 5,000 km); submit → approve (submitter can never approve own) → creates reimbursement bill to the employee contact (Unpaid expense claims control) → paid via E-06 or bank; included in Accounting product (Gap 51 closed in Phase 1 for claims).
- **Gap #s closed:** 51 (partial — expenses included).
- **Business rules:** receipt required above configurable amount; mileage rate effective-dated as data; approval limits; employee contact auto-created from user (role employee).
- **Edge cases:** claim with foreign receipt (reserved); duplicate receipt image (hash check warning); mileage crossing 5,000 km within a claim.
- **UI/UX notes:** mobile-responsive web form; camera upload; category chips most-used first; mileage calculator with from/to text and km field.
- **Dependencies:** E-02, A-06, A-03, B-01.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| E-04-T01 | `ExpenseClaim`, `ExpenseClaimLine` (receipt/mileage types) models | DB | A-06 | Migrates | unit |
| E-04-T02 | `MileageRate` effective-dated table seeded with CRA rates (data) incl. tier threshold | DB | — | Rate by date selected | unit |
| E-04-T03 | Mileage calculator with tier crossing (YTD km per employee) | BE | T02 | Crossing 5,000 km splits rate | unit + Hypothesis |
| E-04-T04 | Tax split for inclusive receipt amounts + partial ITC | BE | D-01-T04, G-01 | Fixture amounts correct | unit |
| E-04-T05 | Workflow: submit/approve/reject; submitter ≠ approver; limits | BE | A-03 | Submitter cannot approve own claim | unit + API |
| E-04-T06 | Reimbursement bill creation on approval (employee contact, Unpaid expense claims control) | BE | E-02 | Bill created and posted | integration |
| E-04-T07 | Receipt duplicate hash warning | BE | A-06 | Same image twice → warning | unit |
| E-04-T08 | API `/api/v1/expense-claims/` + actions; feature key `accounting.expenses` | API | T01–T07 | OpenAPI; sweep; employee sees own only | API + security |
| E-04-T09 | UI: claim form (mobile-responsive, camera upload, category chips) | FE/UX | T08 | Submit claim on 390 px viewport | Playwright (mobile) |
| E-04-T10 | UI: mileage line calculator | FE | T08 | Amount shown live | Vitest |
| E-04-T11 | UI: approver view + inbox registration | FE/BE | C-04-T08 | Approve hidden for submitter | Playwright |
| E-04-T12 | Docs + i18n | DOC | T09–T11 | Gate green | CI |

- **Deliverable acceptance:** submitter cannot approve own claim; approved claim creates reimbursement bill; mileage at CRA rate.
- **Testing:** unit, security (own-records), Playwright mobile viewport.
- **Risks:** CRA rate changes → rate as data, warranty update.

### E-06 · Batch payments and cheques

- **Branch:** `feature/E-06-batch-payments-cheques`
- **Objective:** pay many bills in one batch via CPA 005 EFT file or printed cheques, with a cheque register (void/stale) and positive-pay export.
- **Current behaviour (Xero):** "Checks/Cheques" spelling flips; no positive pay; no register tracking.
- **Expected behaviour:** batch builder (select bills by due date/supplier/discount window), payment date, bank account; method EFT → CPA 005 file (originator settings per bank account: originator ID, data centre, short name, return account) + validation; method Cheque → sequential cheque numbers, print layout (cheque + 2 vouchers, Letter, MICR line), print preview; cheque register with statuses Issued / Printed / Cleared / Void / Stale-dated (configurable days, default 180); void reverses payment; positive-pay CSV export with bank presets; consistent "cheque" spelling (lint dictionary).
- **Gap #s closed:** 26.
- **Business rules:** batch total = Σ bill payments (incl. E-07 discounts); each bill payment posts Dr AP / Cr Bank (or Cr clearing until file confirmed — setting); cheque numbers unique per bank account; void requires reason and is audited; supplier bank details from contact (masked display).
- **Edge cases:** supplier without bank details (excluded with reason for EFT); bill partially paid within batch; batch re-generation (same file id refused unless cancelled); cheque printer misfeed (reprint with new number, old voided).
- **UI/UX notes:** batch builder with filter chips ("Due ≤ 7 days", "Discount ends soon"); summary bar; file download with checksum; print preview at 100 %; register list with status chips and bulk "Mark cleared".
- **Dependencies:** E-02, F-01, B-01 (bank details), E-07.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| E-06-T01 | `PaymentBatch`, `BillPayment` models (method, status, file ref) | DB | E-02 | Migrates | unit |
| E-06-T02 | Bill payment posting (Dr AP / Cr Bank or clearing) + allocation | BE | C-02, F-01 | AP decreases by payment | integration |
| E-06-T03 | `BankOriginatorSettings` on bank account (encrypted fields) | DB | F-01, S-03 | Fields encrypted at rest | unit |
| E-06-T04 | CPA 005 writer (header A, detail C records, trailer Z, fixed-width) | BE | T03 | File validates against CPA 005 layout validator | unit (fixture files) |
| E-06-T05 | CPA 005 validator CLI (internal tool) | OPS | T04 | Detects wrong lengths/totals | unit |
| E-06-T06 | `Cheque` model + numbering per bank account; register statuses | DB/BE | T01 | Unique numbers | unit |
| E-06-T07 | Cheque print PDF (cheque + 2 vouchers, MICR E-13B, Letter/inches) | BE | T06 | PDF snapshot; MICR line correct | snapshot |
| E-06-T08 | Void cheque (reverse payment) + reprint flow | BE | T06, T02 | Voided cheque reverses its payment | integration |
| E-06-T09 | Stale-dated job (days configurable) | BE | A-08 | Cheque > 180 days uncleared → Stale | integration |
| E-06-T10 | Positive-pay export (generic CSV + bank presets) | BE | T06 | Export matches register | unit |
| E-06-T11 | API `/api/v1/payment-batches/`, `/cheques/` + actions | API | T01–T10 | OpenAPI; sweep | API |
| E-06-T12 | UI: batch builder with filter chips, totals bar, discount badges | FE/UX | T11 | Batch of 20 bills in < 2 min | Playwright |
| E-06-T13 | UI: EFT file download + "Mark as sent" | FE | T11 | Download works; status updates | Playwright |
| E-06-T14 | UI: cheque print preview + register list (void, cleared, stale) | FE | T11 | Void dialog requires reason | Playwright |
| E-06-T15 | Spelling lint dictionary ("cheque", not "check") for UI catalogues | QA | A-10 | Lint fails on "check" in money contexts | CI (`gap-26`) |
| E-06-T16 | Docs + i18n | DOC | T12–T14 | Gate green | CI |

- **Deliverable acceptance:** batch total = bills; CPA 005 validates; voided cheque reverses payment; positive-pay export available.
- **Testing:** unit with fixture files, integration, snapshot, Playwright.
- **Risks:** bank-specific CPA 005 variants → per-bank profile options; MICR font licensing → verify licence.

### E-07 · Early-payment discount capture

- **Branch:** `feature/E-07-early-payment-discount`
- **Objective:** support terms like 2/10 net 30 on bills and invoices and post discounts automatically when paid inside the window.
- **Current behaviour (Xero):** no early-payment terms.
- **Expected behaviour:** payment terms master (B-01) gains discount % and discount days; documents show "Pay by 05 Nov to save 22.60"; on payment (D-05/E-06) inside the window the discount is applied: bills → Cr Purchase discounts received (and ITC adjusted per CRA rule on discount — configurable: adjust tax or not), invoices → Dr Sales discounts given; payment outside window → no discount; manual override with reason; reports of discounts captured/missed (feeds FN-04 cost-of-forgoing in Phase 2).
- **Gap #s closed:** 10, 23.
- **Business rules:** discount base = document total (or pre-tax, setting); window by document date + days in org TZ; partial payments: discount pro-rata to amount paid within window.
- **Edge cases:** payment on last day at 23:59; revised invoice (window from original date unless reason "terms changed"); discount on credit-noted invoice.
- **UI/UX notes:** discount badge in batch builder and payment screens; countdown chip "2 days left"; missed-discount list on purchases overview.
- **Dependencies:** B-01 terms, D-05, E-06, C-01 (discount accounts).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| E-07-T01 | Extend `PaymentTerms` with discount_pct, discount_days, discount_base | DB | B-01 | Migrates; 2/10 net 30 seeded | unit |
| E-07-T02 | Discount calculator (window, base, partial pro-rata) | BE | T01 | Fixtures incl. 23:59 boundary | unit + Hypothesis |
| E-07-T03 | Default discount accounts in CoA template (Purchase discounts received, Sales discounts given) | DB | C-01 | Accounts exist and mapped to GIFI | unit |
| E-07-T04 | Bill payment integration: apply discount, post, tax-adjust option | BE | E-06-T02 | Payment inside window posts discount automatically | integration |
| E-07-T05 | Customer payment integration (D-05) | BE | D-05-T03 | Invoice discount posted on early payment | integration |
| E-07-T06 | Manual override (apply/skip) with reason + audit | BE | T04 | Override audited | unit |
| E-07-T07 | Discounts captured/missed report query | BE | T04, T05 | Totals match fixture | integration |
| E-07-T08 | API exposure on documents (`discount_available`, `discount_until`) and report endpoint | API | T02–T07 | OpenAPI | API |
| E-07-T09 | UI: "Pay by … to save …" on invoice/bill + PDF line | FE/BE | T08 | Visible on PDF and screen | snapshot + Playwright |
| E-07-T10 | UI: discount badges/countdown in batch builder and payments | FE/UX | T08 | Badge shows days left | Playwright |
| E-07-T11 | UI: missed-discount card on purchases overview | FE | T07 | Card total = report | Playwright |
| E-07-T12 | Docs + i18n | DOC | T09–T11 | Gate green | CI |

- **Deliverable acceptance:** payment inside the window posts the discount automatically; outside the window none; captured/missed report correct.
- **Testing:** unit boundary tests, integration with D-05/E-06, Playwright.
- **Risks:** tax treatment of discounts → configurable, documented, client confirms.


### 6.4 Banking (Component F)

### F-01 · Never-locked bank, credit-card & cash accounts
- **Branch:** `feature/F-01-never-locked-bank-accounts`
- **Objective:** let an organisation use any bank, credit-card, line-of-credit, loan, cash or clearing account the moment it is created, without a feed, import, reconciliation or plan upgrade.
- **Current behaviour:** Phase 0 delivered the chart of accounts (C-01) and the posting engine (C-02). Bank accounts are plain ledger accounts with no banking screens, no spend/receive money, and no bank-account sub-types.
- **Expected behaviour (better than Xero):** Xero only offers "Credit card / Other", needs a feed or a plan upgrade, and still let REFINED run with no bank at all. In Numo9, a `BankAccount` profile is attached to a ledger account and has one of these types: Chequing, Savings, Credit card, Line of credit, Loan, Cash/Petty cash or Clearing. It can be created in under 30 seconds. Spend money, receive money and transfers work straight away. The balance shown is always the ledger balance, and an optional statement balance sits beside it. Reconciliation is optional and never blocks anything. There is no plan gate. An organisation with no bank account sees a set-up prompt it can dismiss; nothing is blocked.
- **Gap #s closed:** 27 (with F-07), part of 60 (cash definition).
- **Business rules:**
  - Account type drives the GL account type: Chequing, Savings and Cash are current assets; Credit card and Line of credit are current liabilities; Loan is a non-current liability by default and can be overridden.
  - The ledger balance is never edited directly.
  - An account with transactions can be archived but not deleted.
  - Currency is fixed once the account has transactions (R-01 adds multi-currency).
  - The last four digits of the account and transit/institution numbers are stored encrypted and shown masked.
  - Spend/receive money posts through C-02 with contact, tax (G-01) and attachment rules (C-03).
- **Edge cases:**
  - The first transaction is dated before the conversion date.
  - A credit card is paid from chequing (transfer, not spend).
  - Cash account is renamed after transactions exist.
  - Concurrent spend on the same account.
  - An archived account is chosen on an old draft.
  - A spend-money line uses a sales tax code (filtered out).
- **UI/UX:**
  - Banking home with account cards (type icon, ledger balance, statement balance if any, "Not reconciled — optional" chip, last activity).
  - "Add account" side-sheet with 4 fields: type, name, institution, currency.
  - Spend/Receive money form reusing the shared document grid (D-01) in "bank" mode.
  - Quick-create shortcuts.
  - Persistent but dismissible "Add your first bank account" banner on dashboard and banking only.
  - Empty state explains that a feed is not needed.
- **Dependencies:** C-01, C-02, C-03, G-01 (tax on spend/receive), A-06 (attachments), A-09 (quick-create).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| F-01-T01 | Wireframes in Figma: banking home, add-account sheet, account detail, spend/receive money form, no-bank prompt | UX | — | Frames reviewed; states empty/loading/error/archived covered | Design review |
| F-01-T02 | `BankAccount` model (OrgOwnedModel): gl_account 1:1, type enum (CHEQUING/SAVINGS/CREDIT_CARD/LOC/LOAN/CASH/CLEARING), institution, display_name, currency, masked_number (encrypted), statement_balance (nullable), statement_balance_date, is_reconciled_tracking flag, archived_at | DB | C-01 | Migration applies; unique display_name per org | Unit |
| F-01-T03 | Type → GL type/sub-type mapping service; auto-create the linked GL account with the next free code in the bank range | BE | T02 | Chequing creates current-asset bank account 10xx; Credit card creates current liability 21xx | Unit (each type) |
| F-01-T04 | Delete/archive guard: delete refused when lines exist (409 with count); archive allowed; archived accounts hidden from pickers but kept in reports | BE | T02 | Delete with 1 line → 409 "has 1 transaction — archive instead" | Unit + API |
| F-01-T05 | `BankTransaction` service for spend money / receive money: header (date, contact, reference, bank account, amounts tax incl/excl) + lines; posts a balanced JE through C-02 with source link | BE | T02, C-02 | Spend 113.00 incl. HST posts Dr expense 100 / Dr ITC 13 / Cr bank 113 | Unit + property (balanced) |
| F-01-T06 | Ledger-balance query (posted lines, both books = accounting view) with an `as_of` param, cached per account and invalidated on post | BE | T05 | Balance equals TB balance of the linked GL account | Integration |
| F-01-T07 | API: `/api/v1/bank-accounts` (CRUD, archive), `/api/v1/bank-transactions` (spend/receive, list, void→reverse); feature key `accounting.banking`; RBAC permissions declared | API | T03–T06, A-03, U-03 | Router sweep passes; permission catalogue lists new perms | API + tenant sweep |
| F-01-T08 | Banking home screen: account cards with ledger and statement balance, type icon, "optional reconciliation" chip, skeleton loading, error retry | FE | T07, A-10 | Card balance = API ledger balance; empty state shown with 0 accounts | Vitest + Playwright |
| F-01-T09 | Add-account side-sheet (type segmented control with plain-language help, name, institution with Canadian bank list, currency); success toast with "Record a transaction" next action | FE | T07 | Account created and usable in < 30 s in a usability run | Playwright |
| F-01-T10 | Spend/Receive money form reusing the D-01 grid in bank mode (account/tax pickers filtered: purchase side for spend, sales side for receive); attachment drop zone; contact optional per rule | FE | T07, D-01 | Purchase codes only on spend; posting succeeds without any import | Playwright |
| F-01-T11 | Account detail page: running-balance transaction list, filters (date, contact, amount, status), column chooser, export CSV/XLSX | FE | T07 | Running balance of last row = ledger balance | Playwright |
| F-01-T12 | No-bank-account prompt: dashboard and banking banner, dismissible per user for 7 days, never blocks any action | FE | T08 | Org with 0 bank accounts can still post journals; banner reappears after 7 days | Playwright |
| F-01-T13 | Quick-create and global-search registration: Spend money, Receive money, Add bank account; shortcuts shown in the "+" menu | FE | T09, T10, A-09 | Shortcut opens the form; search "petty" finds the Petty Cash account | Playwright |
| F-01-T14 | Audit-log hooks (create/archive/rename/statement-balance edits) and i18n keys en-CA/fr-CA for all strings | BE/FE | T02–T11 | Audit shows old/new name; i18n lint passes | Unit + lint |
| F-01-T15 | Demo/seed: Canadian demo org gets Chequing, Visa, Petty Cash with sample spend/receive (U-07 seed update) | QA | T05 | Demo reset shows the three accounts with expected balances | Fixture test |
| F-01-T16 | Functional E2E for gap-27: new org → add chequing → spend money with no import/reconciliation → Balance Sheet shows it | QA | T10, K-02 | Test tagged `gap-27` green | Playwright |
| F-01-T17 | User-guide section "Bank accounts without feeds" plus the ADR note that the bank never depends on a feed | DOC | T16 | Docs merged in `docs/` | Review |

- **Deliverable acceptance:**
  - A spend-money transaction from a new chequing account with no import shows on the Balance Sheet.
  - Deleting an account with transactions is refused.
  - The no-bank prompt informs but never blocks.
- **Testing:** unit (mapping, guards, posting), property (balanced posting), integration (balance = TB), functional (gap-27), security (tenant sweep, masked numbers never in logs).
- **Risks:**
  - Bank type mapped to the wrong GL type. Mitigation: mapping table tests.
  - Balance cache gets stale. Mitigation: invalidate on post/reverse, with a nightly consistency check.

### F-02 · Statement import (CSV/OFX/QFX/QBO/XLSX)
- **Branch:** `feature/F-02-statement-import`
- **Objective:** import bank and credit-card statements in every common Canadian format, with saved per-bank mappings and zero duplicate lines.
- **Current behaviour:** no statement lines exist; bank accounts post only via spend/receive (F-01).
- **Expected behaviour (better than Xero):** Xero allows manual CSV/OFX import only. Numo9 offers:
  - CSV, OFX, QFX, QBO and XLSX.
  - A mapping wizard with auto-detected columns and saved mappings for RBC, TD, Scotiabank, BMO, CIBC, Desjardins, National Bank, Tangerine and generic credit-union formats.
  - A preview with per-line status (new / duplicate / error).
  - Fingerprint-based duplicate detection.
  - An undo of a whole import batch while no line in it has been matched.
  - Import is fed through the internal `BankStatementSource` interface so Numo9's own banking app (W-02) can plug in later.
- **Gap #s closed:** 27 (import works on every package), 15 (mapping + dry-run pattern reused).
- **Business rules:**
  - Fingerprint = account + date + amount + normalised description + bank reference/FITID.
  - The same file imported twice adds 0 lines.
  - Statement lines are not ledger postings until coded or matched (F-05).
  - Dates are parsed per mapping (DD/MM vs MM/DD declared, never guessed silently).
  - Debit/credit sign convention is chosen per mapping.
  - Opening/closing statement balance is captured when the file provides it.
- **Edge cases:**
  - Same amount and description on the same day: legitimate duplicates, kept via sequence and FITID.
  - Files with BOM or Windows-1252 encoding; French bank descriptions with accents.
  - QBO with an Intuit header; overlapping date ranges; an empty file; a 50,000-line file.
- **UI/UX:**
  - 4-step wizard: Upload → Map → Preview → Confirm, with a progress stepper.
  - Drag-and-drop zone and sample-format help.
  - Mapping step shows the first 5 rows with dropdowns per column.
  - Preview groups new/duplicate/error with counts, plus a "Skip errors and import valid lines" toggle.
  - Result toast with "Undo import".
- **Dependencies:** F-01, A-06 (file storage), A-08 (background jobs for large files).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| F-02-T01 | Wireframes: 4-step import wizard, mapping grid, preview with grouped statuses, import history list | UX | — | Reviewed frames incl. error and large-file states | Design review |
| F-02-T02 | `StatementImport` (batch: file, mapping, counts, status, created_by) and `StatementLine` (bank_account, date, amount, description, payee, reference, fitid, fingerprint, status UNCODED/CODED/MATCHED/IGNORED, import FK) models; unique index on (bank_account, fingerprint) | DB | F-01 | Migration; duplicate insert raises integrity error | Unit |
| F-02-T03 | `BankStatementSource` interface (`fetch_lines()`, `source_name`) and `FileStatementSource` implementation | BE | T02 | Interface documented; file source returns normalised `RawLine` objects | Unit |
| F-02-T04 | Parsers: OFX/QFX (ofxparse), QBO (OFX variant with header stripping), CSV (encoding sniff via charset-normalizer, delimiter sniff), XLSX (openpyxl) | BE | T03 | 5 fixture files per format parse to the expected lines | Unit (fixtures) |
| F-02-T05 | `StatementMapping` model and seed mappings for 9 Canadian banks plus a generic layout (column roles, date format, sign convention, skip rows) | DB/BE | T02 | Seeds load; RBC fixture auto-maps with 0 manual changes | Unit |
| F-02-T06 | Mapping auto-detection: header similarity scoring picks the best saved mapping; user override saved per bank account | BE | T05 | TD sample auto-selects the TD mapping | Unit |
| F-02-T07 | Fingerprinting and duplicate detection, with a same-day identical-line sequence counter | BE | T02 | Importing the same file twice → 0 new lines; 2 identical coffees on the same day both kept on first import | Unit + property |
| F-02-T08 | Dry-run preview service: returns new/duplicate/error lines with reasons, without writing | BE | T04, T07 | Preview counts = later committed counts | Integration |
| F-02-T09 | Commit service (atomic batch insert) plus a Celery job for files > 2,000 lines with progress | BE | T08, A-08 | 50k-line file imports in < 60 s on staging; progress visible | Perf + integration |
| F-02-T10 | Undo import: deletes the batch's lines only if none are CODED/MATCHED; otherwise refused with a list | BE | T09 | Undo after one match → 409 listing that line | Unit |
| F-02-T11 | API `/api/v1/bank-accounts/{id}/imports` (upload, preview, commit, undo, history); feature key; permissions | API | T08–T10 | Tenant sweep and RBAC matrix pass | API |
| F-02-T12 | Wizard UI: upload with drag-and-drop, encoding/format detection message, mapping grid, preview tabs, confirm | FE | T11 | Usability task "import RBC CSV" done in < 90 s | Playwright |
| F-02-T13 | Import history and statement-lines list on the account page with status filters and an "Uncoded" count badge | FE | T11 | Badge equals the count of UNCODED lines | Playwright |
| F-02-T14 | Capture statement opening/closing balance from file (OFX LEDGERBAL); update `statement_balance` on the account | BE | T04, F-01 | OFX fixture sets the statement balance and date | Unit |
| F-02-T15 | i18n keys, audit hooks (import, undo), error-message catalogue (e.g. "Row 14: date '13/25/2026' doesn't match DD/MM/YYYY") | BE/FE | T12 | i18n lint passes; messages name the row and the fix | Lint + unit |
| F-02-T16 | Regression suite: idempotent re-import, overlapping ranges, BOM, accents, empty file | QA | T09 | All fixtures green | pytest |

- **Deliverable acceptance:**
  - The same file imported twice adds 0 lines.
  - Saved Canadian mappings work.
  - The preview is accurate.
- **Testing:** unit parsers, property (fingerprint idempotency), integration (commit and undo), perf (50k lines), security (file MIME validation and size limit from A-06).
- **Risks:**
  - Bank format changes. Mitigation: mappings are data and editable.
  - False duplicates. Mitigation: sequence counter plus FITID priority.

### F-04 · Bank rules
- **Branch:** `feature/F-04-bank-rules`
- **Objective:** code statement lines automatically using ordered, testable rules.
- **Current behaviour:** statement lines (F-02) can only be coded one by one.
- **Expected behaviour (better than Xero):** Xero offers equals/contains/starts with/blank only, with no priority, no regex, no history preview and no auto-apply. Numo9 adds:
  - Conditions on payee, description, reference, amount and any text field, with operators equals, contains, does not contain, starts with, ends with, regex, is blank, amount between, amount greater/less than.
  - Any/all matching.
  - Set contact.
  - Fixed-amount plus percentage allocation lines (the percentages must total 100 %).
  - Tax code per line, a reference template, and scope (all accounts or a selected set).
  - Explicit drag-ordered priority, where the first match wins.
  - "Test against history" preview.
  - Auto-apply (code without review), off by default; when on, lines are marked "auto-coded" and can be reviewed and reverted.
- **Gap #s closed:** 28.
- **Business rules:**
  - Priority order is unique per org and rule type (spend / receive / transfer).
  - Regex is validated at save with a 50 ms timeout guard (RE2 or the `regex` timeout).
  - Allocation total must equal the line amount after percentages.
  - Rounding remainder goes to the last percentage line.
  - Rules never touch MATCHED or locked-period lines.
  - Every application is logged (rule id on the line).
- **Edge cases:**
  - Two rules match: the higher priority wins and the preview shows the losing rule.
  - Regex catastrophic backtracking.
  - A 33.33 % × 3 split.
  - A rule referencing an archived account (it is disabled with a warning).
  - A rule with transfer type pointing at the same account.
- **UI/UX:**
  - Rules list with drag handles for priority, an on/off toggle and a "last applied" count.
  - Rule builder as a sentence-style condition builder ("When Description contains 'PETRO' and Amount is between 20 and 200…").
  - Live preview panel showing the last 90 days of matches.
  - Allocation grid with a running % total.
  - "Create rule from this line" shortcut on statement lines.
- **Dependencies:** F-02, G-01, B-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| F-04-T01 | Wireframes: rules list with priority drag, sentence builder, allocation grid, history preview panel | UX | — | Reviewed | Design review |
| F-04-T02 | `BankRule` model (type, name, match_mode ANY/ALL, priority, scope_accounts M2M, contact_strategy, contact FK, reference_template, auto_apply, active) and `BankRuleCondition` (field, operator, value, value_to) | DB | F-02 | Migration; unique (org, type, priority) deferrable | Unit |
| F-04-T03 | `BankRuleAllocation` (account, tax_code, description, fixed_amount or percent, order) with validator: percentages total 100 when present | DB/BE | T02 | 60 % + 30 % rejected; fixed 10 + 100 % accepted | Unit |
| F-04-T04 | Condition evaluator with all operators, case-insensitive with accent folding; regex with timeout guard | BE | T02 | Operator truth table passes; malicious regex rejected at save | Unit (parametrised) |
| F-04-T05 | Priority engine: ordered evaluation, first match wins; returns the winner plus shadowed matches | BE | T04 | Two matching rules → priority 1 applied, rule 2 reported shadowed | Unit |
| F-04-T06 | Allocation calculator: fixed lines first, remainder by percentage, rounding to the last line, tax split per line | BE | T03 | 100.00 split 33.33 % ×3 → 33.33/33.33/33.34 | Unit + property (sum = amount) |
| F-04-T07 | Apply service: codes a statement line into a draft bank transaction (F-01) with `applied_rule` link; auto-apply posts directly and flags `auto_coded` | BE | T05, T06, F-01 | Auto-applied line posts a balanced JE and keeps the rule reference | Integration |
| F-04-T08 | History preview: runs a rule against the last N days (default 90) of lines without writing; returns matches and conflicts | BE | T05 | Preview count equals actual apply count on the same data | Integration |
| F-04-T09 | Reorder endpoint (atomic renumber) and API CRUD `/api/v1/bank-rules`; permissions; feature key | API | T02–T08 | Reorder of 50 rules is atomic; sweep passes | API |
| F-04-T10 | Rules list UI with drag-to-reorder (dnd-kit), toggle, counters, search | FE | T09 | Order persists after reload | Playwright |
| F-04-T11 | Sentence-style rule builder with operator-aware inputs (amount range shows two fields; regex shows a tester) | FE | T09 | Regex tester highlights matches in sample text | Vitest |
| F-04-T12 | Allocation grid with running % total, red/green validation, tax picker filtered by rule type | FE | T11 | Save disabled until total = 100 % | Vitest |
| F-04-T13 | Preview panel listing affected historical lines and shadowing rules | FE | T08, T11 | Panel shows the shadowed-by rule name | Playwright |
| F-04-T14 | "Create rule from line" action on statement lines, pre-filling the payee/description condition | FE | T11, F-02 | Opens the builder pre-filled | Playwright |
| F-04-T15 | Revert auto-coded line (reverse JE, line back to UNCODED) with an audit entry | BE/FE | T07 | Revert restores the UNCODED state and the GL nets to 0 | Integration |
| F-04-T16 | i18n, audit hooks and gap-28 functional test (regex, not-contains, range, priority, preview) | QA | T10–T15 | `gap-28` green | Playwright |

- **Deliverable acceptance:**
  - Rule order is respected.
  - The preview shows affected history.
  - Regex, does-not-contain and amount ranges are all supported.
  - Auto-apply is optional.
- **Testing:** unit (operators, allocation), property (allocation sum), integration (apply/revert), functional (gap-28), security (regex DoS).
- **Risks:**
  - Over-eager auto-apply. Mitigation: off by default, "auto-coded" review filter, revert.
  - Regex performance. Mitigation: timeout and RE2.

### F-05 · Optional reconciliation
- **Branch:** `feature/F-05-optional-reconciliation`
- **Objective:** let users match statement lines to ledger transactions when they want to, without reconciliation ever gating any other function.
- **Current behaviour:** statement lines (F-02) and bank transactions (F-01) exist separately; there is no matching.
- **Expected behaviour (better than Xero):** Xero ties banking to feeds and reconciliation. In Numo9, reconciliation is a per-account opt-in. It offers:
  - Suggested matches (amount, date ±N days, contact, reference).
  - One-to-one, one-to-many and many-to-one matching, and split.
  - Find & match against open invoices, bills and existing transactions.
  - Create from line (spend/receive/transfer, rule-assisted).
  - A reconciliation report (statement balance vs reconciled ledger balance vs unreconciled items).
  - Unreconcile with a reason and audit entry.
  - "Mark account as not reconciled", which hides the reconciliation UI for that account.
  - Nothing else in the system (posting, reports, payroll, payments) depends on reconciliation state.
- **Gap #s closed:** 27.
- **Business rules:**
  - A statement line is matched once only.
  - A ledger line can be matched to one statement line, or to several when the many-side is a split.
  - Matched amounts must be equal to the cent.
  - Reconciled lines in a locked Bank period cannot be unreconciled without permission.
  - The reconciled balance is the sum of matched ledger lines plus the opening reconciled balance.
- **Edge cases:**
  - Payment of 3 invoices in one deposit.
  - A bank fee netted from a deposit (split creates a fee line).
  - Duplicate suggestions.
  - Unreconciling a line whose transaction was later reversed.
  - Reconciliation started mid-history (opening reconciled balance).
- **UI/UX:**
  - Two-pane reconcile screen: statement line on the left, suggested match on the right, "OK" with Enter, keyboard J/K navigation, match confidence chips.
  - Tabs: Match / Create / Find & match / Split.
  - Progress bar ("38 of 52 lines").
  - "Reconciliation is optional" banner explaining that it never blocks anything.
  - Undo snackbar on each match.
- **Dependencies:** F-01, F-02, F-04, D-05, E-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| F-05-T01 | Wireframes: two-pane reconcile, find & match modal, split modal, reconciliation report | UX | — | Reviewed incl. keyboard map | Design review |
| F-05-T02 | `ReconciliationMatch` (statement_lines M2M, ledger_lines M2M, matched_by, matched_at, reversed_at, reason) and a `reconciled` flag on statement lines; constraint: one active match per statement line | DB | F-02 | Second active match on the same line → integrity error | Unit |
| F-05-T03 | Per-account reconciliation settings: enabled flag, opening reconciled balance and date | DB/BE | F-01 | Disabling hides UI; posting is unaffected | Unit |
| F-05-T04 | Suggestion engine scoring amount equality, date proximity (±7 days configurable), contact name similarity (rapidfuzz), reference match; returns top 3 with score | BE | T02 | Fixture: 90 % of correct matches ranked first | Unit (fixtures) |
| F-05-T05 | Match service for 1:1, 1:n and n:1 with a cent-equality check, atomic, audit | BE | T02 | Mismatched totals → 422 with the difference amount | Unit |
| F-05-T06 | Find & match: search open invoices/bills/unreconciled transactions; matching to an open invoice creates a payment (D-05/E-05 payment service) | BE | T05, D-05 | Deposit matched to 3 invoices creates 3 allocations | Integration |
| F-05-T07 | Split: one statement line into a match portion plus a new spend/receive line (e.g. a bank fee) | BE | T05, F-01 | 1,000 deposit = 990 invoice + 10 fee; GL balanced | Integration |
| F-05-T08 | Create-from-line using F-04 rules or manual coding, auto-matched on creation | BE | F-04, T05 | Created transaction is matched immediately | Integration |
| F-05-T09 | Unreconcile with reason; blocked in a locked Bank period without `bank.unlock` permission | BE | T05, A-05 | Locked period → 403 naming the lock | Unit |
| F-05-T10 | Reconciliation report: statement balance, reconciled ledger balance, unreconciled statement lines, unpresented ledger items, difference | BE | T05 | Reconciled balance = statement balance on the fixture | Integration |
| F-05-T11 | API `/api/v1/bank-accounts/{id}/reconcile/*` (suggestions, match, split, unreconcile, report); permissions | API | T04–T10 | Sweep passes | API |
| F-05-T12 | Two-pane reconcile UI with keyboard (Enter = OK, J/K = next/prev, F = find, S = split), progress bar, undo snackbar | FE | T11 | 50 lines reconciled with keyboard only in a usability run | Playwright |
| F-05-T13 | Find & match modal with multi-select and live difference; split modal | FE | T11 | OK disabled until difference = 0.00 | Vitest |
| F-05-T14 | Reconciliation report screen and PDF/XLSX export | FE | T10 | Export equals the screen | Playwright |
| F-05-T15 | Proof that nothing depends on reconciliation: a regression test in which an account with reconciliation disabled runs every banking, report and payment flow | QA | T03 | All flows pass with 0 reconciled lines | E2E |
| F-05-T16 | i18n, audit hooks, docs "Reconciliation is optional" | DOC | T12 | Lint passes; docs merged | Review |

- **Deliverable acceptance:**
  - Reconciled balance equals the statement balance.
  - A line is matched once only.
  - Reconciliation never blocks anything.
- **Testing:** unit (constraints, scoring), integration (find & match, split), functional (keyboard flow), regression (no-dependency proof).
- **Risks:**
  - Wrong auto-suggestions. Mitigation: suggestions only, never auto-OK.
  - Double match under concurrency. Mitigation: DB constraint plus `select_for_update`.

### F-06 · Transfers
- **Branch:** `feature/F-06-transfers`
- **Objective:** move money between any two bank, card, line-of-credit, loan or cash accounts with one entry, both sides auto-matched.
- **Current behaviour:** only spend/receive exist; a transfer would need two entries or a journal.
- **Expected behaviour:**
  - One Transfer form (from, to, date, amount, reference) posts one JE that nets to zero.
  - When both sides appear on imported statements, each statement line auto-suggests the single transfer.
  - Cross-currency transfers are deferred to R-02, with a clear message.
  - Credit-card payment and petty-cash float presets ("Fund petty cash", "Pay credit card").
- **Gap #s closed:** 33 (prevents journal-based transfers), supports 27.
- **Business rules:**
  - From ≠ to.
  - Amount > 0.
  - Both accounts are active and in the same currency in Phase 1.
  - The transfer is one JE with two lines and the source type TRANSFER.
  - Reversal reverses both sides.
- **Edge cases:**
  - The transfer drives the from-account negative (F-07 warning).
  - Only one side imported.
  - Back-dated into a locked period.
- **UI/UX:**
  - Compact transfer dialog with swap-accounts button and account balances shown under each picker.
  - Presets as chips.
  - Keyboard Alt+T.
- **Dependencies:** F-01, F-05, F-07.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| F-06-T01 | Wireframe: transfer dialog with swap button, balances under pickers, preset chips | UX | — | Reviewed | Design review |
| F-06-T02 | `BankTransfer` model (from_account, to_account, date, amount, reference, journal FK) with validators | DB | F-01 | Same from/to rejected | Unit |
| F-06-T03 | Transfer posting service: one JE Dr to / Cr from, source TRANSFER; void reverses | BE | T02, C-02 | GL net movement across both = 0 | Unit + property |
| F-06-T04 | Auto-match: when a statement line on either account equals the transfer amount ±3 days, suggest the transfer side with top score | BE | T03, F-05 | Both statement lines match the same transfer, each to its own side | Integration |
| F-06-T05 | Presets: "Fund petty cash" (chequing → cash), "Pay credit card" (chequing → card) | BE/FE | T03 | Preset pre-fills accounts by type | Vitest |
| F-06-T06 | API `/api/v1/bank-transfers`; permission; feature key | API | T03 | Sweep passes | API |
| F-06-T07 | Transfer dialog UI with balances under pickers and swap; F-07 warning inline | FE | T06, F-07 | Negative-balance warning appears before save | Playwright |
| F-06-T08 | Quick-create Alt+T registration and list of transfers on both account pages | FE | T07 | Transfer visible on both accounts | Playwright |
| F-06-T09 | i18n, audit, functional test (fund petty cash 1,000 → both balances correct) | QA | T07 | Green | Playwright |

- **Deliverable acceptance:**
  - A transfer nets to zero in the GL.
  - Both sides auto-match.
- **Testing:** unit, property (net zero), integration (auto-match), functional.
- **Risks:** a transfer suggested as a payment match. Mitigation: transfer candidates get a type bonus in the score.

### F-07 · Negative-balance & cash controls
- **Branch:** `feature/F-07-negative-balance-controls`
- **Objective:** never accept a negative cash or bank asset balance silently.
- **Current behaviour:** C-03 has a journal-level negative-cash warning; banking and payments do not check yet. Balance Sheet presentation is in K-02.
- **Expected behaviour (better than Xero):** Xero let Petty Cash reach −994.17 with no warning. Numo9 adds:
  - A per-org setting per account type: Cash/Petty cash defaults to BLOCK for non-advisers and WARN for advisers; Chequing/Savings default to WARN (an overdraft is possible).
  - The check runs on every posting source: spend money, payments, transfers, journals, payroll and bill batches.
  - A warning requires a reason, which is stored on the JE.
  - Overdrawn asset bank accounts are presented as current liabilities on the BS (K-02 hook).
  - Exceptions engine rule `NEG_CASH` (K-09).
  - Suggested remedies shown inline, e.g. "Fund petty cash from Chequing" or "Record as owner paid (Shareholder loan)".
- **Gap #s closed:** 27, 33, 56 (presentation via K-02).
- **Business rules:**
  - The projected balance is computed as of the transaction date and as of today; the worst case is used.
  - Back-dated entries are checked against every later day's balance (min running balance).
  - Credit-card, line-of-credit and loan accounts are excluded (liabilities).
  - Override permission is `bank.allow_negative`.
- **Edge cases:**
  - Back-dated spend that makes an intermediate day negative while today stays positive.
  - Concurrent spends.
  - Reversal that makes the balance negative.
  - Payroll run with 30 payments.
- **UI/UX:**
  - Inline warning panel in the form (not a modal) showing "Petty Cash will be −994.17 on 15 Jun 2026". The panel offers two remedy buttons and a reason field.
  - A block state names who can override.
- **Dependencies:** F-01, F-06, C-03, A-03, A-05.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| F-07-T01 | `CashControlPolicy` per org and bank-account type (ALLOW/WARN/BLOCK, adviser level) with defaults seeded | DB | F-01 | Defaults: Cash BLOCK (non-adviser) / WARN (adviser), Chequing WARN | Unit |
| F-07-T02 | Minimum-running-balance projector: given an account, a date and a delta, returns the minimum balance from that date onward (windowed SQL) | BE | F-01 | Back-dated −100 on a day with a later trough detects the negative | Unit + property |
| F-07-T03 | Pre-post hook in C-02 posting pipeline: evaluates the policy for every bank/cash line of any source; raises `NegativeBalanceWarning` / `NegativeBalanceBlocked` | BE | T01, T02, C-02 | Hook fires for journal, spend, transfer, payment, payroll sources | Integration (per source) |
| F-07-T04 | Reason capture: `override_reason` and `override_by` on the JE; required to post past a WARN | BE | T03 | Posting without a reason past a WARN → 422 | Unit |
| F-07-T05 | Concurrency safety: `select_for_update` on the bank account row during the check+post | BE | T03 | Two concurrent spends cannot both pass a BLOCK | Concurrency test |
| F-07-T06 | Remedy suggestion service: proposes a transfer from the funded account or a Shareholder-loan entry with the shortfall amount | BE | T02, F-06 | Teardown scenario suggests "Cr 2900 Shareholder Loan 994.17" | Unit |
| F-07-T07 | Inline warning/block panel component (design system) with remedy buttons and reason field; used by spend, transfer, journal and payment forms | FE | T03, A-10 | Panel renders in all four forms | Vitest + Playwright |
| F-07-T08 | Policy settings UI in Banking settings (per account type, with an explanation) | FE | T01 | Changing to BLOCK takes effect on the next post | Playwright |
| F-07-T09 | BS presentation hook: flag overdrawn asset bank accounts for K-02 reclassification | BE | T02 | K-02 receives the overdrawn list | Integration |
| F-07-T10 | Exceptions rule registration `NEG_CASH` (rule body in K-09) | BE | K-09 | Rule listed in the catalogue | Unit |
| F-07-T11 | Teardown fixture: two journals crediting Petty Cash (417.22 on 3 Jun, 576.95 on 15 Jun) → blocked for a non-adviser and warned for an adviser | QA | T03 | `gap-27` and `gap-33` scenario green | E2E |
| F-07-T12 | i18n, audit, docs "Why Numo9 stops negative cash" | DOC | T07 | Merged | Review |

- **Deliverable acceptance:** the Petty Cash −994.17 scenario is caught at entry and by the exceptions engine.
- **Testing:** unit, property (running min), concurrency, E2E fixture.
- **Risks:**
  - Performance of the running-min check on large accounts. Mitigation: daily balance snapshot table plus delta.
  - User fatigue. Mitigation: WARN, not BLOCK, for bank accounts.

### 6.5 Tax Engine — core (Component G)

### G-01 · Tax codes & rates
- **Branch:** `feature/G-01-tax-codes-rates`
- **Objective:** a correct, effective-dated Canadian sales-tax table that the whole system calculates from.
- **Current behaviour:** C-01 created separate control accounts (GST/HST payable, ITC receivable, PST payable, QST payable, QST ITR). No tax codes exist.
- **Expected behaviour (better than Xero):** Xero has 36 flat codes, expired rates selectable forever, no zero-rated vs exempt split, no partial ITC, and every account defaulting to Exempt. Numo9 has:
  - `TaxComponent` rows (GST 5 %, HST 13/14/15 %, PST BC 7 / MB RST 7 / SK 6, QST 9.975 %), each effective-dated and with a recoverable flag.
  - `TaxCode` = a group of components with a type: TAXABLE, ZERO_RATED, EXEMPT or OUT_OF_SCOPE.
  - A side: SALES or PURCHASE (separate lists).
  - Partial ITC/ITR % per code or per account (e.g. Meals & entertainment 50 %).
  - Rates are hidden and unselectable after their end date.
  - Expense accounts default to the home-province purchase rate, not Exempt.
  - A rate history view.
  - Seed data covers every province and territory.
- **Gap #s closed:** 7, 8, 45 (with G-02 and C-01).
- **Business rules:**
  - Calculation is per line, rounded half-up to the cent per component; a document-level rounding option is configurable (default per line).
  - Tax-inclusive amounts are back-calculated per component with the residual cent assigned to the largest component.
  - The non-recoverable portion (PST, restricted ITC %) is added to the expense line.
  - A code can't change components retroactively; a new effective-dated version is created instead.
  - Codes used on posted lines can't be deleted, only archived.
- **Edge cases:**
  - A document dated on a rate change day (NS 15 % → 14 % on 1 Apr 2025).
  - A tax-inclusive 0.01 line.
  - 50 % ITC on HST 13 % of 10.01.
  - A QC purchase where GST is recoverable and QST is recoverable via ITR.
  - BC PST is non-recoverable.
- **UI/UX:**
  - Tax codes page (inside the G-06 settings hub) with Sales / Purchases tabs, type badges (Taxable, Zero-rated, Exempt, Out of scope), an effective-date timeline per code and a "Show expired" toggle.
  - Code editor with a component builder and live example ("100.00 → GST 5.00 + PST 7.00 = 112.00; recoverable 5.00").
- **Dependencies:** C-01, A-05.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-01-T01 | Wireframes: tax code list with tabs/badges/timeline, code editor with live example | UX | — | Reviewed | Design review |
| G-01-T02 | `TaxAuthority` (CRA, RQ, BC, MB, SK) and `TaxComponent` (authority, name, rate numeric(7,4), effective_from, effective_to, recoverable, control_account_sales FK, control_account_purchase FK) models | DB | C-01 | Migration; overlapping effective ranges for the same component rejected | Unit |
| G-01-T03 | `TaxCode` (name, code, side, type, province, active range) and `TaxCodeComponent` (component, recoverable_pct override) models | DB | T02 | Sales code with a purchase-only component rejected | Unit |
| G-01-T04 | Seed migration with all 2026 provinces/territories plus historical rows (NS 15 % to 31 Mar 2025, MB RST 8 % to 30 Jun 2019), both sides, ZERO_RATED / EXEMPT / OUT_OF_SCOPE codes | DB | T03 | Seed loads; 13 jurisdictions × 2 sides present | Fixture test |
| G-01-T05 | Partial-recovery setting: `itc_restriction_pct` on Account and on TaxCode; resolution order line > account > code | DB/BE | T03, C-01 | Meals account 50 % resolves for an HST line | Unit |
| G-01-T06 | `TaxCalculator` service (Decimal, ROUND_HALF_UP): exclusive/inclusive, per-component amounts, recoverable vs non-recoverable split, residual-cent rule | BE | T03, T05 | Every provincial combination to the cent on 2026 fixtures | Unit (matrix) + property (incl → excl → incl round-trip) |
| G-01-T07 | Posting mapper: tax lines to the right control accounts (GST/HST payable, ITC receivable, PST payable, QST payable, QST ITR); non-recoverable added to the expense line | BE | T06, C-02 | 50 % ITC posts half the tax to expense, half to ITC receivable | Integration |
| G-01-T08 | Effective-date resolver: `codes_available(side, date, org)` returns only active codes; expired codes raise `TaxCodeExpired` on validation | BE | T03 | MB RST 8 % not offered and rejected on a 2026 document | Unit |
| G-01-T09 | Default purchase code per expense account = home-province purchase code (from A-05 province); migration helper for the CoA template | BE | T04, A-05 | New ON org: expense accounts default to "HST 13 % on purchases" | Unit |
| G-01-T10 | Versioning: editing a code's components creates a new version effective from a date; posted lines keep the old version FK | BE | T03 | Old documents recalc unchanged after edit | Unit |
| G-01-T11 | API `/api/v1/tax/components`, `/api/v1/tax/codes` (list filtered by side/date, CRUD, archive, versions); feature key `tax.core` read on all packages, edit permission `tax.manage` | API | T03–T10 | Sweep passes; sales picker endpoint never returns purchase codes | API |
| G-01-T12 | Tax code list UI: tabs, type badges, effective timeline, "Show expired" toggle, usage count | FE | T11 | Expired codes hidden by default | Playwright |
| G-01-T13 | Code editor with component builder, recoverable % input, live calculation example, effective-date picker | FE | T11 | Example matches API calculation | Vitest |
| G-01-T14 | Shared `TaxCodePicker` component for the design system (side + date + account aware) used by D-01/E-02/F-01 | FE | T11, A-10 | Picker shows type badges; sales mode excludes purchase codes | Vitest |
| G-01-T15 | Compliance fixture set `tests/fixtures/compliance/sales_tax_2026.yaml` (provinces × types × incl/excl × partial ITC) | QA | T06 | 100 % pass | pytest |
| G-01-T16 | Audit hooks (code/component edits attributed to a user; never "System Generated" without a job id), i18n en/fr names | BE | T10 | Edit shows user and old/new rate | Unit |
| G-01-T17 | Gap tests `gap-07`, `gap-08`, `gap-45` | QA | T14 | Green | Playwright |

- **Deliverable acceptance:**
  - Every provincial combination computes to the cent.
  - MB RST 8 % (pre-2019) is unselectable in 2026.
  - A 50 % ITC posts half to expense.
- **Testing:** unit matrix, property, integration posting, compliance fixtures, gap tests.
- **Risks:**
  - Rounding disputes. Mitigation: per-line default plus a documented option.
  - Seed errors. Mitigation: fixture cross-checked against CRA published rates (confirmed by the client).

### G-02 · Place-of-supply defaulting
- **Branch:** `feature/G-02-place-of-supply`
- **Objective:** pick the right tax code automatically from the contact's province and the organisation's registrations.
- **Current behaviour:** after G-01, codes exist but the user picks them manually on every line (the Xero behaviour).
- **Expected behaviour (better than Xero):** a resolver picks the default sales code per line:
  - Ship-to province, else bill-to province, else the contact's default.
  - Applies the organisation's registrations: GST/HST always; PST if registered in BC/MB/SK; QST if registered in QC.
  - Outside Canada → zero-rated export.
  - Item/account overrides apply (exempt services, zero-rated basic groceries).
  - The user can still override per line; the override is shown with a "changed from default" dot.
  - A warning appears when selling taxable goods into a PST province without a PST registration.
  - Purchases default from the account's code, then the supplier's province.
- **Gap #s closed:** 9, 45.
- **Business rules:**
  - Precedence: line override > item tax setting > contact explicit default > place-of-supply resolver > account default.
  - The resolver is a pure function of (side, date, org registrations, contact address, item/account, ship-to) and is fully unit-testable.
  - It never reads "last used" (the Xero anti-pattern).
- **Edge cases:**
  - A contact with no province (fallback to the org province plus a missing-data hint).
  - QC customer when the org is not QST-registered (GST only plus info).
  - US customer with a Canadian ship-to.
  - A deregistered registration (G-03b) after its end date → out-of-scope.
  - A services-vs-goods distinction is noted as simplified (documented assumption).
- **UI/UX:**
  - A small "auto" chip in the tax cell with a tooltip explaining why (e.g. "Ontario customer → HST 13 %").
  - The override dot can be reset to the default.
  - The PST warning appears inline above the totals.
- **Dependencies:** G-01, B-01, A-05, G-06 (registrations).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-02-T01 | Decision table document (province × registration × side × item type → code), reviewed by the client's accountant | DOC | G-01 | Table signed off | Review |
| G-02-T02 | `TaxResolver.resolve(context)` pure function implementing precedence and the decision table, returning code plus explanation string key | BE | T01, G-01 | ON → HST 13 %; US → zero-rated; QC registered → GST+QST | Unit (table-driven) |
| G-02-T03 | Context builder from document header/line (contact addresses B-01, ship-to, item H-01 hook, account default) | BE | T02 | Missing province falls back with a `missing_province` flag | Unit |
| G-02-T04 | PST-registration warning generator (taxable sale into BC/MB/SK while unregistered) | BE | T02 | BC customer, not PST-registered → warning code returned | Unit |
| G-02-T05 | Registration-end awareness: after a G-03b stop date, sales default to OUT_OF_SCOPE (configurable) | BE | T02, G-03b | 15 Jul document after a 30 Jun stop → out-of-scope plus warning | Unit |
| G-02-T06 | API `POST /api/v1/tax/resolve` (batch lines) used by editors; response includes explanation keys | API | T02–T05 | 50 lines resolved < 100 ms | API + perf |
| G-02-T07 | Editor integration: tax cell auto-fills, "auto" chip, tooltip reason, override dot, reset-to-default action | FE | T06, D-01 | Changing the contact re-resolves non-overridden lines only | Playwright |
| G-02-T08 | Inline PST/missing-province warnings in sales and purchase editors | FE | T04, T07 | Warning appears without blocking save | Playwright |
| G-02-T09 | Purchase-side resolution (account default then supplier province) for bills and spend money | BE/FE | T02 | Expense account with an HST default and an ON supplier → HST 13 % purchase code | Integration |
| G-02-T10 | i18n of explanation strings en/fr; gap tests `gap-09`, `gap-45` | QA | T07 | Green | Playwright |

- **Deliverable acceptance:**
  - An Ontario customer gets HST 13 %.
  - A US customer gets zero-rated.
  - The PST warning appears.
- **Testing:** table-driven unit tests, integration in editors, functional.
- **Risks:** complex place-of-supply rules for services and intangibles. Mitigation: documented simplified rule plus the override, with the client's accountant sign-off.

### G-03 · GST/HST return worksheet
- **Branch:** `feature/G-03-gst-hst-return`
- **Objective:** produce a GST/HST return (lines 101–115) per filing period, mark it filed, and lock the period.
- **Current behaviour:** Xero had no GST/HST return on the plan inspected. In Numo9 before this deliverable, tax lines are posted (G-01) but no return exists.
- **Expected behaviour (better than Xero):** a return worksheet per period from the G-03a engine:
  - Line 101 (sales and other revenue, incl. zero-rated, excl. exempt), 103 (GST/HST collected), 104 (adjustments), 105 (total), 106 (ITCs), 107 (adjustments), 108 (total ITCs and adjustments), 109 (net tax), 110 (instalments paid), 111 (rebates), 112, 113 A/B/C, 114 (refund claimed), 115 (amount owing).
  - A quick-method flag with remittance rates as data.
  - Drill-down from every line to source documents.
  - A preparer → reviewer workflow (Draft → Reviewed → Filed).
  - Mark filed with CRA confirmation number and date; the period locks for Tax.
  - Late adjustments: a back-dated document into a filed period is refused unless flagged; when flagged, the tax difference posts into the next open period's line 104/107.
  - Printable PDF and a CSV of line values for entry into CRA My Business Account / NETFILE.
- **Gap #s closed:** 54.
- **Business rules:**
  - Amounts come from posted tax lines with tax-point date in the period, on the organisation's tax basis (accrual/cash from G-06).
  - Line 105 equals the tax report (G-05) collected total.
  - A filed return is immutable; a correction is an amended return version.
  - Instalments come from G-09 records (Phase 4) or a manual entry until then.
- **Edge cases:**
  - Invoice revision across periods (D-03b): the revision delta goes to the revision's period.
  - Cash-basis org.
  - Out-of-cycle stub period.
  - Zero-activity period (nil return).
  - Negative net tax (refund).
  - Quick method with a 1 % credit on the first 30,000.
- **UI/UX:**
  - The worksheet looks like a clean form: line numbers left, amounts right, each amount is a link to its drill-down.
  - A "What changed since last view" banner.
  - A status stepper (Draft → Reviewed → Filed).
  - A large "Mark as filed" dialog asking for the confirmation number.
  - Filed periods show a lock icon everywhere.
- **Dependencies:** G-01, G-03a, G-05, G-06, A-05.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-03-T01 | Line-mapping specification (which tax types/components feed lines 101–115), signed off by the client | DOC | G-01 | Signed off | Review |
| G-03-T02 | `TaxReturn` (registration, period FK, version, status DRAFT/REVIEWED/FILED/AMENDED, method REGULAR/QUICK, line values JSON, filed_at, confirmation_no, prepared_by, reviewed_by) | DB | G-03a | Migration; one non-amended FILED return per period | Unit |
| G-03-T03 | Line calculator (regular method) from posted tax lines by tax-point date and basis | BE | T01, T02, G-05 | Line 103 = sum of GST/HST collected; 109 = 105 − 108 | Unit + fixtures |
| G-03-T04 | Quick-method calculator with remittance rates as effective-dated data and a 1 % credit rule | BE | T03 | Quick-method fixture matches the worked example | Unit |
| G-03-T05 | Drill-down service: each line returns its source document list | BE | T03 | Drill-down sum = line value | Integration |
| G-03-T06 | Workflow: prepare → review (reviewer ≠ preparer, A-03) → file with confirmation number; audit entries | BE | T02, A-03 | Self-review refused | Unit |
| G-03-T07 | On FILED: set the Tax lock for the period end (A-05) and the period status FILED in G-03a | BE | T06, A-05 | Posting a GST document dated inside → refused naming the lock | Integration |
| G-03-T08 | Late-adjustment flow: a document with `late_adjustment=true` in a filed period posts its tax delta to the next open period's line 104/107 and is listed on that return | BE | T07 | Back-dated 113.00 tax appears on the next return's line 104 | Integration |
| G-03-T09 | Amendment: create version n+1 from a filed return with a reason; the original remains viewable | BE | T06 | Two versions visible; latest marked current | Unit |
| G-03-T10 | API `/api/v1/tax/returns` (generate, recalc, review, file, amend, pdf, csv); feature key `tax.returns`; permissions | API | T03–T09 | Sweep passes | API |
| G-03-T11 | Worksheet UI: form layout, drill-down drawer, status stepper, changed-since banner | FE | T10 | Drill-down opens the document list in a drawer | Playwright |
| G-03-T12 | Mark-as-filed dialog, lock indicators, amend action | FE | T10 | Lock icon appears on period in all lists | Playwright |
| G-03-T13 | PDF (WeasyPrint, Letter, inch margins) and CSV export of line values | BE | T10 | PDF lines = screen; snapshot test | Snapshot |
| G-03-T14 | Compliance fixtures: regular, quick, nil, refund, stub period, cash basis, revision across periods | QA | T03–T08 | 100 % pass | pytest |
| G-03-T15 | Gap test `gap-54` (return exists on every Tax package) and entitlement check | QA | T11 | Green | Playwright |
| G-03-T16 | i18n en/fr (CRA French line labels), docs | DOC | T11 | Lint passes | Review |

- **Deliverable acceptance:**
  - Line 105 equals the tax report.
  - A filed period refuses back-dated documents without the late-adjustment flag.
- **Testing:** fixtures, integration, functional, security (reviewer ≠ preparer).
- **Risks:** misunderstanding of the line mapping. Mitigation: T01 sign-off plus fixtures from the client's real returns.

### G-03a · Filing-cycle engine (switch & out-of-cycle)
- **Branch:** `feature/G-03a-filing-cycles`
- **Objective:** generate GST/HST and QST reporting periods from effective-dated frequencies, support switching, custom stub periods, instalments and due dates, and never produce gaps or overlaps.
- **Current behaviour:** no periods exist. Xero has one fixed tax period setting ("Annually").
- **Expected behaviour (better than Xero):**
  - Each `TaxRegistration` (G-06) has a sequence of `FilingCycle` rows: frequency MONTHLY/QUARTERLY/ANNUAL, effective_from, fiscal anchor, CRA approval reference/date and note.
  - The generator produces `FilingPeriod` rows (start, end, due_date, payment_due_date, status OPEN/CLOSED/FILED/PAID).
  - Switching frequency regenerates only unfiled future periods from the effective date.
  - Custom out-of-cycle periods (e.g. 1 Jan–15 Mar) can be inserted, and subsequent regular periods realign from the next day.
  - Annual filers get quarterly instalment dates.
  - Due dates: one month after period end for monthly/quarterly; three months for annual (or 15 June for individuals with business income, as data).
  - Full change history.
  - A timeline UI.
- **Gap #s closed:** beyond Xero (client decision 11); supports 54.
- **Business rules:**
  - Periods for a registration cover every day from the registration start to the stop date (or open-ended) exactly once.
  - Filed periods are immutable and never regenerated.
  - A switch's effective date must not fall inside a filed period, and if it falls inside an open period, that period is split.
  - Switching is CRA-approved per the accountant's input (the reference is stored); the system warns when the effective date is not a fiscal-year start.
  - Due dates falling on a weekend or holiday roll per CRA practice (next business day), using a holiday calendar as data.
- **Edge cases:**
  - Switch on the 1st of the month vs mid-month.
  - Annual → quarterly mid-year creating a stub.
  - Two switches in the same year.
  - A switch back.
  - Fiscal year not on a calendar boundary (FYE 31 March).
  - Leap year.
  - Registration starting mid-month.
  - Deleting a custom period (allowed only if unfiled and with no tax postings locked).
- **UI/UX:**
  - Horizontal timeline per registration showing coloured period blocks (filed green, open blue, due-soon amber, overdue red) and markers at switch points.
  - "Change filing frequency" wizard (frequency → effective date → CRA approval ref → preview of resulting periods with diffs → confirm).
  - "Add out-of-cycle period" dialog with an overlap preview.
  - Every change is previewed before it is saved.
- **Dependencies:** G-06 (registrations; the model can be built first here and G-06 builds the page), A-05 (FYE), A-08 (jobs), O-04 hook later.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-03a-T01 | Rules specification: frequencies, due-date rules, instalment rules, holiday roll, switch constraints (signed off by the client) | DOC | — | Signed off | Review |
| G-03a-T02 | Wireframes: registration timeline, change-frequency wizard with preview diff, out-of-cycle dialog | UX | T01 | Reviewed | Design review |
| G-03a-T03 | `TaxRegistration` model (type GST_HST/QST, number, start_date, stop_date, status) if not already present from G-06 | DB | A-05 | Migration | Unit |
| G-03a-T04 | `FilingCycle` model (registration, frequency, effective_from, approval_ref, approval_date, note, created_by) | DB | T03 | Unique (registration, effective_from) | Unit |
| G-03a-T05 | `FilingPeriod` model (registration, start, end, kind REGULAR/CUSTOM/STUB, sequence_no, due_date, payment_due_date, status) with an exclusion constraint (PostgreSQL `daterange` + GiST) preventing overlaps | DB | T03 | Overlapping insert rejected by DB | Unit |
| G-03a-T06 | `HolidayCalendar` data (federal and provincial statutory holidays by year) and a business-day roll helper | DB/BE | — | 2026 holidays loaded; roll of a Saturday → Monday | Unit |
| G-03a-T07 | Pure period generator: (cycles, fiscal anchor, from, to, custom periods) → list of periods (dateutil.rrule) | BE | T04 | Quarterly FYE 31 Dec yields Jan–Mar, Apr–Jun… | Unit |
| G-03a-T08 | Due-date calculator (monthly/quarterly +1 month end; annual +3 months; individual 15 Jun rule as data) with holiday roll | BE | T06, T07 | Q3 2026 due 31 Oct 2026 (rolled if weekend) | Unit |
| G-03a-T09 | Instalment schedule for annual filers (quarter-end-month+1 dates) with amount placeholder for G-09 | BE | T08 | Annual filer gets 4 instalment dates | Unit |
| G-03a-T10 | Regeneration service: deletes/recreates only unfiled periods after the effective date, splits an open period crossing the effective date, keeps tax postings re-assigned by date | BE | T07, T05 | Quarterly → monthly from 1 Jul keeps filed Q1/Q2 untouched | Integration |
| G-03a-T11 | Switch validation: effective date not inside a filed period; warning if not a fiscal-year start; approval_ref required for a mid-year switch | BE | T10 | Mid-year switch without a ref → 422 | Unit |
| G-03a-T12 | Custom/stub period insertion: validates no overlap with filed periods, realigns subsequent regular periods from end+1 | BE | T10 | 1 Jan–15 Mar stub then quarters from 16 Mar accepted | Integration |
| G-03a-T13 | Property test (Hypothesis): random switch/custom sequences over 3 years → no gaps, no overlaps, filed periods unchanged, every document date maps to exactly one period | QA | T10–T12 | 1,000 examples pass | Property |
| G-03a-T14 | Document → period resolver `period_for(registration, date)` used by tax reports/returns | BE | T05 | Every document falls into exactly one period | Unit |
| G-03a-T15 | Preview endpoint: proposed change → diff (removed/added/changed periods) without writing | BE/API | T10, T12 | Preview diff = actual result after confirm | Integration |
| G-03a-T16 | API `/api/v1/tax/registrations/{id}/cycles`, `/periods`, `/custom-periods`, `/preview`; permissions `tax.manage`; audit | API | T10–T15 | Sweep passes | API |
| G-03a-T17 | Nightly job: rolls forward 24 months of periods, recomputes due-soon/overdue status, emits events for O-04 calendar and notifications | OPS/BE | T10, A-08 | Job idempotent across 2 workers | Integration |
| G-03a-T18 | Timeline UI component (period blocks, status colours, switch markers, hover cards with due dates) | FE | T16 | Timeline matches API periods | Vitest + Playwright |
| G-03a-T19 | Change-frequency wizard with preview diff | FE | T15, T18 | Confirm creates exactly the previewed periods | Playwright |
| G-03a-T20 | Out-of-cycle period dialog with overlap preview and realignment explanation | FE | T15 | Stub scenario completed through UI | Playwright |
| G-03a-T21 | Cycle change history panel (who, when, approval ref) | FE | T16 | History shows all switches | Playwright |
| G-03a-T22 | Compliance fixtures: switch Q→M 1 Jul; A→Q mid-year stub; FYE 31 Mar; leap year; two switches in a year | QA | T13 | 100 % pass | pytest |
| G-03a-T23 | i18n, docs "Changing your GST/HST filing frequency" | DOC | T19 | Merged | Review |

- **Deliverable acceptance:**
  - Quarterly → monthly from 1 Jul keeps Q1/Q2.
  - A 1 Jan–15 Mar stub plus quarters is accepted.
  - There are no gaps or overlaps (property test).
- **Testing:** pure-function unit tests, property tests, DB exclusion constraint, integration, E2E.
- **Risks:** the CRA rule nuances. Mitigation: rules as data plus client sign-off; the accountant confirms approval dates.

### G-03b · Stop & restart filing
- **Branch:** `feature/G-03b-stop-restart-filing`
- **Objective:** stop a registration at an end date and restart it later, without corrupting history.
- **Current behaviour:** after G-03a, periods roll forward forever.
- **Expected behaviour:**
  - "Stop filing" (reason: deregistration / small-supplier / suspension / other; end date) truncates the open period at the end date and deletes later unfiled periods.
  - It blocks generation after that date.
  - Sales defaults flip to OUT_OF_SCOPE after that date (configurable, via G-02).
  - A document dated after the stop with a GST code raises a warning.
  - "Restart" takes a date and a frequency, creates a new cycle and regenerates periods.
  - Both actions are audited with a reason.
  - The timeline shows a gap band labelled "Not registered".
- **Gap #s closed:** beyond Xero (client decision 12); 44 (attribution of registration status changes).
- **Business rules:**
  - Stop date ≥ last filed period end.
  - A final return covers up to the stop date.
  - Restart date > stop date.
  - Registration status changes are always attributed to a user (never "System Generated").
- **Edge cases:**
  - Stop with tax postings already dated after the stop (listed for review).
  - Restart within the same month.
  - Stopping QST but not GST.
  - Stopping and restarting with the same frequency.
- **UI/UX:**
  - "Stop filing" danger-zone card with an impact preview ("Periods after 30 Jun 2026 will be removed: Jul–Dec (6). 3 documents dated after 30 Jun use GST codes → review").
  - Restart wizard reusing the G-03a preview.
- **Dependencies:** G-03a, G-02, G-06.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-03b-T01 | Wireframes: danger-zone stop card with impact preview, restart wizard, timeline gap band | UX | G-03a-T02 | Reviewed | Design review |
| G-03b-T02 | `RegistrationStatusEvent` model (registration, action STOP/RESTART, date, reason_code, reason_text, user) | DB | G-03a | Migration | Unit |
| G-03b-T03 | Stop service: validate date, truncate the open period, delete later unfiled periods, set stop_date, status INACTIVE, record event | BE | T02, G-03a-T10 | After stop 30 Jun no July period exists | Integration |
| G-03b-T04 | Generator guard: no periods after stop_date until a restart event exists | BE | T03 | Nightly job does not create July | Integration |
| G-03b-T05 | Post-stop document checker: lists documents after the stop date with tax codes of that registration; returns a warning on new documents | BE | T03 | 15 Jul GST document → warning `REGISTRATION_STOPPED` | Unit |
| G-03b-T06 | Configurable default flip (org setting) wired into the G-02 resolver | BE | T03, G-02 | New sales default to out-of-scope after the stop | Unit |
| G-03b-T07 | Restart service: create a cycle with frequency from the restart date, status ACTIVE, regenerate periods, record event | BE | T03 | Restart on 1 Jan recreates periods | Integration |
| G-03b-T08 | Impact preview endpoint for stop and restart | API | T03, T07 | Preview = result | Integration |
| G-03b-T09 | API endpoints `/stop`, `/restart`, `/events`; permission `tax.manage`; audit | API | T03–T08 | Sweep passes | API |
| G-03b-T10 | Danger-zone stop UI with a typed confirmation of the registration number, and the restart wizard | FE | T09 | Stop requires typing the registration number | Playwright |
| G-03b-T11 | Timeline "Not registered" gap band and event markers | FE | T09, G-03a-T18 | Band displayed between stop and restart | Vitest |
| G-03b-T12 | Inline editor warning for post-stop documents | FE | T05 | Warning visible on a 15 Jul invoice | Playwright |
| G-03b-T13 | Fixtures and property test extension (stop/restart sequences keep no-overlap invariants) | QA | T07 | Pass | Property |
| G-03b-T14 | i18n, docs | DOC | T10 | Merged | Review |

- **Deliverable acceptance:**
  - After a stop on 30 Jun there is no July period.
  - A 15 Jul GST document warns.
  - A restart on 1 Jan recreates periods.
- **Testing:** integration, property, functional.
- **Risks:** accidental stop. Mitigation: typed confirmation, preview, and a restart that restores the periods.

### G-05 · Tax reports
- **Branch:** `feature/G-05-tax-reports`
- **Objective:** tax reports that always tie to the ledger.
- **Current behaviour:** no tax report exists (the Xero gap: "Taxes and balances" contains none).
- **Expected behaviour (better than Xero):** on every package with Tax:
  - Tax summary by code/component for any range or a filing period.
  - Tax detail by document.
  - Tax audit report (every line with code, rate, tax, user, posting date; flags for overrides and late adjustments).
  - ITC/ITR detail including restricted portions.
  - Tax-to-GL tie-out (each control account's GL movement vs report totals, difference = 0 or the offending journals named).
  - Basis follows G-06 (accrual/cash) with an explicit override per report.
- **Gap #s closed:** 54, 49.
- **Business rules:**
  - Reports read posted tax lines only and use the current invoice revision (D-03b).
  - Manual journals hitting tax control accounts appear in a "Journals affecting tax accounts" section (an exception).
  - Exports equal the screen.
- **Edge cases:**
  - Journals coded to the GST payable account directly.
  - Restricted ITC.
  - Cash basis with partial payments (proportional tax).
  - Revision delta across periods.
- **UI/UX:**
  - Report runner from K-01 with tax presets (current period, last filed period).
  - A tie-out card at the top (green tick "Ties to GL" or red with the difference and a link).
  - Every figure drills down.
- **Dependencies:** G-01, G-03a, K-01, D-03b.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-05-T01 | Report specs (columns, filters, grouping) for summary, detail, audit, ITC/ITR detail, tie-out | DOC | — | Reviewed | Review |
| G-05-T02 | Tax line query layer (SQL view/materialised view of posted tax lines with code, component, period, basis amounts, current revision only) | DB/BE | G-01, D-03b | View returns lines for the fixture | Integration |
| G-05-T03 | Cash-basis allocator: tax recognised proportionally to payments in range | BE | T02 | 50 % paid invoice reports 50 % of its tax under cash basis | Unit |
| G-05-T04 | Tax summary by code/component report definition in K-01 | BE | T02, K-01 | Totals per component = sum of lines | Unit |
| G-05-T05 | Tax detail by document report | BE | T02 | Drill-down to document | Integration |
| G-05-T06 | Tax audit report with flags (override, late adjustment, journal source, restricted ITC) | BE | T02 | Flags present on the fixture | Unit |
| G-05-T07 | ITC/ITR detail incl. restricted portion and non-recoverable amounts | BE | T02 | Meals 50 % shows recoverable/non-recoverable | Unit |
| G-05-T08 | Tax-to-GL tie-out: control account movement vs report total per component; lists journals hitting tax accounts directly | BE | T04 | Fixture difference 0.00; injected journal named | Integration |
| G-05-T09 | API registrations in the K-01 catalogue; feature key `tax.reports` available on every Tax package | API | T04–T08 | Entitlement test: Tax package sees it; non-Tax sees the explicit gate | API |
| G-05-T10 | UI: report presets, tie-out status card, drill-down, flags as chips | FE | T09 | Card green on the fixture | Playwright |
| G-05-T11 | Exports PDF/XLSX/CSV equal to screen | BE | T09 | Snapshot equal | Snapshot |
| G-05-T12 | Gap tests `gap-54`, `gap-49`; i18n | QA | T10 | Green | Playwright |

- **Deliverable acceptance:** totals tie to the GL control accounts.
- **Testing:** unit, integration tie-out, snapshot exports.
- **Risks:** performance on big ledgers. Mitigation: materialised view refresh on post plus indexes (S-06).

### G-06 · Tax settings on one page
- **Branch:** `feature/G-06-tax-settings-hub`
- **Objective:** one page for every tax setting, with history.
- **Current behaviour:** A-05 stores the BN and program accounts (RT/RP/RC) and the QST number. Xero splits tax config across 4 pages and silently removed the GST type.
- **Expected behaviour (better than Xero):** a single "Tax registrations & settings" page with sections:
  - Business number and program accounts.
  - Registrations: GST/HST, QST, PST BC/MB/SK, each with number, start date, status, filing cycle summary (link to the G-03a timeline) and stop/restart.
  - Tax basis (accrual/cash), which is also the default for reports, with an explicit per-report override (closes the "two pages disagree" gap).
  - Default codes: sales and purchase per account type, rounding mode.
  - Quick-method election.
  - Restricted-ITC accounts list.
  - A change history panel with user attribution and old/new values.
  - Tax-related links elsewhere deep-link here; no other page edits tax settings.
- **Gap #s closed:** 3, 44, 49, 39.
- **Business rules:**
  - The BN is validated (9 digits plus a Luhn-style check where applicable; program account format `123456789RT0001`); the QST number format is `1234567890TQ0001`.
  - Changing the tax basis mid-year warns and requires a reason.
  - Every change is audited and attributed.
  - Tax settings exist in exactly one place (a CI check scans routes/settings forms).
- **Edge cases:**
  - Org with no registrations (non-registrant small supplier): tax codes default to out-of-scope and the return is hidden.
  - Multiple PST registrations.
  - Missing BN while GST-registered (exceptions engine flag plus an inline hint).
- **UI/UX:**
  - Sectioned single page with a left anchor nav, inline edit per card, status badges and a history drawer.
  - Deep links from Sales/Purchases/Reports settings.
  - Empty state "Not registered for GST/HST? Here's what that means" with a small-supplier explanation.
- **Dependencies:** A-05, G-01, G-03a, G-03b.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-06-T01 | Wireframes: single tax settings page with anchor nav, cards, history drawer, empty state | UX | — | Reviewed | Design review |
| G-06-T02 | `TaxSettings` model (basis, rounding_mode, quick_method, default codes per account type) one-to-one with org | DB | A-05 | Migration | Unit |
| G-06-T03 | BN / program account / QST number validators | BE | A-05 | Invalid RT format rejected with an example in the message | Unit |
| G-06-T04 | Registration CRUD service bound to G-03a/G-03b (create triggers initial cycle and periods) | BE | T02, G-03a | New GST registration creates a cycle and periods | Integration |
| G-06-T05 | Tax-basis change guard with reason, mid-year warning; basis used by K-01 as default with per-report override flag | BE | T02 | Report shows "Basis: Cash (organisation default)" label | Unit |
| G-06-T06 | Unified settings history (audit log filter on tax objects) with user attribution enforced (system jobs carry a job id) | BE | A-04 | No history row without user or job id | Unit |
| G-06-T07 | API `/api/v1/tax/settings`, `/registrations`; permission `tax.manage` | API | T02–T05 | Sweep passes | API |
| G-06-T08 | Single page UI: cards (BN and programs, registrations, basis, defaults, quick method, restricted ITC), inline edit, history drawer | FE | T07 | All tax settings editable here | Playwright |
| G-06-T09 | Deep links from module settings and from the G-03 worksheet; remove/redirect any other tax-setting entry points | FE | T08 | Every "Tax settings" link lands on the correct anchor | Playwright |
| G-06-T10 | CI check: settings registry asserts every tax setting key has exactly one editing route | QA | T08 | CI fails on a duplicate | CI |
| G-06-T11 | Gap tests `gap-03`, `gap-44`, `gap-49`, `gap-39`; i18n | QA | T08 | Green | Playwright |

- **Deliverable acceptance:** no tax setting exists on more than one page.
- **Testing:** unit validators, integration, CI uniqueness check, functional.
- **Risks:** the registration model is shared with G-03a. Mitigation: build T04 after G-03a-T03 with a shared migration owner.

### 6.6 Reporting — core (Component K)

### K-01 · Report engine
- **Branch:** `feature/K-01-report-engine`
- **Objective:** one report engine for every financial, tax and operational report.
- **Current behaviour:** no reports exist. Xero has two engines (v1/v2) with different URLs.
- **Expected behaviour (better than Xero):** a single engine of report definitions (Python classes registered in a catalogue) with:
  - Parameters: date range with presets (this/last month, quarter, financial year, MTD/QTD/YTD, custom), comparisons (N periods / prior year, with variance columns), basis (accrual/cash, defaulting to the G-06 value with an explicit override label), book selector (accounting/tax — the tax book is fully populated in K-07, Phase 2, but the selector and filter exist now), and tracking-category filter/columns.
  - Drill-down from any figure to its lines and then to its source document.
  - Layout editor: reorder/rename rows, insert text blocks and notes, cell annotations.
  - Versions: Draft / Published / Custom (saved layouts per org and per practice).
  - Exports: PDF (Letter, inch margins), XLSX, CSV and a Google-Sheets-compatible XLSX.
  - Favourites and report search (registered in A-09).
  - A report header that always prints the display name, the legal name, the period label, "Year to date — unaudited" when the period end is in the future, and "No activity in this period" hints instead of "–".
  - Settings validation that rejects a numeric-only legal name.
- **Gap #s closed:** 46, 49, 54 (one engine), 55.
- **Business rules:**
  - Reports read posted lines only (drafts excluded unless a "include drafts" debug flag is set, advisers only).
  - Every number is reproducible from the drill-down.
  - Published versions are immutable snapshots.
  - Performance budget: a 12-month P&L on a 100k-line GL in under 3 s p95.
- **Edge cases:**
  - Empty org.
  - Comparison periods before the conversion date.
  - FYE not 31 Dec.
  - Tracking hierarchy rollups.
  - Report run while postings are happening (snapshot isolation).
  - Very wide comparisons (12 columns).
- **UI/UX:**
  - Report home with search, categories, favourites, Drafts/Published/Custom tabs and descriptions toggle.
  - Runner with a sticky parameter bar (range, compare, basis chip, book switch, tracking), Update button and keyboard Enter.
  - Results table with sticky header and first column, hover drill icons, a side-drawer drill-down, a compact view toggle and inline notes.
  - Layout editor as a right-hand panel, not a separate page.
- **Dependencies:** C-02, A-05, A-10, A-09.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-01-T01 | Wireframes: report home, runner with parameter bar, drill drawer, layout editor panel, export menu, empty/no-activity states | UX | — | Reviewed | Design review |
| K-01-T02 | Report definition framework: `ReportDefinition` base (params schema, query(), rows(), totals()) and a registry with ids/slugs | BE | C-02 | Two sample reports registered | Unit |
| K-01-T03 | Parameter models: date range presets resolver (FYE-aware), comparison builder, basis resolver (G-06 default + override), book filter (`book in (both, X)`), tracking filter | BE | T02, A-05 | "Last financial year" for FYE 31 Mar resolves correctly | Unit |
| K-01-T04 | Ledger aggregation query layer: period balances by account with an index on (org, account, date, book); repeatable-read snapshot | DB/BE | T02, S-06 | 100k-line 12-month aggregation < 1 s on staging data | Perf |
| K-01-T05 | Drill-down API: figure → lines (paginated) → source document link | BE/API | T04 | Drill-down sum = figure | Integration |
| K-01-T06 | Header service: display name, legal name, period label, unaudited/YTD label, basis and book labels | BE | T03 | Future period end shows "Year to date" label | Unit |
| K-01-T07 | Legal-name validation in A-05 settings (reject numeric-only, min letters) | BE | A-05 | "1001633222" rejected with a message | Unit |
| K-01-T08 | Layout model `ReportLayout` (report id, org/practice, rows config, text blocks, notes, status DRAFT/PUBLISHED/CUSTOM, version) and published snapshot storage | DB | T02 | Published snapshot unchanged after new postings | Unit |
| K-01-T09 | Cell annotation (`ReportNote` on row/column key) | DB/BE | T08 | Note survives re-run | Unit |
| K-01-T10 | Export renderers: PDF (WeasyPrint Letter, inch margins), XLSX (openpyxl with formulas for totals), CSV | BE | T02 | Exports equal screen values (snapshot) | Snapshot |
| K-01-T11 | API `/api/v1/reports` (catalogue, run, drill, layouts, publish, export, favourites); feature keys per report | API | T02–T10 | Sweep passes; gated report returns 402 with product | API |
| K-01-T12 | Report home UI: search, categories, favourites, tabs Drafts/Published/Custom | FE | T11 | Search "tax" finds tax reports | Playwright |
| K-01-T13 | Runner UI: sticky param bar, comparisons, basis chip, book switch, tracking filter, result table (virtualised for long reports) | FE | T11 | 12-column comparison renders without layout break | Playwright |
| K-01-T14 | Drill-down drawer with lines table and "open document" | FE | T05 | 2 clicks from P&L figure to invoice | Playwright |
| K-01-T15 | Layout editor panel (drag rows, rename, text blocks, notes) and Save as Draft/Publish/Custom | FE | T08, T09 | Published version listed and immutable | Playwright |
| K-01-T16 | "No activity in this period" and zero-rendering rules in the design-system table component | FE | A-10 | Empty P&L shows hint, never "–" | Vitest |
| K-01-T17 | Performance test: k6 run on 100k-line fixture org | QA | T13 | p95 < 3 s | k6 |
| K-01-T18 | Register reports in global search (A-09) and quick-open | FE | T12 | "balance sheet" search opens runner | Playwright |
| K-01-T19 | Gap tests `gap-46`, `gap-49`, `gap-54`, `gap-55`; i18n | QA | T13 | Green | Playwright |

- **Deliverable acceptance:**
  - A 12-month report on a 100k-line GL renders in under 3 s p95.
  - A numeric-only legal name is rejected.
- **Testing:** unit, integration, perf, snapshot exports, functional.
- **Risks:**
  - Slow aggregations. Mitigation: daily balance table plus a read replica (S-06).
  - The layout editor grows in scope. Mitigation: limit to rows, text and notes.

### K-02 · Core financial statements (accounting book)
- **Branch:** `feature/K-02-core-statements`
- **Objective:** GAAP-correct core statements built on K-01.
- **Current behaviour:** the engine exists (K-01) with no statements.
- **Expected behaviour (better than Xero):**
  - **P&L:** revenue, COGS, gross profit, operating expenses and net income.
  - **Balance Sheet:**
    - Always prints the Assets, Liabilities and Equity sections, even when empty.
    - Overdrawn bank/cash accounts are reclassified to current liabilities with a note (F-07 hook).
    - Contra accounts (accumulated amortisation) sit directly under their asset with consistent naming.
    - Current-year earnings are computed.
  - **Cash Flow:** both indirect (from net income with working-capital changes) and direct methods.
  - **Trial Balance:** sorted by account code, with opening, movement and closing debit/credit columns and totals.
  - **GL detail.**
  - **Journal report:** order by id or date, ascending/descending control.
  - **Movements in Equity / Statement of retained earnings with comparative.**
  - **Account transactions.**
- **Gap #s closed:** 54, 56, 57, 58, 55.
- **Business rules:**
  - BS must balance (assets = liabilities + equity) or the report shows a red integrity banner and alerts S-04.
  - P&L net income = change in retained earnings + current-year earnings.
  - Cash flow cash definition is configurable (bank + cash + petty cash by default; closes gap 60 with K-05).
  - Account classification comes from C-01 types and sub-types.
- **Edge cases:**
  - An account changes type mid-year (reclassify the history view).
  - Mid-year conversion with opening balances.
  - FX accounts (R, Phase 2) as placeholder.
  - Negative equity.
  - Accounts with zero balance (toggle).
- **UI/UX:**
  - Statements open with a sensible default: BS defaults to today, not end of last FY (a Xero gap).
  - Section headings are always visible, a GAAP note on reclassified overdrafts, "Show account codes" toggle and drill on every figure.
  - The TB has a code-sorted default with sort controls.
- **Dependencies:** K-01, C-01, C-02, F-07.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-02-T01 | Statement presentation spec (ASPE-style sections, sub-totals, contra placement, overdraft reclassification note) reviewed by the client | DOC | — | Signed off | Review |
| K-02-T02 | P&L definition: sections by account type, gross profit, operating income, net income; comparatives | BE | K-01 | NI on fixture = expected | Unit |
| K-02-T03 | Balance Sheet definition: A/L/E always printed, current-year earnings line, contra accounts under parents | BE | K-01, C-01 | Empty org prints all 3 sections with 0.00 | Unit |
| K-02-T04 | Overdraft reclassification: overdrawn asset bank/cash shown in current liabilities with note | BE | T03, F-07 | Petty Cash −994.17 shows as a liability 994.17 with note | Unit |
| K-02-T05 | Integrity check: BS balances; NI = ΔRE + CYE; failure banner and S-04 event | BE | T02, T03 | Injected imbalance → banner | Unit |
| K-02-T06 | Trial Balance: sorted by code, opening/movement/closing Dr/Cr columns, totals equal | BE | K-01 | TB totals balance; first row is lowest code | Unit |
| K-02-T07 | Cash Flow indirect: NI + non-cash items + working-capital changes by account classification mapping | BE | T02, T03 | Indirect total = change in cash | Unit + fixture |
| K-02-T08 | Cash Flow direct: classify cash lines by counterpart account (customers, suppliers, payroll, tax, financing, investing) | BE | T07 | Direct total = indirect total | Unit |
| K-02-T09 | Cash definition setting (which bank types count as cash) shared with K-05 | BE | T07 | Petty cash included by default | Unit |
| K-02-T10 | GL detail and Account transactions reports with running balance | BE | K-01 | Closing = TB closing | Integration |
| K-02-T11 | Journal report with order-by and direction control | BE | K-01 | Asc/desc both correct | Unit |
| K-02-T12 | Movements in Equity / retained earnings with comparative | BE | T03 | Closing RE = BS RE | Unit |
| K-02-T13 | UI: statement-specific defaults (BS as at today), toggles (codes, zero balances), notes on reclassification | FE | T02–T12 | BS opens as at today | Playwright |
| K-02-T14 | Statement PDF templates (Letter, inch margins, legal + display name) snapshot tests | QA | T13 | Snapshots approved | Snapshot |
| K-02-T15 | Data validation script: for fixture orgs, BS balances, NI = ΔRE, TB = GL, CF = Δcash | QA | T05–T08 | Script green in CI | pytest |
| K-02-T16 | Gap tests `gap-54`, `gap-55`, `gap-56`, `gap-57`, `gap-58`; i18n | QA | T13 | Green | Playwright |

- **Deliverable acceptance:**
  - The BS balances.
  - Net income equals the change in retained earnings.
  - Every figure drills down.
- **Testing:** unit, data validation, snapshot, functional.
- **Risks:** cash-flow classification errors. Mitigation: mapping by account sub-type plus fixtures with known answers.

### K-03 · Receivables/payables reports
- **Branch:** `feature/K-03-ar-ap-reports`
- **Objective:** AR/AP aging and a control-vs-sub-ledger reconciliation.
- **Current behaviour:** invoices/bills post AR/AP (D-03a, E-02); no aging exists.
- **Expected behaviour (better than Xero):**
  - Aged receivables/payables summary and detail by contact. Buckets (current, 1–30, 31–60, 61–90, 90+) are configurable; ageing is by due date or invoice date.
  - Uses current invoice revisions (D-03b), unapplied credits and prepayments.
  - **AR/AP control vs sub-ledger reconciliation report** (new vs Xero). It compares the control-account GL balance with the sum of open documents, and when they differ it names the offending journals: manual journals to AR/AP without a contact, or posted to control accounts directly.
- **Gap #s closed:** 54.
- **Business rules:**
  - Aging total = control balance when no direct journals exist.
  - Control accounts are flagged system accounts (C-01).
  - C-03 contact-on-line allows journals with a contact to count in the sub-ledger.
- **Edge cases:**
  - Foreign-currency documents (Phase 2).
  - Revised invoices.
  - Credit balances.
  - As-at dates in the past (historical aging).
  - Payments dated after the as-at date.
- **UI/UX:**
  - Aging report with bucket bar per contact, a click to the contact statement (B-02) and a "send statement" bulk action.
  - Reconciliation report with a green/red status card and offending-journal list with links.
- **Dependencies:** K-01, D-03a, D-03b, D-05, D-06, E-02, C-03, B-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-03-T01 | Open-item query: open documents as at date (current revisions, allocations up to as-at date, credits, prepayments) | BE | D-03b, D-05 | Historical as-at fixture correct | Unit |
| K-03-T02 | Aging bucket engine (configurable buckets, by due/invoice date) | BE | T01 | 1–30 bucket counts correct on fixture | Unit |
| K-03-T03 | AR aging summary and detail report definitions | BE | T02, K-01 | Totals = sum of open items | Unit |
| K-03-T04 | AP aging summary and detail report definitions | BE | T02, K-01 | Same for AP | Unit |
| K-03-T05 | Control vs sub-ledger reconciliation: GL control balance vs open items; difference explained by listing journals hitting control accounts without contact | BE | T03, T04, C-03 | Fixture 0.00; injected journal named | Integration |
| K-03-T06 | Aging settings (buckets, basis) per org | BE/FE | T02 | Changing buckets updates report | Playwright |
| K-03-T07 | UI: aging with bucket bars, contact drill to statement, bulk "send statements" | FE | T03, B-02 | Bulk statements queued for selected contacts | Playwright |
| K-03-T08 | UI: reconciliation status card and offending journal list | FE | T05 | Red card links to journal | Playwright |
| K-03-T09 | Property test: random invoices/payments/revisions/credits → aging total = AR control (no direct journals) | QA | T03 | 1,000 examples pass | Property |
| K-03-T10 | Gap test `gap-54` (control reconciliation), exports, i18n | QA | T07 | Green | Playwright |

- **Deliverable acceptance:**
  - Aging equals the control balance.
  - The reconciliation shows 0 on fixtures, and names the offending journal otherwise.
- **Testing:** unit, property, integration, functional.
- **Risks:** allocation-date edge cases. Mitigation: as-at semantics documented and fixtures.

### K-05 · Dashboard
- **Branch:** `feature/K-05-dashboard`
- **Objective:** a useful organisation home that shows the true position at a glance, with no advertising.
- **Current behaviour:** Phase 0 has an empty org home. Xero shows no bank-balance widget by default, "—k" axis labels on empty charts, and an advertising widget.
- **Expected behaviour (better than Xero):** default widgets by role:
  - Bank & cash balances (all bank/cash accounts incl. petty cash, ledger balance, statement balance if any).
  - Cash in/out for the last 6 months.
  - Invoices owed (awaiting/overdue with aging bar).
  - Bills to pay.
  - Upcoming tax and filing deadlines (G-03a periods and due dates).
  - P&L snapshot (MTD/YTD).
  - Account watchlist.
  - Exceptions summary (K-09 count by severity).
  - Items awaiting my approval.

  Widgets can be added, removed and reordered per user. Empty data renders 0 and an actionable empty state. There is no ad or app-store widget. Every figure links to the report that produced it.
- **Gap #s closed:** 4, 60.
- **Business rules:**
  - Dashboard figures are computed by the same services as the reports (no separate math).
  - Cash definition comes from the K-02-T09 setting.
  - Role defaults: owner, accountant, sales and purchasing get different layouts.
  - Load in under 1.5 s.
- **Edge cases:**
  - New org with no data.
  - Org without the Tax product (deadlines widget gated with an explicit message).
  - Large number of bank accounts (scroll).
  - Negative cash shown in red with an exception link.
- **UI/UX:**
  - Responsive grid (12-col desktop, 1-col mobile), drag-to-reorder widgets (dnd-kit), skeleton loaders per widget (independent loading, one failing widget doesn't break the page) and widget-level retry.
  - Charts use the dataviz palette with zero baselines, CAD formatting, accessible table fallbacks and a "Data as of hh:mm" timestamp.
- **Dependencies:** K-01, K-02, K-03, F-01, G-03a, K-09, U-03.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-05-T01 | Wireframes: default layouts per role, widget library, empty states, mobile layout | UX | — | Reviewed | Design review |
| K-05-T02 | `DashboardLayout` per user (widgets, order, settings) with role defaults | DB | — | New user gets role default | Unit |
| K-05-T03 | Widget data services reusing report services: bank & cash, cash in/out, owed, to pay, P&L snapshot, watchlist | BE | K-02, K-03, F-01 | Each widget value = report total (test) | Integration |
| K-05-T04 | Deadlines widget service from G-03a periods (and payroll later) with due-soon/overdue status | BE | G-03a | Next due period shown | Unit |
| K-05-T05 | Exceptions widget and approvals widget services | BE | K-09, C-04 | Counts = list counts | Integration |
| K-05-T06 | API `/api/v1/dashboard` (layout CRUD, per-widget data endpoints); entitlement-aware (gated widgets return gate info) | API | T02–T05 | Gated widget returns 402 info, not an error | API |
| K-05-T07 | Dashboard grid UI with drag reorder, add/remove widget drawer, per-widget skeleton and retry | FE | T06 | One failing widget doesn't break others | Playwright |
| K-05-T08 | Chart components (bar/line) with zero rendering rule, CAD axis format, table fallback | FE | A-10 | Empty chart axis shows 0, never "—k" | Vitest |
| K-05-T09 | Bank & cash widget with petty cash and negative highlight linking to exceptions | FE | T03 | Petty cash included | Playwright |
| K-05-T10 | Performance budget check < 1.5 s on fixture org | QA | T07 | Lighthouse/k6 pass | Perf |
| K-05-T11 | Gap tests `gap-04`, `gap-60` (no ads, bank widget default, zero rendering, cash definition); i18n | QA | T07 | Green | Playwright |

- **Deliverable acceptance:**
  - Dashboard figures equal report totals.
  - Empty states show 0, never "—k".
- **Testing:** integration (equality), visual regression, perf, functional.
- **Risks:** N+1 queries across widgets. Mitigation: per-widget endpoints with caching.

### K-09 · Exceptions engine (assurance)
- **Branch:** `feature/K-09-exceptions-engine`
- **Objective:** an assurance engine that catches real bookkeeping problems and proposes fixes.
- **Current behaviour:** no checks exist. Xero's GL Exceptions report flagged nothing on a ledger with negative cash, journal-only expenses, all-exempt tax, no BN, no lock date and 0 GIFI; its Assurance dashboard ignores journals.
- **Expected behaviour (better than Xero):** a rule engine over the ledger with these rules, each with a configurable severity (info/warning/critical) and parameters:
  - NEG_CASH — negative cash/bank balance.
  - JOURNAL_TO_CASH — manual journals posting to bank/cash.
  - EXPENSE_JOURNAL_NO_CONTACT.
  - EXPENSE_JOURNAL_NO_ATTACHMENT.
  - EXEMPT_ON_TAXABLE_ACCOUNT — Exempt code on accounts normally taxable for a registrant.
  - BACKDATED — gap between document date and posting date > N days, for journals, invoices and bills.
  - ROUND_AMOUNT — journals with round amounts ≥ threshold.
  - WEEKEND_POSTING.
  - SOD_SAME_CREATOR_APPROVER.
  - DUPLICATE_PAYMENT — same supplier, amount and date window.
  - DUPLICATE_SUPPLIER_INVOICE.
  - UNMAPPED_GIFI.
  - MISSING_BN — registered with no BN.
  - MISSING_LOCK_DATE — no lock date after a period that is more than N days old.
  - DORMANT_USER_WITH_ADMIN — no login for 60 days while holding manage-users.
  - CONTACT_BANK_DETAILS_CHANGED.
  - TAX_CODE_OVERRIDE_RATE — share of lines overriding the default above a threshold.
  - UNBALANCED_CONVERSION — the C-05 state.

  The engine also provides:
  - Runs on demand, nightly and on posting (incremental).
  - A findings list with status (open / acknowledged / resolved / false positive with reason).
  - For each finding, a proposed correcting entry as a **draft journal** where applicable (e.g. Dr Petty Cash 994.17 / Cr Shareholder Loan 994.17) that the accountant reviews and posts through C-04.
  - A user-activity heatmap (from A-04 counts).
  - An "Assurance score" summary.
- **Gap #s closed:** 36, 53, 59, plus 33 (detection side).
- **Business rules:**
  - Rules are plug-ins with a registry; each has a code, a description key (i18n), parameters with defaults, a severity and an optional `propose_fix()`.
  - Findings are deduplicated by (rule, subject); they reopen if the condition recurs after being resolved.
  - A draft fix is never auto-posted.
  - Results respect tenancy and role (practice staff see the findings of assigned orgs only).
  - Findings and fixes are audited.
- **Edge cases:**
  - Huge ledgers (incremental run).
  - Rule parameters changed (re-evaluate).
  - A false positive acknowledged then recurring with a different amount (new finding).
  - Weekend in the org's time zone, not UTC.
  - Holidays (optional parameter).
- **UI/UX:**
  - Assurance page: score card, severity filter chips, grouped findings list (rule → items), each item shows why (plain-language explanation and the numbers) plus buttons View source / Propose fix / Acknowledge / Mark false positive.
  - The proposed-fix drawer shows the draft journal with an editable grid and an explanation of the reasoning.
  - Rule settings page with toggles and parameters.
  - Heatmap tab.
  - Exceptions count badge in the nav and on the dashboard.
- **Dependencies:** C-02, C-03, C-04, C-05, F-07, G-01, G-06, A-04, A-05, E-02, D-05, C-01 (GIFI).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-09-T01 | Rule catalogue specification (code, condition, parameters, severity, fix template) signed off by the client | DOC | — | Signed off | Review |
| K-09-T02 | Wireframes: assurance page, finding detail, proposed-fix drawer, rule settings, heatmap | UX | T01 | Reviewed | Design review |
| K-09-T03 | Models: `ExceptionRuleConfig` (org, rule_code, enabled, severity, params JSON), `ExceptionFinding` (rule_code, subject type/id, fingerprint, amount, details JSON, status, first_seen, last_seen, resolved_at, ack_by, reason), `ExceptionRun` | DB | — | Migration; unique open finding per fingerprint | Unit |
| K-09-T04 | Rule plug-in framework: base class, registry, parameter schema validation, `evaluate(org, scope)` → findings, `propose_fix(finding)` → draft JE payload | BE | T03 | Two dummy rules register and run | Unit |
| K-09-T05 | Runner: full run (Celery), incremental run triggered by posting events (affected accounts/documents only), dedupe/reopen logic | BE | T04, A-08 | Re-run creates no duplicates; recurrence reopens | Integration |
| K-09-T06 | Rule NEG_CASH (uses F-07 running-min projector) with fix proposal (transfer from funded bank or Shareholder loan credit) | BE | T04, F-07 | Teardown fixture: finding −994.17 with draft Dr 1000 / Cr 2900 | Unit |
| K-09-T07 | Rule JOURNAL_TO_CASH | BE | T04 | Both teardown journals flagged | Unit |
| K-09-T08 | Rules EXPENSE_JOURNAL_NO_CONTACT and EXPENSE_JOURNAL_NO_ATTACHMENT | BE | T04, C-03 | Teardown journals flagged for both | Unit |
| K-09-T09 | Rule EXEMPT_ON_TAXABLE_ACCOUNT (registrant org, expense account normally taxable, line coded Exempt) with fix "recode tax" via C-07 link | BE | T04, G-01 | All-exempt teardown lines flagged | Unit |
| K-09-T10 | Rule BACKDATED (param N days, default 7) across journals/invoices/bills | BE | T04 | Journal dated 3 Jun posted 15 Jun flagged | Unit |
| K-09-T11 | Rules ROUND_AMOUNT and WEEKEND_POSTING (org time zone) | BE | T04 | Fixtures flagged; Saturday in America/Toronto detected | Unit |
| K-09-T12 | Rule SOD_SAME_CREATOR_APPROVER (journals, bills, pay runs placeholder) | BE | T04, C-04 | Same user create+approve flagged (where permitted by legacy import) | Unit |
| K-09-T13 | Rules DUPLICATE_PAYMENT and DUPLICATE_SUPPLIER_INVOICE (similarity window) | BE | T04, E-02, D-05 | Fixture duplicates flagged | Unit |
| K-09-T14 | Rules UNMAPPED_GIFI, MISSING_BN, MISSING_LOCK_DATE, UNBALANCED_CONVERSION | BE | T04, C-01, G-06, A-05, C-05 | Teardown: 0 GIFI, no BN, no lock date all flagged | Unit |
| K-09-T15 | Rules DORMANT_USER_WITH_ADMIN, CONTACT_BANK_DETAILS_CHANGED, TAX_CODE_OVERRIDE_RATE | BE | T04, A-04, V-05 | Dormant subscriber with manage-users flagged | Unit |
| K-09-T16 | Fix-to-draft service: converts `propose_fix` payload into a Draft journal (C-04) linked to the finding; posting resolves the finding | BE | T06, C-04 | Posting the draft resolves NEG_CASH | Integration |
| K-09-T17 | Finding workflow: acknowledge, false positive with reason, resolve (auto when condition clears); audit | BE | T05 | Status transitions audited | Unit |
| K-09-T18 | Assurance score (weighted by severity, 0–100) and summary per org; practice-level aggregation hook for V-04 | BE | T05 | Score decreases with critical findings | Unit |
| K-09-T19 | User-activity heatmap data from A-04 counts | BE | A-04 | Heatmap counts = audit counts | Integration |
| K-09-T20 | API `/api/v1/assurance` (findings, run, rules config, fix, heatmap); feature key `accounting.assurance`; permissions | API | T05–T19 | Sweep passes | API |
| K-09-T21 | Assurance page UI: score, filters, grouped findings, plain-language explanation, actions | FE | T20 | Teardown fixture shows ≥ 7 rule groups | Playwright |
| K-09-T22 | Proposed-fix drawer with editable draft journal grid and reasoning text | FE | T16, T21 | Draft created from drawer appears in journals Draft tab | Playwright |
| K-09-T23 | Rule settings page (toggle, severity, parameters with validation) | FE | T20 | Changing N re-evaluates on next run | Playwright |
| K-09-T24 | Heatmap tab (calendar grid, accessible table alternative) and nav badge | FE | T19 | Badge = open critical+warning count | Vitest |
| K-09-T25 | Teardown migration fixture (REFINED-like org) test: all issues flagged (negative petty cash, journal-only expenses, all-exempt, no BN, no lock date, 0 GIFI, backdated journal, dormant admin) | QA | T06–T15 | `gap-36`, `gap-53`, `gap-59` green | E2E |
| K-09-T26 | Performance: incremental run < 2 s per posting batch; nightly full run 500 orgs within window | QA | T05 | Perf targets met | k6 / pytest-benchmark |
| K-09-T27 | i18n (rule names and explanations en/fr), docs "Assurance rules reference" | DOC | T21 | Merged | Review |

- **Deliverable acceptance:** every teardown issue is flagged on the migrated fixture.
- **Testing:** unit per rule, integration (runner, fix), E2E fixture, perf, security (tenant scoping of findings).
- **Risks:**
  - Noise and false positives. Mitigation: severities, parameters, false-positive workflow.
  - Runtime cost. Mitigation: incremental runs and indexes.

---

## 7. TEST — Phase 1 test plan

### 7.1 Test matrix by category

| Category | Phase 1 scope | Tooling | Target |
|---|---|---|---|
| Unit | Journal types and negative-balance controls (C-03); recurring JE scheduler and approval (C-04); conversion difference (C-05); period close and RE roll (C-06); recode/undo (C-07); D-01 grid totals and discounts; quote state machine; invoice posting; revision state machine (D-03b); recurring tick idempotency; payment allocation; credit notes; reminder scheduler; PO/GRN/3-way match; bill uniqueness/duplicates/routing; expense claims; CPA 005 writer; early-payment discount; bank mapping, fingerprints, rules, reconciliation scoring, transfers, running-min projector; tax calculator, resolver, return lines, cycle generator, due dates; report definitions; exceptions rules | pytest, Hypothesis, factory_boy, Vitest | ≥ 85 % on `ledger`, `revisions`, `tax`, `banking`, `sales`, `purchases`, `reports`, `assurance` |
| Property | Every posting balanced; AR = sum of open current revisions (1,000 random edits); allocation sums; filing periods no gaps/overlaps over random switch/stop/restart sequences; fingerprint idempotency; aging = control; incl/excl tax round-trip | Hypothesis | 1,000 examples per property, 0 failures |
| Integration | Endpoint ↔ DB ↔ JE engine for every Phase 1 endpoint (one happy + one failure test each); statement import commit/undo; reconciliation find & match creates payments; late adjustments; tie-outs; inbound bills from A-06 | pytest + DRF client, MinIO, mailpit | 100 % endpoints covered |
| Functional (E2E) | Invoice-to-cash incl. revision 101-1; quote → invoice; recurring invoice; credit note; reminders before/after due; PO → GRN → bill with 3-way match → batch payment CPA 005 → cheque void; expense claim; spend money with no feed; import → rules → reconcile; transfer; negative cash blocked; GST cycle switch + out-of-cycle stub + return filed; stop/restart; P&L/BS/CF/TB; exceptions on teardown fixture | Playwright | One scripted scenario per deliverable; exit demo scripted |
| Regression | Full suite on every PR; nightly on `main` with the growing fixture practice; Phase 0 suites (tenancy, RBAC, entitlements, billing) re-run | GitHub Actions | 0 known regressions |
| Data validation | BS balances; NI = ΔRE; TB debits = credits per book; aging = AR/AP control; tax report = GL tax control accounts; return line 105 = tax report; GL bank balance = sum of bank transactions; reconciled balance = statement balance | `scripts/validate_ledger.py` run in CI and before demo | 0 differences |
| Security | Tenant-isolation sweep on all new routers; RBAC matrix incl. approval limits (C-04, E-01, E-02); reviewer ≠ preparer (G-03), approver ≠ creator (C-04, E-04); entitlement leak tests (tax returns, assurance, reminders gated correctly, approvals never gated); file upload validation (statements, attachments); regex DoS (bank rules); masked bank numbers never logged; ZAP baseline | Custom sweeps, ZAP, semgrep, gitleaks | No high findings |
| Performance | Reports p95 < 3 s on 100k-line GL; dashboard < 1.5 s; 50k-line statement import < 60 s; tax resolve 50 lines < 100 ms; 1,000 concurrent postings gap-free (regression from C-02); incremental exceptions < 2 s | k6, pytest-benchmark, Lighthouse CI | Targets met on staging-sized data |
| Compliance fixtures | Sales-tax matrix 2026 (all provinces, both sides, partial ITC); GST/HST return lines (regular, quick, nil, refund, stub, cash basis, revision across periods); filing-cycle scenarios; CPA 005 file layout | `tests/fixtures/compliance` | 100 % pass |
| Localisation | i18n missing-key gate (en-CA complete, fr-CA keys present); pseudo-localisation (+30 %) on editors, reports, worksheet; Canadian terms lint (cheque, organisation, Province, Postal code, GST/HST, vacation pay) | CI extraction, Playwright | 0 missing keys; no clipped layouts |
| Accessibility | axe-core on every new screen; keyboard-only runs: invoice editor, reconcile screen, journal entry, report runner | axe-core, Playwright | 0 serious/critical violations |
| Visual regression | Shared grid in invoice/quote/bill/PO/spend money; overview pages (sales and purchases share one pattern); report tables; PDFs | Storybook + Chromatic (or Playwright screenshots) | Approved baselines |
| Usability | 5 moderated tasks with 2 accountants and 1 owner (see 7.4) | Figma prototype, staging | ≥ 4/5 task success, SUS ≥ 75 |

### 7.2 Gap-closure tests delivered in Phase 1 (tag `gap-NN`)
Phase 1 delivers or extends tests for these gaps:
- 4, 5, 6, 7, 8, 9, 10, 12, 13, 14, 16, 17, 22, 23, 24, 25, 26, 27, 28, 33, 35, 36, 44, 45, 47, 49, 53, 54, 55, 56, 57, 58, 59, 60.
- Gaps 1, 3, 39 continue from Phase 0, extended to the new editors and settings.

Each test asserts the "observable closing behaviour" column of Plan §4.

### 7.3 Exit demonstration script (on staging, observed by Profitex)

| # | Step | Expected result |
|---|---|---|
| 1 | Log in as accountant; open paying organisation "Maple Retail Ltd" (ON, GST/HST quarterly, FYE 31 Dec) | Dashboard shows bank & cash widget, deadlines, zero-safe charts, no ads |
| 2 | Create customer (ON) and invoice 101: 1 line 1,000.00, HST auto-selected 13 % → total 1,130.00; approve and email | Invoice posted; JE Dr AR 1,130 / Cr Revenue 1,000 / Cr HST payable 130; PDF Letter with org legal name |
| 3 | Edit approved invoice 101 to 900.00 + HST → 1,017.00, reason "price correction" | Revision 101-1 created; AR −113.00; two linked JEs (reversal + repost); 101 marked superseded; PDF stamped "Revision 1" |
| 4 | Record payment 1,017.00 from Chequing (created in step 0 with no feed) | Invoice paid; AR 0; Chequing ledger balance +1,017.00 |
| 5 | Spend money 226.00 incl. HST from Chequing on office supplies (no import, no reconciliation) | Posted; ITC 26.00; Chequing balance updated; appears on Balance Sheet |
| 6 | Try spend money 500.00 from Petty Cash (balance 0) as a non-adviser | Blocked with message naming the balance and remedies; as adviser → warning + reason required |
| 7 | Import an RBC CSV statement twice | First import adds N lines; second adds 0; rules auto-code the coffee line; reconcile 2 lines (optional) |
| 8 | Open Tax settings (one page); switch GST/HST from quarterly to monthly effective 1 Jul 2026 with approval ref | Preview shows Q1/Q2 unchanged, Jul…Dec monthly; confirm; timeline shows switch marker |
| 9 | Add out-of-cycle period example on a second fixture org (1 Jan–15 Mar, then quarters from 16 Mar) | Accepted; every document in exactly one period |
| 10 | Open GST/HST return for the out-of-cycle period; check line 103 and 105 vs tax report; mark filed with confirmation number | Lines tie; period locked; back-dated invoice refused unless late-adjustment flag |
| 11 | Run P&L, Balance Sheet (as at today), Trial Balance (sorted by code), Cash Flow (indirect) | BS balances; NI = ΔRE; TB sorted; every figure drills to source |
| 12 | Run AR aging and AR control reconciliation | Aging = control; difference 0.00 |
| 13 | Open Assurance on the teardown-style fixture org | Negative petty cash, journal-to-cash, no contact/attachment, all-exempt, no BN, no lock date, 0 GIFI, backdated journal flagged; "Propose fix" creates draft Dr Petty Cash / Cr Shareholder Loan 994.17 |
| 14 | Show CI: green pipeline incl. tenant sweep, i18n gate, compliance fixtures, gap tests | All green |

### 7.4 Usability tasks (success metrics)

| Task | User | Target |
|---|---|---|
| Create and send a first invoice for a new customer | Owner | < 2 min, ≤ 12 clicks, no help needed |
| Correct an already-sent invoice | Accountant | < 60 s; user understands "101-1" without explanation |
| Record a cash expense with receipt photo | Owner | < 60 s |
| Import a bank CSV and code 10 lines with a rule | Accountant | < 5 min |
| Switch GST/HST frequency and verify periods | Accountant | < 3 min, preview understood |

### 7.5 Failure handling
Failures are handled per Plan §6.2:
1. Stop dependent tasks.
2. Find the exact failing condition and its cause (code, data, config or assumption).
3. Apply one focused fix.
4. Re-run the affected tests, then the regression suite.

A failing test is never hidden or skipped. If a test cannot run, the reason is recorded in the sprint report. Debugging follows the structured process of Rule 6, including the 30-minute principle.

---

## 8. IMPROVE — Phase 1 post-verification review

Run after all Phase 1 acceptance criteria are observed. Improve only where meaningful, then re-run tests.

**Correctness**
- Re-verify every ledger invariant with the data-validation script on the fixture practice (BS, TB, aging, tax tie-outs, AR revisions).
- Review rounding policy consistency across the tax calculator, grid totals, PDFs and returns.

**Readability / maintainability**
- One posting pipeline (C-02) is used by every source (invoice, revision, bill, payment, spend/receive, transfer, journal, discount): no duplicated JE code.
- The D-01 grid is shared by invoice/quote/recurring/credit note/bill/PO/spend money.
- Tax logic lives only in the `tax` package; report math only in report definitions (the dashboard reuses them).

**Performance budgets**

| Item | Budget |
|---|---|
| Report p95 (100k lines) | < 3 s |
| Dashboard | < 1.5 s |
| Invoice save + post | < 400 ms p95 |
| Revision save | < 600 ms p95 |
| Tax resolve (50 lines) | < 100 ms |
| Statement import (50k lines) | < 60 s |
| Reconcile screen suggestions | < 300 ms per line |
| Exceptions incremental | < 2 s |

- Profile slow queries (`django-silk` / `pg_stat_statements`); add indexes; never cache ledger totals without invalidation.

**Reliability**
- Idempotency keys on recurring invoice/bill ticks, reminders, statement commits and batch payments.
- Retries with backoff are visible in the job dashboard (A-08).

**Security**
- RBAC and approval-limit matrix re-run.
- Tenant sweep on every new router.
- No bank numbers or SIN in logs (log scrubber test).
- Regex timeout in bank rules.
- Webhook/email inputs sanitised.

**Consistency / UX**
- Design-system audit: every new screen uses design-system components only (lint for raw HTML tables/inputs).
- Canadian-term lint.
- Empty/loading/error/gated states present on every list and editor.
- Keyboard shortcuts documented in the "+" menu and help overlay (`?`).

**Accessibility:** axe 0 serious; focus order on grids; screen-reader labels on amount cells and status badges.

**i18n:** all keys extracted; fr-CA placeholders present; pseudo-locale layout pass.

**Clean-up**
- Remove mocks/fixtures used only in development; keep the compliance fixtures.
- Remove debug flags.
- Docs updated (user guides per module, ADR-002 invoice revisions finalised).

---

## 9. Git branch plan (Phase 1)

| Order | Branch | Base | Deliverable | Merge after |
|---|---|---|---|---|
| 1 | `feature/C-03-journal-types-controls` | main | C-03 | Phase 0 merged |
| 1 | `feature/G-01-tax-codes-rates` | main | G-01 | Phase 0 merged (parallel with C-03) |
| 1 | `feature/D-01-shared-document-grid` | main | D-01 | Phase 0 merged (parallel) |
| 2 | `feature/C-04-manual-recurring-approval` | main | C-04 | C-03 |
| 2 | `feature/G-06-tax-settings-hub` | main | G-06 | G-01 |
| 2 | `feature/G-03a-filing-cycles` | main | G-03a | G-06 model task (shared registration migration) |
| 2 | `feature/G-02-place-of-supply` | main | G-02 | G-01, G-06 |
| 2 | `feature/F-01-never-locked-bank-accounts` | main | F-01 | C-03, G-01, D-01 |
| 3 | `feature/F-07-negative-balance-controls` | main | F-07 | F-01, C-03 |
| 3 | `feature/D-03a-invoices-posting` | main | D-03a | D-01, G-02 |
| 3 | `feature/D-02-quotes` | main | D-02 | D-01 |
| 3 | `feature/E-02-bills` | main | E-02 | D-01, G-02 |
| 3 | `feature/C-05-conversion-balances` | main | C-05 | C-03 |
| 3 | `feature/G-03b-stop-restart-filing` | main | G-03b | G-03a |
| 4 | `feature/D-05-payments-allocation` | main | D-05 | D-03a, F-01 |
| 4 | `feature/D-03b-invoice-revisions` | main | D-03b | D-03a, G-03a (period rules) |
| 4 | `feature/D-06-credit-notes` | main | D-06 | D-03a |
| 4 | `feature/D-04-recurring-invoices` | main | D-04 | D-03a |
| 4 | `feature/E-01-po-receiving-3way` | main | E-01 | E-02 |
| 4 | `feature/E-03-recurring-bills-credits` | main | E-03 | E-02, D-04 pattern |
| 4 | `feature/E-04-expense-claims` | main | E-04 | E-02 |
| 4 | `feature/F-02-statement-import` | main | F-02 | F-01 |
| 4 | `feature/F-06-transfers` | main | F-06 | F-01, F-07 |
| 5 | `feature/E-06-batch-payments-cheques` | main | E-06 | E-02, F-01 |
| 5 | `feature/E-07-early-payment-discounts` | main | E-07 | D-05, E-06 |
| 5 | `feature/F-04-bank-rules` | main | F-04 | F-02 |
| 5 | `feature/F-05-optional-reconciliation` | main | F-05 | F-02, F-04, D-05 |
| 5 | `feature/D-07-reminders-statements` | main | D-07 | D-05, B-02 |
| 5 | `feature/C-06-period-close-year-end` | main | C-06 | C-03 |
| 5 | `feature/C-07-find-recode-undo` | main | C-07 | C-03, G-01 |
| 5 | `feature/K-01-report-engine` | main | K-01 | C-02 (can start early, parallel) |
| 6 | `feature/G-05-tax-reports` | main | G-05 | G-01, G-03a, K-01, D-03b |
| 6 | `feature/G-03-gst-hst-return` | main | G-03 | G-05, G-03a |
| 6 | `feature/K-02-core-statements` | main | K-02 | K-01, F-07 |
| 6 | `feature/K-03-ar-ap-reports` | main | K-03 | K-01, D-05, E-02 |
| 6 | `feature/D-09-sales-overview-lists` | main | D-09 | D-02…D-07 |
| 7 | `feature/K-09-exceptions-engine` | main | K-09 | C-03, F-07, G-06, C-05, E-02 |
| 7 | `feature/K-05-dashboard` | main | K-05 | K-02, K-03, K-09, G-03a |

**Before each branch** (Rule 7.1):
- Run `git status` and confirm no uncommitted work.
- Pull `main`.
- Restate the objective and acceptance criteria in the PR description (template `.github/pull_request_template.md`).
- List the dependencies and confirm they are merged.

**Before declaring a branch complete** (Rule 7.4):
- Acceptance criteria observed.
- CI green: unit, integration, tenant sweep, RBAC matrix, i18n gate, compliance fixtures and gap tests.
- No unrelated changes, debug code or secrets (gitleaks).
- Docs and permission catalogue updated.
- Final diff reviewed by a second engineer.
- No merge to `main` without project-lead authorisation.

---

## 10. Phase 1 risks register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Invoice revisions leave AR/tax out of step with the document | Medium | High | Reversal + repost in one transaction; AR property test; tax report reads current revision; filed-period rules (G-03) |
| 2 | Filing-cycle switch produces gaps/overlaps | Medium | High | DB exclusion constraint; Hypothesis property tests; preview before confirm; filed periods immutable |
| 3 | Tax rounding differences vs client expectations | Medium | Medium | Documented rounding policy; per-line default with option; fixtures from client's real documents |
| 4 | Place-of-supply simplifications mis-tax services/intangibles | Medium | High | Decision table signed by client's accountant; override with "changed from default" marker; exceptions rule TAX_CODE_OVERRIDE_RATE |
| 5 | GST/HST return line mapping misunderstood | Low | High | Line-mapping sign-off (G-03-T01); tie-out to tax report; fixtures from prior filed returns |
| 6 | Negative-cash controls annoy users / block legitimate overdrafts | Medium | Low | WARN default for bank, BLOCK only for cash for non-advisers; remedy buttons |
| 7 | Statement formats differ per bank/version | High | Medium | Mappings as data; auto-detect; wizard override saved per account |
| 8 | Duplicate statement lines or false duplicate detection | Medium | Medium | Fingerprint + FITID + same-day sequence; undo import |
| 9 | Report performance on large ledgers | Medium | Medium | Indexed aggregation, daily balance table, read replica (S-06), k6 in CI nightly |
| 10 | Exceptions engine noise | Medium | Medium | Severity, parameters, false-positive workflow, rule settings |
| 11 | Scope pressure: 37 deliverables in one week | High | High | Parallel branches per §9; smallest useful implementation first (walking skeleton); strict change control; client inputs on time |
| 12 | Double processing of recurring ticks, reminders, batch payments | Low | High | Idempotency keys; DB unique constraints; worker-restart tests |
| 13 | Missing client inputs (sample documents, CRA numbers) | Medium | Medium | Request at kickoff; synthetic fixtures meanwhile, replaced before acceptance |
| 14 | UI inconsistency between modules | Low | Medium | One grid and one overview pattern; visual regression; design-system lint |

---

## 11. Phase 1 completion checklist & reporting template

### 11.1 Mandatory execution checklist (Rule 11) — tick per deliverable in `docs/checklists/phase-1/<ID>.md`

**UNDERSTAND**
- [ ] Investigated the existing implementation from Phase 0 (tenancy, RBAC, entitlements, CoA, posting engine, design system)
- [ ] Identified the user and the outcome
- [ ] Defined inputs and outputs
- [ ] Identified business rules
- [ ] Considered edge cases
- [ ] Restated the objective in the PR

**PLAN**
- [ ] Decomposed into atomic tasks (section 6)
- [ ] Identified dependencies
- [ ] Ordered tasks
- [ ] Defined acceptance criteria
- [ ] Defined tests

**BUILD**
- [ ] Smallest functional piece first (model → service → API → UI)
- [ ] Followed existing architecture (C-02 pipeline, D-01 grid, tax package, K-01 engine)
- [ ] No unrelated changes
- [ ] Feature key and i18n keys declared

**TEST**
- [ ] Behaviour verified
- [ ] Edge cases tested
- [ ] Failures resolved
- [ ] Regressions checked
- [ ] Tenant sweep run
- [ ] Gap tests green
- [ ] Unverified conditions recorded

**IMPROVE**
- [ ] Code quality reviewed
- [ ] Temporary artifacts removed
- [ ] Readability improved where needed
- [ ] Behaviour still correct

**COMPLETE**
- [ ] Final diff reviewed
- [ ] Docs updated
- [ ] Changes and results reported
- [ ] Acceptance confirmed
- [ ] Final status reported

**Phase exit:**
- [ ] All 37 deliverables Complete
- [ ] Exit demonstration (7.3) observed on staging
- [ ] Release notes and test results delivered
- [ ] Client review window (5 business days, Agreement §07) started

### 11.2 Reporting template (Rule 10)

**Before implementation (per deliverable — in the PR description)**
1. Problem understanding: objective; existing behaviour; expected behaviour.
2. Task breakdown: components; atomic tasks (IDs); dependencies.
3. Implementation plan: execution order; acceptance criteria; testing strategy.

**After implementation (per deliverable — PR closing comment and sprint report)**
1. Changes made: completed tasks (IDs); files/components modified; important decisions (ADR links).
2. Testing results: tests executed; passed; failed; not executed and why.
3. Remaining issues: known limitations; unresolved bugs; risks/dependencies.
4. Final status: Complete / Partially complete / Blocked.

**Phase 1 sprint report (to Profitex)**
- Deliverables by status.
- Exit-demo readiness.
- Gap rows observed (list of `gap-NN`).
- Compliance fixture results.
- Performance budget results.
- Open risks.
- Client inputs outstanding.
- Staging link.

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| C-03 | 17 | 25.5 |
| C-04 | 16 | 24 |
| C-05 | 15 | 22.5 |
| C-06 | 11 | 16.5 |
| C-07 | 15 | 22.5 |
| D-01 | 19 | 28.5 |
| D-02 | 17 | 25.5 |
| D-03a | 19 | 28.5 |
| D-03b | 25 | 37.5 |
| D-04 | 12 | 18 |
| D-05 | 13 | 19.5 |
| D-06 | 11 | 16.5 |
| D-07 | 14 | 21 |
| D-09 | 12 | 18 |
| E-01 | 16 | 24 |
| E-02 | 18 | 27 |
| E-03 | 10 | 15 |
| E-04 | 12 | 18 |
| E-06 | 16 | 24 |
| E-07 | 12 | 18 |
| F-01 | 17 | 25.5 |
| F-02 | 16 | 24 |
| F-04 | 16 | 24 |
| F-05 | 16 | 24 |
| F-06 | 9 | 13.5 |
| F-07 | 12 | 18 |
| G-01 | 17 | 25.5 |
| G-02 | 10 | 15 |
| G-03 | 16 | 24 |
| G-03a | 23 | 34.5 |
| G-03b | 14 | 21 |
| G-05 | 12 | 18 |
| G-06 | 11 | 16.5 |
| K-01 | 19 | 28.5 |
| K-02 | 16 | 24 |
| K-03 | 10 | 15 |
| K-05 | 11 | 16.5 |
| K-09 | 27 | 40.5 |
| **Total** | **572** | **858** |

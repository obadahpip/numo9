# NUMO9 — PHASE 2 IMPLEMENTATION PLAN
## Operations, Finance & Two Books (Weeks 3–4)

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | 2 — Operations, Finance & Two Books |
| **Weeks** | 3–4 (from kickoff) |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment) |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §1.6, §1.7, §3 (H, I, J, K, L, R, G, E), §4, §5.2, §6 · Project_Phases.md (Phase 2) · Quotation GMA-PFX-2026-003 §4 (★ items) · Agreement GMA-PFX-2026-003-A clauses 4.3, 7, 9.1(b) · xero_teardown.md (26 Oct 2026) · AI Coding Agent — Mandatory Engineering Workflow |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE — applied to the phase, to every deliverable (one Git branch each) and separately to every atomic task |
| **Deliverables** | 40 (H-01…H-13, FN-01…FN-05, I-01…I-05, J-01…J-03, L-01…L-04, R-01, R-02, K-04, K-06, K-07, K-08, K-10, G-04, G-07, G-08, E-05) |

---

## 0. How to use this file

1. Each deliverable in §6 is one Git branch (`feature/<ID>-<short-name>`) and one pull request. Nothing outside the deliverable's card goes into its branch.
2. Each atomic task (`<ID>-Tnn`) is sized for one focused session of 1–2 hours and is worked through its own UNDERSTAND → PLAN → BUILD → TEST → IMPROVE loop: restate it, check what already exists, build the smallest working piece, run its test, fix, then continue.
3. Tasks are listed in dependency order (model → migration → service → API → permission / feature key → UI → i18n keys → tests → docs). A task is not started until the tasks in its "Depends" column pass their acceptance.
4. Deliverables marked **[v2.1]** (H-09…H-13, FN-01…FN-05, the loan-continuity template in L-03) come from Quotation §4 ★ and Agreement clause 4.3. Their IDs and acceptance wording are **provisional** until Plan v2.1 is approved in writing; the tasks below are built so that only the client formula data changes, never the code structure.
5. A deliverable is complete only when its acceptance criteria are **observed** (test output, screenshot or staging demo); the phase is complete only when every deliverable is complete **and** the exit demonstration (§7, written by the Part 2 section of this plan) is observed on staging (Agreement §07).
6. This file is Part 1: sections 0–5 cover the whole phase; §6 contains the cards for Inventory (H-01…H-13) and the Finance module (FN-01…FN-05). The remaining cards (I, J, L, R, K, G, E-05) and sections 7–12 follow in Part 2.

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase

At the start of week 3 the repository contains the verified outputs of Phases 0 and 1 (nothing in Phase 2 is assumed to exist — each task begins with a check of the codebase for overlapping code):

| Area | Exists (from Phase 0/1) | Relevant to Phase 2 because |
|---|---|---|
| Tenancy & security | `Practice`, `Organisation`, `PracticeAssignment`, `OrgOwnedModel` base, scoped managers, tenant-isolation router sweep, RBAC with approval limits (A-01, A-03) | Every new model (Item, StockMovement, Loan, Asset, Sheet…) inherits `OrgOwnedModel` and registers in the sweep |
| Audit | Append-only `AuditEvent` with field diffs (A-04) | Price-list bulk updates, loan rate changes, CCA claims, EOQ parameter edits are all audited |
| Settings & locks | `OrganisationSettings`, fiscal year, per-module `LockDate` (GL/AR/AP/Bank/Payroll/Tax) (A-05) | Stock postings, depreciation runs and loan postings obey GL lock; tax-book entries obey Tax lock |
| Files & inbox | `Document` storage, per-org inbound email address, "create bill from file" stub (A-06) | E-05 OCR capture plugs into the inbox |
| Jobs | Celery + Redis + beat, idempotency keys, job dashboard (A-08) | Depreciation runs, FX-rate fetch, loan period-end accruals, reorder alerts, analytics snapshots |
| Search & design system | Global search registry, quick-create, design-system package (`@numo9/ui`) with shared `DocumentGrid`, `DataTable`, `MoneyInput`, `DatePicker`, `EmptyState`, `GatedFeature` (A-09, A-10) | Items, assets, loans, sheets registered in search; screens built only from `@numo9/ui` |
| SaaS | Product catalogue with feature keys incl. **Inventory** and **Finance [v2.1]** products, entitlement engine (402 + explicit gating) (U-01, U-03) | Every Phase 2 endpoint declares `inventory.*`, `finance.*`, `tax.*`, `accounting.*` feature keys |
| Contacts | `Contact` with roles, province, currency, terms master incl. early-payment and late-interest terms (B-01) | Customer price lists, supplier links, contact currency (R-01), FN-04 terms |
| Ledger | CoA with sub-accounts and GIFI defaults, `JournalEntry` / `JournalLine` posting engine with **book dimension** (`accounting`/`tax`/`both`), journal types incl. `tax_adjustment` and `depreciation`, approval, period close, recode (C-01…C-07) | Every stock, depreciation, loan, FX and tax-adjustment posting goes through the one `post_journal()` service |
| Sales & purchases | Shared `DocumentGrid`, invoices with revisions (D-03b), payments, credit notes, POs with GRN and 3-way match (E-01), bills (E-02), early-payment discount capture (E-07) | Items appear on lines; GRN/bill/invoice drive stock movements and COGS; FN-04 extends E-07/D-07 |
| Banking | Never-locked bank accounts incl. Loan and Line-of-credit types (F-01) | FN-01 links each loan to a Loan-type ledger account |
| Tax | Effective-dated codes, place of supply, GST/HST worksheet, filing-cycle engine (G-01…G-03b, G-05, G-06) | G-04 QST reuses the cycle engine; G-07/G-08 use the tax book |
| Reporting | Report engine with **book selector**, P&L/BS/CF/TB/GL, AR/AP, dashboard, exceptions engine (K-01…K-03, K-05, K-09) | K-07/K-08 extend the engine; H-13 and FN-05 dashboards reuse widgets |

What does **not** exist: any item / stock / costing model, asset register, loan model, project model, Sheets grid, currency-rate table, budget model, tax-book computation, QST worksheet, GIFI export, OCR pipeline.

### 1.2 Problem definition — the seven questions for Phase 2

**1. Who uses this phase's functionality?**

| Actor | Phase 2 use |
|---|---|
| Accountant (practice member) | Configures items, costing and price lists; runs depreciation and CCA claims; posts tax adjustments; reviews two-book statements and computed tax; prepares working papers; exports GIFI; files QST worksheet; reviews OCR-captured bills |
| Organisation owner | Sees best-sellers, margins and price what-ifs; approves EOQ-suggested POs; registers a car or equipment loan and sees interest to date; sees accounting vs tax statements |
| Organisation users (purchasing, sales clerk, warehouse) | Receive/issue/transfer stock, count stock, build assemblies, raise POs from reorder suggestions, log time |
| Employee | Timesheets and timers (J-02) |
| Platform owner | Sees feature-key usage for Inventory and Finance products |
| System | Nightly analytics snapshots, reorder alerts, depreciation and loan accrual schedules, FX-rate fetch, unrealised FX revaluation, OCR extraction jobs |

**2. What is the desired outcome?** An organisation on a package that includes Inventory, Finance and Tax can run stock-controlled sales with automatic COGS, see which SKUs make money and what price maximises contribution margin, reorder with EOQ in one click, record loans whose principal/interest post automatically, depreciate assets by SL/DB in the accounting book and claim discretionary CCA (incl. full-CCA-as-loss) in the tax book, and view accounting and tax statements side by side with the computed income tax — all reconciling to the cent.

**3. What are the inputs?** Item master data (SKU, barcode, UoM, category, prices, cost, supplier, reorder point, EOQ parameters); stock receipts, issues, adjustments, transfers, counts; BOMs; client EOQ equation and management-accounting KPI material (PDFs, Agreement 9.1(b)); price scenarios; loan contracts (principal, nominal rate, compounding, payment frequency, term, start, balloon, rate changes, early repayments); credit terms (2/10 net 30, late-interest rate); asset data and client depreciation templates (XLSX/CSV); CCA class table; projects, tasks, timesheets, rates; currency rates (provider feed + manual overrides); budgets; tax-adjustment journals; T2 rate tables (SBD limit, federal/provincial rates); QST filing data; GIFI mapping; bill/receipt files via inbound email.

**4. What are the outputs?** Stock on hand by location, stock cards, valuation, movement, aging and stock-take reports; COGS and inventory postings; SKU rankings, velocity, days of cover, dead/slow lists; EOQ and reorder suggestions → POs; margin and contribution reports; what-if scenarios; KPI dashboard; amortisation schedules, loan postings, YTD and total interest, cost-of-forgoing-discount figures, loan reports in both books; asset register, depreciation schedules, continuity reports, CCA schedules (UCC per class), loss carry-forward; project P&L, invoiced time; Sheets working papers; FX gains/losses; budget variance; management pack and NTR/Compilation/Review templates; Book Reconciliation report; tax-purpose IS/BS with computed tax; adjusted TB; QST worksheet; GIFI/T2 export; draft bills from OCR with per-field confidence.

**5. What are the business rules?** Every stock movement and every finance/asset event posts through the single posting engine and balances; inventory GL = valuation report at all times; negative stock blocked unless back-ordering is enabled for the item/location; costing is moving average by default, FIFO optional per organisation (change only at a fiscal-year boundary); services never touch stock; a serial number exists in one location at a time; EOQ and KPI formulas are **data supplied by the client**, stored versioned, never hard-coded; what-if scenarios never change live prices until "Apply" is confirmed and audited; loan schedules match a reference calculator to the cent and past (posted) payments are never recalculated; loan liability in GL = schedule balance after each payment; CCA is discretionary 0…maximum per class per year, half-year rule and AII per class data, posts to the tax book only; accounting book never changed by tax adjustments; accounting NI − tax adjustments = tax NI; T2 rates are effective-dated data; FX rate used = rate on the document date; OCR suggestions always require human confirmation; Inventory/Finance/Tax features are gated by entitlement with explicit prompts, never silent redirects.

**6. What could go wrong?** Moving-average cost corrupted by back-dated receipts; FIFO layers mismatching GL after a revision of an invoice that sold stock (D-03b interaction); concurrent issues driving stock negative; UoM conversion rounding (boxes of 12 vs units); landed-cost allocation leaving pennies; analytics on stale snapshots; EOQ with zero demand or zero holding cost (division by zero); client formula not supplied by Phase 2 start; scenario applied to wrong price list; loan rounding drift over 60 payments; rate change mid-period; early repayment on a non-payment date; interest accrual crossing a lock date; FN-04 double-posting a discount already handled by E-07; CCA half-year applied twice; disposals exceeding UCC (recapture) mis-classified; tax book drifting from accounting book; T2 rate table year mismatch; FX revaluation reversing twice; OCR mis-reading tax amount; performance of rankings on 100k+ lines; Sheets formula cycles.

**7. What is the smallest useful implementation?** One tracked item with a base UoM in one location, received on a GRN and sold on an invoice with moving-average COGS posted; one 5-year car loan with a monthly schedule posting principal/interest; one Class 8 asset with SL book depreciation and a discretionary CCA claim in the tax book; and a side-by-side accounting vs tax P&L with the computed tax line. Every other Phase 2 feature extends these four skeletons.

### 1.3 Restated objective

- **Currently:** Numo9 runs core books (ledger, sales with revisions, purchases with PO/GRN, never-locked banking, tax engine, core reports) in the accounting book only. There is no inventory, no fixed assets, no finance module, no tax book content, no multi-currency, no projects, no working papers. Xero (teardown §2.10, §5.10) blocks inventory behind CoA typing and has no UoM/locations/costing/BOM, no CCA tax book, an asset module unusable until a start date is set, and no loan or credit-terms handling.
- **Change:** Build Inventory (H-01…H-08) and Inventory Analytics & Profit Optimisation (H-09…H-13), the Finance module (FN-01…FN-05), Fixed Assets & CCA (I-01…I-05), Projects & Time (J-01…J-03), Sheets (L-01…L-04), Multi-currency (R-01, R-02), budgets, management pack, the two-book engine, tax-purpose statements, adjusted TB (K-04, K-06, K-07, K-08, K-10), QST return, GIFI/T2 export, corporate tax computation (G-04, G-07, G-08) and OCR capture (E-05).
- **Why:** These are the modules Profitex's clients need beyond Xero (client decisions 7, 8, 9 and the ★ additions of 27 Oct 2026), and they are the commercial reason Inventory and Finance are separate products in the package model.
- **Done means:** every Phase 2 acceptance criterion in Project_Phases.md is observed, and the exit demonstration runs on staging: SKU / margin dashboards; EOQ reorder → PO; loan schedule posted with principal / interest / YTD; full-CCA-as-loss; accounting vs tax statements with computed tax.

### 1.4 Assumptions & interpretations

1. **Costing method** is chosen per organisation (moving average default, FIFO optional); a change is allowed only effective the first day of a fiscal year and is audited (CRA expects a consistent method).
2. **Landed cost** (freight, duty, brokerage) is allocated by value by default, by quantity or weight optionally, from a bill line flagged "landed cost" against one or more GRNs.
3. **Back-ordering** is a per-item flag with an organisation default of "off"; when on, negative on-hand is allowed only for sales documents, never for adjustments or transfers.
4. **Analytics** (H-09…H-13) read from posted sales and COGS lines (the current invoice revision only, per D-03b) and from stock movements; heavy aggregates are materialised nightly and on demand, with an "as of" timestamp shown on every widget.
5. **EOQ equation**: the client's equation is supplied by the start of Phase 2 (Agreement 9.1(b)). Until it arrives the engine ships with the classical Wilson EOQ √(2DS/H) registered as the **default** formula and a safety-stock formula (z × σ_d × √L) — both stored as versioned formula records, replaceable by the client's without code change. The acceptance fixture "EOQ output = client's worked example" is a placeholder test marked `xfail(reason="awaiting client EOQ example")` until the example is received; it is never reported as passed before then.
6. **Management-accounting KPIs** (H-13, FN-05) are loaded from the client's material as formula records in a pluggable **Formula Registry** (safe expression language, no `eval`). Until the material arrives, a starter set (gross margin %, contribution margin %, inventory turnover, days inventory outstanding, GMROI, sell-through %, debt-service coverage, interest coverage, effective annual cost of forgoing a discount) is seeded and clearly labelled "Numo9 default — replace with client formula".
7. **Loans**: nominal annual rate with a compounding frequency (Canadian mortgages compound semi-annually by convention; vehicle/equipment loans usually monthly) and a payment frequency; the effective periodic rate is derived from both. Payment types: blended (annuity), fixed-principal, interest-only, with optional balloon. Leases recorded as "lease-type financing" use the same engine (ASPE 3065 capital-lease style); the plan does not implement IFRS 16 right-of-use accounting beyond that.
8. **FN-04** extends, never duplicates, E-07 (discount capture) and D-07 (late-fee line): the terms master in B-01 remains the single source of truth for terms; FN-04 adds interest accrual, cost-of-forgoing calculation and supplier-interest bills.
9. **Tax book** content is created only by `tax_adjustment` journals (book = `tax`) and accounting-only journals (book = `accounting`); everything else is `both` (K-07).
10. **T2 rates** (federal general 15 %, SBD rate 9 % on the first $500,000, provincial rates) are effective-dated data entered and confirmed by the accountant; the software computes, it does not advise (Agreement 15.1).
11. **OCR provider** is pluggable (`ExtractionProvider` interface); the default on-server implementation (Tesseract + layout heuristics) ships first; a paid provider is added only if the client elects it (fees are the client's, Quotation §6).
12. **Exchange rates** come from the Bank of Canada Valet API (daily CAD rates) as the default provider; manual override per date is allowed and audited.

Open questions for the client (do not block coding; each has a default above): EOQ equation and worked example; KPI formula list; whether founding organisations' Finance product is visible to existing trial organisations; preferred landed-cost allocation basis.

### 1.5 Client inputs required (Agreement 9.1(b): no later than the start of Phase 2)

| Input | Used by | If late |
|---|---|---|
| Depreciation templates and methods (SL/DB rates, class list, conventions) | I-01, I-02, I-04 | Schedule II defaults used; I-04 acceptance waits; timeline extends per Agreement 6.3 |
| EOQ equation and parameters with a worked example | H-11 | Wilson EOQ default; acceptance test held `xfail` |
| Management-accounting material (inventory, pricing and finance KPIs/formulas) | H-12, H-13, FN-04, FN-05 | Default KPI set labelled as default; acceptance waits |
| Reference loan calculator choice (or worked loan examples) | FN-02 | Plan uses standard annuity maths cross-checked against two published calculators |
| T2 fixture corporation with known result | G-08, K-08 | GMA builds a fixture, client confirms |
| Sample QST return | G-04 | Built from FPZ-500 line definitions |

---

## 2. BETTER THAN XERO — gap analysis for Phase 2

### 2.1 Teardown gaps closed in this phase

| Gap # | Teardown ref | What Xero does / fails to do | What Numo9 does instead (better) | Observable proof (test tag) |
|---|---|---|---|---|
| 11 | §2.3 | No multi-currency on the inspected plan; Currency field absent | Multi-currency is part of the Accounting product: currency per contact, foreign invoices/bills/bank accounts, daily Bank of Canada rates, realised/unrealised FX | `gap-11`: USD invoice to US customer posts CAD at document-date rate; revaluation posts unrealised FX |
| 18 | §2.10 | Inventory tracking blocked because no Inventory-type account; no UoM, categories, SKU/barcode, price lists, costing, locations, reorder, lot/serial, BOM | Inventory account auto-created on first tracked item; all of UoM, categories, SKU + barcode separate from code, price lists + customer pricing, moving-average/FIFO + landed cost, locations, reorder points, batch/serial/expiry, BOM | `gap-18`: fresh org creates tracked item with no CoA setup; every listed capability has a test |
| 20 | §3.2 | No contact currency | Currency per contact drives document currency default (R-01) | `gap-20` (shared with B-01) |
| 30 | §5.5 | 0 of 139 accounts mapped to GIFI; period confusion | GIFI mapping editor with "unmapped" counter that must reach 0 before export; one balance basis (tax-book TB) | `gap-30`: GIFI export balances to tax-book TB |
| 32 | §5.7 | Documents page slow; no period tagging; no OCR confidence | Inbox list virtualised (< 1 s for 5,000 files); OCR shows per-field confidence chips; every suggestion needs confirmation | `gap-32`: confidence visible per field; ≥ 80 % accuracy on fixtures |
| 34 | §5.10 | Fixed assets unusable until a start date; hard 404; no CCA tax book; register not linked to CoA | Register opens immediately (conversion date default); SL/DB; Schedule II classes; CCA in the tax book; register ties to GL asset accounts | `gap-34` (Part 2 cards) |
| 46 | §6.10 | No tracking hierarchy | Projects (J) act as a hierarchical dimension on lines; budgets by project/account | `gap-46` (with K-01) |
| 49 | §6.14 | Report basis and tax basis on different pages | Book selector + one basis setting; tax book reports read the same setting | `gap-49` |
| 51 | §7 | Projects, Expenses, document capture are paid add-ons | Projects & time and OCR capture included in the Accounting product (no add-on) | `gap-51`: feature matrix shows them under Accounting |
| 54 | §9.1 | No sales-tax report; two report engines | QST worksheet in the same engine as GST/HST; one report engine | `gap-54` |
| 57 | §9.4 | No adjusted TB | Adjusted TB with proposed-adjustment columns posting to a chosen book | `gap-57` |

### 2.2 Beyond-Xero additions in this phase (Xero has nothing equivalent)

| Addition | Deliverables | Why it matters to a Canadian practice |
|---|---|---|
| Best-selling SKU rankings by quantity, revenue and margin | H-09 | Owners see what actually makes money, not just what sells |
| Sales velocity, days of cover, dead / slow stock | H-10 | Cash tied in stock becomes visible |
| EOQ reorder engine with client formula and one-click PO | H-11 | Replaces spreadsheet reorder planning |
| Contribution-margin pricing with what-if scenarios and bulk apply | H-12 | Price decisions modelled before they hit the price list |
| Management-accounting KPI dashboard from client formulas | H-13 | Profitex's own methodology embedded in the product |
| Loan register, amortisation schedule, auto-posting of principal/interest | FN-01…FN-03 | Removes the most common manual journal in small-business books |
| Credit-terms interest: discounts, late interest, cost of forgoing a discount | FN-04 | Quantifies the true cost of paying suppliers late |
| Loan and finance reports in both books | FN-05 | Interest deductibility visible in the tax book |
| Two-book engine, tax-purpose BS/IS with computed tax | K-07, K-08, G-08 | Client decision 7 |
| Discretionary CCA incl. full-CCA-as-loss | I-03 | Client decision 9 |
| Working papers linked to the GL by book | L-01…L-04 | Removes CaseWare-style exports for small files |

### 2.3 Xero strengths matched conceptually (original design, never copied)

| Xero does well | Numo9 equivalent (original) |
|---|---|
| Per-org inbound email + AI extraction for bills | E-05 with per-field confidence and mandatory confirmation |
| Inventory item list / summary reports | H-07 valuation, movement, aging, stock-take with drill-down to the stock card |
| Report layout editor and adviser templates | K-06 management pack and NTR / Compilation / Review templates in Numo9 wording |
| Budget manager | K-04 budgets with variance and import from XLSX |

### 2.4 [EXTRA] improvements beyond the gap report (inside Schedule A scope — refinements, not new modules)

| # | Improvement | Lands in |
|---|---|---|
| X1 | Barcode scanning through the device camera on any stock screen (web `BarcodeDetector` with ZXing fallback) | H-01, H-03, H-04 |
| X2 | "Why this cost?" panel on each stock card line showing the moving-average or FIFO layer arithmetic | H-05 |
| X3 | Stock-take mode on a phone-width layout with blind count (system quantity hidden) and variance approval | H-07 |
| X4 | Reorder suggestions grouped by supplier, merged into one draft PO per supplier | H-11 |
| X5 | Price-scenario "guard rails": warn when a scenario price falls below landed cost or below the minimum margin set by the owner | H-12 |
| X6 | KPI cards show the formula, the inputs and the period in a hover/press explainer so owners trust the number | H-13, FN-05 |
| X7 | Loan "what if I pay extra $X per month?" slider showing interest saved and new payoff date before committing | FN-02 |
| X8 | Loan statement import: match a lender statement to the schedule and flag differences | FN-03 |
| X9 | Supplier "pay now or later" helper on bills with an early-payment discount: shows the annualised cost of waiting | FN-04 |
| X10 | Dead-stock action list: one click to create a markdown price scenario or a write-down adjustment draft | H-10, H-12 |
| X11 | Every analytics widget exports the exact rows behind it (CSV/XLSX) | H-09…H-13, FN-05 |
| X12 | Inventory GL vs valuation tie-out check added to the exceptions engine (K-09 rule `inventory_gl_mismatch`) | H-04 |
| X13 | Loan liability vs schedule tie-out check added to the exceptions engine (K-09 rule `loan_schedule_mismatch`) | FN-03 |
| X14 | Current / long-term split of each loan (principal due within 12 months) for GAAP balance-sheet presentation | FN-05 |

---

## 3. UI/UX DESIGN PLAN

### 3.1 UX principles applied in this phase

1. **Task-first navigation**: Inventory, Finance and Assets appear as top-level sections only when the organisation's package includes them; otherwise they appear once in the navigation with an explicit "Included in package X — view packages" card (U-03), never a silent redirect (gap #14, #41).
2. **One grid, one form language**: item lines on invoices, bills, POs, GRNs, adjustments, transfers and BOMs all use `@numo9/ui` `DocumentGrid`; numbers right-aligned, tabular figures, currency code shown when it differs from CAD.
3. **Progressive disclosure**: an item starts with four fields (name, type, price, tax code); SKU, barcode, UoM, costing, batch/serial, reorder and EOQ parameters live in collapsible sections with sensible defaults. A loan starts with the five numbers on the lender's paper (amount, rate, term, frequency, first payment date); compounding, balloon and fees are under "More terms".
4. **Explain every number**: analytics, KPIs, amortisation lines and stock costs carry an `ⓘ Explain` popover showing formula, inputs, period and source rows (X2, X6).
5. **Preview before commit**: price scenarios, bulk price updates, depreciation runs, loan postings, CCA claims, FX revaluations and imports show a preview with totals and affected rows before "Apply"; "Apply" is the only state-changing click and it is audited.
6. **Undo over confirm where safe**: draft stock adjustments, draft scenarios and draft schedules can be discarded freely; posted entries are reversed (never deleted) through a single "Reverse" action with a reason.
7. **Forgiving inputs**: quantities accept "2 box" or "24" with UoM parsing; rates accept "6.5", "6.5%" or "0.065"; dates accept typed `2026-11-07`, `7 Nov 2026` or `+30`.
8. **Keyboard-first for accountants**: every list supports `/` search, `j/k` row navigation, `Enter` open, `n` new; grids support `Tab`, `Shift+Tab`, `Ctrl+D` duplicate line, `Ctrl+Enter` save; shortcuts listed in the `?` help overlay.
9. **Speed budgets**: list screens interactive < 1 s at 10,000 items; analytics widgets < 1.5 s from the nightly snapshot; schedule recalculation < 300 ms for 360 payments (client-side preview, server-confirmed).
10. **Accessibility**: WCAG 2.1 AA; charts have a data-table alternative and patterns, not colour alone; focus order matches visual order; all icons labelled; 44 px touch targets on stock-take and capture screens.
11. **Localisation-ready**: every string is an ICU key (`inventory.item.form.sku.label`); layouts tested with +30 % pseudo-locale strings; dates and money via the locale formatter (en-CA now, fr-CA in Phase 6); Canadian terms only ("cheque", "organisation", "GST/HST", "Province").
12. **Empty states that teach**: a fresh organisation sees "No items yet — add your first item, import a list, or scan a barcode", with the action buttons; analytics with no sales show `0` and "No sales in this period", never "—k" (gap #4).
13. **Responsive**: owner-facing analytics and loan screens are fully usable at 375 px; accountant grids are optimised for ≥ 1280 px and degrade to card lists on small screens.
14. **Brand**: Numo9 yellow/black identity applied through design tokens only; analytics palette from the dataviz-validated categorical scale with sufficient contrast on both themes.

### 3.2 Information architecture added in this phase

```
Top navigation (shown per entitlement)
├── Inventory                    [inventory.*]
│   ├── Items                    (list / item detail with tabs: Overview · Stock · Pricing · Suppliers · Movements · Analytics)
│   ├── Stock                    (On hand by location · Movements · Adjustments · Transfers · Stock-takes · Assemblies)
│   ├── Price lists
│   ├── Reorder                  (Suggestions · EOQ parameters)
│   ├── Analytics                (Best sellers · Movement & cover · Margins & pricing · Scenarios · KPIs)
│   └── Inventory settings       (costing method · locations · units · categories · back-ordering · formula versions)
├── Finance                      [finance.*]
│   ├── Loans                    (list / loan detail with tabs: Summary · Schedule · Payments · Postings · Documents)
│   ├── Credit terms & interest  (Discounts captured · Discounts missed · Interest charged · Interest received)
│   ├── Finance reports & KPIs
│   └── Finance settings         (default accounts · accrual policy · formula versions)
├── Accounting
│   ├── Fixed assets             (Part 2: I-01…I-05)
│   ├── Projects & time          (Part 2: J-01…J-03)
│   └── Sheets                   (Part 2: L-01…L-04)
├── Reporting                    (book selector everywhere; Book reconciliation; Tax statements; Budgets; Management pack)
└── Tax                          (QST return; GIFI & T2 export; Corporate tax computation)
Quick-create additions: Item (Alt+Shift+I), Stock adjustment (Alt+Shift+A), Stock transfer (Alt+Shift+T), Loan (Alt+Shift+L), Asset (Alt+Shift+F)
Global search additions: items (name, SKU, barcode), batches/serials, locations, loans (lender, reference), assets, projects, sheets
```

### 3.3 Screen inventory (whole phase)

| Screen | Primary user | Purpose | Key components | States | Keyboard |
|---|---|---|---|---|---|
| Items list | Accountant / owner | Find, filter, bulk-edit items | `DataTable` with column chooser, saved views, category tree filter, stock badges | empty (teaching), loading skeleton, gated, read-only (downgraded) | `/` search, `n` new, `j/k`, `x` select |
| Item detail / editor | Accountant / purchasing | Create and maintain an item | `FormSection`, `MoneyInput`, `UnitPicker`, `AccountPicker` filtered by type, `TaxCodePicker` filtered by side, image dropzone, barcode field with camera scan | draft, saved, archived, has-stock (type locked) | `Ctrl+Enter` save, `Esc` cancel |
| Units of measure | Accountant | Define units and conversions | inline editable table, conversion tester ("2 box = 24 each") | empty, validation error | `Tab` |
| Locations | Accountant | Warehouses / bins | tree list | empty | |
| On hand | Warehouse / owner | Stock by item × location | pivot `DataTable`, low-stock chips | zero-stock, negative (back-order) highlighted | |
| Stock card | Accountant | Movement history with running qty and cost | ledger-style table, "Why this cost?" explainer | | |
| Adjustment / transfer editor | Warehouse | Record count differences / moves | `DocumentGrid` with item, location, batch/serial, qty, reason | draft, posted, reversed | `Ctrl+D` |
| Stock-take (mobile-friendly) | Warehouse | Blind count by location | large-touch list, scan, numeric keypad | in progress, submitted, approved | |
| Assembly build | Warehouse | Build finished goods from BOM | BOM preview, component availability check | insufficient components (explains which) | |
| Price lists | Owner / accountant | Manage price lists and customer assignment | grid with bulk % change preview | | |
| Reorder suggestions | Purchasing / owner | Review and create POs | grouped-by-supplier table, EOQ explainer, "Create POs" | no suggestions (all healthy) | `Space` select, `p` create PO |
| EOQ parameters | Accountant | Per-SKU demand, ordering/holding cost, safety stock, lead time | grid with "derive from history" button | formula version banner | |
| Best sellers | Owner | Rank SKUs | segmented control (qty / revenue / margin), period picker, bar chart + table | no sales | |
| Movement & cover | Owner | Velocity, days of cover, dead/slow | sortable table with traffic-light cover, action buttons | | |
| Margins & pricing | Owner | GP, CM, margin % by SKU / category / location | pivot table + waterfall chart (revenue → variable cost → CM) | | |
| Price scenario editor | Owner | What-if price changes | side-by-side current vs scenario, elasticity input, guard-rail warnings, "Apply to price list" | draft, applied, discarded | |
| KPI dashboard | Owner / accountant | Client KPI set | `StatTile` grid with explainers, period compare | default-formula badge until client formulas loaded | |
| Loans list | Owner / accountant | All financing | table with balance, next payment, rate, status | empty teaching state | `n` new |
| Loan editor | Accountant / owner | Register a loan | five-field quick form + "More terms", live schedule preview | validation errors explain fix | `Ctrl+Enter` |
| Loan detail | Owner | Schedule, payments, postings | tabs, amortisation chart (principal vs interest), YTD interest tile, extra-payment slider | paid off, in arrears | |
| Rate change / early repayment dialog | Accountant | Recalculate from a date | before/after schedule diff | | |
| Credit terms & interest | Accountant / owner | Discounts captured/missed, interest charged | tables + cost-of-forgoing explainer | | |
| Finance reports & KPIs | Accountant | Loan continuity, interest by book, KPIs | report engine with book selector | | |
| Asset register, depreciation run, CCA schedule, disposals | Accountant | Part 2 | | | |
| Projects, timesheets, timer | Staff | Part 2 | | | |
| Sheets editor | Accountant | Part 2 | | | |
| Currencies & rates | Accountant | Part 2 | | | |
| Budgets, management pack, book reconciliation, tax statements, adjusted TB | Accountant | Part 2 | | | |
| QST return, GIFI & T2 export, corporate tax computation | Accountant | Part 2 | | | |
| Capture review (OCR) | Accountant / owner | Confirm extracted bill | split view: document left, form right, confidence chips per field | low-confidence fields highlighted | `Tab` through low-confidence first |

### 3.4 Key user flows (with targets)

**F1 — First tracked item to first COGS (target ≤ 3 minutes, ≤ 12 clicks)**
1. Inventory → Items → "Add item" (or `Alt+Shift+I`).
2. Enter name, choose "Tracked stock item"; Numo9 shows "An Inventory asset account (1500 Inventory) and a COGS account (5000 Cost of goods sold) will be created" with an editable preview — no CoA prerequisite (gap #18).
3. Enter sale price and cost; tax codes default from organisation province (G-02).
4. Save → item detail shows "0 on hand — receive stock".
5. Purchases → PO → GRN (from E-01) receives 10 → stock card shows 10 at cost.
6. Sales → invoice sells 4 → on approval, COGS posts at moving average; item Overview shows "6 on hand · margin 38 %".

**F2 — Reorder with EOQ (target ≤ 1 minute)**
1. Inventory → Reorder → Suggestions (badge shows count).
2. Rows grouped by supplier show on hand, reorder point, EOQ, suggested qty, "ⓘ" explainer of the formula.
3. Select rows (`Space`) → "Create draft POs" → one PO per supplier opens in a review drawer → "Submit for approval".

**F3 — Price what-if (target ≤ 2 minutes)**
1. Analytics → Margins & pricing → select SKUs → "Model a price change".
2. Enter "+5 %" or a target margin; set expected volume change (elasticity) or leave at 0.
3. Scenario shows current vs projected revenue, variable cost, contribution margin, profit; guard rails flag any price below landed cost.
4. "Apply to price list" → preview of changed prices → confirm → audited; live prices unchanged until this point.

**F4 — Register a car loan (target ≤ 90 seconds)**
1. Finance → Loans → "Add loan" (`Alt+Shift+L`).
2. Type: Vehicle loan; lender (contact); amount 35,000; rate 6.99 %; term 60 months; monthly; first payment 1 Dec 2026.
3. Live schedule preview: payment 692.88, total interest, payoff date.
4. Choose or auto-create liability account "2610 Vehicle loan — <lender>" and interest expense account; choose paying bank account.
5. Save → schedule stored; first payment auto-posts on its date (or on matching bank transaction), dashboard shows YTD interest.

**F5 — Pay now or later (supplier bill with 2/10 net 30)**
1. Bill detail shows "Pay by 17 Nov to save $40.00 (2 %). Waiting until 7 Dec costs the equivalent of 37.2 % a year (2 ÷ 98 × 365 ÷ 20)."
2. Pay inside the window → discount posts automatically (E-07); pay late → no discount; if supplier charges interest, FN-04 accrues it.

### 3.5 Microcopy & error-message rules

Rules: plain language; say what happened, why, and how to fix; name the record and the number; never blame the user; never use "invalid" alone; no Xero wording.

| Situation | Message |
|---|---|
| Issue would make stock negative | "Only 6 units of SKU CH-100 are in Main Warehouse. Reduce the quantity to 6, choose another location, or turn on back-ordering for this item." |
| UoM conversion not defined | "Numo9 doesn't know how many 'each' are in a 'box' for this item. Add the conversion under Units (for example 1 box = 12 each)." |
| Costing method change mid-year | "Costing method can only change from the first day of a fiscal year. Choose 1 Jan 2027 or later." |
| Serial already in stock elsewhere | "Serial SN-4471 is already in Montréal Store. Transfer it first, or pick a different serial." |
| EOQ cannot compute | "EOQ needs a holding cost above zero for SKU CH-100. Enter the yearly holding cost per unit, or set it as a % of cost in Reorder settings." |
| Scenario price below landed cost | "At $18.00, SKU CH-100 would sell below its landed cost of $19.40. Save anyway or adjust the price." |
| Loan schedule mismatch | "The lender's statement shows a balance of $33,912.40, but the schedule shows $33,910.15 after the 1 Mar payment. Review the payment or record a rate change." |
| Posting into a locked period | "The GL is locked up to 30 Sep 2026, so this depreciation can't post on 30 Sep. Post it on 1 Oct or ask an adviser to change the lock date." |
| Gated feature | "Price optimisation is part of the Inventory product. Your package (Starter) includes Accounting and Tax. See packages." |

### 3.6 Accessibility & usability test plan

| Usability task (5 owners + 5 accountants, moderated, staging) | Success metric |
|---|---|
| Create a tracked item and receive stock without help | ≥ 9/10 succeed; median ≤ 3 min |
| Explain why COGS on the last sale was $X using the stock card | ≥ 8/10 explain correctly using "Why this cost?" |
| Create POs from reorder suggestions | ≥ 9/10; ≤ 60 s |
| Model a 5 % price rise and tell whether profit rises | ≥ 8/10 correct |
| Register a 60-month car loan from a lender letter | ≥ 9/10; schedule payment matches letter |
| Find total interest paid this year on all loans | ≥ 9/10 within 30 s |
| Complete a stock-take on a phone | ≥ 8/10; no mis-taps reported |

Automated: axe-core on every new screen in Playwright (0 serious/critical violations); keyboard-only path test for F1–F4; Lighthouse accessibility ≥ 95 on analytics pages; chart data-table alternative present (test asserts `role="table"` sibling); pseudo-locale (+30 %) screenshots reviewed in Chromatic.

---

## 4. TOOLS & TECHNOLOGY FOR THIS PHASE

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| Backend core | Python 3.12, Django 5, Django REST Framework | Models, services, API | Existing stack |
| Money & maths | `decimal.Decimal` (context precision 28, `ROUND_HALF_UP` at posting), `py-moneyed` | All monetary arithmetic; never float | Rounding policy in `numo9.money` |
| Financial maths | `numpy-financial` (pmt, ipmt, ppmt, rate) for cross-checks; own Decimal amortisation engine for production | FN-02 schedule; tests compare to numpy-financial within 0.005 | MIT licence |
| Dates & recurrence | `python-dateutil` (`relativedelta`, `rrule`) | Loan payment dates, depreciation periods, accrual dates, business-day rolling | |
| Formula engine | `asteval`-style sandbox replaced by an own AST-whitelisted evaluator (`numo9.formulas`) built on Python `ast`; `simpleeval` as reference | Client EOQ/KPI formulas stored as data, safe evaluation | No `eval`; whitelist of operators and functions (`sqrt`, `min`, `max`, `abs`, `round`, `ln`, `exp`, `norm_ppf`) |
| Statistics | `scipy.stats` (`norm.ppf` for service-level z), `statistics` stdlib | Safety stock, demand σ | Only in analytics workers |
| Data processing | `pandas` (analytics workers only), PostgreSQL window functions, materialised views | Rankings, velocity, cover | Production queries use SQL; pandas for exports and tests |
| Async jobs | Celery 5, Redis, celery-beat, `django-celery-results` | Nightly snapshots, reorder alerts, loan accruals, depreciation runs, FX fetch, OCR | Existing |
| Concurrency | PostgreSQL `SELECT … FOR UPDATE`, advisory locks, `django-pgtrigger` | Stock level row locks; append-only movement tables | |
| Partitioning | Postgres declarative partitioning (by `organisation_id` hash) via `django-postgres-extra` or raw migrations | `StockMovement`, `LoanScheduleLine` large tables | S-06 baseline |
| Spreadsheet I/O | `openpyxl`, `XlsxWriter`, `tablib` | Item import/export, EOQ parameter import, template import (I-04), report exports | |
| Barcodes | `python-barcode`, `qrcode` (labels); browser `BarcodeDetector` + `@zxing/browser` fallback (scan) | Item labels, scan on stock screens | X1 |
| PDF | WeasyPrint | Amortisation schedule PDF, stock-take sheets, valuation report | Letter, inch margins |
| OCR (E-05) | Tesseract 5 + `pytesseract`, `pdfplumber`, `pdf2image`, OpenCV (deskew) ; pluggable cloud provider adapter | Bill extraction | Part 2 card |
| FX rates (R-01) | Bank of Canada Valet API client (`httpx`) | Daily rates | Part 2 card |
| Frontend core | Next.js 15 App Router, TypeScript, React Query, Tailwind, `@numo9/ui` | All screens | Existing |
| Forms | React Hook Form + Zod | Item, loan, scenario forms | Zod schemas generated from OpenAPI |
| Grids | TanStack Table + TanStack Virtual; AG-Grid not used (licence) | Items list, on-hand pivot, schedule table | Virtualised for 10k rows |
| Charts | Recharts (or visx) themed via design tokens | Best sellers, waterfall, amortisation, cover | Data-table fallback |
| Number formatting | `Intl.NumberFormat`, `@formatjs/intl` (ICU) | en-CA / fr-CA money and percentages | |
| API types | `drf-spectacular` → OpenAPI 3 → `openapi-typescript` | Typed clients | Contract tests |
| Design / prototyping | Figma (Numo9 library), FigJam (flows), Storybook 8 with interaction tests, Chromatic | Wireframes, component states, visual regression | Each screen has a story per state |
| Testing — backend | pytest, pytest-django, factory_boy, Hypothesis (property tests), freezegun / time-machine, pytest-xdist, coverage.py | Unit, property (on-hand = Σ movements; GL inventory = valuation; loan balance = schedule) | Coverage ≥ 85 % on `inventory`, `finance` |
| Testing — frontend | Vitest, Testing Library, MSW (API mocks), Playwright (E2E), axe-core/playwright | Component and flow tests | |
| Testing — performance | k6, Django Silk / `django-debug-toolbar` in dev, `EXPLAIN ANALYZE` snapshots, Lighthouse CI | Analytics < 1.5 s, list < 1 s, scenario < 300 ms | |
| Testing — data | Own reconciliation scripts (`manage.py tieout_inventory` / `tieout_loans` / `tieout_books`) | Release gates | Built in this phase |
| Quality | ruff, black, mypy (strict on `inventory`, `finance`), eslint, prettier, pre-commit, import-linter (module boundaries: `inventory` may not import `payroll`), semgrep (no float money, no raw SQL without org filter) | Static checks | |
| Security | OWASP ZAP baseline, pip-audit, npm audit, gitleaks, Trivy (images), tenant-isolation sweep, entitlement-leak sweep | CI gates | |
| Observability | Sentry (backend + frontend), Prometheus + Grafana dashboards (job durations, snapshot freshness), structured logs (structlog) | Monitor analytics jobs and posting errors | |
| Docs | MkDocs Material in `docs/`, ADR template (`docs/adr/NNN-title.md`), OpenAPI docs, data dictionary generator (`django-extensions graph_models` + custom) | ADR-005 costing, ADR-006 formula registry, ADR-007 loan engine | |
| Dev productivity | Docker Compose, Makefile targets, mailpit, MinIO, Stripe CLI (not used this phase), `django-extensions` shell_plus, `just` recipes, GitHub Codespaces devcontainer | Local dev | |
| Reference calculators (verification only) | Government of Canada (FCAC) loan calculator, numpy-financial, an Excel `PMT/IPMT` workbook kept in `tests/fixtures/finance/` | FN-02 acceptance | Not shipped |
| **Internal tools built in this phase** | `manage.py seed_inventory_fixture` (500 SKUs, 3 locations, 2 years of movements); `manage.py seed_finance_fixture` (car loan, equipment loan, LOC, shareholder loan); `manage.py tieout_inventory` (GL vs valuation per org); `manage.py tieout_loans` (GL vs schedule); `manage.py rebuild_cost_layers --org` (repair tool, dry-run default); `manage.py snapshot_analytics --org --date`; Formula Registry admin (versioned formulas, test console with sample inputs); dev dashboard page `/internal/analytics-freshness`; Hypothesis strategies package `tests/strategies/inventory.py`, `finance.py`; Storybook fixtures for analytics widgets | Repeatable fixtures, release gates, support | Each is an atomic task in §6 |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 — Objective

Deliver Numo9's operations and finance layer — inventory with analytics and profit optimisation, the finance module, fixed assets with CCA, projects and time, working papers, multi-currency — and the two-book reporting and tax layer (tax book, tax-purpose statements with computed tax, adjusted TB, QST, GIFI/T2, OCR capture), all posting through the one ledger and reconciling to the cent.

### 5.2 Level 2 — Components

| Component | Deliverables | Purpose |
|---|---|---|
| H — Inventory & Quantity Management | H-01, H-02, H-03, H-04, H-05, H-06, H-07, H-08 | Items, units, locations, movements, costing, batch/serial, reorder, assemblies |
| H [v2.1] — Inventory Analytics & Profit Optimisation | H-09, H-10, H-11, H-12, H-13 | Rankings, movement analysis, EOQ, margin & price optimisation, KPIs |
| FN [v2.1] — Finance module | FN-01, FN-02, FN-03, FN-04, FN-05 | Loans, schedules, posting, credit-terms interest, reports & KPIs |
| I — Fixed Assets & CCA | I-01, I-02, I-03, I-04, I-05 | Register, SL/DB, discretionary CCA, templates, disposals |
| J — Projects & Time | J-01, J-02, J-03 | Projects, timesheets, billing |
| L — Sheets | L-01, L-02, L-03, L-04 | Working papers with GL functions |
| R — Multi-currency | R-01, R-02 | Rates, foreign documents, FX |
| K / G — Two-book reporting & tax | K-04, K-06, K-07, K-08, K-10, G-04, G-07, G-08 | Budgets, pack, two books, tax statements, adjusted TB, QST, GIFI, corporate tax |
| E — Purchases capture | E-05 | Inbound email + OCR |
| Shared foundation (this phase) | Formula Registry (built inside H-11-T01…T04, reused by H-13, FN-04, FN-05) | Client formulas as data |

### 5.3 Dependency graph and execution order

```
Phase 1 outputs (C ledger + book dimension, D/E docs, F banking, G tax, K engine)
   │
   ├── R-01 ── R-02 ───────────────────────────────────────────────┐
   │                                                               │
   ├── H-01 ── H-02 ── H-03 ── H-04 ── H-05 ─┬─ H-06              │
   │                                         ├─ H-07 ─┐            │
   │                                         └─ H-08  │            │
   │        Formula Registry (H-11-T01..T04) ─────────┤            │
   │                     H-09 ── H-10 ── H-11 ── H-12 ── H-13      │
   │                                                               │
   ├── FN-01 ── FN-02 ── FN-03 ─┬─ FN-04 (extends E-07, D-07)      │
   │                            └─ FN-05 (needs K-07 for tax book) │
   │                                                               │
   ├── K-07 two-book engine ─┬─ I-01 ── I-02 ── I-03 ── I-05       │
   │                         │          I-04 (after I-02)          │
   │                         ├─ K-10 ── K-08 ◄── G-08 ◄── I-03     │
   │                         ├─ G-07                               │
   │                         └─ L-01 ── L-02 ── L-03 ── L-04       │
   ├── J-01 ── J-02 ── J-03                                        │
   ├── K-04 ── K-06                                                │
   ├── G-04 (reuses G-03a cycle engine)                            │
   └── E-05 (A-06 inbox, E-02 bills) ◄─────────────────────────────┘
```

Execution order (parallel lanes run concurrently; a lane waits only on its listed prerequisites):

| Order | Lane A (inventory) | Lane B (finance / assets / books) | Lane C (other) |
|---|---|---|---|
| 1 | H-01 Items catalog | K-07 Two-book engine | R-01 Currencies & rates |
| 2 | H-02 Units of measure | FN-01 Loan register | J-01 Projects |
| 3 | H-03 Locations & on hand | FN-02 Calculator & schedule | R-02 Foreign documents & FX |
| 4 | H-04 Stock movements | FN-03 Loan posting | J-02 Timesheets |
| 5 | H-05 Costing | I-01 Asset register | J-03 Time & expense to invoice |
| 6 | H-06 Batch/serial (∥ H-07, H-08) | I-02 Book depreciation | G-04 QST return |
| 7 | H-07 Reorder & stock reports | I-04 Template importer | K-04 Budgets |
| 8 | H-08 Assemblies | I-03 Discretionary CCA | E-05 Receipt & bill capture |
| 9 | H-09 Best-selling rankings | I-05 Disposals | L-01 Grid editor |
| 10 | H-10 Movement analysis | FN-04 Credit-terms interest | L-02 GL functions |
| 11 | H-11 EOQ reorder (Formula Registry first) | K-10 Adjusted TB | L-03 Templates & versioning |
| 12 | H-12 COGS-to-profit & pricing | G-08 Corporate tax computation | L-04 Import/export |
| 13 | H-13 KPIs & dashboard | K-08 Tax-purpose BS & IS | K-06 Management pack |
| 14 | — | FN-05 Loan reports & KPIs | G-07 GIFI & T2 export |

Critical path: K-07 → I-01 → I-02 → I-03 → G-08 → K-08 (exit demo "accounting vs tax statements with computed tax"). Second critical path: H-01 → … → H-05 → H-09 → H-11 → H-12 (exit demo "SKU/margin dashboards; EOQ reorder → PO"). FN-01 → FN-03 is short and is used as a buffer lane.

---

## 6. PLAN — Deliverable cards with ATOMIC TASKS (Rule 3)

> Part 1 cards: H-01…H-13, FN-01…FN-05. Cards for I, J, L, R, K, G and E-05 follow in Part 2.
> Layer codes: DB (model/migration), BE (service/domain logic), API (endpoint/serializer/permission), FE (Next.js UI), UX (design/prototype/copy), QA (tests/fixtures), DOC (docs/ADR), OPS (jobs/infra/monitoring).
> Every task that adds an endpoint also: declares its feature key, registers in the tenant-isolation sweep, and emits audit events — these are listed explicitly where they are separate work.

---

### 6.1 Inventory & Quantity Management (Component H)

### H-01 · Items catalog

- **Branch:** `feature/H-01-items-catalog`
- **Objective:** one catalogue of goods and services that every sales, purchase and stock document draws from.
- **Current behaviour:** document lines take a free-text description, an account and a tax code; there is no item model. (Xero: item creation works but "Track inventory" is disabled until the CoA has an Inventory-type account; no SKU/barcode separate from code, no categories, no price lists — gap #18.)
- **Expected behaviour (better than Xero):** items of type *Tracked stock*, *Untracked stock* (non-inventory goods) and *Service*; code, SKU and barcode as three separate fields; hierarchical categories; multiple price lists (base, wholesale, retail…) and customer-specific prices; default sales/purchase/inventory/COGS accounts; default sales and purchase tax codes; images; supplier links (supplier SKU, last cost, lead time); creating the first tracked item auto-creates (or maps) the Inventory asset and COGS accounts with a preview — no CoA prerequisite.
- **Gap #s closed:** 18 (catalogue part), 7 (pickers filtered on item defaults).
- **Business rules:** SKU unique per organisation (case-insensitive, trimmed); barcode unique per organisation when present; code unique; service items never create stock movements; an item with stock or posted movements cannot change type from Tracked to anything else (archive instead); archived items hidden from pickers but kept on history; price precedence on a document = customer-specific price → contact's price list → base price list → item base price; prices are effective-dated (start/end) and stored in the price list's currency.
- **Edge cases:** duplicate SKU with different case ("ch-100" vs "CH-100"); barcode with leading zeros (store as string); an item whose default tax code later expires (G-01) → picker shows warning and suggests the replacement; price list in USD for a CAD contact (R-01 conversion at document date); deleting a supplier linked to items; images > 5 MB; 10,000-item import.
- **UI/UX notes:** progressive form (name, type, price, tax first; "Stock & costing", "Identifiers", "Suppliers", "Pricing" collapsible); type chooser with plain descriptions ("Tracked — Numo9 counts it and posts cost of goods sold"); account auto-create preview card; camera barcode scan button; list with category tree, stock badge, margin badge, column chooser and saved views; bulk edit (category, tax code, account, archive) with preview.
- **Dependencies:** C-01 (CoA), G-01 (tax codes), B-01 (contacts), U-03 (entitlement), A-10 (design system).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-01-T01 | Figma wireframes: items list, item editor (all sections), account-auto-create preview, empty state, bulk-edit drawer; review with project lead | UX | — | Frames approved and linked in PR | Design review |
| H-01-T02 | `ItemCategory` model (org-owned, parent FK, path/materialised path, name, sort) + migration; max depth 5 | DB | — | Migration applies; category tree query returns ordered path | Unit: tree ops, depth limit |
| H-01-T03 | `Item` model: code, name, description, type (tracked/untracked/service), sku, barcode, category FK, sales/purchase/inventory/cogs account FKs, sales/purchase tax code FKs, base sale price, base cost, is_sold, is_purchased, status (active/archived), image FK, custom_fields JSON; inherits `OrgOwnedModel` | DB | H-01-T02 | Migration applies; model registered in sweep | Unit: model validation |
| H-01-T04 | DB constraints: unique (org, lower(sku)), unique (org, lower(code)), partial unique (org, barcode) where barcode not null; check constraint type ∈ set | DB | H-01-T03 | Duplicate inserts raise IntegrityError | Unit: constraint tests incl. case variants |
| H-01-T05 | `ItemSupplier` model (item, supplier contact, supplier_sku, last_cost, currency, lead_time_days, min_order_qty, preferred flag; one preferred per item) | DB | H-01-T03 | Second preferred supplier rejected | Unit |
| H-01-T06 | `PriceList` (name, currency, tax-inclusive flag, is_default) and `PriceListItem` (price list, item, price, min_qty, valid_from, valid_to) + `ContactPriceList` assignment and `CustomerItemPrice` override | DB | H-01-T03, B-01 | Overlapping validity for same item/list/min_qty rejected | Unit: overlap validation |
| H-01-T07 | `PriceResolver` service: resolves price for (item, contact, date, qty, currency) by precedence; returns price + source label for the UI | BE | H-01-T06 | Fixture: customer price beats list beats base; qty break applies at min_qty | Unit + Hypothesis (random lists, precedence invariant) |
| H-01-T08 | `InventoryAccountProvisioner` service: on first tracked item, find existing Inventory-typed and COGS accounts or propose creation (1500 Inventory / 5000 COGS with GIFI 1121 / 8518 defaults); returns a preview, applies on confirmation; audited | BE | H-01-T03, C-01 | Fresh org: preview lists two accounts; confirm creates them; second item reuses them | Integration |
| H-01-T09 | Item type-change guard: block tracked→other when movements exist; archive instead; error message per §3.5 | BE | H-01-T03 | Attempt returns 409 with explanatory message | Unit |
| H-01-T10 | Item CRUD API `/api/v1/inventory/items/` (list with filters: type, category subtree, status, search on name/sku/barcode/code; detail; create; update; archive) with feature key `inventory.items`; serializer validation | API | H-01-T03…T09 | OpenAPI generated; 402 when package lacks Inventory (services remain available under `accounting.items_basic`) | Integration: happy + failure per endpoint |
| H-01-T11 | Category, supplier-link, price-list, customer-price APIs (`/categories/`, `/items/{id}/suppliers/`, `/price-lists/`, `/price-lists/{id}/items/`, `/contacts/{id}/prices/`) | API | H-01-T05, T06 | CRUD works; tenant sweep passes | Integration |
| H-01-T12 | Price resolution endpoint `/api/v1/inventory/prices/resolve` used by `DocumentGrid` on item select | API | H-01-T07 | Returns price + source in < 50 ms p95 | Integration + micro-benchmark |
| H-01-T13 | Item image upload via A-06 storage (5 MB limit, image MIME only, thumbnail generation 64/256 px) | BE/API | H-01-T10, A-06 | Oversize rejected with message; thumbnail served by signed URL | Integration |
| H-01-T14 | Register items, categories in global search (A-09) with SKU/barcode exact-match boost | BE | H-01-T10, A-09 | Searching a barcode returns the item first | Integration |
| H-01-T15 | Audit hooks: create/update/archive item, price changes (old/new), supplier link changes | BE | H-01-T10, A-04 | Audit viewer shows field diffs | Integration |
| H-01-T16 | Items list screen: `DataTable` with category tree filter, type/status chips, column chooser, saved views, stock/margin badges (placeholder until H-03/H-12), keyboard nav | FE | H-01-T10 | Story for empty/loading/data/gated/read-only; Playwright list test | Vitest + Playwright |
| H-01-T17 | Item editor: progressive sections, type chooser with descriptions, account and tax pickers filtered by side/type, account-auto-create preview card, unsaved-changes guard | FE | H-01-T10, T08 | F1 steps 1–4 pass in Playwright | Playwright + axe |
| H-01-T18 | Barcode field with camera scan (`BarcodeDetector` → `@zxing/browser` fallback), manual entry, duplicate warning while typing | FE | H-01-T17 | Scan of a test EAN-13 fills field; duplicate warns before save | Vitest (mock detector) |
| H-01-T19 | Price lists screen: list grid, item price grid with effective dates, assign to contacts, bulk % change with preview | FE | H-01-T11 | Bulk +5 % preview shows old/new; apply audited | Playwright |
| H-01-T20 | `DocumentGrid` integration: item column selects item → fills description, account, tax code, price from resolver; service items hide quantity-tracking hints | FE | H-01-T12, D-01 | Selecting an item on invoice and bill fills defaults | Playwright |
| H-01-T21 | Item import/export (CSV/XLSX) with column mapping, external ID / SKU matching, non-destructive updates, dry-run report (reuse B-03 import framework) | BE/FE | H-01-T10, B-03 | Re-import → 0 duplicates, 0 changes | Integration with fixture file |
| H-01-T22 | Bulk edit action (category, tax codes, accounts, archive) via V-03 job pattern with per-row result | BE/FE | H-01-T10 | 1,000 items updated, per-row result shown | Integration |
| H-01-T23 | i18n keys for all H-01 strings (`inventory.item.*`), pseudo-locale check | FE | H-01-T16…T19 | Missing-key gate passes; +30 % layout screenshot reviewed | CI i18n gate |
| H-01-T24 | Acceptance tests: SKU unique; services never affect stock (asserted after H-04 integration, test written now with skip-until marker removed in H-04-T14); price list applies per contact | QA | all | All pass in CI | pytest + Playwright, tag `gap-18` |
| H-01-T25 | Docs: item model in data dictionary; user guide page "Items and price lists" | DOC | all | Pages in `docs/` | Review |

- **Deliverable acceptance:** SKU unique; services never affect stock; price list applies per contact (Project_Phases.md). Added: first tracked item works on a fresh organisation without CoA setup; barcode search returns the item.
- **Testing approach:** unit (constraints, resolver precedence, provisioner), property (resolver precedence invariant), integration (APIs, import), functional (F1 up to save), security (tenant sweep, entitlement 402), accessibility (axe on list/editor).
- **Risks & mitigations:** price precedence confusion → resolver returns a source label shown on the line; import duplicates → SKU/external-ID matching only, never name; large catalogues → server-side pagination + indexes on (org, lower(sku)), (org, barcode), trigram index on name.

---

### H-02 · Units of measure

- **Branch:** `feature/H-02-units-of-measure`
- **Objective:** buy, stock and sell in different units with exact conversions.
- **Current behaviour:** quantities are unit-less numbers. (Xero: no unit of measure — gap #18.)
- **Expected behaviour:** organisation unit catalogue (each, box, case, kg, g, L, mL, m, hour…) seeded per locale; each item has a **base unit** (stock is always held in it), an optional default purchase unit and sales unit, and item-specific conversions (1 box = 12 each); global conversions for physical units (1 kg = 1,000 g); document lines record the entered unit and quantity plus the base-unit quantity; prices can be per entered unit.
- **Gap #s closed:** 18 (UoM part).
- **Business rules:** conversion factor > 0, stored as Decimal(18,6); base quantity = entered qty × factor, rounded to the item's quantity precision (default 4 dp) with residual tracked; base unit cannot change once movements exist; deleting a unit in use refused.
- **Edge cases:** conversion chains (case → box → each) resolved by path; circular conversions rejected; fractional units for each-based items (warn when base qty not integer for "each"); unit-price conversion (price per box ÷ 12 for per-each cost).
- **UI/UX notes:** inline unit picker in grid next to quantity; typing "2 box" parses; conversion tester widget in item editor ("2 box = 24 each"); unit list screen with in-use badges.
- **Dependencies:** H-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-02-T01 | Wireframes: unit catalogue, item units section, grid unit picker, conversion tester | UX | — | Approved | Review |
| H-02-T02 | `Unit` model (org-owned, code, name, dimension: count/mass/volume/length/time, is_system) + seed migration with en-CA defaults | DB | — | Seed loads 14 units | Unit |
| H-02-T03 | `UnitConversion` model (item nullable for global, from_unit, to_unit, factor Decimal(18,6)) with check factor > 0 | DB | H-02-T02 | Zero/negative factor rejected | Unit |
| H-02-T04 | Item fields: base_unit (required for stock items), purchase_unit, sales_unit, quantity_precision; migration with default "each" | DB | H-02-T02, H-01 | Existing items get "each" | Migration test |
| H-02-T05 | `UnitConverter` service: path search over item-specific then global conversions; cycle detection; returns factor and path | BE | H-02-T03 | 2 box → 24 each; case(=2 box) → 24 each via path; cycle rejected | Unit + Hypothesis (round-trip a→b→a = 1 within precision) |
| H-02-T06 | Quantity parser ("2 box", "2bx", "24") → (qty, unit) using unit codes and aliases | BE | H-02-T02 | Parser fixtures pass | Unit |
| H-02-T07 | Document line fields: entered_unit, entered_qty, base_qty (computed), unit_price_per_entered_unit; migration on sales/purchase/stock line models | DB | H-02-T04 | Lines store both quantities | Migration test |
| H-02-T08 | Line calculation hook in `DocumentGrid` service: compute base_qty and per-base cost/price; rounding residual stored | BE | H-02-T05, T07 | Line of 2 box @ 60.00 → base 24, per-each 5.00 | Unit |
| H-02-T09 | Base-unit change guard and unit-in-use delete guard | BE | H-02-T04 | 409 with explanatory message | Unit |
| H-02-T10 | APIs `/api/v1/inventory/units/`, `/conversions/`, `/units/convert?item=&from=&to=&qty=` | API | H-02-T05 | OpenAPI; sweep passes | Integration |
| H-02-T11 | Unit catalogue screen (in-use badges, add/edit, dimension grouping) | FE | H-02-T10 | Story + Playwright | Playwright |
| H-02-T12 | Item editor "Units" section with conversion table and live tester | FE | H-02-T10, H-01-T17 | Tester shows "2 box = 24 each" | Vitest |
| H-02-T13 | Grid unit picker + inline "2 box" parsing on PO, GRN, bill, invoice, adjustment lines | FE | H-02-T08 | Typing "2 box" sets unit and qty | Playwright |
| H-02-T14 | i18n keys for units (unit names translatable, codes not) | FE | H-02-T11…T13 | Gate passes | CI |
| H-02-T15 | Acceptance test: receive 2 boxes of 12 → on-hand +24 (test enabled after H-04) | QA | H-04 | Passes | pytest |
| H-02-T16 | Docs: units guide; ADR note on rounding precision | DOC | all | Published | Review |

- **Deliverable acceptance:** 2 boxes of 12 add 24 (Project_Phases.md).
- **Testing approach:** unit + property (round-trip), integration, functional (grid parsing).
- **Risks:** rounding drift on fractional conversions → Decimal(18,6) factors, residual tracking, base qty precision per item.

---

### H-03 · Locations & stock on hand

- **Branch:** `feature/H-03-locations-on-hand`
- **Objective:** know how many of each item are where, at any date.
- **Current behaviour:** no stock levels. (Xero: no multi-location/warehouse — gap #18.)
- **Expected behaviour:** hierarchical locations (warehouse → zone → bin) per organisation with one default; on-hand per item × location derived from movements (never typed); a cached `StockLevel` row per item × location (qty on hand, qty reserved for confirmed sales orders/quotes when enabled, qty on order from approved POs) kept transactionally in sync; stock card per item (and per location) with running quantity; negative on-hand blocked unless back-ordering is enabled for the item.
- **Gap #s closed:** 18 (locations part).
- **Business rules:** on-hand(item, location, date) = Σ movement base_qty up to date; `StockLevel` updated in the same transaction as the movement with `SELECT … FOR UPDATE`; available = on hand − reserved; negative check uses the locked row; archived location must have zero stock.
- **Edge cases:** concurrent issues of the last unit; back-dated movement before a later issue (as-of date negative check); location archived with stock; transfer within the same location (rejected).
- **UI/UX notes:** On-hand pivot (items × locations) with low-stock chips; location switcher on stock screens; stock card with running qty, filters, export; "as at" date picker.
- **Dependencies:** H-01, H-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-03-T01 | Wireframes: locations tree, on-hand pivot, stock card, location switcher | UX | — | Approved | Review |
| H-03-T02 | `Location` model (org-owned, parent, code, name, address, is_default, status) + seed "Main" default on Inventory activation | DB | — | One default enforced (partial unique) | Unit |
| H-03-T03 | `StockLevel` model (item, location, qty_on_hand, qty_reserved, qty_on_order, updated_at) unique (item, location) | DB | H-03-T02, H-01 | Unique enforced | Unit |
| H-03-T04 | Item field `allow_backorder` (bool) and org default setting | DB | H-01 | Migration applies | Unit |
| H-03-T05 | `StockLevelService.apply(delta, item, location)` with row lock and negative check (respect allow_backorder, as-of date check for back-dated movements) | BE | H-03-T03, T04 | Issue beyond on-hand raises `InsufficientStock` naming qty and location | Unit + concurrency test (two threads, last unit) |
| H-03-T06 | As-of on-hand query (Σ movements ≤ date) with index (org, item, location, date) | BE | H-04-T02 | Query < 50 ms on 1M movements | Perf test |
| H-03-T07 | Location archive guard (zero stock) and default reassignment | BE | H-03-T02 | Archive with stock → 409 | Unit |
| H-03-T08 | APIs `/api/v1/inventory/locations/`, `/stock-levels/?item=&location=&as_at=`, `/items/{id}/stock-card/` | API | H-03-T05, T06 | OpenAPI; sweep | Integration |
| H-03-T09 | Locations screen (tree, drag to re-parent, default star, archive) | FE | H-03-T08 | Playwright | Playwright |
| H-03-T10 | On-hand pivot screen (virtualised, low-stock chips, as-at picker, export) | FE | H-03-T08 | 10k items × 5 locations renders < 1 s | Playwright + perf |
| H-03-T11 | Stock card screen/tab with running qty and drill to source document | FE | H-03-T08 | Running qty = API values | Playwright |
| H-03-T12 | Item detail "Stock" tab and list stock badge wired to StockLevel | FE | H-03-T08, H-01-T16 | Badge shows on-hand | Vitest |
| H-03-T13 | Reconciliation command `manage.py tieout_stocklevels` (StockLevel vs Σ movements) + Hypothesis property test | QA/OPS | H-04 | 0 differences on fixture | Hypothesis |
| H-03-T14 | i18n keys, audit hooks for location changes | FE/BE | all | Gate passes | CI |
| H-03-T15 | Docs: locations guide | DOC | all | Published | Review |

- **Deliverable acceptance:** on-hand = sum of movements (Project_Phases.md); negative stock blocked unless back-ordering.
- **Testing approach:** unit, concurrency, property (on-hand invariant), performance.
- **Risks:** cache drift → transactional update + nightly tie-out + exceptions rule; deadlocks → consistent lock order (item id, location id).

---

### H-04 · Stock movements

- **Branch:** `feature/H-04-stock-movements`
- **Objective:** every change of stock is a posted, auditable movement.
- **Current behaviour:** GRN (E-01) records received quantities without stock or GL effect; invoices post revenue only.
- **Expected behaviour:** immutable `StockMovement` rows of types receipt (GRN / bill without PO), issue (invoice, credit-note return as negative issue), adjustment (+/−, reason codes: count, damage, expiry, write-down, opening), transfer (out + in pair), assembly (component issue / finished receipt); each movement posts a balanced JE through `post_journal()` (receipt: Dr Inventory / Cr GRNI or AP; issue: Dr COGS / Cr Inventory; adjustment: Dr/Cr Inventory vs adjustment expense; transfer: no GL unless location-specific inventory accounts); invoice revisions (D-03b) reverse and re-issue the stock and COGS of the superseded revision; reversals instead of deletes.
- **Gap #s closed:** 18; EXTRA X12 (exceptions rule `inventory_gl_mismatch`).
- **Business rules:** movement and JE in one DB transaction; GL inventory balance = valuation report; movements obey GL lock date; quantities in base unit; reason required on adjustments; transfer source ≠ destination.
- **Edge cases:** invoice revision changing quantity 10 → 8 (re-issue 8, return 10); credit note returning stock to a different location; GRN reversal after bill; bill without PO for tracked items; adjustment in a locked period.
- **UI/UX notes:** adjustment and transfer editors on `DocumentGrid`; reason-code picker; "Post" vs "Save draft"; movement list with filters by type/location/date/source; drill from JE to movement and back.
- **Dependencies:** H-03, C-02, E-01, D-03a, D-03b.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-04-T01 | Wireframes: adjustment editor, transfer editor, movement list, drill links | UX | — | Approved | Review |
| H-04-T02 | `StockMovement` model (org, item, location, date, type, base_qty signed, unit_cost, total_cost, source_type/source_id, journal_entry FK, reversal_of FK, batch/serial refs nullable, created_by) append-only via `django-pgtrigger` (no UPDATE/DELETE) | DB | H-03 | UPDATE raises at DB level | Unit |
| H-04-T03 | `StockAdjustment` and `StockTransfer` document models (draft/posted/reversed) with lines | DB | H-04-T02 | Migrations apply | Unit |
| H-04-T04 | `AdjustmentReason` catalogue seeded (count, damage, expiry, write-down, opening, other) with default expense account mapping | DB | H-04-T03 | Seed loads | Unit |
| H-04-T05 | `MovementService.record()` — validates, calls StockLevelService, asks CostingService (H-05; temporary fixed-cost stub until H-05) for unit cost, builds JE lines, posts via `post_journal()` atomically | BE | H-04-T02, H-03-T05 | Receipt of 10 @ 5.00 posts Dr Inventory 50 / Cr GRNI 50 | Unit + integration |
| H-04-T06 | GRN hook (E-01): receipt movements on GRN post; GRNI clearing on bill match | BE | H-04-T05, E-01 | Receive 6 of 10 → stock +6, GRNI 30 | Integration |
| H-04-T07 | Bill-without-PO hook: tracked lines on a bill create receipt movements (Dr Inventory instead of expense) | BE | H-04-T05, E-02 | Bill for 5 units posts to Inventory | Integration |
| H-04-T08 | Invoice approval hook: issue movements + COGS JE linked to the invoice revision | BE | H-04-T05, D-03a | Sell 4 → Dr COGS / Cr Inventory | Integration |
| H-04-T09 | Invoice revision hook (D-03b): reverse superseded revision's movements/COGS, issue current revision's, same transaction | BE | H-04-T08, D-03b | 10 → 8 leaves net issue 8 and COGS for 8 | Integration + property (stock = Σ current revisions) |
| H-04-T10 | Credit-note return hook: return-to-stock option per line with location | BE | H-04-T05, D-06 | Return 2 → stock +2, COGS reversed at original cost | Integration |
| H-04-T11 | Adjustment and transfer posting services (transfer = paired out/in in one transaction) | BE | H-04-T03, T05 | Transfer nets to 0 qty overall | Unit |
| H-04-T12 | Reversal service for movements/documents (creates opposite movements and reversing JE, reason required) | BE | H-04-T05 | Reversed adjustment restores on-hand | Unit |
| H-04-T13 | APIs `/api/v1/inventory/adjustments/`, `/transfers/`, `/movements/` (read-only list with filters) + post/reverse actions; lock-date enforcement messages | API | H-04-T11, T12 | OpenAPI; 423 on locked date with message | Integration |
| H-04-T14 | Enable H-01 "services never affect stock" acceptance test (service item on invoice creates no movement) | QA | H-04-T08 | Pass | pytest |
| H-04-T15 | Adjustment editor and transfer editor UI (DocumentGrid, reason picker, location pickers, post/draft) | FE | H-04-T13 | Playwright adjustment + transfer | Playwright + axe |
| H-04-T16 | Movement list screen + drill links (movement ↔ JE ↔ source document) | FE | H-04-T13 | Drill works both ways | Playwright |
| H-04-T17 | `manage.py tieout_inventory` (GL Inventory per account vs valuation) + exceptions-engine rule `inventory_gl_mismatch` (K-09 registry) | QA/BE | H-04-T05, K-09 | Fixture shows 0 difference; injected mismatch flagged | Integration |
| H-04-T18 | Hypothesis property test: random sequence of receipts/issues/adjustments/transfers/revisions → GL inventory = valuation and on-hand = Σ movements | QA | H-04-T05…T12 | 1,000 examples pass | Hypothesis |
| H-04-T19 | i18n keys, audit hooks, search registration for adjustments/transfers | FE/BE | all | Gate passes | CI |
| H-04-T20 | Docs: posting map table (movement type → JE lines) in data dictionary | DOC | all | Published | Review |

- **Deliverable acceptance:** every movement posts; GL inventory = valuation report (Project_Phases.md).
- **Testing approach:** unit, integration per hook, property (two invariants), regression on D-03b revision tests, security (sweep).
- **Risks:** revision interaction → same-transaction reverse + re-issue and a dedicated property test; lock-date conflicts with auto movements → hooks surface the lock message on the source document.

---

### H-05 · Costing

- **Branch:** `feature/H-05-costing`
- **Objective:** correct cost of goods sold and inventory value under the organisation's chosen method.
- **Current behaviour:** H-04 uses a fixed-cost stub.
- **Expected behaviour:** moving weighted average (default) per item (organisation-wide, or per location when location-costing is on); FIFO optional with cost layers; landed cost (freight, duty, brokerage, insurance) allocated from a bill line to one or more GRNs by value (default), quantity or weight, adjusting layer/average cost and posting the difference to Inventory (or to COGS for quantities already sold); back-dated receipts trigger a deterministic recalculation of affected issues inside the open period; "Why this cost?" explainer per movement.
- **Gap #s closed:** 18 (costing).
- **Business rules:** costing method set per organisation, changes only effective the first day of a fiscal year; average cost recalculated on each receipt: new_avg = (old_qty × old_avg + rcpt_qty × rcpt_cost) / (old_qty + rcpt_qty); issues at current average; FIFO issues consume oldest open layer first; negative stock (back-order) issues at last known cost, corrected when receipt arrives (revaluation entry); recalculation never touches locked periods — differences post on the first open date with reference.
- **Edge cases:** zero-quantity receipt with cost (landed cost after sale); receipt making negative stock positive; FIFO layer exhaustion mid-line; back-dated receipt before 300 issues; currency receipts (R-02 rate on GRN date).
- **UI/UX notes:** Inventory settings costing card with method explanation and effective date; landed-cost allocation dialog on bills ("Allocate to receipts") with preview; stock card "Why this cost?" popover.
- **Dependencies:** H-04.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-05-T01 | ADR-005 costing model (average vs FIFO, location costing, recalculation policy, lock interaction) | DOC | — | ADR merged | Review |
| H-05-T02 | Wireframes: costing settings card, landed-cost dialog, "Why this cost?" popover | UX | — | Approved | Review |
| H-05-T03 | `CostingSettings` (org: method, per_location, effective_from) + change-guard (fiscal-year start only, audited) | DB/BE | — | Mid-year change rejected with message | Unit |
| H-05-T04 | `ItemCost` state (item, location nullable, avg_cost, qty) for average method | DB | H-05-T03 | Migration applies | Unit |
| H-05-T05 | `CostLayer` model (item, location, receipt movement FK, qty_in, qty_remaining, unit_cost) for FIFO | DB | H-05-T03 | Migration applies | Unit |
| H-05-T06 | `CostingService` interface + `MovingAverageStrategy` (receipt updates avg, issue returns avg) | BE | H-05-T04 | Fixture A (known answers) passes to the cent | Unit with fixture table |
| H-05-T07 | `FifoStrategy` (receipt creates layer, issue consumes layers, returns blended cost and layer breakdown) | BE | H-05-T05 | Fixture B passes | Unit |
| H-05-T08 | Replace H-04 stub with `CostingService` in `MovementService` | BE | H-05-T06, T07, H-04-T05 | H-04 tests still green | Regression |
| H-05-T09 | Back-dated receipt recalculation job: recompute affected issues in open period; post revaluation JEs on first open date when locked | BE/OPS | H-05-T08 | Back-dated receipt fixture yields known COGS | Integration |
| H-05-T10 | Negative-stock (back-order) cost correction on next receipt | BE | H-05-T08 | Correction JE posts the difference | Unit |
| H-05-T11 | `LandedCostAllocation` model + service (by value/qty/weight; penny remainder to largest line; split sold vs on-hand portion) | DB/BE | H-05-T08, E-02 | Freight 100 over 3 GRNs allocates exactly 100.00 | Unit + Hypothesis (sum = amount) |
| H-05-T12 | APIs: costing settings, landed-cost allocate preview/apply, movement cost explanation `/movements/{id}/cost-explain` | API | H-05-T06…T11 | OpenAPI; sweep | Integration |
| H-05-T13 | Inventory settings costing card UI | FE | H-05-T12 | Playwright | Playwright |
| H-05-T14 | Landed-cost dialog on bill lines (choose GRNs, basis, preview, apply) | FE | H-05-T12 | Playwright | Playwright |
| H-05-T15 | "Why this cost?" popover on stock card rows (avg arithmetic or FIFO layers) | FE | H-05-T12 | Popover values = API | Vitest |
| H-05-T16 | Fixture set `tests/fixtures/inventory/costing/*.yaml` (10 average, 10 FIFO, 5 landed-cost, 5 back-dated scenarios) with expected answers | QA | — | Fixtures reviewed by accountant | Review |
| H-05-T17 | Property test: inventory value = Σ layers (FIFO) / qty × avg (average) after random sequences | QA | H-05-T06, T07 | Pass | Hypothesis |
| H-05-T18 | i18n keys, docs (costing guide for accountants) | FE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** fixtures with known answers pass (Project_Phases.md); landed cost allocates to the cent.
- **Testing approach:** unit with fixture tables, property, regression on H-04, integration for recalculation.
- **Risks:** recalculation cost on big histories → bounded to open period, run as job with progress; method change misuse → fiscal-year guard + audit.

---

### H-06 · Batch/serial & expiry

- **Branch:** `feature/H-06-batch-serial-expiry`
- **Objective:** trace lots and serial numbers from receipt to sale.
- **Current behaviour:** quantities only. (Xero: no lot/serial/expiry — gap #18.)
- **Expected behaviour:** per-item tracking mode none / batch / serial; batch has number, manufacture date, expiry date; serial has number and current location; receipts capture batch/serial; issues pick batch (FEFO suggestion: first-expiry-first-out) or serial; traceability report (where did batch X go? where did serial Y come from?); expiry alerts N days before expiry.
- **Gap #s closed:** 18 (lot/serial).
- **Business rules:** a serial exists in one location only and quantity 1; a serial cannot be issued twice; batch quantity per location ≥ 0; tracking mode cannot change once movements exist; expired batch issue warns (configurable block).
- **Edge cases:** return of a serial previously sold (re-enters stock); duplicate serial across items (allowed — unique per item); bulk serial entry (paste 100 serials, range generator SN-001…SN-100).
- **UI/UX notes:** batch/serial picker inline in grid, opened with `Ctrl+B`; paste-many and range generator; scan to add serial; expiry chips (amber ≤ 30 days, red expired).
- **Dependencies:** H-04, H-05.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-06-T01 | Wireframes: tracking settings on item, batch/serial picker, traceability report | UX | — | Approved | Review |
| H-06-T02 | Item field `tracking_mode` + change guard | DB/BE | H-01 | Change after movement → 409 | Unit |
| H-06-T03 | `Batch` model (item, number, mfg_date, expiry_date) unique (item, number) and `BatchLevel` (batch, location, qty) | DB | H-06-T02 | Migration applies | Unit |
| H-06-T04 | `SerialNumber` model (item, number, status in_stock/issued/scrapped, location nullable, last movement) unique (item, number) | DB | H-06-T02 | Migration applies | Unit |
| H-06-T05 | Movement line linkage (`StockMovementBatch`, `StockMovementSerial`) and validation in `MovementService` | BE | H-06-T03, T04, H-04 | Receipt without serials for serial item rejected | Unit |
| H-06-T06 | Serial one-location / no-double-issue guard with row lock | BE | H-06-T05 | Concurrent issue of same serial: one succeeds | Concurrency test |
| H-06-T07 | FEFO batch suggestion service and expired-batch warn/block setting | BE | H-06-T05 | Suggestion picks earliest expiry with stock | Unit |
| H-06-T08 | Traceability queries (forward: batch → documents/customers; backward: serial → receipt/supplier) | BE | H-06-T05 | Fixture trace returns expected chain | Integration |
| H-06-T09 | Expiry alert job (daily, configurable days) → notifications (A-07) | OPS | H-06-T03, A-08 | Alert fires for fixture batch at N days | Integration (freezegun) |
| H-06-T10 | APIs: batches, serials, trace, FEFO suggestion | API | H-06-T05…T08 | OpenAPI; sweep | Integration |
| H-06-T11 | Grid batch/serial picker (inline, `Ctrl+B`, paste-many, range generator, scan) | FE | H-06-T10 | Playwright 100-serial paste | Playwright |
| H-06-T12 | Traceability report screen and item "Batches/Serials" tab with expiry chips | FE | H-06-T10 | Playwright | Playwright + axe |
| H-06-T13 | Acceptance tests + i18n keys + docs | QA/FE/DOC | all | Serial exists in one location only | pytest |

- **Deliverable acceptance:** a serial exists in one location only (Project_Phases.md); traceability both directions.
- **Testing approach:** unit, concurrency, integration, functional.
- **Risks:** heavy serial entry UX → paste/range/scan; performance on large serial sets → index (item, number), (item, status, location).

---

### H-07 · Reorder & stock reports

- **Branch:** `feature/H-07-reorder-stock-reports`
- **Objective:** keep stock at the right level and report it clearly.
- **Current behaviour:** no reorder or stock reports. (Xero: no reorder level; only basic item list/summary reports — gap #18.)
- **Expected behaviour:** per item × location reorder point, reorder quantity (or "use EOQ" from H-11), max level; low-stock alert when on-hand (or available) < reorder point; suggested POs grouped by preferred supplier; stock reports in the K-01 engine: valuation (as at date, by item/category/location, method shown), movement summary/detail, stock aging (by receipt layer/date buckets), stock-take sheet and stock-take workflow (blind count, variance review, approve → adjustment).
- **Gap #s closed:** 18 (reorder), EXTRA X3 (mobile stock-take), X4 (grouped suggestions).
- **Business rules:** alert evaluated on each issue and nightly; one open alert per item × location until resolved; stock-take freezes nothing but records snapshot qty at start; variances post as adjustments with reason "count" on approval; approver ≠ counter when SoD setting on.
- **Edge cases:** stock-take while movements continue (variance computed vs snapshot + movements during count); item with no preferred supplier (suggestion shows "Choose supplier"); reorder point zero (no alerts).
- **UI/UX notes:** reorder fields in item "Stock" tab; suggestions screen (§3.3); reports via the shared runner with book selector hidden (inventory not book-specific); stock-take mobile layout with large targets and scan.
- **Dependencies:** H-03, H-04, H-05, E-01 (PO creation), K-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-07-T01 | Wireframes: reorder fields, suggestions, stock-take (desktop + 375 px), report layouts | UX | — | Approved | Review |
| H-07-T02 | `ReorderRule` model (item, location, reorder_point, reorder_qty, max_level, use_eoq flag) | DB | H-03 | Migration applies | Unit |
| H-07-T03 | `LowStockAlert` model + evaluator on movement commit (on_commit hook) and nightly job | BE/OPS | H-07-T02, H-04 | Alert when on-hand < reorder point; one open per item × location | Unit + integration |
| H-07-T04 | Suggestion service: qty = max(reorder_qty or EOQ, max_level − (on_hand + on_order)), grouped by preferred supplier, MOQ rounding | BE | H-07-T02, H-01-T05 | Fixture suggestions match expected | Unit |
| H-07-T05 | "Create draft POs" service (one PO per supplier, lines from suggestions, supplier price/last cost) via E-01 | BE | H-07-T04, E-01 | 3 suppliers → 3 draft POs | Integration |
| H-07-T06 | Valuation report definition in K-01 (as-at, grouping, method column, totals tie to GL with tie-out footer) | BE | H-05, K-01 | Total = GL inventory balance on fixture | Integration |
| H-07-T07 | Movement summary/detail report definitions | BE | H-04, K-01 | Totals = Σ movements | Integration |
| H-07-T08 | Stock aging report (buckets 0–30/31–90/91–180/181–365/>365 by layer or average receipt date) | BE | H-05 | Fixture buckets correct | Unit |
| H-07-T09 | `StockTake` model (location, status draft/counting/submitted/approved, snapshot) + lines (item, batch/serial, counted qty, system qty, variance) | DB | H-04 | Migration applies | Unit |
| H-07-T10 | Stock-take service: start (snapshot), count, submit, approve → adjustment with reason "count"; SoD check | BE | H-07-T09, H-04-T11 | Approve posts variance adjustment; counter cannot approve when SoD on | Integration |
| H-07-T11 | APIs: reorder rules, alerts, suggestions, create POs, stock-takes, report endpoints | API | H-07-T03…T10 | OpenAPI; sweep | Integration |
| H-07-T12 | Item stock tab reorder fields + low-stock badges in list | FE | H-07-T11 | Vitest | Vitest |
| H-07-T13 | Reorder suggestions screen (grouped, select, create POs, review drawer) | FE | H-07-T11 | F2 flow in Playwright | Playwright |
| H-07-T14 | Stock-take screens (desktop + mobile, blind count toggle, scan, variance review, approve) | FE | H-07-T11 | Playwright at 375 px | Playwright + axe |
| H-07-T15 | Report screens wired to shared runner with export PDF/XLSX/CSV | FE | H-07-T06…T08 | Exports match screen | Playwright |
| H-07-T16 | Stock-take printable sheet PDF (WeasyPrint, Letter) | BE | H-07-T09 | PDF snapshot test | Snapshot |
| H-07-T17 | Acceptance tests, i18n keys, docs | QA/FE/DOC | all | Alert when on-hand < reorder point | pytest + Playwright |

- **Deliverable acceptance:** alert when on-hand < reorder point (Project_Phases.md); valuation ties to GL; suggestions create POs.
- **Testing approach:** unit, integration, functional (F2), data validation (valuation tie-out), accessibility (mobile stock-take).
- **Risks:** alert spam → one open alert per item × location, digest notification; stock-take during movement → snapshot + delta logic.

---

### H-08 · Simple assemblies (BOM)

- **Branch:** `feature/H-08-assemblies-bom`
- **Objective:** build finished goods from components with correct cost.
- **Current behaviour:** none. (Xero: no BOM/assemblies — gap #18.)
- **Expected behaviour:** single-level BOM per assembled item (component, qty per unit in component base unit, optional scrap %); BOM versions with effective date; build document: choose assembly, qty, location → availability check → posts component issues at their cost and a finished-goods receipt at Σ component cost (+ optional labour/overhead line to an absorption account); unbuild (disassembly) reverses.
- **Gap #s closed:** 18 (BOM).
- **Business rules:** assembled item must be tracked; a component cannot be the assembly itself (no cycles across BOMs — validated); build blocked if any component insufficient (unless back-order allowed for that component); finished cost = Σ component costs + labour/overhead; build is one transaction.
- **Edge cases:** component with batch/serial tracking (picker required); BOM changed after builds (versioning keeps history); scrap % rounding.
- **UI/UX notes:** BOM tab on item with component grid and cost roll-up preview; build dialog shows "can build up to N" with limiting component highlighted.
- **Dependencies:** H-04, H-05, H-06 (for tracked components).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-08-T01 | Wireframes: BOM tab, build dialog, max-buildable indicator | UX | — | Approved | Review |
| H-08-T02 | `BillOfMaterials` (item, version, effective_from, status) and `BomLine` (component, qty, scrap_pct) | DB | H-01 | Migration applies | Unit |
| H-08-T03 | Cycle and self-reference validation across BOMs | BE | H-08-T02 | A→B→A rejected | Unit |
| H-08-T04 | Cost roll-up service (current costs × qty × (1+scrap)) and max-buildable calculation | BE | H-08-T02, H-05 | Fixture roll-up correct; limiting component returned | Unit |
| H-08-T05 | `AssemblyBuild` document + build service (issues, receipt, optional labour/overhead line, single transaction) | DB/BE | H-08-T04, H-04-T05 | Build 10 consumes per BOM, finished +10 | Integration |
| H-08-T06 | Unbuild service (reverse) | BE | H-08-T05 | Unbuild restores components | Integration |
| H-08-T07 | APIs: BOMs, builds, roll-up, max-buildable | API | H-08-T04…T06 | OpenAPI; sweep | Integration |
| H-08-T08 | BOM tab UI with component grid and roll-up | FE | H-08-T07 | Playwright | Playwright |
| H-08-T09 | Build dialog UI with availability, batch/serial pickers for tracked components | FE | H-08-T07, H-06-T11 | Playwright | Playwright + axe |
| H-08-T10 | Property test: build/unbuild sequences keep GL inventory = valuation | QA | H-08-T05, T06 | Pass | Hypothesis |
| H-08-T11 | Acceptance tests, i18n keys, docs | QA/FE/DOC | all | Build 10 consumes components per BOM, finished +10 | pytest |

- **Deliverable acceptance:** build 10 consumes per BOM, finished +10 (Project_Phases.md).
- **Testing approach:** unit, integration, property.
- **Risks:** multi-level BOM requests → out of scope (single level), documented; cost timing → roll-up at build time, shown in preview.

---

### 6.2 Inventory Analytics & Profit Optimisation [v2.1]

### H-09 · Best-selling SKU rankings [v2.1] (provisional ID)

- **Branch:** `feature/H-09-sku-rankings`
- **Objective:** rank SKUs by quantity, revenue and margin over any period.
- **Current behaviour:** no inventory analytics. (Xero: "Sales by item" report only, no margin ranking — beyond Xero.)
- **Expected behaviour:** rankings by quantity sold (base unit), net revenue (after line and document discounts, excluding tax, current invoice revision only, net of credit notes) and gross margin ($ and %) using posted COGS; filters: period presets + custom, category, location, customer, price list, item type; compare to previous period with rank movement arrows; Pareto (ABC) classification A/B/C by revenue share (80/15/5 default, editable); top-N and bottom-N; every figure drills to the invoice lines; data from a nightly `SalesItemFact` snapshot plus an on-demand refresh.
- **Gap #s closed:** beyond Xero; EXTRA X11 (export rows behind widget).
- **Business rules:** revenue in organisation base currency (R-02 converted at document rate); figures tie to sales and COGS postings for the period; current invoice revision only (D-03b); credit notes reduce quantity/revenue/COGS in their own date; services included in revenue rankings, excluded from margin when they have no cost (shown "n/a").
- **Edge cases:** revised invoice crossing period boundary; zero-revenue items; negative margin; item merged/archived; very large org (500 SKUs × 2 years) performance.
- **UI/UX notes:** segmented control (Quantity / Revenue / Margin), period picker, horizontal bar chart with data-table toggle, rank delta arrows, ABC chips, "as of" freshness stamp with Refresh; empty state "No sales in this period".
- **Dependencies:** H-04, H-05, D-03b, K-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-09-T01 | Wireframes + chart spec (dataviz palette, data-table alternative, mobile layout) | UX | — | Approved | Review |
| H-09-T02 | Metric definitions doc (net revenue, COGS, margin, quantity) signed off by accountant | DOC | — | Definitions in `docs/analytics/metrics.md` | Review |
| H-09-T03 | `SalesItemFact` table (org, date, item, location, customer, category, qty_base, revenue_base, cogs_base, document refs) partitioned by org | DB | H-04 | Migration applies | Unit |
| H-09-T04 | Fact builder: from current invoice revisions + credit notes + COGS movements; incremental by changed documents (event on post/revise) | BE/OPS | H-09-T03, D-03b | Fact totals = GL revenue and COGS for fixture period | Integration (tie-out) |
| H-09-T05 | Nightly full rebuild job + on-demand refresh endpoint with freshness timestamp | OPS | H-09-T04 | Job idempotent; freshness shown | Integration |
| H-09-T06 | Ranking query service (by qty/revenue/margin, filters, previous-period compare, rank delta) using SQL window functions | BE | H-09-T03 | Fixture ranking matches expected order | Unit |
| H-09-T07 | ABC classification service with configurable thresholds | BE | H-09-T06 | 80/15/5 split on fixture correct | Unit |
| H-09-T08 | API `/api/v1/inventory/analytics/rankings` (+ export CSV/XLSX of underlying rows) feature key `inventory.analytics` | API | H-09-T06, T07 | 402 without entitlement; export rows sum to widget | Integration |
| H-09-T09 | Best-sellers screen (segmented metric, period picker, bar chart + table, ABC chips, drill to lines) | FE | H-09-T08 | Playwright; axe | Playwright + axe |
| H-09-T10 | Item detail "Analytics" tab (rank, trend sparkline) | FE | H-09-T08 | Vitest | Vitest |
| H-09-T11 | Dashboard widget "Top 5 SKUs by margin" for K-05 widget registry | FE | H-09-T08, K-05 | Widget renders with 0 state | Vitest |
| H-09-T12 | Performance test: 500 SKUs × 2 years × 100k lines → ranking < 1.5 s p95 | QA | H-09-T06 | k6 passes | k6 |
| H-09-T13 | Revision/credit-note property test: rankings equal recomputation from current revisions | QA | H-09-T04 | Pass | Hypothesis |
| H-09-T14 | i18n keys, docs (owner guide "Which products make money?") | FE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** rankings tie to sales and COGS postings for the period (Project_Phases.md).
- **Testing approach:** data validation (fact vs GL tie-out), unit, property, performance, functional.
- **Risks:** stale facts → event-driven incremental update + freshness stamp; revision double counting → facts keyed by current revision only.

---

### H-10 · Stock-movement analysis [v2.1] (provisional ID)

- **Branch:** `feature/H-10-movement-analysis`
- **Objective:** show how fast stock moves, how long it will last, and what is dead or slow.
- **Current behaviour:** none (beyond Xero).
- **Expected behaviour:** per item × location: average daily sales velocity over a chosen window (30/90/180/365 days, excluding stock-out days optionally), demand standard deviation, days of cover = on-hand ÷ velocity, last sale date, last receipt date, sell-through % (sold ÷ (opening + received)), inventory turnover (COGS ÷ average inventory value), days inventory outstanding; classification Fast / Normal / Slow / Dead with thresholds (default dead = no sale in 180 days with stock > 0; slow = cover > 180 days); action list for dead/slow (create markdown scenario in H-12, create write-down adjustment draft in H-04) — EXTRA X10.
- **Gap #s closed:** beyond Xero.
- **Business rules:** velocity from `SalesItemFact` quantities (net of returns); stock-out days computed from daily on-hand snapshots (`StockDailySnapshot`); thresholds editable per organisation; average inventory value from daily snapshots; figures reproduce on fixtures with known movements.
- **Edge cases:** new items (< window days of history → "insufficient history" badge); zero velocity (cover = ∞ shown as "No recent sales"); negative on-hand (back-order); seasonal items (window choice explained).
- **UI/UX notes:** sortable table with traffic-light cover chips; filters by class; bulk actions; ⓘ explainer per metric; mobile card view.
- **Dependencies:** H-09, H-03, H-05.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-10-T01 | Wireframes: movement & cover table, class filters, action menu, mobile cards | UX | — | Approved | Review |
| H-10-T02 | `StockDailySnapshot` (org, date, item, location, qty, value) + nightly job; backfill command for history | DB/OPS | H-03, H-05 | Snapshot equals as-of on-hand for sample dates | Integration |
| H-10-T03 | Velocity & σ service (window, stock-out exclusion option) | BE | H-10-T02, H-09-T03 | Fixture velocity correct to 4 dp | Unit |
| H-10-T04 | Cover, sell-through, turnover, DIO service | BE | H-10-T03 | Fixture values match spreadsheet | Unit |
| H-10-T05 | Classification service with org thresholds (`AnalyticsSettings`) | DB/BE | H-10-T04 | Fixture classes correct | Unit |
| H-10-T06 | Action services: create markdown scenario draft (H-12 hook, stubbed until H-12) and write-down adjustment draft (H-04) | BE | H-10-T05, H-04 | Draft adjustment created, not posted | Integration |
| H-10-T07 | API `/api/v1/inventory/analytics/movement` with export | API | H-10-T03…T06 | OpenAPI; sweep; 402 | Integration |
| H-10-T08 | Movement & cover screen (table, chips, filters, bulk actions, explainers) | FE | H-10-T07 | Playwright | Playwright + axe |
| H-10-T09 | Analytics settings UI (thresholds, window default) | FE | H-10-T07 | Audited change | Playwright |
| H-10-T10 | Fixture `tests/fixtures/inventory/movement/*.yaml` with known movements and expected metrics; reproduction test | QA | H-10-T04 | All metrics reproduce | pytest |
| H-10-T11 | Performance test on large fixture (< 1.5 s) | QA | H-10-T07 | k6 passes | k6 |
| H-10-T12 | i18n keys, docs (metric glossary) | FE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** figures reproduce on fixtures with known movements (Project_Phases.md).
- **Testing approach:** unit with fixtures, data validation, performance.
- **Risks:** snapshot storage size → partitioning + 3-year retention for daily snapshots, monthly beyond; misinterpretation → explainers and glossary.

---

### H-11 · EOQ reorder engine [v2.1] (provisional ID)

- **Branch:** `feature/H-11-eoq-reorder`
- **Objective:** suggest how much and when to reorder using the client's EOQ equation, and turn a suggestion into a PO in one action.
- **Current behaviour:** H-07 suggests quantities from fixed reorder quantity / max level.
- **Expected behaviour:** a **Formula Registry** (shared foundation built here, reused by H-13, FN-04, FN-05) storing versioned formulas as safe expressions with named, typed, unit-labelled inputs; the EOQ formula (client's, default Wilson √(2DS/H)) and safety-stock formula (default z × σ_d × √L) registered; per-SKU parameters: annual demand D (manual or derived from H-10 velocity × 365), ordering cost S per order, holding cost H per unit per year (amount or % of unit cost), safety stock (manual or formula from service level %), lead time L (days, from supplier link); reorder point = demand during lead time + safety stock; suggestion = EOQ rounded up to supplier MOQ / pack size; one-click PO creation (single or grouped by supplier) through H-07-T05; explainer shows formula, version, inputs and result.
- **Gap #s closed:** beyond Xero; EXTRA X4.
- **Business rules:** formulas are data, versioned (version, effective_from, author, approval status); only an approved version is used; each suggestion stores the formula version used; inputs validated (H > 0, D ≥ 0, S ≥ 0); EOQ output must equal the client's worked example; suggestions never auto-create POs without a user action (unless an "auto-draft" org setting is on, which still creates drafts only).
- **Edge cases:** D = 0 (no suggestion, explains); H = 0 (error message per §3.5); missing lead time (falls back to org default, flagged); client formula referencing an unknown variable (rejected at registration); formula producing negative/NaN (guarded, logged, suggestion withheld).
- **UI/UX notes:** EOQ parameters grid with "Derive from history" bulk action; formula-version banner ("Using EOQ formula v2 — Profitex, approved 12 Nov 2026"); suggestions screen from H-07 extended with EOQ column and explainer; Formula Registry admin with test console.
- **Dependencies:** H-07, H-10, E-01. Client input: EOQ equation + worked example (Agreement 9.1(b)).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-11-T01 | ADR-006 Formula Registry (expression language, whitelist, versioning, approval, units) | DOC | — | ADR merged | Review |
| H-11-T02 | `Formula` model (scope platform/practice/org, key e.g. `inventory.eoq`, version, expression, inputs schema JSON, output unit, status draft/approved/retired, effective_from, source note, approved_by) | DB | H-11-T01 | Migration applies; one approved version per key/scope/date | Unit |
| H-11-T03 | Safe evaluator `numo9.formulas.evaluate(expr, inputs)` on Python `ast` with operator/function whitelist (`+ - * / ** sqrt ln exp min max abs round ceil floor norm_ppf`), Decimal arithmetic, depth/size limits, timeout | BE | H-11-T02 | Malicious expressions (`__import__`, attribute access, lambdas) rejected; fixtures evaluate exactly | Unit + fuzz (Hypothesis on random ASTs) |
| H-11-T04 | Formula validation on save: parse, unknown-variable check against inputs schema, dry-run on sample inputs; approval workflow (approver ≠ author) with audit | BE/API | H-11-T03 | Unknown variable rejected; self-approval refused | Integration |
| H-11-T05 | Seed default formulas: `inventory.eoq` = `sqrt(2*D*S/H)`, `inventory.safety_stock` = `z*sigma_d*sqrt(L)`, `inventory.reorder_point` = `d*L + SS`, labelled "Numo9 default — replace with client formula" | DB | H-11-T02 | Seeds present, approved at platform scope | Unit |
| H-11-T06 | Formula Registry admin UI (list, edit with syntax highlighting, inputs schema editor, test console with sample inputs, approve, version history diff) | FE | H-11-T04 | Playwright: create, test, approve | Playwright + axe |
| H-11-T07 | `EoqParameters` model (item, location nullable, D, D_source manual/derived, S, H, H_mode amount/% of cost, service_level %, safety_stock manual nullable, lead_time_days nullable) | DB | H-01 | Migration applies | Unit |
| H-11-T08 | Parameter derivation service (D from H-10 velocity × 365; σ_d from H-10; L from preferred supplier; H from % × current cost) | BE | H-11-T07, H-10-T03 | Derived values match fixture | Unit |
| H-11-T09 | `EoqEngine.suggest(item, location)` → EOQ, safety stock, reorder point, suggested qty rounded to MOQ/pack, formula versions used, explanation payload | BE | H-11-T03, T05, T08 | Default Wilson fixture: D=1200, S=50, H=2 → EOQ 244.95 → 245 | Unit |
| H-11-T10 | Integrate with H-07 suggestions (use_eoq flag) and store formula version on each suggestion | BE | H-11-T09, H-07-T04 | Suggestion row carries version | Integration |
| H-11-T11 | APIs: `/formulas/`, `/formulas/{id}/test`, `/inventory/eoq-parameters/` (bulk), `/inventory/eoq/suggest`, derive action | API | H-11-T04…T10 | OpenAPI; sweep; feature key `inventory.eoq` | Integration |
| H-11-T12 | EOQ parameters grid UI (bulk edit, derive from history, validation messages) | FE | H-11-T11 | Playwright | Playwright |
| H-11-T13 | Suggestions screen extension: EOQ/ROP/SS columns, explainer popover, version banner, one-click "Create PO" per row and grouped | FE | H-11-T11, H-07-T13 | F2 one-click → draft PO opens | Playwright |
| H-11-T14 | Client-formula acceptance fixture `tests/fixtures/inventory/eoq/client_example.yaml` + test marked `xfail(reason="awaiting client EOQ worked example")`; checklist to load the client formula as a new approved version and flip the test | QA | H-11-T09 | Test present, reported as expected-fail (never as pass) until client data loaded | pytest |
| H-11-T15 | Edge-case tests (D=0, H=0, missing L, NaN guard, negative guard) with user messages | QA | H-11-T09 | All produce explained outcomes | pytest |
| H-11-T16 | Notification: weekly "reorder digest" email/in-app per org (A-07) | OPS | H-11-T10 | Digest sent with count and link | Integration |
| H-11-T17 | i18n keys, docs (EOQ guide, how to replace the formula) | FE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** EOQ output = client's worked example; suggestion → PO in one action (Project_Phases.md).
- **Testing approach:** unit, fuzz/security (evaluator), integration, functional, compliance-style fixture with client example.
- **Risks:** client formula late → default formula + xfail fixture, schedule extension per Agreement 6.3; evaluator security → AST whitelist + fuzzing + no attribute access; formula misuse → approval workflow and version stamping.

---

### H-12 · COGS-to-profit & price optimisation [v2.1] (provisional ID)

- **Branch:** `feature/H-12-margin-price-optimisation`
- **Objective:** show profit per SKU / category / location and model price changes before applying them.
- **Current behaviour:** H-09 ranks by margin; no contribution-margin view and no price modelling.
- **Expected behaviour:** for any period and grouping (SKU, category, location, customer): revenue, COGS, gross profit, gross margin %, variable costs beyond COGS (configurable per item/category: freight-out, commissions %, payment-processing %, packaging), contribution margin, CM % and CM per unit; waterfall chart revenue → COGS → variable costs → CM; **price scenarios**: select items or a category, set change (+/− %, +/− $, target margin %, target price), optional price elasticity (% volume change per 1 % price change, default 0), see projected units, revenue, CM, profit vs baseline; guard rails (below landed cost, below minimum margin) — EXTRA X5; save scenario drafts, compare up to 3, "Apply" updates a chosen price list effective a chosen date with preview and audit; scenarios never change live prices until applied.
- **Gap #s closed:** beyond Xero.
- **Business rules:** contribution margin = revenue − variable costs (COGS + other variable costs); fixed costs excluded (shown separately in H-13 KPIs); baseline from the chosen historic period; projections are estimates labelled as such; applying creates new `PriceListItem` rows effective-dated (old prices end the day before) — never overwrites history; apply requires `inventory.pricing.apply` permission.
- **Edge cases:** item with no sales in baseline (projection uses manual expected units); multi-currency price lists; scenario on archived item; elasticity making units negative (floored at 0, flagged); rounding to price points (.99 option).
- **UI/UX notes:** margins pivot with drill; scenario editor side-by-side with deltas coloured and signed; sticky totals bar; "Apply" step with explicit price-list and date choice; comparison view.
- **Dependencies:** H-09, H-05, H-01 (price lists), H-11 (Formula Registry for CM formula keys).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-12-T01 | Wireframes: margins pivot, waterfall, scenario editor, compare view, apply step | UX | — | Approved | Review |
| H-12-T02 | `VariableCostRule` model (scope item/category/org, type amount/%-of-revenue/%-of-cost, account mapping optional, effective dates) | DB | H-01 | Migration applies | Unit |
| H-12-T03 | Register formula keys `inventory.contribution_margin`, `inventory.cm_ratio`, `inventory.gross_margin_pct` in Formula Registry (defaults; replaceable by client) | DB | H-11-T05 | Seeds present | Unit |
| H-12-T04 | Margin service: aggregates from `SalesItemFact` + variable cost rules → GP, GM %, CM, CM %, per-unit; grouping by SKU/category/location/customer | BE | H-12-T02, T03, H-09-T03 | CM = revenue − variable cost on fixtures | Unit |
| H-12-T05 | `PriceScenario` model (name, baseline period, status draft/applied/discarded, lines: item, current price, change type, change value, elasticity, rounding rule, projected price/units/revenue/CM) | DB | H-12-T04 | Migration applies | Unit |
| H-12-T06 | Scenario projection engine (price change → units via elasticity → revenue/variable cost/CM/profit; floor units at 0; rounding to price points) | BE | H-12-T05 | Projection fixtures match spreadsheet | Unit + Hypothesis (elasticity 0 ⇒ units unchanged) |
| H-12-T07 | Guard-rail checks (below landed cost, below min margin setting) returning warnings per line | BE | H-12-T06, H-05 | Warnings on fixture lines | Unit |
| H-12-T08 | Apply service: create effective-dated `PriceListItem` rows, end previous, audit, permission check | BE | H-12-T05, H-01-T06 | Live prices unchanged before apply; after apply new price used from effective date | Integration |
| H-12-T09 | Hook from H-10 action "markdown scenario" (replace stub) | BE | H-12-T05, H-10-T06 | Dead-stock action opens scenario with items | Integration |
| H-12-T10 | APIs: `/inventory/analytics/margins`, `/inventory/price-scenarios/` (CRUD, project, compare, apply) feature key `inventory.pricing` | API | H-12-T04…T09 | OpenAPI; sweep; 402 | Integration |
| H-12-T11 | Margins & pricing screen (pivot, waterfall chart + table alternative, drill) | FE | H-12-T10 | Playwright + axe | Playwright |
| H-12-T12 | Scenario editor (side-by-side, deltas, guard rails, elasticity input with explainer, rounding rule) | FE | H-12-T10 | F3 flow passes | Playwright |
| H-12-T13 | Compare view (up to 3 scenarios) and apply step (price list, effective date, preview) | FE | H-12-T10 | Apply preview shows old/new; audit visible | Playwright |
| H-12-T14 | Fixture set for margins and scenarios with expected values; acceptance tests | QA | H-12-T04, T06 | Pass | pytest |
| H-12-T15 | Bulk price-list update from scenario for 1,000 items as job with per-row result | BE/OPS | H-12-T08 | 1,000 rows < 30 s, per-row result | Integration |
| H-12-T16 | i18n keys, docs (pricing guide; projections disclaimer) | FE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** contribution margin = revenue − variable cost on fixtures; scenario does not change live prices until applied (Project_Phases.md).
- **Testing approach:** unit with fixtures, property, integration (apply), functional, permission tests.
- **Risks:** users treating projections as facts → "Estimate" labels and explainer; accidental apply → explicit price list + date + preview + permission.

---

### H-13 · Management-accounting KPIs & dashboard [v2.1] (provisional ID)

- **Branch:** `feature/H-13-inventory-kpis`
- **Objective:** an inventory and pricing KPI dashboard driven by the client's management-accounting formulas.
- **Current behaviour:** dashboard (K-05) has generic accounting widgets only.
- **Expected behaviour:** KPI definitions stored in the Formula Registry (`kpi.inventory.*`) with inputs bound to named data sources (revenue, COGS, average inventory, on-hand value, units sold, fixed costs from GL account groups, etc.); starter set seeded (gross margin %, contribution margin %, inventory turnover, DIO, GMROI, sell-through %, stock-out rate, break-even units = fixed costs ÷ CM per unit, margin of safety %) labelled "Numo9 default"; client formulas loaded as approved versions; dashboard of `StatTile`s with period compare, sparkline, target/threshold colouring, explainer (formula + inputs + period — EXTRA X6); export to PDF/XLSX; KPIs available as widgets on the main dashboard and as report rows in K-06 management pack.
- **Gap #s closed:** beyond Xero.
- **Business rules:** each KPI matches the client's source formula on a fixture; data-source bindings are a fixed catalogue (no free SQL); divide-by-zero returns "n/a" with reason; KPI thresholds per organisation.
- **Edge cases:** client KPI needing a data source not in the catalogue (add source as a task, never free SQL); fixed-cost account mapping missing (prompt to map); period with no data.
- **UI/UX notes:** grid of tiles grouped (Profitability / Efficiency / Risk); "default formula" badge until client formula approved; tile click → trend chart + inputs table; responsive at 375 px.
- **Dependencies:** H-11 (Formula Registry), H-09, H-10, H-12, K-05. Client input: management-accounting material (Agreement 9.1(b)).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| H-13-T01 | Extract KPI list and formulas from client material into `docs/analytics/client-kpis.md` (or record "not yet received") with source page references | DOC | client input | Document reviewed by client | Review |
| H-13-T02 | Wireframes: KPI grid, tile states, detail drawer, threshold editor | UX | — | Approved | Review |
| H-13-T03 | `KpiDataSource` catalogue (code, description, unit, resolver function) for revenue, cogs, avg_inventory_value, on_hand_value, units_sold, fixed_costs (mapped account group), variable_costs, stockout_days, etc. | BE | H-09, H-10, H-12 | Each source returns fixture values | Unit |
| H-13-T04 | `KpiDefinition` (formula key, data-source bindings, display unit, direction good-up/good-down, group) and `KpiThreshold` (org) | DB | H-11-T02 | Migration applies | Unit |
| H-13-T05 | Seed starter KPI set with default formulas and "Numo9 default" flag | DB | H-13-T04 | Seeds present | Unit |
| H-13-T06 | KPI evaluation service (period, compare period, n/a handling with reason, caching per period) | BE | H-13-T03…T05, H-11-T03 | Fixture KPIs computed exactly | Unit |
| H-13-T07 | Fixed-cost account-group mapping UI + API (choose GL accounts / account groups) | FE/API | H-13-T03 | Mapping saved, audited | Playwright |
| H-13-T08 | APIs: `/analytics/kpis?group=inventory&period=…`, `/analytics/kpis/{key}/detail`, export | API | H-13-T06 | OpenAPI; sweep; 402 | Integration |
| H-13-T09 | KPI dashboard screen (tiles, compare, sparkline, thresholds, explainer drawer, export) | FE | H-13-T08 | Playwright + axe | Playwright |
| H-13-T10 | K-05 widget registration and K-06 management-pack section hook | FE/BE | H-13-T08, K-05 | Widget renders; pack section available | Vitest + integration |
| H-13-T11 | Load client formulas as approved versions (task executed when material arrives) and flip acceptance fixtures from xfail | BE/QA | H-13-T01 | Each KPI matches client's source formula on a fixture | pytest |
| H-13-T12 | Client-KPI fixture file `tests/fixtures/analytics/client_kpis.yaml` (xfail until client data) + default-KPI fixtures (passing) | QA | H-13-T06 | Defaults pass; client cases reported xfail, never pass | pytest |
| H-13-T13 | Performance: full KPI grid < 1.5 s on large fixture | QA | H-13-T06 | k6 passes | k6 |
| H-13-T14 | i18n keys, docs (KPI glossary with formulas) | FE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** each KPI matches the client's source formula on a fixture (Project_Phases.md).
- **Testing approach:** unit, data validation, performance, accessibility.
- **Risks:** material late or ambiguous → default set + documented questions; free-form data needs → catalogue extension tasks, never free SQL.

---

### 6.3 Finance Module — Loans, Interest & Credit Terms [v2.1]

### FN-01 · Loan register [v2.1] (provisional ID)

- **Branch:** `feature/FN-01-loan-register`
- **Objective:** record every financing arrangement of the organisation with its contractual terms and its ledger accounts.
- **Current behaviour:** loans exist only as a Loan-type bank/ledger account (F-01) with manual journals. (Xero: no loan module — beyond Xero.)
- **Expected behaviour:** `Loan` record with type (vehicle loan, equipment loan, term loan, line of credit, shareholder loan — to / from shareholder, lease-type financing, mortgage), direction (borrowed / lent), lender or borrower contact, reference/contract number, principal, disbursement date, first payment date, nominal annual rate, rate type (fixed / variable with rate-change history), compounding frequency (monthly, semi-annual, annual, daily, simple), payment frequency (weekly, bi-weekly, semi-monthly, monthly, quarterly, annual), term (months) or amortisation period with renewal term, payment type (blended, fixed principal, interest-only, custom), balloon/residual amount, fees (capitalised or expensed), security/collateral note, linked asset (I-01, e.g. the financed vehicle); ledger links: liability (or receivable for loans lent) account (auto-created as a sub-account under the Loan / LOC parent, e.g. "2610 Vehicle loan — RBC"), interest expense (or income) account, accrued interest account, paying bank account; documents attached (contract PDF); status draft / active / paid off / refinanced / written off.
- **Gap #s closed:** beyond Xero (Quotation §4 ★).
- **Business rules:** loan creates (or links) a liability account; principal > 0, rate ≥ 0, term ≥ 1 period; disbursement posts Dr bank (or asset / dealer clearing) / Cr loan liability, or is linked to an existing posted entry (no double posting); shareholder loans tagged for tax-book reporting (FN-05); a loan's terms are editable only in draft — after activation changes go through rate change / restructure events (FN-02); archived only when balance = 0.
- **Edge cases:** vehicle bought from a dealer with loan paid directly to the dealer (disbursement to clearing account linked to the asset bill); LOC with no fixed term (revolving: draws and repayments, interest on daily balance); interest-free shareholder loan; loan in USD (R-02); migration of an existing loan mid-life (opening balance at conversion date with remaining schedule).
- **UI/UX notes:** five-field quick form (amount, rate, term, frequency, first payment date) with the rest under "More terms"; type cards with icons and plain descriptions; account auto-create preview; "existing loan" toggle asks for current balance and next payment; live schedule preview (FN-02); empty-state copy "Record a car, equipment or shareholder loan — Numo9 splits every payment into principal and interest for you."
- **Dependencies:** F-01 (Loan/LOC account types), C-01, C-02, B-01, U-03 (feature key `finance.loans`), I-01 (optional asset link; link added when I-01 is merged).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| FN-01-T01 | ADR-007 loan engine (rate conventions, compounding vs payment frequency, rounding, schedule versioning, posting model) | DOC | — | ADR merged | Review |
| FN-01-T02 | Wireframes: loans list, quick form, "More terms", existing-loan mode, account preview, loan detail shell | UX | — | Approved | Review |
| FN-01-T03 | `Loan` model (fields above, OrgOwnedModel, status machine) + migration; register in tenant sweep | DB | — | Migration applies; sweep includes model | Unit |
| FN-01-T04 | `LoanRateChange` model (loan, effective_date, new_rate, reason) and `LoanFee` model (amount, treatment capitalise/expense, date) | DB | FN-01-T03 | Migration applies | Unit |
| FN-01-T05 | Validation service (ranges, date order: disbursement ≤ first payment, balloon < principal, frequency/compounding combos) with plain-language messages | BE | FN-01-T03 | Invalid combos rejected with message | Unit |
| FN-01-T06 | `LoanAccountProvisioner`: propose/create liability sub-account under Loan/LOC parent, interest expense/income, accrued interest accounts with GIFI defaults (2780/3140 long-term debt, 8710 interest); preview → confirm | BE | FN-01-T03, C-01 | Fresh org: preview lists accounts; confirm creates; GIFI mapped | Integration |
| FN-01-T07 | Disbursement service: post Dr bank/clearing / Cr loan liability via `post_journal()` or link an existing JE (prevent double posting) | BE | FN-01-T06, C-02 | Disbursement posts once; linking existing JE posts nothing new | Integration |
| FN-01-T08 | Existing-loan onboarding: opening balance at conversion date, remaining term, next payment date; opening entry through C-05 conversion balances when before conversion date | BE | FN-01-T07, C-05 | Mid-life loan shows correct remaining balance | Integration |
| FN-01-T09 | Revolving LOC mode: draws/repayments as loan events, daily-balance basis flag | DB/BE | FN-01-T03 | Draw increases liability; repayment decreases | Unit |
| FN-01-T10 | Status machine (draft → active → paid off / refinanced / written off) with guards and audit | BE | FN-01-T03, A-04 | Illegal transitions refused | Unit |
| FN-01-T11 | APIs `/api/v1/finance/loans/` (CRUD in draft, activate, events), feature key `finance.loans`, permissions (`finance.loans.manage`, `.view`) | API | FN-01-T05…T10 | OpenAPI; 402 without Finance; sweep passes | Integration |
| FN-01-T12 | Attach contract documents (A-06) and optional asset link (I-01 FK, nullable; wired when I-01 merges) | BE/API | FN-01-T11, A-06 | Document attached and visible | Integration |
| FN-01-T13 | Loans list screen (balance, next payment, rate, status chips, filters, saved views, empty state) | FE | FN-01-T11 | Story per state; Playwright | Playwright + axe |
| FN-01-T14 | Loan editor (quick form + More terms, type cards, account preview, existing-loan toggle, inline validation) | FE | FN-01-T11 | F4 steps 1–4 in Playwright | Playwright |
| FN-01-T15 | Global search registration (lender, reference, type) and quick-create `Alt+Shift+L` | FE/BE | FN-01-T11, A-09 | Search by contract number finds loan | Integration |
| FN-01-T16 | i18n keys (`finance.loan.*`), audit hooks | FE/BE | all | Gate passes; audit diffs visible | CI |
| FN-01-T17 | Acceptance tests: loan creates liability account link; data validated; disbursement single-posting | QA | all | Pass | pytest + Playwright |
| FN-01-T18 | Docs: loan types guide; data dictionary entries | DOC | all | Published | Review |

- **Deliverable acceptance:** loan creates liability account link; data validated (Project_Phases.md). Added: disbursement never double-posts.
- **Testing approach:** unit (validation, status), integration (provisioner, disbursement), functional (F4), security (sweep, 402).
- **Risks:** double-posting disbursement already entered via bank → "link existing entry" path and duplicate detector on amount/date; term ambiguity → ADR-007 conventions and explicit compounding field.

---

### FN-02 · Payment calculator & amortisation schedule [v2.1] (provisional ID)

- **Branch:** `feature/FN-02-amortisation-schedule`
- **Objective:** an exact schedule splitting every payment into principal and interest, recalculated safely on rate changes and early repayments.
- **Current behaviour:** none.
- **Expected behaviour:** Decimal schedule engine: periodic rate from nominal rate and compounding vs payment frequency (effective periodic rate = (1 + j/m)^(m/p) − 1); payment for blended loans by annuity formula (rounded to the cent, last payment adjusts residual), fixed-principal, interest-only and balloon variants; day-count for LOC / daily basis (actual/365); schedule lines: number, date, opening balance, payment, interest, principal, closing balance, cumulative interest, status (scheduled / posted / skipped); summary: payment amount, number of payments, total interest over term, total cost, payoff date, interest YTD (fiscal and calendar), interest remaining; **recalculation events**: rate change from a date, extra/early repayment (lump sum or recurring extra), payment holiday, restructure — the engine regenerates only lines after the event date, preserves posted lines exactly and stores schedule versions with a diff; "what if I pay extra $X" slider (EXTRA X7) shows interest saved and new payoff date without saving; PDF/XLSX export.
- **Gap #s closed:** beyond Xero.
- **Business rules:** schedule matches the reference calculator to the cent (reference = Decimal implementation cross-checked with numpy-financial and the client-chosen calculator; tolerance 0.00 on payment amount, ≤ 0.01 on the final balloon adjustment); posted lines are immutable; every recalculation creates a new `LoanScheduleVersion` with reason and audit; rounding: ROUND_HALF_UP to the cent per line; payment dates roll forward to the next business day when the setting is on (interest computed to the actual date for daily-basis loans only).
- **Edge cases:** 0 % rate (payment = principal ÷ n); very long terms (360 payments); semi-monthly dates (15th and last day); month-end first payment (31st → shorter months); rate change between two payment dates (split interest by days for daily basis, apply from next period for periodic basis — per ADR-007, setting per loan); extra payment larger than balance (caps and pays off); negative amortisation (interest-only below interest due) warned.
- **UI/UX notes:** schedule table virtualised with sticky header and posted/scheduled chips; stacked area chart principal vs interest with table alternative; summary tiles (payment, total interest, YTD interest, payoff date); recalculation dialogs show before/after diff (changed lines highlighted, totals delta); slider with instant client-side preview (server-confirmed on save).
- **Dependencies:** FN-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| FN-02-T01 | Wireframes: schedule tab, summary tiles, chart, rate-change and extra-payment dialogs with diff, what-if slider | UX | — | Approved | Review |
| FN-02-T02 | Reference fixtures `tests/fixtures/finance/loans/*.yaml`: 12 loans (car 35,000 / 6.99 % / 60 m → 692.88; equipment quarterly; mortgage semi-annual compounding; 0 %; balloon; interest-only; fixed-principal; semi-monthly; LOC daily; USD loan; rate change; early repayment) with expected lines from two independent calculators | QA | — | Fixtures reviewed; sources noted | Review |
| FN-02-T03 | `LoanScheduleVersion` (loan, version, reason, created_by, created_at, active) and `LoanScheduleLine` (version, n, date, opening, payment, interest, principal, closing, cumulative_interest, status, posted_journal FK) partitioned by org | DB | FN-01 | Migration applies | Unit |
| FN-02-T04 | Periodic-rate converter (nominal j, compounding m, payments p → effective periodic rate) Decimal, 28 digits | BE | — | Semi-annual mortgage rate fixture exact | Unit |
| FN-02-T05 | Payment-date generator (rrule by frequency, month-end handling, semi-monthly, business-day roll setting) | BE | — | Date fixtures pass incl. 31 Jan start | Unit |
| FN-02-T06 | Blended (annuity) generator with cent rounding and final-payment residual adjustment | BE | FN-02-T04, T05 | Car loan fixture: 692.88 × 59 + final adjusted; closing 0.00 | Unit against fixtures |
| FN-02-T07 | Fixed-principal, interest-only and balloon generators | BE | FN-02-T06 | Fixtures pass | Unit |
| FN-02-T08 | Daily-basis / LOC interest calculator (actual/365 on daily balances from draws/repayments) | BE | FN-02-T04, FN-01-T09 | LOC fixture interest exact | Unit |
| FN-02-T09 | Summary service (payment, count, total interest, total cost, payoff date, YTD interest calendar and fiscal, remaining interest) | BE | FN-02-T06…T08 | Summary fixtures pass | Unit |
| FN-02-T10 | Recalculation engine: rate change, extra payment (lump/recurring), payment holiday, restructure → new version regenerating lines after event date; posted lines copied unchanged | BE | FN-02-T06…T09, FN-01-T04 | Recalculation preserves past (posted) lines byte-for-byte; fixture post-change lines match | Unit + Hypothesis (posted prefix invariant) |
| FN-02-T11 | Cross-check harness comparing engine to numpy-financial for random loans (tolerance 0.005 per line pre-rounding) | QA | FN-02-T06 | 10,000 random loans pass | Hypothesis |
| FN-02-T12 | Version diff service (changed lines, totals delta) | BE | FN-02-T10 | Diff fixture correct | Unit |
| FN-02-T13 | What-if endpoint (stateless projection with extra payment) and TypeScript port of the generator for instant slider preview, parity-tested against the API | BE/FE | FN-02-T06 | TS and Python outputs identical on fixtures | Vitest + pytest parity |
| FN-02-T14 | APIs `/finance/loans/{id}/schedule`, `/schedule/versions`, `/recalculate` (preview + commit), `/what-if`, export PDF/XLSX | API | FN-02-T09…T13 | OpenAPI; sweep; permission `finance.loans.manage` for commit | Integration |
| FN-02-T15 | Schedule tab UI (virtualised table, chips, sticky header, export) and summary tiles | FE | FN-02-T14 | Playwright; values = API | Playwright |
| FN-02-T16 | Principal-vs-interest chart with table alternative | FE | FN-02-T14 | axe passes; table present | Vitest + axe |
| FN-02-T17 | Rate-change, extra-payment, payment-holiday dialogs with before/after diff and confirm | FE | FN-02-T14 | Playwright for each event | Playwright |
| FN-02-T18 | What-if slider (interest saved, new payoff date) | FE | FN-02-T13 | Slider updates < 100 ms | Vitest |
| FN-02-T19 | Schedule PDF (WeasyPrint, Letter, inch margins, organisation name header) | BE | FN-02-T14 | PDF snapshot test | Snapshot |
| FN-02-T20 | i18n keys, docs (how schedules are calculated; conventions) | FE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** schedule matches reference calculator to the cent; recalculation preserves past payments (Project_Phases.md).
- **Testing approach:** unit against fixtures, property (posted prefix invariant, closing = 0), cross-check harness, parity (TS vs Python), functional, snapshot.
- **Risks:** convention mismatch with lender (compounding, day count) → explicit per-loan fields + lender-statement match (FN-03 X8); rounding drift → per-line rounding + final-line adjustment documented in ADR-007.

---

### FN-03 · Automatic loan posting [v2.1] (provisional ID)

- **Branch:** `feature/FN-03-loan-posting`
- **Objective:** every loan payment and period-end accrual posts itself correctly, so loan liability in the GL always equals the schedule.
- **Current behaviour:** accountants post loan payments as manual journals (Xero: same — the teardown shows journals as the riskiest entry path, gap #33 context).
- **Expected behaviour:** on each scheduled payment date (or when a matching bank transaction is recorded/imported), post Dr loan liability (principal) + Dr interest expense (interest) / Cr bank (payment) via `post_journal()` with journal type `loan_payment` and a link to the schedule line; period-end accrual job posts accrued interest from last payment date to period end (Dr interest expense / Cr accrued interest) with auto-reversal on the first day of the next period (C-03 auto-reverse); bank-match: a spend-money / imported line matching a scheduled payment (amount ± tolerance, date window, payee) is proposed as "Loan payment" and on confirm posts the split instead of a single expense line; missed payment handling (status overdue, notification, optional late fee line); lender statement import/match (EXTRA X8) flags differences; exceptions-engine rule `loan_schedule_mismatch` (EXTRA X13).
- **Gap #s closed:** beyond Xero; reduces manual journals (gap #33 context).
- **Business rules:** loan liability in GL = schedule closing balance after each posted payment (tie-out gate); a schedule line posts once (idempotency key = loan + version + line n); postings obey GL lock (a payment dated in a locked period is held with a message, not silently moved); auto-post is a per-loan setting (auto / on bank match only / manual confirm); accruals only when the organisation's accrual setting is on (default on for accrual-basis orgs); posting uses book `both` (tax differences handled in FN-05/K-07).
- **Edge cases:** payment amount on bank differs from schedule (difference prompt: extra principal, fee, or variance account); payment on a non-scheduled date; schedule recalculated after an accrual was posted (accrual reversal handles it); LOC interest charged by bank statement (post from statement amount and reconcile to calculated interest); USD loan (FX revaluation through R-02).
- **UI/UX notes:** "Postings" tab with posted / upcoming / overdue sections; bank-transaction coding panel shows a "Looks like a payment on Vehicle loan — RBC (#14 of 60)" suggestion card with split preview; overdue chip on loans list and dashboard tile; lender-statement match screen with difference highlighting.
- **Dependencies:** FN-02, C-02, C-03 (journal types, auto-reverse), F-01/F-02/F-04 (bank transactions, import, rules), A-08 (jobs), K-09 (exceptions).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| FN-03-T01 | Wireframes: postings tab, bank suggestion card with split preview, overdue states, lender-statement match | UX | — | Approved | Review |
| FN-03-T02 | Journal types `loan_payment`, `loan_accrual`, `loan_disbursement` registered in C-03 catalogue | DB/BE | C-03 | Types available | Unit |
| FN-03-T03 | `LoanPostingService.post_line(line)` — builds principal/interest/bank lines, idempotency key, links JE to line, marks line posted | BE | FN-02-T03, C-02 | Car loan payment 1: interest 203.88, principal 489.00 posts once; second call no-op | Unit + integration |
| FN-03-T04 | Lock-date handling: hold with reason when date locked; notify accountant | BE | FN-03-T03, A-05 | Locked payment held, message names lock | Integration |
| FN-03-T05 | Scheduler job (daily, per org timezone) posting due lines for loans with auto-post setting; idempotent across workers | OPS | FN-03-T03, A-08 | Two workers → one posting per line | Integration (concurrency) |
| FN-03-T06 | Period-end accrual job + auto-reversal on next period's first day; skip when setting off | BE/OPS | FN-03-T03, C-03 | Month-end accrual fixture exact; reversal posted | Integration (freezegun) |
| FN-03-T07 | Bank-match matcher (amount tolerance, date window, payee/lender contact, reference) producing suggestions for bank lines (F-02 import and spend money) | BE | FN-03-T03, F-02 | Imported payment matched to line #14 | Unit + integration |
| FN-03-T08 | Confirm-from-bank flow: post split instead of single expense; difference handling (extra principal → recalculation event via FN-02; fee → expense; variance → account) | BE | FN-03-T07, FN-02-T10 | Payment 742.88 with 50 extra creates extra-payment event and new version | Integration |
| FN-03-T09 | Missed-payment detector (overdue after N days), notification (A-07), optional late-fee line | BE/OPS | FN-03-T05 | Overdue status after grace days | Integration |
| FN-03-T10 | LOC statement-interest posting and variance vs calculated interest | BE | FN-02-T08 | Variance shown; posted amount = statement | Integration |
| FN-03-T11 | Lender-statement import (CSV/XLSX/PDF manual entry) and match vs schedule with difference list (X8) | BE/FE | FN-03-T03 | Fixture difference flagged with message per §3.5 | Integration |
| FN-03-T12 | `manage.py tieout_loans` + exceptions rule `loan_schedule_mismatch` (GL liability vs schedule closing) registered in K-09 | QA/BE | FN-03-T03, K-09 | 0 differences on fixture; injected mismatch flagged | Integration |
| FN-03-T13 | APIs: `/finance/loans/{id}/postings`, `/post-line`, `/bank-suggestions`, `/confirm-bank-match`, `/statement-match` | API | FN-03-T03…T11 | OpenAPI; sweep; permissions | Integration |
| FN-03-T14 | Postings tab UI (posted/upcoming/overdue, drill to JE, manual "post now") | FE | FN-03-T13 | Playwright | Playwright |
| FN-03-T15 | Bank coding suggestion card in F-module bank transaction panel | FE | FN-03-T13, F-01 | Suggestion visible and confirm posts split | Playwright |
| FN-03-T16 | Property test: random payment/extra/rate-change sequences → GL liability = schedule balance after each posting | QA | FN-03-T03, T08 | 1,000 examples pass | Hypothesis |
| FN-03-T17 | Dashboard tile "Loan payments due this week / overdue" (K-05 widget) | FE | FN-03-T13, K-05 | Widget shows counts; 0 state | Vitest |
| FN-03-T18 | i18n keys, audit hooks, docs (posting map for loans) | FE/BE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** loan liability in GL = schedule balance after each payment (Project_Phases.md).
- **Testing approach:** unit, integration, concurrency, property, data validation (tie-out), functional.
- **Risks:** duplicate posting from both scheduler and bank match → single idempotency key per line; bank amount variance → explicit difference handling, never silent.

---

### FN-04 · Credit-terms interest handling [v2.1] (provisional ID)

- **Branch:** `feature/FN-04-credit-terms-interest`
- **Objective:** handle the money cost of credit terms on purchases and sales: discounts captured or missed, late-payment interest charged by suppliers or to customers, and the effective annual cost of forgoing a discount.
- **Current behaviour:** E-07 captures early-payment discounts on bills and invoices; D-07 can add a late-fee line on reminders; there is no interest accrual and no cost-of-forgoing figure.
- **Expected behaviour:** terms master (B-01) extended with late-interest terms (rate % per month or per year, simple or compound, grace days, minimum charge, basis: overdue balance); **customer side** — overdue interest calculated daily, charged by a periodic "interest charge" invoice (or added to the next statement), posted Dr AR / Cr interest income, respecting disputes and opt-outs (D-07); **supplier side** — supplier interest recorded from the supplier's statement or auto-accrued per supplier terms, posted Dr interest expense (non-deductible flag option for penalties) / Cr AP; **discount analytics** — discounts captured vs missed (amount and count) by supplier and period, "pay now or later" helper on each discountable bill (EXTRA X9) showing the effective annual cost of forgoing the discount = (d ÷ (1 − d)) × (365 ÷ (net days − discount days)), formula stored in the Formula Registry (`finance.cost_of_forgoing_discount`) so the client's version can replace it; postings to configured accounts (discount received, discount allowed, interest income, interest expense).
- **Gap #s closed:** 10 and 23 (extends E-07 / D-07 beyond Xero); beyond Xero.
- **Business rules:** FN-04 never re-posts a discount already posted by E-07 (single source: E-07 posts; FN-04 reports); late interest posts to configured accounts; no interest on disputed invoices or contacts opted out; interest charge invoices are ordinary invoices (revisable per D-03b, taxable status per G-01: interest is generally GST/HST-exempt — default tax code "Exempt — financial service", editable); cost-of-forgoing figure matches formula; interest calculation uses the organisation's day count (actual/365) and stops at payment date.
- **Edge cases:** partial payments (interest on remaining overdue balance by day); payment allocated across invoices; invoice revision changing due date or amount after interest charged (recalculate next run, adjustment line); currency invoices (interest in document currency); supplier interest already included on a bill line (avoid double count via "interest included" flag).
- **UI/UX notes:** terms editor with plain-language summary ("2 % off if paid within 10 days, otherwise due in 30 days; 1.5 % per month interest after 15 days' grace"); bill detail banner (F5 flow); Credit terms & interest screen with four tabs (Discounts captured / Discounts missed / Interest charged / Interest received); interest run preview before creating charge invoices.
- **Dependencies:** E-07, D-07, B-01 (terms), FN-01 (Finance product key), H-11 (Formula Registry), G-01 (tax codes).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| FN-04-T01 | Wireframes: terms editor summary sentence, bill "pay now or later" banner, interest run preview, credit terms & interest screen | UX | — | Approved | Review |
| FN-04-T02 | Extend `PaymentTerms` (B-01) with late-interest fields (rate, period basis, simple/compound, grace days, minimum charge) + migration | DB | B-01 | Migration applies; existing terms unaffected | Migration test |
| FN-04-T03 | Terms summary-sentence generator (en-CA ICU messages; fr-CA keys) | BE/FE | FN-04-T02 | Fixture terms produce expected sentence | Unit |
| FN-04-T04 | Register `finance.cost_of_forgoing_discount` default formula `(d/(1-d))*(365/(N-D))` in Formula Registry | DB | H-11-T05 | 2/10 net 30 → 37.24 % | Unit |
| FN-04-T05 | Cost-of-forgoing service per bill (uses terms, payment date choices) | BE | FN-04-T04, E-07 | Bill fixture banner values exact | Unit |
| FN-04-T06 | Customer overdue-interest calculator (daily on overdue balance, partial payments, grace, minimum, stop at payment, skip disputed/opt-out) | BE | FN-04-T02, D-05, D-07 | Fixture: 1,000 overdue 45 days at 1.5 %/month with 15-day grace → expected amount | Unit + Hypothesis (interest monotonic in days) |
| FN-04-T07 | Interest run (periodic job + manual): preview → create interest-charge invoices (or statement lines) with tax code default "Exempt — financial service"; posting Dr AR / Cr interest income | BE/OPS | FN-04-T06, D-03a | Run creates one invoice per customer; posts to configured account | Integration |
| FN-04-T08 | Supplier interest: record from supplier statement (B-02 reconciliation) or auto-accrue per supplier terms; post Dr interest expense / Cr AP; non-deductible penalty flag (feeds K-07 tax adjustment suggestion) | BE | FN-04-T02, B-02, E-02 | Supplier interest posts to configured account; flag stored | Integration |
| FN-04-T09 | Double-count guards: never re-post E-07 discounts; "interest included" flag on bill lines | BE | FN-04-T08, E-07 | Regression: E-07 discount posted once | Regression |
| FN-04-T10 | Discount analytics service (captured vs missed by supplier/customer/period, amounts and counts) | BE | E-07 | Totals = discount accounts in GL | Data validation |
| FN-04-T11 | Account-mapping settings (discount received, discount allowed, interest income, interest expense, penalty account) | DB/FE | C-01 | Mapping saved, audited | Playwright |
| FN-04-T12 | APIs: `/finance/terms-interest/runs` (preview/commit), `/finance/discounts/analytics`, `/bills/{id}/cost-of-forgoing`, supplier-interest endpoints; feature key `finance.credit_terms` | API | FN-04-T05…T10 | OpenAPI; sweep; 402 | Integration |
| FN-04-T13 | Terms editor UI with summary sentence | FE | FN-04-T03, T12 | Playwright | Playwright |
| FN-04-T14 | Bill banner "pay now or later" (F5) and invoice "interest accrued" chip | FE | FN-04-T12 | F5 flow passes | Playwright |
| FN-04-T15 | Credit terms & interest screen (4 tabs, export) and interest run preview UI | FE | FN-04-T12 | Playwright + axe | Playwright |
| FN-04-T16 | Fixtures `tests/fixtures/finance/credit_terms/*.yaml` and acceptance tests (late interest and discounts post to configured accounts; cost-of-forgoing matches formula) | QA | all | Pass | pytest |
| FN-04-T17 | Client-formula placeholder fixture (xfail until client finance material supplies its version) | QA | FN-04-T04 | Reported xfail, never pass | pytest |
| FN-04-T18 | i18n keys, docs (credit terms guide) | FE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** late interest and discounts post to configured accounts; cost-of-forgoing figure matches formula (Project_Phases.md).
- **Testing approach:** unit with fixtures, property, integration, regression on E-07/D-07, data validation.
- **Risks:** double posting with E-07 → E-07 is the single poster, FN-04 reports; tax status of interest → default exempt code with accountant override, documented.

---

### FN-05 · Loan & interest reports + finance KPIs [v2.1] (provisional ID)

- **Branch:** `feature/FN-05-finance-reports-kpis`
- **Objective:** report loans and interest in both the accounting and the tax book and show finance KPIs from the client's material.
- **Current behaviour:** report engine (K-01) has no loan reports; two-book engine K-07 is built in Part 2 of this phase.
- **Expected behaviour:** reports in the K-01 engine with book selector: **Loan continuity** (opening balance, additions/draws, principal repaid, interest charged, interest paid, closing balance, current portion due within 12 months, long-term portion — EXTRA X14), **Interest expense/income by loan and period** (accrued vs paid), **Loan schedule summary** (all loans, next 12 months cash requirement), **Credit-terms report** (discounts captured/missed, interest charged/received from FN-04), **Shareholder loan report** (balances and movements for tax review); tax book view shows interest after tax adjustments (e.g. non-deductible penalties removed, shareholder-loan interest treatment) using K-07 tax-adjustment journals; Balance Sheet presentation: current portion of long-term debt reclassified for presentation (K-02 presentation hook, no posting); finance KPIs in the Formula Registry (`kpi.finance.*`): debt-to-equity, debt-service coverage ratio, interest coverage, average cost of debt, current portion ratio, discounts-captured ratio, effective annual cost of forgone discounts — starter set labelled "Numo9 default" until client material is loaded; dashboard tiles reuse H-13 components.
- **Gap #s closed:** beyond Xero; supports K-02 GAAP presentation (gap #56 context).
- **Business rules:** reports tie to GL in both books (loan continuity closing = GL liability per book; interest = GL interest accounts per book); current portion = Σ principal of schedule lines due within 12 months of the report date; KPIs evaluate through the Formula Registry; tax-book differences come only from tax-adjustment journals (K-07).
- **Edge cases:** loan with rate change inside the 12-month window (current portion from active version); LOC (current by default); FX loans (closing at report-date rate via R-02); report date before loan start (excluded).
- **UI/UX notes:** report screens via shared runner with book selector (Accounting / Tax / Side by side); continuity report drill to schedule lines and JEs; KPI tiles with explainers; export PDF/XLSX with organisation name header.
- **Dependencies:** FN-03, FN-04, K-01, K-07 (Part 2), K-02, H-13 (KPI components), H-11 (Formula Registry). Build order: start report services after FN-03; enable tax-book tests after K-07 merges.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| FN-05-T01 | Wireframes: loan continuity, interest report, side-by-side book view, finance KPI tiles | UX | — | Approved | Review |
| FN-05-T02 | Extract finance KPIs/formulas from client material into `docs/analytics/client-kpis.md` (finance section) or record "not yet received" | DOC | client input | Reviewed | Review |
| FN-05-T03 | Loan continuity report service (per book, per loan, period) incl. current / long-term split | BE | FN-03, K-01 | Closing = GL liability per book on fixture | Data validation |
| FN-05-T04 | Interest by loan and period report (accrued vs paid; per book) | BE | FN-03 | Total = GL interest accounts per book | Data validation |
| FN-05-T05 | Loan schedule summary / 12-month cash requirement report | BE | FN-02 | Fixture totals correct | Unit |
| FN-05-T06 | Credit-terms report (from FN-04 analytics) | BE | FN-04 | Totals = GL discount/interest accounts | Data validation |
| FN-05-T07 | Shareholder loan report (balances, movements, interest) | BE | FN-01, FN-03 | Fixture correct | Unit |
| FN-05-T08 | Balance-sheet presentation hook: reclassify current portion of long-term debt for display in K-02 (no posting) | BE | FN-05-T03, K-02 | BS shows current portion under current liabilities; TB unchanged | Integration |
| FN-05-T09 | Tax-book support: report services read `book` parameter; tax-adjustment suggestions for non-deductible penalty interest (FN-04 flag) as draft K-07 journals | BE | K-07, FN-04-T08 | Accounting vs tax interest differ exactly by adjustments | Integration (enabled after K-07) |
| FN-05-T10 | Register finance KPI definitions and data sources (total debt, equity, EBITDA from mapped accounts, debt service, interest expense, discounts captured/available) in Formula Registry / `KpiDataSource` | BE | H-13-T03, T04 | Default KPI fixtures pass | Unit |
| FN-05-T11 | APIs for reports (runner definitions) and `/analytics/kpis?group=finance`; feature key `finance.reports` | API | FN-05-T03…T10 | OpenAPI; sweep; 402 | Integration |
| FN-05-T12 | Report screens (continuity, interest, schedule summary, credit terms, shareholder loans) with book selector and drill-down | FE | FN-05-T11 | Playwright | Playwright + axe |
| FN-05-T13 | Finance KPI dashboard section (reuse H-13 tiles) + K-05 widgets | FE | FN-05-T11, H-13-T09 | Renders; 0 states | Vitest |
| FN-05-T14 | PDF/XLSX exports with organisation display and legal name header (K-01 rule) | BE | FN-05-T12 | Export matches screen | Snapshot |
| FN-05-T15 | Acceptance tests: reports tie to GL in both books; client-KPI fixtures (xfail until material) and default KPI fixtures (pass) | QA | all | Pass / xfail as stated | pytest |
| FN-05-T16 | K-06 management-pack section "Financing" hook | BE | FN-05-T03, K-06 | Section available in pack | Integration |
| FN-05-T17 | i18n keys, docs (finance reports guide, KPI glossary) | FE/DOC | all | Gate passes | CI |

- **Deliverable acceptance:** reports tie to GL in both books (Project_Phases.md); KPIs match client formulas once supplied.
- **Testing approach:** data validation (per-book tie-outs), unit, integration, functional, snapshot.
- **Risks:** dependency on K-07 timing → report services built book-agnostic first, tax-book tests enabled at K-07 merge; KPI material late → defaults + xfail.


---

### 6.4 Fixed Assets & CCA (Component I)

### I-01 · Asset register with book & tax settings
- **Branch:** `feature/I-01-asset-register`
- **Objective:** a fixed-asset register that opens on a fresh organisation with zero setup, holds book (SL/DB) and tax (CCA class) settings per asset, and ties every asset to its GL cost and accumulated-depreciation accounts.
- **Current behaviour:** no asset model exists. Bills (E-02) and journals (C-02/C-03) can post to fixed-asset accounts but nothing records the asset itself. (In Xero the module is blocked behind a "start date" wall, the `/FixedAssets` URL is a hard 404, and 21 fixed-asset accounts are not linked to the register.)
- **Expected behaviour (better than Xero):** Fixed assets opens immediately, using the organisation's conversion date (C-05) as the default start date. Assets are created manually, from a bill line, from a document in the inbox (A-06) or by import. Each asset has a book method (straight-line or declining-balance, rate or useful life, residual, convention full-month/half-month) and a tax setting (CCA class from a seeded, effective-dated Schedule II table, half-year rule, AII and immediate-expensing flags). The register reconciles to the GL by asset type every time it is opened.
- **Gap #s closed:** #34 (usable immediately; no hard 404; register tied to CoA), #18 partial (CoA typing respected).
- **Business rules:** asset type maps to exactly one cost account, one accumulated-depreciation account and one depreciation-expense account; status Draft → Registered → Disposed; registering requires cost > 0, in-service date, book method, CCA class; CCA class list is data with effective dates; Class 8 = 20 % DB, Class 10 = 30 %, Class 10.1 = 30 % with cost cap, Class 12 = 100 %, Class 13 = SL over lease, Class 14.1 = 5 %, Class 43 = 30 %, Class 50 = 55 %, Class 53 = 50 %, Class 54/55 = 30 %/40 %; half-year rule default on except for classes flagged exempt; edits to a registered asset with posted depreciation create an audit entry and a "recalculate from period" prompt — never silent rewrites.
- **Edge cases:** asset bought before conversion date (opening accumulated depreciation entered); bill line split into several assets; asset with cost in foreign currency (R-02 rate on bill date); class 10.1 cost above the prescribed limit; asset type changed after depreciation posted; deleted bill that created an asset (blocked while asset registered).
- **UI/UX notes:** register list with tabs Draft / Registered / Disposed and a reconciliation strip at the top ("Register 48,200.00 · GL 48,200.00 · Difference 0.00 ✓", red with drill-down when not zero); asset form in two clear columns "Accounting book" and "Tax book (CCA)" with a live 5-year schedule preview on the right; CCA class picker shows class number, description, rate and an example ("Class 8 — furniture, fixtures, most equipment · 20 % declining balance"); "Create asset" action available on every bill line coded to a fixed-asset account; first-run empty state explains in one sentence and offers three buttons (Add asset, Import register, Create from a bill).
- **Dependencies:** C-01, C-02, C-05, E-02, A-06, A-04, U-03 (feature key `assets.register`).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| I-01-T01 | Figma wireframes: register list, asset form (book / tax columns + schedule preview), empty state, reconciliation strip | UX | — | Wireframes reviewed by project lead; every state (empty/loading/error/gated/read-only) drawn | Design review |
| I-01-T02 | `CCAClass` model (class_no, description, rate, method DB/SL, half_year_rule bool, aii_eligible, immediate_expensing_eligible, cost_cap, effective_from/to) + migration | DB | — | Migration applies; unique (class_no, effective_from) | Unit |
| I-01-T03 | Seed command `seed_cca_classes` loading Schedule II starter set (8, 10, 10.1, 12, 13, 14.1, 43, 50, 53, 54, 55 …) as data | BE | I-01-T02 | `Class 8` returns 20 % DB on 2026-06-30; idempotent re-run adds 0 rows | Unit |
| I-01-T04 | `AssetType` model (org-owned: name, cost_account, accum_dep_account, dep_expense_account, default book method/rate/life, default CCA class) with account-type validation | DB | C-01 | Saving with a non-asset cost account rejected with field error | Unit |
| I-01-T05 | Default asset types created with the Canadian CoA template (Furniture → Class 8, Computer equipment → Class 50, Vehicles → Class 10, Leasehold → Class 13, Building → Class 1) | BE | I-01-T04 | Fresh org has 6 asset types mapped to template accounts; 0 unmapped | Unit |
| I-01-T06 | `FixedAsset` model (`OrgOwnedModel`): number, name, type, serial, location, purchase_date, in_service_date, cost, residual, book_method, book_rate, useful_life_months, convention, cca_class, half_year_rule, aii_flag, immediate_expensing, status, source_bill_line, opening_accum_dep | DB | I-01-T04, A-01 | Migration applies; tenant manager scopes queries | Unit + tenant sweep |
| I-01-T07 | Validation service: registration rules (cost > 0, in-service date ≥ purchase date, method fields consistent, SL needs life, DB needs rate) | BE | I-01-T06 | Each invalid combination returns a named field error | Unit (parametrised) |
| I-01-T08 | Default start date = conversion date from C-05; no blocking setup screen | BE | C-05 | New org opens register with no "set start date" step | Functional |
| I-01-T09 | Schedule preview service (pure function: asset → list of periods with book dep and CCA) used by form preview | BE | I-01-T06 | Class 8, 10,000, mid-year → CCA 1,000 yr 1, 1,800 yr 2 | Unit (fixture) |
| I-01-T10 | Register action "Register asset" posting nothing (cost already in GL) but linking asset to bill line / journal line; status → Registered | BE | I-01-T07 | Asset from bill links back both ways; status audited | Integration |
| I-01-T11 | "Create asset from bill line" service + split one line into N assets with cost totals checked | BE | E-02, I-01-T10 | Split totals must equal line amount (net of recoverable tax) | Unit |
| I-01-T12 | "Create asset from document" hook on A-06 inbox (prefill from file metadata / E-05 extraction when available) | BE | A-06 | File attached to new draft asset | Integration |
| I-01-T13 | Register ↔ GL reconciliation query per asset type (cost and accumulated dep vs account balances at date) | BE | I-01-T06, C-02 | Returns difference and offending journal lines | Unit |
| I-01-T14 | REST API `/api/v1/assets/`, `/asset-types/`, `/cca-classes/` (list/filter/create/update/register), permission `assets.manage`, feature key `assets.register` | API | I-01-T07, U-03 | Gated org receives 402 with product name; cross-org ID → 404 | Integration + sweep |
| I-01-T15 | Audit-log hooks on asset create/edit/register with field diffs | BE | A-04 | Edit of cost shows old/new in history | Integration |
| I-01-T16 | Register list screen (tabs, search, column chooser, saved views, reconciliation strip) | FE | I-01-T14 | Strip shows 0.00 on fixture; tabs count = list count | Playwright |
| I-01-T17 | Asset form with Accounting / Tax columns and live schedule preview (debounced) | FE | I-01-T09 | Changing rate updates preview < 300 ms | Playwright + Vitest |
| I-01-T18 | CCA class picker component (search by number/description, rate badge, effective-date filter) | FE | I-01-T03 | Expired class not offered on later in-service date | Vitest |
| I-01-T19 | "Create asset" action on bill editor lines coded to fixed-asset accounts | FE | I-01-T11 | Button appears only on asset-account lines | Playwright |
| I-01-T20 | Asset import (CSV/XLSX, column mapping, dry-run, opening accumulated depreciation) | BE/FE | I-01-T07 | Dry-run report shows errors per row; re-import 0 duplicates by asset number | Integration |
| I-01-T21 | i18n keys (en-CA, fr-CA placeholders) for all asset strings; Canadian terms (amortization/CCA) | FE | I-01-T16 | i18n lint passes | CI |
| I-01-T22 | Gap-34 test: fresh org → open module → add asset without any setup; `/fixed-assets` and legacy-style URLs redirect | QA | I-01-T16 | Test tagged `gap-34` green | Playwright |
| I-01-T23 | Docs: user guide page + data dictionary entries for asset models | DOC | I-01-T16 | Page in `docs/` | Review |

- **Deliverable acceptance:** asset from a bill links back; Class 8 asset of 10,000 bought mid-year → CCA 1,000 (half-year) year 1 and 1,800 year 2; module opens on a fresh organisation with no setup; register ties to GL (difference 0.00 on fixture).
- **Testing approach:** unit (validation, schedule preview, seed idempotency), integration (bill → asset, API gating), functional (Playwright first-run), tenant sweep, gap-34 tag.
- **Risks & mitigations:** CCA rates changing → classes are effective-dated data; register drifting from GL → reconciliation strip + exceptions rule (K-09) "register ≠ GL".

### I-02 · Book depreciation runs (SL & DB)
- **Branch:** `feature/I-02-depreciation-runs`
- **Objective:** monthly/annual depreciation runs posting accounting-book journals that equal the schedule, with a continuity report.
- **Current behaviour:** assets exist (I-01) with methods but nothing posts depreciation.
- **Expected behaviour:** "Run depreciation to <period end>" previews every asset's charge, posts one depreciation journal per run (journal type `depreciation`, book `accounting`), is idempotent per period, and can be rolled back while the period is open. The continuity report (opening cost, additions, disposals, closing cost; opening accumulated, charge, disposals, closing accumulated; NBV) ties to the GL.
- **Gap #s closed:** #34.
- **Business rules:** SL = (cost − residual) / life months × months in period with convention; DB = opening NBV × rate × period fraction; never depreciate below residual; one run per period per org; run cannot post into a locked GL period (A-05); rollback only latest run and only if period open; template methods from I-04 override defaults; rounding difference absorbed in last period.
- **Edge cases:** asset added mid-period (half-month vs full-month), asset disposed mid-period, change of method after runs (prospective only), life ending mid-period, catch-up run over several periods, concurrent run requests.
- **UI/UX notes:** run wizard: 1) choose period end (defaults to last month end), 2) preview table with totals by asset type and per-asset expand, 3) Post — one click, with a success toast linking the journal; "last run" badge on register header; rollback is an explicit secondary action with reason.
- **Dependencies:** I-01, C-02, C-03, A-05, A-08.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| I-02-T01 | Wireframes: run wizard (period, preview, post), rollback dialog, continuity report | UX | — | Approved | Review |
| I-02-T02 | SL calculation function with conventions (full-month, half-month) and residual floor | BE | I-01 | Fixtures match client SL template to the cent | Unit (Hypothesis: never below residual) |
| I-02-T03 | DB calculation function (rate, period fraction, first-period convention) | BE | I-01 | Fixtures match client DB template to the cent | Unit |
| I-02-T04 | `DepreciationRun` model (period_end, status Preview/Posted/RolledBack, journal FK, created_by) + `DepreciationLine` (asset, amount, book) | DB | I-01 | Unique (org, period_end, status=Posted) | Unit |
| I-02-T05 | Preview service: computes lines for all registered assets up to period end incl. catch-up periods | BE | I-02-T02/T03 | Preview totals = sum of per-asset schedules | Unit |
| I-02-T06 | Post service: one balanced JE (Dr dep expense per type / Cr accumulated dep per type), type `depreciation`, book `accounting`, inside one transaction with advisory lock | BE | I-02-T05, C-02 | Two concurrent posts → one succeeds, one gets conflict | Integration (concurrency) |
| I-02-T07 | Lock-date enforcement (refuse period ≤ GL lock, message names the lock) | BE | A-05 | Error text "GL locked to 30 Jun 2026" | Unit |
| I-02-T08 | Rollback service (latest run only, open period, reason required) via JE reverse() | BE | I-02-T06 | Rollback restores NBV; audit row with reason | Integration |
| I-02-T09 | Scheduled monthly auto-run option (Celery beat, org setting off by default, idempotency key org+period) | OPS/BE | A-08 | Worker restart → still one run per period | Integration |
| I-02-T10 | Continuity report query (cost and accumulated roll-forward by type and by asset) | BE | I-02-T06 | Closing = GL balances at date | Unit (data validation) |
| I-02-T11 | API `/api/v1/assets/depreciation-runs/` preview/post/rollback; permission `assets.depreciate` | API | I-02-T06 | Permission matrix test passes | Integration |
| I-02-T12 | Run wizard UI with preview grid (virtualised for 5,000 assets) | FE | I-02-T11 | 5,000-asset preview renders < 2 s | Playwright + perf |
| I-02-T13 | Continuity report screen + PDF/XLSX export (K-01 engine) | FE | I-02-T10, K-01 | Export totals = screen | Playwright |
| I-02-T14 | Client SL/DB template fixtures in `tests/fixtures/compliance/depreciation/` | QA | I-04 inputs | Fixtures committed with expected answers | Compliance |
| I-02-T15 | i18n keys + user guide section | DOC | I-02-T12 | Lint passes | CI |

- **Deliverable acceptance:** JE = schedule; SL/DB match client templates to the cent; one posted run per period; rollback restores.
- **Testing approach:** unit + property tests on calculators, concurrency integration, data-validation against GL, compliance fixtures.
- **Risks:** rounding drift → last-period absorption + property test; locked period → explicit error.

### I-03 · Discretionary CCA claim incl. full-CCA-as-loss
- **Branch:** `feature/I-03-cca-claim`
- **Objective:** per class per tax year, compute UCC and maximum CCA, let the accountant choose any claim from 0 to maximum (with a one-click "claim maximum even if it creates or increases a loss"), post the claim to the tax book only, and feed G-08 and the loss carry-forward.
- **Current behaviour:** asset register (I-01) holds CCA class settings; no UCC pool, claim or tax-book posting exists. Xero has no real CCA tax book at all.
- **Expected behaviour (better than Xero):** a CCA schedule screen (Schedule 8 equivalent) per tax year lists every class: opening UCC, additions, dispositions (lesser of proceeds and capital cost), half-year / AII adjustment, UCC before CCA, rate, maximum CCA, **claim (editable)**, closing UCC; recapture and terminal loss computed automatically; a live "effect on net income for tax" panel shows NI before CCA, claim, NI after CCA, loss created/increased; posting the claim creates a tax-adjustment journal (book `tax`) reversing book amortisation and booking CCA; the accounting book is never touched.
- **Gap #s closed:** #34 (real CCA tax book).
- **Business rules:** claim 0 ≤ claim ≤ max per class; rate × UCC after half-year adjustment; AII: 1.5× first-year factor on eligible additions (data-driven); immediate expensing per eligible additions within the annual limit (data); recapture when UCC < 0 at year end (income, no CCA); terminal loss when class empty and UCC > 0; claim for a short tax year pro-rated by days/365; one claim set per org per tax year, status Draft → Posted → Reopened; posting requires tax year not locked (A-05 Tax lock); claim posts tax-adjustment JE: Dr CCA expense (tax) / Cr accumulated CCA (tax) and reverses book depreciation in tax book (Dr accumulated dep / Cr depreciation expense, book `tax`).
- **Edge cases:** net income negative before CCA (full claim increases loss), class with only disposals, negative UCC, asset transferred between classes, short first fiscal year, claim edited after G-08 computed (G-08 marked stale), two users editing the same claim set.
- **UI/UX notes:** schedule grid with one editable column ("Claim") and three quick buttons per row (0 · Optimal to zero tax · Maximum); a global toggle "Claim maximum even if it creates or increases a loss" with a clear consequence line ("Creates a non-capital loss of 1,300.00 carried forward"); right-hand impact panel always visible; tax-book badge on every screen so nobody mistakes it for the accounting book; stale indicator on G-08 after changes.
- **Dependencies:** I-01, I-02, C-03 (tax-adjustment journal), K-07, A-05.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| I-03-T01 | Wireframes: CCA schedule grid, impact panel, loss toggle, posting confirmation | UX | — | Approved, incl. tax-book badge | Review |
| I-03-T02 | `TaxYear` helper (start/end from FYE, short-year day fraction) | BE | A-05 | Short first year 1 Jul–31 Dec → 184/365 | Unit |
| I-03-T03 | `CCAPool` model (org, tax_year, class, opening_ucc, additions, dispositions, adjustments, max_cca, claim, closing_ucc, recapture, terminal_loss) | DB | I-01 | Unique (org, tax_year, class) | Unit |
| I-03-T04 | `CCAClaimSet` model (tax_year, status Draft/Posted/Reopened, claim_max_even_if_loss bool, journal FK, posted_by) | DB | I-03-T03 | Status transitions enforced | Unit |
| I-03-T05 | Additions/dispositions aggregation from registered and disposed assets by class within tax year (disposition = lesser of proceeds and capital cost) | BE | I-01, I-05 | Fixture class totals correct | Unit |
| I-03-T06 | Opening UCC roll-forward from prior year closing (or opening UCC entered at conversion) | BE | I-03-T03 | Year 2 opening = year 1 closing | Unit |
| I-03-T07 | Half-year rule adjustment (½ of net additions) where class flag on | BE | I-03-T05 | Class 8 10,000 → 1,000 yr 1 | Unit (fixture) |
| I-03-T08 | AII factor and immediate-expensing calculation as effective-dated data | BE | I-03-T05 | Fixture with AII-eligible addition matches worked example | Unit |
| I-03-T09 | Max CCA computation incl. short-year pro-ration and SL classes (Class 13) | BE | I-03-T07 | Short-year fixture correct | Unit |
| I-03-T10 | Recapture and terminal loss computation | BE | I-03-T09 | Negative UCC → recapture; empty class → terminal loss | Unit |
| I-03-T11 | Claim validation 0 ≤ claim ≤ max; "maximum even if loss" sets all claims = max | BE | I-03-T09 | 1,801 on max 1,800 rejected | Unit (Hypothesis) |
| I-03-T12 | Impact service: NI before CCA (tax book, K-07), NI after, loss created/increased, carry-forward amount | BE | K-07 | NI 500, claim 1,800 → −1,300, carry-forward 1,300 | Unit (fixture) |
| I-03-T13 | "Optimal to zero tax" helper: claim = min(max, NI before CCA) for the selected class order | BE | I-03-T12 | NI 500 → claim 500, NI 0 | Unit |
| I-03-T14 | Posting service: tax-adjustment JE (book `tax`) booking CCA and reversing book depreciation in tax book; one transaction; refuses if Tax lock | BE | C-03, K-07 | Accounting book TB unchanged; tax book NI changes by claim − book dep | Integration |
| I-03-T15 | `LossCarryForward` model + entry from claim set (year, amount created, applied, remaining) | DB/BE | I-03-T12 | Full claim fixture stores 1,300 | Unit |
| I-03-T16 | UCC carry-forward when claim < max (closing UCC higher by unclaimed amount) | BE | I-03-T11 | Claim 500 → closing UCC higher by 1,300 | Unit |
| I-03-T17 | Reopen with reason (reverses tax-adjustment JE, marks G-08 stale) | BE | I-03-T14 | Reopen restores; audit row | Integration |
| I-03-T18 | Optimistic locking on claim set (version field) | BE | I-03-T04 | Second concurrent save → conflict, no lost update | Integration |
| I-03-T19 | API `/api/v1/tax/cca/{tax_year}/` get/update claims/post/reopen; feature key `tax.cca` | API | I-03-T14 | 402 when Tax product absent | Integration + sweep |
| I-03-T20 | CCA schedule screen (grid with editable Claim, per-row quick buttons, totals) | FE | I-03-T19 | Editing a claim updates impact panel live | Playwright |
| I-03-T21 | Impact panel + loss toggle with consequence sentence | FE | I-03-T20 | Toggle shows "Creates a non-capital loss of 1,300.00" on fixture | Playwright |
| I-03-T22 | Schedule 8 export (PDF/XLSX) and data feed for G-07/G-08 | BE/FE | I-03-T14 | Export totals = screen | Integration |
| I-03-T23 | Compliance fixture set `cca/`: Class 8 half-year, short year, recapture, terminal loss, AII, full-claim loss | QA | I-03-T14 | 100 % pass | Compliance |
| I-03-T24 | i18n keys, glossary terms (UCC/FNACC, CCA/DPA) + accountant guide page | DOC | I-03-T20 | Lint passes | CI |

- **Deliverable acceptance:** NI 500, max CCA 1,800: full claim → NI for tax −1,300 and 1,300 carry-forward; claim 500 → NI 0 and UCC carry-forward higher by 1,300; accounting book unchanged by either choice.
- **Testing approach:** unit/property tests (claim bounds, UCC continuity across years), integration (posting only to tax book), compliance fixtures, concurrency.
- **Risks:** rule changes (AII phase-out) → data tables; accountant misreading book → persistent tax-book badge; G-08 out of date → stale flag forces recompute.

### I-04 · Client depreciation templates importer
- **Branch:** `feature/I-04-depreciation-templates`
- **Objective:** import the client's own depreciation templates (methods, rates, conventions, class list) and make them the default method set for the practice or organisation, versioned by tax year.
- **Current behaviour:** defaults come from seeded asset types/CCA classes (I-01); client methods are not loadable.
- **Expected behaviour:** XLSX/CSV upload → mapping → validation report (dry-run) → publish as version for a tax year at practice or organisation level; new assets of the matching type default to the template; the template's worked example is stored and re-computed as a self-test on import.
- **Gap #s closed:** (client decision 8).
- **Business rules:** org-level version overrides practice-level; a published version is immutable (new version to change); template rows: asset category, book method, rate/life, convention, residual %, CCA class, half-year flag; publishing never changes existing assets' methods (offer explicit "apply to existing" bulk action with preview).
- **Edge cases:** unknown CCA class in template, rate > 100 %, duplicate categories, overlapping tax-year versions, template example not matching computed schedule (block publish).
- **UI/UX notes:** three-step importer (Upload · Map columns · Review) shared with B-03 pattern; validation report with row-level errors and "download errors as XLSX"; self-test result shown as green "Worked example reproduced to the cent" or red diff table.
- **Dependencies:** I-01, I-02, client input 9.1(b).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| I-04-T01 | Analyse client templates; write template schema spec (columns, types, allowed values) in `docs/` | DOC | client input | Spec approved by project lead | Review |
| I-04-T02 | `DepreciationTemplate` + `TemplateRow` + `TemplateVersion` models (scope practice/org, tax_year, status Draft/Published) | DB | I-01 | Published version immutable (save raises) | Unit |
| I-04-T03 | Parser for XLSX/CSV (openpyxl/csv) into staging rows | BE | I-04-T02 | Client furniture file parses with 0 errors | Unit |
| I-04-T04 | Validator (known CCA class, rate range, method fields, duplicates) producing row-level report | BE | I-04-T03 | Each invalid case reported with row/column | Unit (parametrised) |
| I-04-T05 | Worked-example self-test: compute schedule for the template's example and compare to supplied figures | BE | I-02-T02/T03 | Mismatch blocks publish with diff | Unit |
| I-04-T06 | Publish service + resolution order (org version → practice version → seed) by tax year | BE | I-04-T02 | Furniture asset defaults to Class 8 DB 20 % after publish | Unit |
| I-04-T07 | "Apply to existing assets" bulk action with preview and audit per asset (A-08 job) | BE | I-04-T06 | Preview lists affected assets; nothing changes until confirmed | Integration |
| I-04-T08 | API `/api/v1/assets/templates/` upload/validate/publish; permission `assets.templates` (Practice Admin / Org Admin) | API | I-04-T06 | Permission matrix passes | Integration |
| I-04-T09 | Importer UI (Upload · Map · Review) reusing shared importer component | FE | I-04-T08 | Error download works | Playwright |
| I-04-T10 | Template versions screen (list, compare two versions, which is active for which tax year) | FE | I-04-T08 | Active version badge correct | Playwright |
| I-04-T11 | Fixtures from client templates committed to compliance suite | QA | client input | Output = worked example | Compliance |
| I-04-T12 | i18n keys + guide | DOC | I-04-T09 | Lint passes | CI |

- **Deliverable acceptance:** client furniture template → Class 8 DB 20 % default; output = worked example.
- **Testing approach:** unit (parser, validator, self-test), integration, compliance fixtures.
- **Risks:** late client templates (Agreement 9.1(b)) → seed defaults keep module usable; template format drift → mapping step.

### I-05 · Disposals
- **Branch:** `feature/I-05-disposals`
- **Objective:** sale or scrap of an asset with book gain/loss posting and tax-side proceeds vs UCC treatment.
- **Current behaviour:** registered assets can only be depreciated (I-02).
- **Expected behaviour:** "Dispose" action: date, type (sale / scrap / trade-in / lost), proceeds, optional link to the sales invoice or bank receipt; preview shows depreciation to disposal date, accumulated removed, NBV, gain/loss; posts accounting JE (Dr accumulated dep, Dr proceeds clearing, Cr cost, Dr/Cr gain/loss); tax side records disposition = lesser of proceeds and capital cost into the class pool (I-03), capital gain flag when proceeds > capital cost, recapture/terminal loss evaluated at year end.
- **Gap #s closed:** #34.
- **Business rules:** catch-up depreciation to disposal date posted first (convention); partial disposals allowed by cost %; disposal reversible only while period open; proceeds in foreign currency translated at date.
- **Edge cases:** disposal before any depreciation run; disposal in a closed period; asset with zero NBV; proceeds > cost (capital gain); trade-in linked to new asset purchase.
- **UI/UX notes:** disposal drawer with live preview of both books side by side ("Accounting: loss 450.00 · Tax: reduces Class 8 UCC by 2,000.00"); status moves to Disposed tab with undo link while period open.
- **Dependencies:** I-01, I-02, I-03, D-03a/F-01 (proceeds link).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| I-05-T01 | Wireframe: disposal drawer with dual-book preview | UX | — | Approved | Review |
| I-05-T02 | `AssetDisposal` model (date, type, proceeds, cost_pct, linked document, journal FK, tax_disposition, capital_gain) | DB | I-01 | Migration applies | Unit |
| I-05-T03 | Catch-up depreciation to disposal date using I-02 calculators | BE | I-02 | Charge to date = schedule | Unit |
| I-05-T04 | Book gain/loss calculation and JE builder (full and partial) | BE | I-05-T03 | Fixture sale and scrap correct | Unit |
| I-05-T05 | Tax disposition (lesser of proceeds and capital cost) + capital-gain flag feeding I-03 pools | BE | I-03 | Pool dispositions updated | Unit |
| I-05-T06 | Post service in one transaction; lock-date check | BE | I-05-T04 | Closed-period disposal refused naming lock | Integration |
| I-05-T07 | Reverse disposal (open period) restoring status and pools | BE | I-05-T06 | Undo restores NBV and UCC | Integration |
| I-05-T08 | Link to sales invoice / receive money as proceeds | BE | D-03a, F-01 | Proceeds clearing nets to 0 | Integration |
| I-05-T09 | API `/api/v1/assets/{id}/dispose/` preview/post/reverse | API | I-05-T06 | Permission + sweep pass | Integration |
| I-05-T10 | Disposal drawer UI with dual-book preview | FE | I-05-T09 | Preview = posted amounts | Playwright |
| I-05-T11 | Disposal schedule report (book and tax) | BE/FE | I-05-T06, K-01 | Ties to GL | Data validation |
| I-05-T12 | Fixtures (sale gain, sale loss, scrap, partial, capital gain) both books | QA | I-05-T06 | Fixtures correct in both books | Compliance |

- **Deliverable acceptance:** fixtures correct in both books.
- **Risks:** missing catch-up depreciation → enforced in service; proceeds double-counted → clearing account check.

---

### 6.5 Projects & Time (Component J)

### J-01 · Projects / engagements
- **Branch:** `feature/J-01-projects`
- **Objective:** projects with budget, tasks, linked contact and a live project P&L — included in the Accounting product (not a paid add-on as in Xero).
- **Current behaviour:** sales/purchases/journals post to the GL with no project dimension.
- **Expected behaviour:** a `project` dimension on every transaction line (invoice, bill, expense claim, journal, time entry); project page with budget vs actual (revenue, cost, margin), tasks with estimates, status (Active / On hold / Completed / Archived), and a profitability card that drills to lines.
- **Gap #s closed:** #51 (projects included, not add-on), #46 partial (dimension mandatory per account option).
- **Business rules:** project belongs to one customer (optional internal); line project tag optional unless account flag "require project" (C-01 flag pattern); completed project refuses new time/cost unless reopened; project P&L = revenue lines − cost lines − approved time at cost rate.
- **Edge cases:** invoice lines split across projects, recode of project via C-07, project deleted with lines (archive only), invoice revision (D-03b) moving amounts.
- **UI/UX notes:** project list as cards or table toggle with margin health colour (green ≥ target, amber, red); project page header shows Budget · Actual · Remaining · Margin %; project picker added to the shared line grid as an optional column (column chooser).
- **Dependencies:** C-02, D-01, E-02, U-03 (`projects`).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| J-01-T01 | Wireframes: project list (cards/table), project page, line-grid project column | UX | — | Approved | Review |
| J-01-T02 | `Project` model (code, name, contact, status, start/end, budget revenue/cost, target margin %) + `ProjectTask` (name, estimate hours, rate) | DB | A-01 | Code unique per org | Unit |
| J-01-T03 | Add nullable `project` FK to journal lines and source-document lines; migration on partitioned table | DB | C-02 | Migration reversible; no lock > 5 s on 1M rows (staging) | Perf |
| J-01-T04 | Account flag "require project" + validation on posting | BE | C-01 | Line without project on flagged account refused | Unit |
| J-01-T05 | Project P&L query (revenue, direct cost, time cost, margin) by date range | BE | J-01-T03 | Fixture P&L correct | Unit (data) |
| J-01-T06 | Status rules (completed refuses new cost/time) | BE | J-01-T02 | Posting to completed project refused with reopen hint | Unit |
| J-01-T07 | API `/api/v1/projects/` + tasks; feature key `projects` | API | J-01-T05 | 402/404 rules pass | Integration + sweep |
| J-01-T08 | Project column in shared line grid (D-01) with picker | FE | J-01-T07 | Column hidden by default; chooser shows it | Playwright |
| J-01-T09 | Project list and page with budget vs actual cards and drill-down | FE | J-01-T07 | Every figure drills to lines | Playwright |
| J-01-T10 | Project P&L report in K-01 engine (with tracking filter) | BE/FE | K-01 | Report total = project page | Data validation |
| J-01-T11 | Global search (A-09) indexing for projects | BE | A-09 | Searching code opens project | Integration |
| J-01-T12 | i18n keys + guide | DOC | J-01-T09 | Lint passes | CI |

- **Deliverable acceptance:** project P&L correct on fixture.

### J-02 · Timesheets
- **Branch:** `feature/J-02-timesheets`
- **Objective:** time capture with timers, billable rates and approval.
- **Current behaviour:** projects exist (J-01); no time entries.
- **Expected behaviour:** weekly timesheet grid and start/stop timer (one running timer per user, survives page reload), entries with project, task, billable flag, notes; rate resolution (task rate → project rate → user rate); submit → approve/reject by approver ≠ submitter; approved time recorded once and locked.
- **Business rules:** max 24 h per user per day; entries in locked periods refused; approval follows A-03 roles; rejected entries return to draft with comment.
- **Edge cases:** timer left running overnight (prompt to split/adjust), time zone of user vs org, duplicate submission, edit after approval (requires unapprove).
- **UI/UX notes:** week grid with keyboard entry (Tab across days, "1:30" or "1.5" both accepted), timer chip in the top bar visible on every page, approval inbox with bulk approve and per-row reject reason.
- **Dependencies:** J-01, A-03, M-01 later (employee link optional).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| J-02-T01 | Wireframes: week grid, timer chip, approval inbox | UX | — | Approved | Review |
| J-02-T02 | `TimeEntry` model (user, project, task, date, minutes, billable, rate, cost_rate, status Draft/Submitted/Approved/Rejected/Billed, timer_started_at) | DB | J-01 | Constraint minutes > 0 | Unit |
| J-02-T03 | Rate resolution service (task → project → user default) | BE | J-02-T02 | Fixture resolves correct rate | Unit |
| J-02-T04 | Timer start/stop service (one running per user; stop creates entry) | BE | J-02-T02 | Second start stops first | Unit |
| J-02-T05 | Daily 24 h cap + lock-date checks | BE | A-05 | 25 h day refused | Unit |
| J-02-T06 | Submit/approve/reject state machine; approver ≠ submitter | BE | A-03 | Self-approval impossible | Unit |
| J-02-T07 | API `/api/v1/time-entries/` + `/timer/`; feature key `projects.time` | API | J-02-T06 | Sweep passes | Integration |
| J-02-T08 | Week grid UI with flexible duration parsing | FE | J-02-T07 | "1:30" and "1.5" both store 90 min | Vitest + Playwright |
| J-02-T09 | Global timer chip (persists across reloads) | FE | J-02-T07 | Reload keeps running timer | Playwright |
| J-02-T10 | Approval inbox with bulk approve/reject reason | FE | J-02-T07 | Bulk approve 50 entries one action | Playwright |
| J-02-T11 | Overnight timer guard (beat job notifies after 10 h running) | BE | A-07, A-08 | Notification sent once | Integration |
| J-02-T12 | Timesheet report (by user/project/billable) | BE/FE | K-01 | Totals = entries | Data validation |
| J-02-T13 | i18n + guide | DOC | J-02-T08 | Lint passes | CI |

- **Deliverable acceptance:** approved time recorded once.

### J-03 · Time & expense to invoice
- **Branch:** `feature/J-03-time-to-invoice`
- **Objective:** pull approved billable time and billable expenses into an invoice; billed entries excluded from the next pull.
- **Current behaviour:** approved time (J-02) and billable bill lines exist separately.
- **Expected behaviour:** from a project or from the invoice editor, "Add billable items" opens a picker (grouped by project/task/date, select all), choose grouping (one line per entry / per task / per day / one summary line), mark-up % for expenses; on approval the entries become `Billed` linked to the invoice line; voiding or revising the invoice (D-03b) releases or re-links entries.
- **Business rules:** each entry billed at most once (unique link); pull respects contact match; revision removing a line releases its entries back to Approved.
- **Edge cases:** concurrent pulls by two users; partial pull; currency mismatch between project and invoice; credit note on billed time.
- **UI/UX notes:** picker drawer inside the shared grid with running total; billed badge on time entries with link to invoice.
- **Dependencies:** J-02, D-01, D-03a, D-03b, E-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| J-03-T01 | Wireframe: billable-items picker drawer, grouping options | UX | — | Approved | Review |
| J-03-T02 | `BillableLink` model (entry type time/expense, entry id, invoice line, revision) with unique active constraint | DB | J-02, D-03a | Duplicate active link impossible at DB | Unit |
| J-03-T03 | Billable-expense flag on bill/claim lines with customer + project | BE | E-02, E-04 | Flag stored | Unit |
| J-03-T04 | Pull service (select entries, grouping, mark-up) building invoice lines | BE | J-03-T02 | Grouping fixtures correct | Unit |
| J-03-T05 | Concurrency: select-for-update on entries during pull | BE | J-03-T04 | Two pulls → one gets "already billed" | Integration |
| J-03-T06 | Release/re-link on void, revision (D-03b), credit note | BE | D-03b, D-06 | Removed line releases entries | Integration |
| J-03-T07 | API `/api/v1/invoices/{id}/billable-items/` list/add | API | J-03-T04 | Sweep passes | Integration |
| J-03-T08 | Picker drawer in invoice editor + "Invoice unbilled" button on project page | FE | J-03-T07 | Running total = lines added | Playwright |
| J-03-T09 | Unbilled WIP report by project/customer | BE/FE | K-01 | Totals = unbilled entries | Data validation |
| J-03-T10 | Functional E2E: time → approve → invoice → revise → next pull excludes billed | QA | J-03-T06 | Green | Playwright |
| J-03-T11 | i18n + guide | DOC | J-03-T08 | Lint passes | CI |

- **Deliverable acceptance:** billed entries excluded from next pull.

---

### 6.6 Sheets — Working Papers (Component L)

### L-01 · Grid editor
- **Branch:** `feature/L-01-sheets-grid`
- **Objective:** an in-app spreadsheet (working papers) with formulas, formatting and autosave, inside each organisation.
- **Current behaviour:** none; accountants export to Excel (Xero offers "Classic Workpapers" separately).
- **Expected behaviour:** virtualised grid (200×50 target smooth), cell types (number, text, date, currency), formulas (SUM, AVERAGE, IF, ROUND, VLOOKUP/XLOOKUP, MIN/MAX, ABS, references, ranges across tabs), multiple tabs, freeze panes, number formats en-CA/fr-CA, cell comments, autosave with version history (L-03), undo/redo, copy/paste from Excel.
- **Business rules:** formula engine runs client-side for editing and server-side for authoritative values (same engine via shared spec/tests); circular references flagged; sheet belongs to org; locked-period sheets read-only (L-03).
- **Edge cases:** paste of 10k cells, formulas referencing deleted tabs, concurrent edits by two users (last-writer with cell-level merge + conflict highlight), very long text.
- **UI/UX notes:** Excel-familiar keyboard (arrows, Enter, F2, Ctrl+C/V/Z/Y, Ctrl+Shift+arrow), formula bar with function hints, status bar showing SUM/AVG/COUNT of selection, clear "Saved · 2 s ago" indicator.
- **Dependencies:** A-01, A-06, A-10.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| L-01-T01 | Spike & ADR: grid library (e.g. Glide Data Grid / custom canvas) and formula engine (HyperFormula licence check vs formula.js + own parser) | DOC | — | ADR-005 recorded with licence decision | Review |
| L-01-T02 | Wireframes: sheet workspace, formula bar, tabs, status bar | UX | — | Approved | Review |
| L-01-T03 | `Workbook`, `Worksheet`, `CellData` (sparse JSON per sheet, version int) models | DB | A-01 | 200×50 sheet stored < 200 KB | Unit |
| L-01-T04 | Server formula evaluator (Python) matching client engine on shared test vectors | BE | L-01-T01 | 300 test vectors identical both sides | Unit (cross-engine) |
| L-01-T05 | Circular reference detection both sides | BE/FE | L-01-T04 | Cycle shows #CIRC with cell path | Unit |
| L-01-T06 | Grid component (virtualised, selection, editing, keyboard map) | FE | L-01-T01 | 200×50 scroll ≥ 55 fps on reference laptop | Perf |
| L-01-T07 | Formula bar with function autocomplete and argument hints | FE | L-01-T06 | Typing "=SU" suggests SUM, SUMIF | Vitest |
| L-01-T08 | Number/date/currency formats per locale | FE | A-10 | 1234.5 shows 1,234.50 en-CA and 1 234,50 fr-CA | Vitest |
| L-01-T09 | Autosave (debounced patch API) with optimistic version and conflict merge | BE/FE | L-01-T03 | Two users editing different cells → both saved | Integration |
| L-01-T10 | Undo/redo stack (100 steps) | FE | L-01-T06 | Undo restores value and formula | Vitest |
| L-01-T11 | Clipboard paste from Excel/Google Sheets (TSV/HTML) | FE | L-01-T06 | 10k cells pasted < 1 s | Playwright |
| L-01-T12 | Tabs, freeze panes, cell comments | FE | L-01-T06 | Persist after reload | Playwright |
| L-01-T13 | API `/api/v1/sheets/` workbooks/sheets/patch; feature key `sheets` | API | L-01-T09 | Sweep passes | Integration |
| L-01-T14 | Sheets list screen (by period, tag, template origin) | FE | L-01-T13 | Search finds by name | Playwright |
| L-01-T15 | a11y: grid ARIA roles, screen-reader cell announcement | QA | L-01-T06 | axe-core 0 serious issues | axe |
| L-01-T16 | i18n + guide (keyboard shortcuts sheet) | DOC | L-01-T06 | Lint passes | CI |

- **Deliverable acceptance:** grid 200×50 performance target met.

### L-02 · GL-linked functions
- **Branch:** `feature/L-02-gl-functions`
- **Objective:** spreadsheet functions that pull live ledger values with a `book` argument.
- **Expected behaviour:** `=GL(account, from, to, book)`, `=GLBAL(account, date, book)`, `=TB(account_range, date, book)`, `=GLTAX(code, from, to)`, `=ASSETNBV(type, date, book)`; values refresh on open and on demand, show a small link icon, and drill to the account transactions; cached per (org, args, ledger version).
- **Business rules:** `book` ∈ accounting/tax/both (default accounting); account by code or range "5000:5999"; only accounts the user can see; values evaluated server-side.
- **Edge cases:** renumbered account (C-01) — references stored by account id with code display; invalid date; tax book not yet populated.
- **UI/UX notes:** function picker "Insert ledger value" dialog (account picker, dates presets, book radio) so users never type syntax; stale value indicator when ledger changed since last refresh.
- **Dependencies:** L-01, K-07, K-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| L-02-T01 | Function spec doc (signatures, defaults, errors) | DOC | — | Approved | Review |
| L-02-T02 | Ledger query service for functions (balance/movement by account id, range, book) using reporting replica | BE | K-07 | Matches TB on fixture | Unit (data) |
| L-02-T03 | Account reference storage by id with code display; survives renumber | BE | C-01 | Renumber 5000→5010 keeps value | Integration |
| L-02-T04 | Implement GL, GLBAL, TB, GLTAX, ASSETNBV in evaluator | BE | L-02-T02, L-01-T04 | Each function fixture correct | Unit |
| L-02-T05 | Batch evaluation endpoint (one request per sheet refresh) + cache keyed by ledger version | API | L-02-T04 | 500 GL cells refresh < 2 s | Perf |
| L-02-T06 | Permission filtering (hidden accounts → #NOACCESS) | BE | A-03 | Restricted user gets #NOACCESS | Unit |
| L-02-T07 | "Insert ledger value" dialog | FE | L-02-T05 | Inserted formula evaluates | Playwright |
| L-02-T08 | Drill-down from GL cell to account transactions | FE | K-02 | Click opens filtered report | Playwright |
| L-02-T09 | Stale indicator + Refresh all | FE | L-02-T05 | Posting a JE marks cells stale | Playwright |
| L-02-T10 | Test: lead schedule in tax book = tax-book TB | QA | K-07 | Green | Data validation |

- **Deliverable acceptance:** lead schedule in tax book = tax-book TB.

### L-03 · Templates & versioning
- **Branch:** `feature/L-03-sheet-templates`
- **Objective:** practice/org templates (lead schedules, bank/AR/AP reconciliations, CCA continuity, loan continuity [v2.1], book reconciliation), version history and period lock.
- **Expected behaviour:** create sheet from template for a period → GL functions resolve to that period; snapshots on every sign-off; "Prepared by / Reviewed by" sign-off cells with timestamps; period lock makes sheets read-only when the GL period is locked.
- **Business rules:** template versions immutable once published; practice templates available to all assigned orgs; locked sheet edits require unlocking the GL period.
- **UI/UX notes:** template gallery with preview thumbnails; version timeline sidebar with restore-as-copy; sign-off chips at sheet top.
- **Dependencies:** L-01, L-02, A-05, I-03, FN-02, K-07.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| L-03-T01 | Wireframes: template gallery, version timeline, sign-off chips | UX | — | Approved | Review |
| L-03-T02 | `SheetTemplate` + `TemplateVersion` (scope practice/org) models | DB | L-01 | Published immutable | Unit |
| L-03-T03 | Instantiate template for period (parameter cells `{{period_start}}`, `{{period_end}}`, `{{book}}`) | BE | L-03-T02 | Formulas resolve to chosen period | Unit |
| L-03-T04 | Snapshot/version model (`SheetVersion`, author, reason) on sign-off and manual save point | DB/BE | L-01 | Versions retained; restore creates copy | Integration |
| L-03-T05 | Sign-off (prepared/reviewed, reviewer ≠ preparer) | BE | A-03 | Self-review refused | Unit |
| L-03-T06 | Period lock → read-only enforcement API and UI | BE/FE | A-05 | Locked period sheet read-only with unlock hint | Integration |
| L-03-T07 | Built-in templates: lead schedule, bank rec, AR rec, AP rec, CCA continuity, loan continuity, book reconciliation | BE | I-03, FN-02, K-07 | Each template ties to its report on fixture | Data validation |
| L-03-T08 | Template gallery and version timeline UI | FE | L-03-T04 | Restore copy works | Playwright |
| L-03-T09 | i18n + guide | DOC | L-03-T08 | Lint passes | CI |

- **Deliverable acceptance:** template versions retained; locked period read-only.

### L-04 · Import/export
- **Branch:** `feature/L-04-sheets-xlsx`
- **Objective:** XLSX round-trip preserving values and formulas (GL functions exported as values + comment with formula).
- **Expected behaviour:** import XLSX (sheets, formulas, number formats, merged cells, column widths); export XLSX; unsupported functions flagged in import report rather than silently dropped.
- **Dependencies:** L-01, L-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| L-04-T01 | XLSX import (openpyxl) → CellData incl. formulas/formats/merges | BE | L-01 | Fixture workbook imports | Unit |
| L-04-T02 | Unsupported-function report (cell list) | BE | L-04-T01 | Report lists cells, values kept | Unit |
| L-04-T03 | XLSX export with formulas; GL functions → value + note with original formula | BE | L-02 | Excel opens file without repair | Integration |
| L-04-T04 | Round-trip test suite (values and formulas preserved) | QA | L-04-T03 | 100 % fixture cells equal | Unit |
| L-04-T05 | Import/export UI (drag-drop, report dialog) | FE | L-04-T02 | Playwright green | Playwright |
| L-04-T06 | File size/MIME limits via A-06 (25 MB) and virus-scan hook | BE | A-06 | Oversize refused with message | Integration |

- **Deliverable acceptance:** round-trip preserves values and formulas.

---

### 6.7 Multi-currency (Component R)

### R-01 · Currencies & rates
- **Branch:** `feature/R-01-currencies-rates`
- **Objective:** enabled currencies per org, daily rates with manual override, currency per contact — included in Accounting (gap #11: Xero CAD-only on plan).
- **Expected behaviour:** base currency CAD (locked after first posting); enable currencies; nightly rate fetch (Bank of Canada valet API as default source) at 16:30 ET; manual override per date with audit; rate used = rate on document date (fallback: last available prior business day, labelled).
- **Gap #s closed:** #11, #20 (currency per contact).
- **Business rules:** rates stored as foreign → CAD with 6–10 decimals; override wins over feed; weekend/holiday fallback rule; contact currency defaults document currency.
- **Edge cases:** feed down (retry + alert, documents still allowed with manual rate), rate missing for exotic currency, base currency change attempt after postings.
- **UI/UX notes:** currencies settings page with rate history chart and inline override; document header shows "1 USD = 1.3684 CAD (Bank of Canada, 3 Nov 2026) · Change".
- **Dependencies:** A-05, A-08, B-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| R-01-T01 | `Currency` (ISO 4217 seed), `OrgCurrency`, `ExchangeRate` (date, from, to, rate, source feed/manual) models | DB | A-01 | Unique (org, date, currency, source) | Unit |
| R-01-T02 | Rate provider interface + Bank of Canada adapter | BE | R-01-T01 | Sandbox fetch stores rates | Integration (mocked HTTP) |
| R-01-T03 | Nightly beat job with retry and alert on failure | OPS | A-08, S-04 | Failure alerts once | Integration |
| R-01-T04 | Rate resolver (document date → override → feed → prior business day) | BE | R-01-T01 | Fixture picks correct rate | Unit (Hypothesis) |
| R-01-T05 | Manual override with audit and reason | BE | A-04 | Override audited | Unit |
| R-01-T06 | Base currency lock after first posting | BE | C-02 | Change refused with reason | Unit |
| R-01-T07 | Contact currency default (B-01) | BE | B-01 | New invoice for USD contact defaults USD | Integration |
| R-01-T08 | API `/api/v1/currencies/`, `/exchange-rates/` | API | R-01-T04 | Sweep passes | Integration |
| R-01-T09 | Currencies settings UI with history chart and override | FE | R-01-T08 | Override shows in chart | Playwright |
| R-01-T10 | Rate display/change component for document headers | FE | R-01-T08 | Used by invoice, bill, bank screens | Vitest |
| R-01-T11 | Gap-11 test: multi-currency available on Accounting package | QA | U-03 | `gap-11` green | Playwright |
| R-01-T12 | i18n + guide | DOC | R-01-T09 | Lint passes | CI |

- **Deliverable acceptance:** rate used = rate on document date.

### R-02 · Foreign documents & FX
- **Branch:** `feature/R-02-fx`
- **Objective:** foreign invoices, bills, credit notes, payments and bank accounts with realised and unrealised FX gains/losses.
- **Expected behaviour:** every line stores amount in document currency and CAD; payment at a different rate posts realised gain/loss to the FX gain/loss account; month-end revaluation job (preview → post, auto-reversing on day 1 of next period) for open AR/AP and foreign bank balances; "always show currency code" document option.
- **Business rules:** tax computed in document currency and converted at document rate (CRA: GST at rate on date tax payable); realised FX only on settlement; revaluation journal type `adjusting`, auto-reversed; foreign bank account holds balance in its currency.
- **Edge cases:** partial payments at multiple rates, invoice revision (D-03b) of a foreign invoice after partial payment, cross-currency payment (USD invoice paid from CAD account), rounding to the cent on conversion.
- **UI/UX notes:** foreign amounts shown with CAD equivalent in muted text; revaluation wizard with preview table and one-click post; FX summary on dashboard optional widget.
- **Dependencies:** R-01, D-03a, D-05, E-02, F-01, C-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| R-02-T01 | Add currency, rate, foreign amount fields to document and JE lines (CAD remains ledger amount) | DB | R-01 | Migration applies; TB in CAD balances | Unit |
| R-02-T02 | Conversion service with banker-safe rounding and line-sum reconciliation (rounding line to 860-type account) | BE | R-02-T01 | Converted lines sum = converted total | Unit (Hypothesis) |
| R-02-T03 | Foreign invoice/bill posting (AR/AP in CAD at doc rate, foreign amount tracked) | BE | D-03a, E-02 | Fixture postings correct | Integration |
| R-02-T04 | Realised FX on payment allocation (incl. partial payments) | BE | D-05 | Gain/loss fixture correct | Unit |
| R-02-T05 | Cross-currency payment (USD doc, CAD bank) | BE | R-02-T04 | Clearing nets to 0 | Integration |
| R-02-T06 | Foreign-currency bank accounts (F-01 types with currency) | BE | F-01 | Balance shown in USD and CAD | Integration |
| R-02-T07 | Unrealised revaluation job: preview, post, auto-reverse next period | BE | C-03 | Reversal posted on day 1 | Integration |
| R-02-T08 | Revision of foreign invoice after partial payment keeps realised FX intact | BE | D-03b | Property test AR consistency holds | Unit (property) |
| R-02-T09 | "Always show currency code" document option + PDF template | FE | D-03a | PDF shows "USD 1,000.00" | Snapshot |
| R-02-T10 | Revaluation wizard UI | FE | R-02-T07 | Preview = posted | Playwright |
| R-02-T11 | Reports: FX gain/loss, foreign AR/AP aging in document currency | BE/FE | K-03 | Aging in USD = sum of open USD docs | Data validation |
| R-02-T12 | FX fixture suite | QA | R-02-T07 | 100 % pass | Compliance |
| R-02-T13 | i18n + guide | DOC | R-02-T10 | Lint passes | CI |

- **Deliverable acceptance:** FX gain/loss correct on fixtures.

---

### 6.8 Two-Book Reporting & Tax (Components K, G)

### K-04 · Budgets
- **Branch:** `feature/K-04-budgets`
- **Objective:** budgets by account (and optionally project/tracking) per period with budget vs actual and variance.
- **Expected behaviour:** budget grid (accounts × months) with fill helpers (copy last year actuals, +/- %, spread annual evenly or by last year's seasonality); multiple budgets per year (Original / Revised); budget vs actual report with variance and variance %; budget also feeds E-01 commitment report.
- **Business rules:** variance = actual − budget; favourable sign depends on account type (revenue vs expense) and is labelled, not just coloured; budgets are per book (accounting default).
- **UI/UX notes:** spreadsheet-like grid reusing L-01 component in constrained mode; variance colours with text labels (Favourable / Unfavourable) for accessibility.
- **Dependencies:** K-01, C-01, L-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-04-T01 | Wireframes: budget grid with fill helpers, BvA report | UX | — | Approved | Review |
| K-04-T02 | `Budget` (name, fiscal year, version, book, status) + `BudgetLine` (account, project/tracking, period, amount) | DB | C-01 | Unique (budget, account, dimension, period) | Unit |
| K-04-T03 | Fill helpers service (copy actuals, % change, spread even/seasonal) | BE | K-04-T02 | Spread 12,000 even → 1,000/month | Unit |
| K-04-T04 | Budget vs actual query with variance and favourable flag by account type | BE | K-01 | Variance = actual − budget | Unit |
| K-04-T05 | API `/api/v1/budgets/` + import/export XLSX | API | K-04-T03 | Round-trip equals | Integration |
| K-04-T06 | Budget grid UI (L-01 component, constrained) | FE | K-04-T05 | Keyboard entry works | Playwright |
| K-04-T07 | BvA report in report engine with comparison and drill-down | FE | K-04-T04 | Figures drill to lines | Playwright |
| K-04-T08 | Feed for E-01 commitment report | BE | E-01 | Commitment shows remaining budget | Integration |
| K-04-T09 | i18n + guide | DOC | K-04-T06 | Lint passes | CI |

- **Deliverable acceptance:** variance = actual − budget.

### K-06 · Management pack & adviser templates
- **Branch:** `feature/K-06-management-pack`
- **Objective:** one-click management pack and Canadian engagement report templates (Notice to Reader / Compilation under CSRS 4200, Review) in Numo9's own wording, editable per practice.
- **Expected behaviour:** pack builder: cover, contents, selected reports (P&L, BS, cash flow, aging, KPIs, BvA, two-book reconciliation), commentary blocks, practice branding; saved pack definitions; generated as one PDF in < 10 s; engagement templates with placeholders (organisation legal name, period end, practice name, signing accountant, date) and practice-level editing; Draft / Published versions (K-01).
- **Business rules:** published pack frozen with ledger snapshot timestamp; unpublished shows "Draft — not for distribution" watermark; legal name required (K-01 validation, gap #55).
- **UI/UX notes:** drag-to-reorder section list with live thumbnail preview; template editor with placeholder chips (no raw syntax).
- **Dependencies:** K-01, K-02, K-03, K-07, A-07, A-10.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-06-T01 | Wireframes: pack builder, template editor | UX | — | Approved | Review |
| K-06-T02 | `PackDefinition` (sections ordered, options) + `PackRun` (snapshot ts, status, file) | DB | K-01 | Migration applies | Unit |
| K-06-T03 | `EngagementTemplate` (type NTR/Compilation/Review, scope practice, body with placeholders, version) | DB | — | Published immutable | Unit |
| K-06-T04 | Write original Numo9 wording for Compilation (CSRS 4200), NTR legacy variant, Review templates; client review | DOC | — | Wording approved by client; no third-party text | Review |
| K-06-T05 | Placeholder renderer (safe templating) | BE | K-06-T03 | Unknown placeholder flagged | Unit |
| K-06-T06 | Pack generator (async, WeasyPrint, parallel report rendering) | BE | K-06-T02 | Pack < 10 s on fixture | Perf |
| K-06-T07 | Draft watermark / published freeze | BE | K-06-T06 | Published PDF unchanged after new postings | Integration |
| K-06-T08 | API `/api/v1/reports/packs/` + `/engagement-templates/` | API | K-06-T06 | Sweep passes | Integration |
| K-06-T09 | Pack builder UI with drag order and thumbnails | FE | K-06-T08 | Order reflected in PDF | Playwright |
| K-06-T10 | Template editor with placeholder chips | FE | K-06-T08 | Editable per practice | Playwright |
| K-06-T11 | PDF snapshot tests (Letter, inch margins) | QA | K-06-T06 | Snapshots stable | Snapshot |
| K-06-T12 | i18n keys (FR wording placeholders for Phase 6) | DOC | K-06-T10 | Lint passes | CI |

- **Deliverable acceptance:** pack < 10 s; templates editable per practice.

### K-07 · Two-book engine
- **Branch:** `feature/K-07-two-book-engine`
- **Objective:** make the `book` dimension (accounting / tax / both) on every journal line drive two complete sets of books, with a Book Reconciliation report.
- **Current behaviour:** C-02 stores `book` on lines (default `both`); reports (K-01/K-02) ignore it except for the selector placeholder.
- **Expected behaviour (beyond Xero):** ordinary postings = `both`; tax-adjustment journals (C-03) = `tax`; accounting-only entries = `accounting`; every report has a book selector (accounting default, tax, and "side by side"); TB of each book balances to zero; the Book Reconciliation report lists, by account, accounting balance, tax-only adjustments, accounting-only adjustments, tax balance, and the journal that caused each difference; Schedule 1-style NI reconciliation (accounting NI → additions → deductions → tax NI).
- **Business rules:** tax book = lines with book ∈ {both, tax}; accounting book = book ∈ {both, accounting}; `tax` lines only allowed on journal type tax-adjustment (and system postings from I-03/G-08); every tax-adjustment carries an adjustment category (Schedule 1 line: amortisation add-back, CCA deduction, 50 % meals, fines/penalties, reserves, other) for reconciliation; book of a posted line is immutable (reverse to change).
- **Edge cases:** source document posting to `tax` (forbidden); recode (C-07) changing book (forbidden); year-end retained-earnings roll per book (C-06) — separate tax RE; opening tax-book balances at conversion (C-05 tax column); report caching per book.
- **UI/UX notes:** a persistent book switch in report headers ("Accounting book · Tax book · Side by side"); tax book screens carry a distinct accent border and label; adjustment category picker on tax-adjustment journals with plain-language descriptions; reconciliation report starts with a summary card (Accounting NI · Adjustments · Tax NI · Difference 0.00 ✓).
- **Dependencies:** C-02, C-03, C-05, C-06, K-01, K-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-07-T01 | ADR-004 two-book model (book dimension semantics, RE per book, immutability) | DOC | — | ADR approved | Review |
| K-07-T02 | Wireframes: book switch, side-by-side layout, reconciliation report, adjustment category picker | UX | — | Approved | Review |
| K-07-T03 | DB constraint/validator: `book` ∈ {accounting, tax, both}; `tax` only on tax-adjustment/system journal types | DB/BE | C-03 | Invoice line with book=tax rejected | Unit |
| K-07-T04 | `TaxAdjustmentCategory` seed (Schedule 1 lines) + FK on tax-adjustment journal lines | DB | K-07-T03 | Seed loaded; required on tax-adjustment | Unit |
| K-07-T05 | Book-aware ledger query layer (`ledger.balances(book=…)`) replacing direct queries in K-01 | BE | K-01 | All existing report tests still green | Regression |
| K-07-T06 | Per-book retained earnings roll at year end (C-06 extension) | BE | C-06 | Tax RE and accounting RE each correct on fixture | Unit |
| K-07-T07 | Opening balances per book at conversion (C-05 adds tax column, defaults = accounting) | BE | C-05 | Tax-book opening TB balances | Integration |
| K-07-T08 | Immutability: book cannot change on posted lines; recode (C-07) refuses book changes | BE | C-07 | Recode attempt refused with message | Unit |
| K-07-T09 | Property test: TB(accounting) = 0 and TB(tax) = 0 over random journal sets | QA | K-07-T05 | 1,000 runs pass | Hypothesis |
| K-07-T10 | Property test: accounting NI − Σ(tax adjustments affecting P&L) + Σ(accounting-only) = tax NI | QA | K-07-T05 | 1,000 runs pass | Hypothesis |
| K-07-T11 | Book Reconciliation report query by account with causing journals | BE | K-07-T05 | Nets to 0 against two P&Ls | Data validation |
| K-07-T12 | Schedule 1-style NI reconciliation output grouped by category | BE | K-07-T04 | Fixture matches expected schedule | Unit |
| K-07-T13 | Report cache keyed by (org, report, params, book, ledger version) | BE | K-01 | Switching book never shows other book's cache | Integration |
| K-07-T14 | API: `book` param on all report endpoints + `/api/v1/reports/book-reconciliation/` | API | K-07-T11 | Contract tests from OpenAPI | Integration |
| K-07-T15 | Book switch component in report header (persists per user per report) | FE | K-07-T14 | Selection remembered | Playwright |
| K-07-T16 | Side-by-side layout (Accounting · Adjustments · Tax columns) generic for P&L/BS/TB | FE | K-07-T14 | Columns reconcile per line | Playwright |
| K-07-T17 | Tax-book visual treatment (accent border, label) across reports and journals | FE | A-10 | Visual regression baseline | Chromatic |
| K-07-T18 | Adjustment category picker in manual journal editor (tax-adjustment type) | FE | K-07-T04 | Required; descriptions shown | Playwright |
| K-07-T19 | Book Reconciliation report screen with summary card and drill-down | FE | K-07-T11 | Difference 0.00 ✓ on fixture | Playwright |
| K-07-T20 | Release-gate CI job: run reconciliation on all fixtures, fail if ≠ 0 | OPS | K-07-T11 | CI step red on injected drift | CI |
| K-07-T21 | Exceptions rule (K-09): "Books out of balance" and "tax-only line without category" | BE | K-09 | Rule fires on injected fixture | Integration |
| K-07-T22 | i18n + accountant guide "How the two books work" | DOC | K-07-T19 | Lint passes | CI |

- **Deliverable acceptance:** accounting NI − adjustments = tax NI on every fixture; reconciliation nets to 0.
- **Testing approach:** property tests, regression of all K reports, data validation gate in CI.
- **Risks:** drift between books → CI gate + exceptions rule; performance of double queries → book-aware materialised balances per period.

### K-08 · Tax-purpose BS & IS with tax amount
- **Branch:** `feature/K-08-tax-statements`
- **Objective:** Income Statement and Balance Sheet for tax purposes with CCA replacing amortisation, non-deductibles removed, and a computed income-tax line from G-08, side by side with the accounting book.
- **Expected behaviour (beyond Xero):** tax IS: revenue, expenses (with book amortisation removed and CCA added; 50 % meals removed; fines/penalties removed; reserves adjusted), Net income for tax, **Income tax (computed by G-08: federal + provincial, SBD applied)**, Net income after tax; tax BS: assets at UCC instead of NBV, current tax payable, loss carry-forward disclosure; side-by-side with adjustments column; PDF/XLSX export; stale banner if G-08 is out of date.
- **Business rules:** tax line always from the latest confirmed G-08 computation for the tax year; draft computation shown with "Draft estimate" label; statements require tax year selection aligned with fiscal year; columns reconcile line by line (accounting + adjustments = tax).
- **Edge cases:** no CCA claim yet (amortisation added back, CCA 0, warning); loss year (tax line 0, carry-forward shown); short tax year; multiple provinces of permanent establishment (allocation from G-08).
- **UI/UX notes:** three-column statement with expandable adjustment rows explaining each difference in plain language ("Amortisation added back — tax uses CCA instead"); tax line has an info popover showing the computation summary and a link to G-08.
- **Dependencies:** K-07, I-03, G-08, K-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-08-T01 | Wireframes: tax IS/BS, side-by-side, explanation rows, tax popover, stale banner | UX | — | Approved | Review |
| K-08-T02 | Statement layout definitions for tax IS and tax BS (K-01 layout engine) | BE | K-01 | Layouts load | Unit |
| K-08-T03 | Tax IS builder: tax-book P&L + category grouping for adjustments | BE | K-07 | Fixture tax NI correct | Unit |
| K-08-T04 | Income-tax line from confirmed G-08 computation (draft labelled) | BE | G-08 | Tax line = G-08 total | Integration |
| K-08-T05 | Net income after tax and current-tax payable on tax BS | BE | K-08-T04 | BS balances in tax book | Unit |
| K-08-T06 | Tax BS: assets at UCC (from I-03 pools) with reconciliation to NBV | BE | I-03 | UCC column = Schedule 8 closing | Data validation |
| K-08-T07 | Loss carry-forward disclosure block | BE | I-03-T15 | Shows 1,300 on full-claim fixture | Unit |
| K-08-T08 | Side-by-side builder (accounting / adjustments / tax) with per-line reconciliation assertion | BE | K-07-T16 | Every line: acc + adj = tax | Unit |
| K-08-T09 | Plain-language explanation strings per adjustment category | DOC | K-07-T04 | Reviewed by project lead | Review |
| K-08-T10 | Stale detection (ledger version > G-08 computed version) | BE | G-08 | Banner shows after new posting | Integration |
| K-08-T11 | API `/api/v1/reports/tax-statements/{is,bs}/?tax_year=&view=` | API | K-08-T08 | Contract tests | Integration |
| K-08-T12 | Tax statements screens (single and side-by-side) with expandable rows and popover | FE | K-08-T11 | Playwright green | Playwright |
| K-08-T13 | PDF/XLSX export (Letter, inch margins, legal name header) | BE | K-08-T12 | Export = screen | Snapshot |
| K-08-T14 | T2 fixture end-to-end (accounting NI → adjustments → tax NI → tax) | QA | G-08 | Known answer reproduced | Compliance |
| K-08-T15 | Short-year and loss-year fixtures | QA | K-08-T14 | Correct | Compliance |
| K-08-T16 | i18n + guide | DOC | K-08-T12 | Lint passes | CI |

- **Deliverable acceptance:** T2 fixture: tax NI and computed tax = known answer; columns reconcile per line.

### K-10 · Adjusted trial balance
- **Branch:** `feature/K-10-adjusted-tb`
- **Objective:** TB with proposed-adjustment columns and adjusted balances; adjustments post to the chosen book (gap #57).
- **Expected behaviour:** TB sorted by code (opening / movement / closing), then "Proposed adjustments" Dr/Cr columns where the accountant drafts AJEs inline (numbered AJE-1, AJE-2 …, each balanced), then Adjusted balance; each AJE has book choice (accounting / tax / both) and journal type (adjusting / reclass / tax-adjustment); "Post selected" posts them through C-02/C-04 approval; the client can see proposed AJEs in the portal (O-05 later) before posting.
- **Business rules:** adjusted = TB + adjustments per line; unbalanced AJE cannot be posted; posting respects lock dates and approval limits; drafts stay out of the ledger.
- **UI/UX notes:** inline AJE drawer opened from any TB row (prefilled account); AJE chips in the row show which adjustments touch it; export to XLSX/PDF as a working paper (and to L-03 template).
- **Dependencies:** K-02, C-02, C-04, K-07.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| K-10-T01 | Wireframes: adjusted TB grid, AJE drawer, row chips | UX | — | Approved | Review |
| K-10-T02 | `ProposedAdjustment` (number, description, book, journal type, status Draft/Posted/Discarded) + lines | DB | C-02 | Migration applies | Unit |
| K-10-T03 | Adjusted TB query (TB + draft adjustments per account) | BE | K-02 | Adjusted = TB + adj per line | Unit (property) |
| K-10-T04 | AJE validation (balanced, accounts active, book rules from K-07) | BE | K-07-T03 | Unbalanced refused | Unit |
| K-10-T05 | Post selected AJEs → journals via C-04 approval workflow | BE | C-04 | Posted AJE appears in TB movement; draft removed | Integration |
| K-10-T06 | API `/api/v1/reports/adjusted-tb/` + `/proposed-adjustments/` | API | K-10-T05 | Sweep passes | Integration |
| K-10-T07 | Adjusted TB screen with inline AJE drawer and chips | FE | K-10-T06 | Playwright green | Playwright |
| K-10-T08 | Export XLSX/PDF and "Send to working paper" (L-03) | BE/FE | L-03 | Export totals = screen | Integration |
| K-10-T09 | Gap-57 test (sorted TB, opening/movement/closing, adjusted columns) | QA | K-10-T07 | `gap-57` green | Playwright |
| K-10-T10 | i18n + guide | DOC | K-10-T07 | Lint passes | CI |

- **Deliverable acceptance:** adjusted TB = TB + adjustments per line.

### G-04 · QST return worksheet
- **Branch:** `feature/G-04-qst-return`
- **Objective:** Revenu Québec QST return worksheet (FPZ-500 equivalent) on the same filing-cycle engine as GST/HST (G-03a/b).
- **Current behaviour:** G-01 holds QST 9.975 % codes and separate QST payable / QST ITR control accounts (C-01); G-03 produces the GST/HST worksheet only.
- **Expected behaviour:** for each QST registration period: supplies, QST collectible, adjustments, ITRs, net tax; mark filed; period lock; late adjustments into the next open period; line definitions stored as data per form edition (so a form change is a data update); combined view for Quebec registrants showing GST/HST and QST side by side for the same period, while respecting that QST may have its own frequency.
- **Business rules:** QST frequency independent of GST frequency; filed period immutable; QST collectible = Σ QST on sales by tax point in period; ITR partial % rules from G-01; back-dated documents into filed period require late-adjustment flag; worksheet ties to QST control accounts.
- **Edge cases:** QST registration started mid-year (stub period), stop/restart (G-03b), invoice revision (D-03b) into filed period, bad-debt adjustment, non-Quebec organisation (screen hidden, not gated).
- **UI/UX notes:** same worksheet layout as G-03 (one pattern), each line clickable to its documents; "Ready to file" checklist (all bank lines coded, no draft invoices in period, exceptions clean); "Mark filed" asks for confirmation number and date; FR labels via Phase 6 keys.
- **Dependencies:** G-01, G-03, G-03a, G-03b, G-05.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-04-T01 | Map FPZ-500 edition lines to data definitions (`ReturnForm`, `ReturnLine` with formula refs) — client confirms edition | DOC/DB | — | Line set approved | Review |
| G-04-T02 | QST registration on filing-cycle engine (G-03a reuse, registration type QST) | BE | G-03a | QST periods generated independently of GST | Unit |
| G-04-T03 | Line calculators (supplies, QST collectible, adjustments, ITR incl. partial %, net) | BE | G-01 | Fixture lines correct | Unit |
| G-04-T04 | Tie-out to QST payable / QST ITR control accounts | BE | C-01 | Difference 0.00 on fixture | Data validation |
| G-04-T05 | Mark filed / lock / late-adjustment into next open period (reuse G-03 services) | BE | G-03 | Filed period refuses back-dated doc without flag | Integration |
| G-04-T06 | Ready-to-file checklist service | BE | K-09 | Lists blockers | Unit |
| G-04-T07 | API `/api/v1/tax/returns/qst/` | API | G-04-T05 | Feature key `tax.returns`; sweep passes | Integration |
| G-04-T08 | Worksheet UI (shared return component with G-03) + drill-down | FE | G-04-T07 | Line click lists documents | Playwright |
| G-04-T09 | Combined GST/HST + QST period view for Quebec registrants | FE | G-04-T08 | Both shown with own frequencies | Playwright |
| G-04-T10 | Worksheet PDF/XLSX export | BE | G-04-T08 | Export = screen | Snapshot |
| G-04-T11 | Compliance fixtures: monthly QST + quarterly GST, stub period, late adjustment, revision into filed period | QA | G-04-T05 | 100 % pass | Compliance |
| G-04-T12 | i18n (CRA/RQ terminology keys) + guide | DOC | G-04-T08 | Lint passes | CI |

- **Deliverable acceptance:** parallel to G-03 (net QST = tax report; filed period protected).

### G-07 · GIFI & T2 export
- **Branch:** `feature/G-07-gifi-export`
- **Objective:** GIFI mapping editor and export of Schedule 100 (BS), 125 (IS) and 141 data from the tax book for T2 preparation software (gap #30: 0/139 mapped in Xero).
- **Current behaviour:** C-01 template ships with default GIFI codes per account; no editor, no export.
- **Expected behaviour:** mapping screen with "Unmapped: 0" badge, auto-suggest for new accounts by type/name, bulk map, GIFI code search with descriptions; validation (BS accounts → 1000–3849 range, IS → 8000–9999 range); export as CSV and GIFI flat file format accepted by common T2 software, generated from the **tax book** TB; Schedule 141 notes checklist data; export totals reconcile to tax-book TB.
- **Business rules:** every active account with balance must be mapped before export (blocker list); totals per GIFI line = Σ mapped account balances; required GIFI totals (e.g. 2599 total assets, 3499 total liabilities and equity, 9999 net income) computed, not mapped; sign convention per schedule.
- **Edge cases:** sub-accounts (C-01) inherit parent mapping unless overridden; contra accounts; renumbered accounts keep mapping; mid-year mapping change (mapping is effective per export date).
- **UI/UX notes:** two-pane mapper (accounts left, GIFI tree right) with drag or picker, unmapped filter default when > 0; export dialog shows tie-out summary before download.
- **Dependencies:** C-01, K-07, K-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-07-T01 | GIFI code table seed (code, description, schedule, sign, total flag) | DB | — | Seed complete for 100/125 | Unit |
| G-07-T02 | Account → GIFI mapping model (effective_from) and inheritance for sub-accounts | DB/BE | C-01 | Sub-account inherits parent mapping | Unit |
| G-07-T03 | Auto-suggest service (type + keyword rules) for new accounts | BE | G-07-T01 | New "Meals" expense suggests 8523 | Unit |
| G-07-T04 | Range validation (BS vs IS ranges) and unmapped blocker list | BE | G-07-T02 | Revenue mapped to 1000 refused | Unit |
| G-07-T05 | Schedule 100/125 aggregation from tax-book TB incl. computed totals | BE | K-07 | 2599 = 3640 total check passes on fixture | Data validation |
| G-07-T06 | Schedule 141 data block (engagement type, prepared by practice, flags) | BE | K-06 | Fields populated | Unit |
| G-07-T07 | Export writers: CSV + GIFI flat file | BE | G-07-T05 | Sample imports into T2 software test harness / format validator | Integration |
| G-07-T08 | API `/api/v1/tax/gifi/mappings/`, `/export/` | API | G-07-T07 | Sweep passes | Integration |
| G-07-T09 | Mapper UI (two-pane, bulk map, unmapped badge) | FE | G-07-T08 | Unmapped count updates live | Playwright |
| G-07-T10 | Export dialog with tie-out summary | FE | G-07-T08 | Shows tax-book TB = export | Playwright |
| G-07-T11 | Gap-30 test: template loads with 0 unmapped; export balances | QA | G-07-T05 | `gap-30` green | pytest |
| G-07-T12 | i18n + guide | DOC | G-07-T09 | Lint passes | CI |

- **Deliverable acceptance:** export balances to tax-book TB.

### G-08 · Corporate tax computation (tax book)
- **Branch:** `feature/G-08-corporate-tax`
- **Objective:** compute corporate income tax from the tax book: NI for tax, Schedule 1 adjustments, CCA, loss application, federal SBD/general and provincial rates as effective-dated data, instalments, and a provision JE to the accounting book on confirmation.
- **Current behaviour:** tax-book NI exists (K-07) and CCA claim (I-03); no tax computation.
- **Expected behaviour (beyond Xero):** computation screen per tax year: (1) accounting NI, (2) Schedule 1 additions/deductions by category (from K-07), (3) NI for tax, (4) non-capital loss applied (from carry-forward table, user-chosen amount up to available, oldest first) → taxable income, (5) federal: active business income up to the business limit at the small-business rate, remainder at the general rate (rates/limit as data, business limit shared/ground-down inputs entered), (6) provincial rates by province of permanent establishment (allocation % entered when multiple), (7) total tax, credits/instalments paid (from G-09 records), balance owing/refund, (8) next-year instalment schedule (monthly/quarterly per data rules). Confirm → posts provision JE (Dr income tax expense / Cr income tax payable) to the accounting book (book `accounting`), and K-08 tax line updates. Recompute on change; versions retained.
- **Business rules:** rates are data, never code (effective-dated by tax-year end and province); computation version immutable once confirmed (reconfirm creates new version and an adjusting provision JE for the difference); loss application cannot exceed available carry-forward or taxable income; CCPC flag controls SBD eligibility; GMA supplies software, not tax advice — computation labelled "Estimate for accountant review" until the accountant confirms.
- **Edge cases:** loss year (tax 0, loss added to carry-forward), short tax year (business limit pro-ration by days), multiple provinces, non-CCPC, prior-year loss expiry (20-year rule as data), associated corporations sharing the business limit (manual allocation), refund position.
- **UI/UX notes:** vertical "waterfall" computation with each step expandable and sourced (link to report/adjustment); input chips for the few manual items (CCPC, business limit share, province allocation, loss to apply); "What changed since last version" diff; confirm button shows the provision JE preview.
- **Dependencies:** K-07, I-03, G-09 (instalments paid, later; manual entry until Phase 4), A-05.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| G-08-T01 | Wireframes: computation waterfall, inputs, version diff, provision preview | UX | — | Approved | Review |
| G-08-T02 | `CorporateTaxRate` data model (jurisdiction federal/province, rate type SBD/general/abatement, rate, business limit, effective_from/to) + seed for 2026 published values (client to confirm) | DB | — | Seed loads; rates are rows | Unit |
| G-08-T03 | `TaxProfile` per org (CCPC flag, provinces of PE with allocation %, business-limit share, associated group note) | DB | A-05 | Allocation must total 100 % | Unit |
| G-08-T04 | `TaxComputation` + `TaxComputationVersion` (inputs snapshot, step results JSON, status Draft/Confirmed, ledger version) | DB | — | Confirmed version immutable | Unit |
| G-08-T05 | Step 1–3: accounting NI, Schedule 1 adjustments by category, NI for tax (from K-07) | BE | K-07 | Fixture NI for tax correct | Unit |
| G-08-T06 | Step 4: non-capital loss application (oldest first, cap at available and taxable income, expiry rule as data) | BE | I-03-T15 | Cannot apply more than available | Unit (Hypothesis) |
| G-08-T07 | Step 5: federal tax with SBD up to business limit (short-year pro-ration) and general rate on remainder | BE | G-08-T02 | Fixture federal tax to the dollar | Unit |
| G-08-T08 | Step 6: provincial tax per allocation (small and general rates) | BE | G-08-T03 | Multi-province fixture correct | Unit |
| G-08-T09 | Step 7: instalments/credits paid (manual entry now; G-09 feed in Phase 4) and balance owing/refund | BE | — | Balance = tax − paid | Unit |
| G-08-T10 | Step 8: next-year instalment schedule per data rules | BE | G-08-T02 | Schedule dates/amounts on fixture | Unit |
| G-08-T11 | Versioning, recompute on ledger change (stale flag), diff between versions | BE | G-08-T04 | Diff lists changed steps | Unit |
| G-08-T12 | Confirm → provision JE (accounting book) and adjusting JE on reconfirm | BE | C-02 | Provision = total tax; reconfirm posts difference only | Integration |
| G-08-T13 | Loss-year flow: adds to carry-forward table, tax 0 | BE | I-03-T15 | Full-CCA fixture: carry-forward 1,300, tax 0 | Unit |
| G-08-T14 | API `/api/v1/tax/corporate/{tax_year}/` compute/confirm/versions; feature key `tax.corporate` | API | G-08-T12 | Contract + sweep pass | Integration |
| G-08-T15 | Computation waterfall UI with sourced steps and input chips | FE | G-08-T14 | Each step links to its source | Playwright |
| G-08-T16 | Version diff + confirm dialog with JE preview | FE | G-08-T14 | Preview = posted JE | Playwright |
| G-08-T17 | Rates admin screen (platform owner + practice override proposals) with effective dates | FE | G-08-T02 | New rate effective next year leaves current computation unchanged | Playwright |
| G-08-T18 | T2 fixture corporation with known result (client-verified) | QA | G-08-T12 | Computes to the dollar | Compliance |
| G-08-T19 | Fixtures: short year, multi-province, non-CCPC, loss application, loss year | QA | G-08-T18 | 100 % pass | Compliance |
| G-08-T20 | Disclaimer copy and audit of who confirmed | DOC/BE | A-04 | Confirmation audited with user | Integration |
| G-08-T21 | i18n + accountant guide | DOC | G-08-T15 | Lint passes | CI |

- **Deliverable acceptance:** T2 fixture computes to the dollar; rates are data.
- **Risks:** rate errors → data seeded from published sources and client confirmation; misuse as advice → explicit estimate labelling and accountant confirmation.

---

### 6.9 Purchases — capture (Component E)

### E-05 · Receipt & bill capture (inbound email + OCR)
- **Branch:** `feature/E-05-capture-ocr`
- **Objective:** documents arriving by per-organisation email address, upload or mobile (later Y-02) are read by a pluggable extraction provider that proposes supplier, date, invoice number, totals, tax and lines with per-field confidence; nothing is created without user confirmation.
- **Current behaviour:** A-06 inbox receives files and per-org inbound email; bills (E-02) are keyed manually.
- **Expected behaviour (better than Xero):** extraction runs automatically on arrival; inbox item shows the document beside a prefilled draft bill/expense with each field's confidence (High ≥ 0.90 green, Medium amber, Low red with the field focused); supplier matched by BN/GST number first, then name similarity, with "create supplier" suggestion; GST/HST amount split detected and mapped to ITC via G-01/G-02 defaults; duplicate check (E-02 uniqueness + similarity) before create; learning: confirmed corrections stored as supplier-specific hints (default account, tax code) for next time; confidence and corrections logged for accuracy measurement.
- **Gap #s closed:** #32 (per-field confidence; period tagging), #51 (capture included in Accounting product, not paid add-on).
- **Business rules:** every suggestion requires confirmation; extraction never posts; provider is an interface (`ExtractionProvider.extract(file) → fields+confidence`) with on-server OCR (Tesseract + layout heuristics) as default and an optional paid provider (client choice; fees client's); PII not sent to a provider outside the approved region unless configured; files tagged with period/tax year from document date.
- **Edge cases:** multi-page PDFs, multiple invoices in one PDF (split suggestion), photos rotated/skewed, French-language receipts, foreign currency, credit notes, password-protected PDFs (rejected with message), email with many attachments, provider timeout (item stays in inbox with "Read failed — enter manually").
- **UI/UX notes:** split-view review screen: document viewer (zoom, page nav, highlight of the region a field came from) on the left; form on the right with confidence dots; keyboard flow (Tab through low-confidence fields first, Enter to confirm, J/K next/previous inbox item); batch mode for many receipts; clear empty state showing the org's forwarding address with Copy button.
- **Dependencies:** A-06, E-02, E-04, B-01, G-01, G-02, A-08.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| E-05-T01 | Wireframes: split-view review, confidence states, batch mode, empty state | UX | — | Approved | Review |
| E-05-T02 | ADR: extraction provider interface + default on-server engine; data-residency rules | DOC | — | ADR recorded | Review |
| E-05-T03 | `ExtractionJob` model (file, provider, status Queued/Running/Done/Failed, raw result, duration) + `ExtractedField` (name, value, confidence, bbox) | DB | A-06 | Migration applies | Unit |
| E-05-T04 | `ExtractionProvider` interface + fixture provider for tests | BE | E-05-T03 | Fixture provider drives full flow in CI | Unit |
| E-05-T05 | Default provider: PDF text layer (pdfplumber) + OCR (Tesseract en/fr) with preprocessing (deskew, rotate) | BE | E-05-T04 | Fixture set processed | Integration |
| E-05-T06 | Field parsers: date (en-CA/fr-CA formats), totals, GST/HST/QST/PST amounts, BN/GST number regex, invoice number | BE | E-05-T05 | Parser unit fixtures pass | Unit |
| E-05-T07 | Confidence scoring per field (source quality + parser certainty + cross-check subtotal+tax=total) | BE | E-05-T06 | Inconsistent totals lower confidence | Unit |
| E-05-T08 | Supplier matching (BN/GST no. → exact; name fuzzy) + create-supplier suggestion | BE | B-01 | Fixture suppliers matched | Unit |
| E-05-T09 | Tax mapping to G-01 codes via place of supply (G-02) and amount check | BE | G-02 | ON receipt with 13 % → HST purchase code | Unit |
| E-05-T10 | Duplicate check before create (E-02 rules) | BE | E-02 | Duplicate blocked with link to existing bill | Integration |
| E-05-T11 | Celery pipeline on file arrival (A-06 inbound) with timeout/retry and failure state | OPS/BE | A-08 | Timeout → "Read failed" item | Integration |
| E-05-T12 | Supplier hint learning (default account/tax from confirmed corrections) | BE | E-05-T08 | Second receipt from same supplier prefilled | Integration |
| E-05-T13 | Period/tax-year tagging from document date | BE | A-06 | Tag set on file | Unit |
| E-05-T14 | API `/api/v1/capture/items/` list/get/confirm (→ bill/expense/asset draft) | API | E-05-T10 | Confirm creates draft only; sweep passes | Integration |
| E-05-T15 | Split-view review UI with document viewer and field-region highlight | FE | E-05-T14 | Clicking field highlights region | Playwright |
| E-05-T16 | Confidence dots + low-confidence-first tab order + keyboard shortcuts | FE | E-05-T15 | Tab order starts at lowest confidence | Playwright |
| E-05-T17 | Batch mode (next/previous, bulk confirm high-confidence items) | FE | E-05-T15 | 20 receipts processed without mouse | Playwright |
| E-05-T18 | Accuracy measurement script over labelled fixture set (≥ 50 documents EN/FR) | QA | E-05-T07 | Report shows ≥ 80 % field accuracy | Fixture report |
| E-05-T19 | Security: MIME validation, password-protected PDF rejection, no PII in logs | QA | A-06 | Tests green; log scan clean | Security |
| E-05-T20 | Optional paid provider adapter behind feature flag (client decision) | BE | E-05-T04 | Swapping provider changes no screen | Integration |
| E-05-T21 | Gap-32 test (confidence shown per field; period tag) | QA | E-05-T16 | `gap-32` green | Playwright |
| E-05-T22 | i18n + guide | DOC | E-05-T15 | Lint passes | CI |

- **Deliverable acceptance:** ≥ 80 % field accuracy on fixtures; confidence shown per field; every suggestion requires confirmation.
- **Risks:** OCR accuracy on photos → preprocessing + paid-provider option; privacy → on-server default.

---

## 7. TEST — Phase 2 test plan (Rules 5–6)

### 7.1 Test matrix

| Category | Phase 2 scope | Tooling | Target |
|---|---|---|---|
| Unit | Costing (moving average, FIFO, landed cost), UoM conversion, EOQ formula, contribution margin, loan amortisation, interest/discount formulas, SL/DB depreciation, UCC/CCA (half-year, AII, short year, recapture, terminal loss), claim bounds, book filter, Schedule 1 grouping, corporate tax steps, FX conversion/rounding, formula engine, GL functions, OCR parsers | pytest, Hypothesis, factory_boy, Vitest | ≥ 85 % on `inventory`, `finance`, `assets`, `cca`, `twobook`, `tax`, `fx`, `sheets` packages |
| Property-based | On-hand = Σ movements; GL inventory = valuation; TB(accounting)=0 and TB(tax)=0; accounting NI − adjustments = tax NI; loan liability = schedule balance; depreciation never below residual; adjusted TB = TB + adjustments; FX converted lines sum = total | Hypothesis | 1,000 runs per property, nightly 10,000 |
| Integration | Endpoint ↔ DB ↔ JE engine for every posting service (stock movement, loan payment, depreciation, CCA claim, disposal, FX revaluation, tax provision); Celery jobs (depreciation, FX rates, revaluation, loan accruals, extraction); provider stubs (FX feed, OCR) | pytest + DRF client, MinIO, fixture providers | Each endpoint: one happy path + one failure |
| Functional (E2E) | Stock-controlled sale with COGS; PO from EOQ suggestion; build assembly; loan created → schedule → payment posted; asset from bill → depreciation run → CCA full claim → tax statements; time → invoice; working paper tied to tax TB; foreign invoice paid with FX; receipt captured → bill | Playwright | One scripted scenario per component (H, H-analytics, FN, I, J, L, R, K two-book, G-04/07/08, E-05) |
| Regression | Full suite on every PR; nightly on `main` with the 500-org fixture practice; all Phase 0–1 suites stay green (book-aware query layer change in K-07-T05 is the main regression risk) | GitHub Actions | 0 known regressions |
| Data validation | Valuation report = GL inventory; COGS in rankings = COGS postings; loan GL = schedule (both books); register = GL; continuity = GL; Schedule 8 closing = tax-BS UCC; reconciliation report nets to 0; GIFI export = tax-book TB; QST worksheet = QST control accounts | Reconciliation scripts in CI release gate | 0.00 difference on every fixture |
| Security | Tenant sweep over all new endpoints (assets, inventory, finance, sheets, tax, capture); feature-key gating (Inventory, Finance, Tax products) and entitlement-leak tests; GL-function permission (#NOACCESS); upload hardening (XLSX templates, OCR files); no PII in logs | Custom sweeps, ZAP, pip-audit, npm audit, gitleaks, semgrep | No high findings |
| Performance | 12-month two-book side-by-side on 100k-line GL < 3 s p95; SKU ranking over 10k SKUs × 12 months < 2 s; EOQ recompute 10k SKUs < 60 s job; depreciation preview 5,000 assets < 2 s; sheet 200×50 smooth; 500 GL cells refresh < 2 s; management pack < 10 s | k6, Lighthouse, browser perf traces | Targets met on staging-sized data |
| Compliance fixtures | Client depreciation templates (SL/DB); CCA classes incl. half-year, AII, short year, recapture/terminal loss, full-claim-as-loss; T2 fixture for G-08 (to the dollar); QST return incl. stub period; client EOQ worked example; loan reference calculator schedules; client KPI formulas | `tests/fixtures/compliance/{depreciation,cca,t2,qst,eoq,loans,kpi}` | 100 % pass |
| Localisation | i18n missing-key gate (en-CA complete, fr-CA keys present); pseudo-localisation +30 % on all new screens; fr-CA number formats in Sheets and reports | CI extraction, Playwright | 0 missing keys; no clipped layouts |
| Accessibility | axe-core on every new screen; keyboard-only completion of: asset add, depreciation run, CCA claim, receipt review, budget entry | axe, Playwright | 0 serious/critical issues |
| Usability | 5 moderated sessions (2 accountants, 2 owners, 1 bookkeeper) on scripted tasks (see §3.6) | Figma prototype + staging | ≥ 80 % task success, SUS ≥ 75 |
| Gap closure | gap-11, gap-18, gap-30, gap-32, gap-34, gap-46, gap-51, gap-57 tagged checks | Playwright + pytest | All green before phase exit |

### 7.2 Compliance fixture inventory (created in Phase 2)
1. `depreciation/` — client SL and DB templates with worked examples (I-04 input).
2. `cca/class8_half_year.yaml` — 10,000 mid-year → 1,000 / 1,800.
3. `cca/full_claim_loss.yaml` — NI 500, max 1,800 → −1,300, carry-forward 1,300; claim 500 → NI 0, UCC +1,300.
4. `cca/short_year.yaml`, `cca/recapture.yaml`, `cca/terminal_loss.yaml`, `cca/aii.yaml`.
5. `t2/ccpc_on_basic.yaml` — known T2 result (client-verified) for G-08/K-08.
6. `qst/monthly_qst_quarterly_gst.yaml`, `qst/stub_period.yaml`, `qst/late_adjustment.yaml`.
7. `eoq/client_worked_example.yaml` (H-11 input), `kpi/*.yaml` (H-13/FN-05 inputs).
8. `loans/car_loan_60m.yaml`, `loans/rate_change.yaml`, `loans/early_repayment.yaml`, `loans/loc_interest.yaml`.
9. `inventory/moving_average.yaml`, `inventory/fifo.yaml`, `inventory/landed_cost.yaml`, `inventory/bom_build.yaml`.
10. `fx/partial_payments_usd.yaml`, `fx/revaluation.yaml`.
11. `capture/labelled_set/` — ≥ 50 receipts/bills EN and FR with ground-truth fields.

### 7.3 Exit demonstration script (observed on staging, Agreement §07)

| # | Step | Expected result |
|---|---|---|
| 1 | Log in as accountant; open the Phase 2 fixture organisation (Inventory + Finance + Tax products) | Dashboard loads < 1.5 s; no gating prompts for included products |
| 2 | Inventory → Analytics: best-selling SKUs, last 12 months, by margin | Ranking shown; top SKU's revenue and COGS drill down to postings and tie to P&L |
| 3 | Open stock-movement analysis; filter Dead stock | Dead/slow SKUs listed with days of cover; figures reproduce fixture |
| 4 | Reorder suggestions (EOQ): open a SKU below reorder point; check EOQ = client's worked example; click "Create PO" | Draft PO created in one action with suggested quantity and supplier |
| 5 | Price optimisation: run what-if +5 % on a category | Projected contribution margin shown; live prices unchanged until "Apply" |
| 6 | Finance → Loans: create car loan (principal, rate, 60 months, monthly) | Schedule generated; matches reference calculator to the cent |
| 7 | Record the first loan payment from the chequing account | JE posted: principal reduction + interest expense; loan GL = schedule balance; YTD interest shown |
| 8 | Fixed assets: from a bill line create a Class 8 furniture asset 10,000 | Asset linked to bill; register ↔ GL difference 0.00 |
| 9 | Run depreciation to year end | Depreciation JE = schedule (client template method) |
| 10 | Tax → CCA for the year: NI before CCA 500, max CCA 1,800; toggle "Claim maximum even if it creates a loss"; post | NI for tax −1,300; carry-forward 1,300; accounting book unchanged |
| 11 | Reports → Income Statement, side by side (Accounting · Adjustments · Tax) | Columns reconcile per line; amortisation replaced by CCA |
| 12 | Tax → Corporate tax computation; confirm | Tax computed (loss year → 0, carry-forward recorded); on T2 fixture org, tax = known answer to the dollar; provision JE posted |
| 13 | Tax-purpose Balance Sheet and Income Statement with tax line; Book Reconciliation report | Tax line = G-08; reconciliation difference 0.00 |
| 14 | Export GIFI | Export totals = tax-book TB; 0 unmapped accounts |
| 15 | Sheets: create lead schedule from template, book = tax | Values = tax-book TB; locked period read-only |
| 16 | Forward a supplier PDF to the org's inbound address | Item appears < 60 s with per-field confidence; confirm creates draft bill only |
| 17 | Foreign USD invoice paid at a different rate | Realised FX posted to FX account; AR cleared |

### 7.4 Failure handling
A failing step stops dependent work; the exact condition is recorded; cause classified (code / data / configuration / assumption); one focused fix; re-run affected tests then the regression suite. Tests are never skipped or reported as passed without execution; unverifiable items (e.g. client fixture not yet supplied) are reported as "not executed — waiting for client input 9.1(b)".

---

## 8. IMPROVE — post-verification review (Rule 8)

### 8.1 Review checklist (per deliverable, after acceptance criteria pass)
- **Correctness:** every posting service reuses C-02 `post()`; no service writes journal lines directly; two-book filter used everywhere (no raw queries bypassing `ledger.balances(book=)`).
- **Readability:** calculators (costing, EOQ, amortisation, SL/DB, CCA, tax) are pure functions with docstrings citing the formula source (client material / Schedule II / published rate table).
- **Maintainability:** all rates, classes, limits and formulas are data with effective dates; client-supplied formulas stored with version and source document reference.
- **Performance:** analytics read from the reporting replica and nightly materialised aggregates (SKU-day sales, stock-day balances, ledger period balances per book); no N+1 in lists (django-silk/nplusone checks).
- **Reliability:** every scheduled job idempotent (keys: org + period + job); failed jobs visible in A-08 dashboard; provider failures degrade to manual entry, never block.
- **Security:** feature keys declared (`inventory.*`, `inventory.analytics`, `finance.loans`, `assets.*`, `tax.cca`, `tax.corporate`, `tax.returns`, `sheets`, `projects`, `capture`); tenant sweep green; uploads scanned.
- **Consistency:** shared grid, importer, report engine, wizard and drawer patterns reused; no module-specific variants; Canadian terms (amortization in statements per ASPE wording chosen at kickoff, CCA, UCC).
- **UX polish:** empty states written; error messages name cause and fix; keyboard paths complete; visual regression baselines updated.

### 8.2 Performance budgets for Phase 2
| Item | Budget |
|---|---|
| Side-by-side two-book IS/BS (100k lines, 12 months) | < 3 s p95 |
| SKU rankings (10k SKUs, 12 months) | < 2 s p95 |
| Stock card (5k movements) | < 1 s |
| EOQ batch recompute (10k SKUs) | < 60 s background |
| Loan schedule generation (360 periods) | < 200 ms |
| Depreciation preview (5,000 assets) | < 2 s |
| CCA schedule load | < 500 ms |
| Corporate tax recompute | < 1 s |
| Sheets: 200×50 scroll / 500 GL cells refresh | ≥ 55 fps / < 2 s |
| Management pack PDF | < 10 s |
| OCR extraction per page (default engine) | < 15 s, inbox item < 60 s |

### 8.3 Phase-end IMPROVE checkpoint
Module boundaries review (inventory ↔ purchases ↔ sales; finance ↔ banking; assets ↔ tax), query performance on the growing fixture practice, design-system consistency audit of all Phase 2 screens, accessibility pass, i18n key hygiene, entitlement matrix review (Inventory and Finance products), and a list of improvement items moved to the backlog (never mixed into feature branches).

---

## 9. Git branch plan (Rule 7)

| Order | Branch | Base | Deliverable | Parallel group | Merge after |
|---|---|---|---|---|---|
| 1 | `feature/K-07-two-book-engine` | main | K-07 | A (foundation) | Phase 1 merged |
| 2 | `feature/R-01-currencies-rates` | main | R-01 | A | — |
| 3 | `feature/H-01-items-catalog` | main | H-01 | B (inventory) | — |
| 4 | `feature/H-02-units-of-measure` | main | H-02 | B | H-01 |
| 5 | `feature/H-03-locations-stock` | main | H-03 | B | H-02 |
| 6 | `feature/H-04-stock-movements` | main | H-04 | B | H-03 |
| 7 | `feature/H-05-costing` | main | H-05 | B | H-04 |
| 8 | `feature/H-06-batch-serial` | main | H-06 | B | H-04 |
| 9 | `feature/H-07-reorder-reports` | main | H-07 | B | H-05 |
| 10 | `feature/H-08-assemblies` | main | H-08 | B | H-05 |
| 11 | `feature/H-09-sku-rankings` | main | H-09 | C (analytics) | H-05 |
| 12 | `feature/H-10-stock-movement-analysis` | main | H-10 | C | H-09 |
| 13 | `feature/H-11-eoq-reorder` | main | H-11 | C | H-07, H-10 |
| 14 | `feature/H-12-margin-price-optimisation` | main | H-12 | C | H-09 |
| 15 | `feature/H-13-mgmt-kpis` | main | H-13 | C | H-12 |
| 16 | `feature/FN-01-loan-register` | main | FN-01 | D (finance) | K-07 |
| 17 | `feature/FN-02-amortisation-schedule` | main | FN-02 | D | FN-01 |
| 18 | `feature/FN-03-loan-posting` | main | FN-03 | D | FN-02 |
| 19 | `feature/FN-04-credit-terms-interest` | main | FN-04 | D | FN-03 |
| 20 | `feature/FN-05-loan-reports-kpis` | main | FN-05 | D | FN-04 |
| 21 | `feature/I-01-asset-register` | main | I-01 | E (assets/tax) | K-07 |
| 22 | `feature/I-04-depreciation-templates` | main | I-04 | E | I-01 |
| 23 | `feature/I-02-depreciation-runs` | main | I-02 | E | I-01 |
| 24 | `feature/I-03-cca-claim` | main | I-03 | E | I-02, K-07 |
| 25 | `feature/I-05-disposals` | main | I-05 | E | I-03 |
| 26 | `feature/K-08-tax-statements` | main | K-08 | E | G-08 |
| 27 | `feature/G-08-corporate-tax` | main | G-08 | E | I-03 |
| 28 | `feature/K-10-adjusted-tb` | main | K-10 | E | K-07 |
| 29 | `feature/G-07-gifi-export` | main | G-07 | E | K-07 |
| 30 | `feature/G-04-qst-return` | main | G-04 | F (tax/other) | Phase 1 G-03 |
| 31 | `feature/R-02-fx` | main | R-02 | F | R-01 |
| 32 | `feature/J-01-projects` | main | J-01 | F | — |
| 33 | `feature/J-02-timesheets` | main | J-02 | F | J-01 |
| 34 | `feature/J-03-time-to-invoice` | main | J-03 | F | J-02 |
| 35 | `feature/L-01-sheets-grid` | main | L-01 | G (sheets) | — |
| 36 | `feature/L-02-gl-functions` | main | L-02 | G | L-01, K-07 |
| 37 | `feature/L-03-sheet-templates` | main | L-03 | G | L-02, I-03, FN-02 |
| 38 | `feature/L-04-sheets-xlsx` | main | L-04 | G | L-02 |
| 39 | `feature/K-04-budgets` | main | K-04 | F | — |
| 40 | `feature/K-06-management-pack` | main | K-06 | F | K-07 |
| 41 | `feature/E-05-capture-ocr` | main | E-05 | F | — |

**Before each branch:** `git status` clean; pull `main`; restate objective and acceptance criteria in the PR description; confirm prerequisites merged; note client inputs needed.
**During:** one atomic task per commit (message `<Task ID>: <summary>`), each verified before the next; no unrelated changes.
**Before complete:** all atomic tasks ✓; acceptance criteria observed; CI green (unit, integration, isolation sweep, entitlement leak, i18n gate, compliance fixtures, reconciliation release gate); no debug code; no secrets (gitleaks); docs updated; diff reviewed by a second engineer. No merge to `main` without the project lead's authorisation.

---

## 10. Phase 2 risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Client inputs late (depreciation templates, EOQ equation, management-accounting material — due start of Phase 2, Agreement 9.1(b)) | Medium | High | Seeded defaults keep modules usable; formula slots are data; timeline extends per Agreement 6.3; flagged in sprint report on day 1 |
| 2 | Two books drift after K-07 query-layer change | Medium | High | Property tests + CI reconciliation gate + exceptions rule |
| 3 | CCA / corporate tax computation errors | Medium | High | Rates as data, client-verified T2 fixture, accountant confirmation step, "estimate" labelling |
| 4 | Inventory valuation ≠ GL (costing bugs, back-dated movements) | Medium | High | Every movement posts; property test; nightly valuation-vs-GL check; back-dated movement re-costing job |
| 5 | Loan schedule ≠ lender statements (day-count, compounding conventions) | Medium | Medium | Configurable compounding and day-count; reference calculator fixtures; manual adjustment entry |
| 6 | Analytics performance at 10k SKUs / 500 orgs | Medium | Medium | Materialised daily aggregates on reporting replica; background recompute |
| 7 | OCR accuracy below 80 % on photos/French receipts | Medium | Medium | Preprocessing, labelled set measurement, optional paid provider, confirmation always required |
| 8 | Sheets formula-engine licence or parity issues | Low | Medium | ADR-005 licence check; shared test vectors between client and server engines |
| 9 | Scope breadth (40 deliverables in 2 weeks) | High | High | Parallel groups A–G; smallest working piece first; strict change control; daily burn-down of atomic tasks |
| 10 | FX feed outage | Low | Low | Manual rates allowed; alert; prior-business-day fallback labelled |
| 11 | Users mistaking tax book for accounting book | Medium | Medium | Persistent book switch, accent styling and labels, side-by-side default for tax screens |

---

## 11. Phase completion checklist (Rule 11) & reporting template (Rule 10)

### 11.1 Mandatory execution checklist — tracked per atomic task and per deliverable in the repository (`docs/phase-2/checklists/<ID>.md`)

**UNDERSTAND**
- [ ] Investigated existing implementation (Phase 0–1 models/services reused: C-02 posting, G-01 tax codes, E-01/E-02 purchasing, K-01 report engine, A-06 files, A-08 jobs)
- [ ] Identified user and outcome
- [ ] Defined inputs and outputs
- [ ] Identified business rules (incl. client formulas and statutory data)
- [ ] Considered edge cases
- [ ] Restated objective in PR

**PLAN**
- [ ] Decomposed into atomic tasks (tables in §6)
- [ ] Dependencies identified and ordered (§5.3, §9)
- [ ] Acceptance criteria defined
- [ ] Testing procedures defined (§7)

**BUILD**
- [ ] Smallest functional piece first (model → service → API → UI)
- [ ] Followed architecture; reused shared engines and design-system components
- [ ] No unnecessary or unrelated changes
- [ ] Existing functionality preserved
- [ ] Feature key and i18n keys declared

**TEST**
- [ ] Behaviour verified against acceptance criteria
- [ ] Edge cases tested
- [ ] Failures investigated and resolved (structured debugging, 30-minute rule)
- [ ] Regression suite green
- [ ] Tenant-isolation sweep and entitlement-leak tests green
- [ ] Data-validation gates (valuation, loans, register, two books, GIFI, QST) at 0.00
- [ ] Unverified conditions recorded

**IMPROVE**
- [ ] Code quality reviewed (§8.1)
- [ ] Temporary artefacts and mocks removed / real integrations connected
- [ ] Readability improved where needed
- [ ] Behaviour re-verified after improvements

**COMPLETE**
- [ ] Final diff reviewed
- [ ] Documentation updated (user guide, data dictionary, ADR-004/005)
- [ ] Changes and test results reported
- [ ] Acceptance criteria confirmed
- [ ] Final status reported

**Phase gate**
- [ ] All 40 deliverables (H-01…H-13, FN-01…FN-05, I-01…I-05, J-01…J-03, L-01…L-04, R-01, R-02, K-04, K-06, K-07, K-08, K-10, G-04, G-07, G-08, E-05) meet acceptance
- [ ] Phase-2 gap checks green (gap-11, 18, 30, 32, 34, 46, 51, 57)
- [ ] Exit demonstration (§7.3) observed on staging and recorded
- [ ] Release notes + test results delivered to Profitex; 5-business-day review window started (Agreement 7.2)

### 11.2 Reporting template

**Before implementation (per deliverable PR description)**
1. Problem understanding — objective; existing behaviour; expected behaviour.
2. Task breakdown — components; atomic tasks (IDs); dependencies.
3. Implementation plan — execution order; acceptance criteria; testing strategy.

**After implementation (per deliverable and in the bi-weekly sprint report)**
1. Changes made — completed tasks; files/components modified; key decisions (ADR links).
2. Testing results — executed; passed; failed; not executed and why (e.g. awaiting client EOQ example).
3. Remaining issues — known limitations; unresolved bugs; risks/dependencies.
4. Final status — Complete / Partially complete / Blocked.

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| H-01 | 25 | 37.5 |
| H-02 | 16 | 24 |
| H-03 | 15 | 22.5 |
| H-04 | 20 | 30 |
| H-05 | 18 | 27 |
| H-06 | 13 | 19.5 |
| H-07 | 17 | 25.5 |
| H-08 | 11 | 16.5 |
| H-09 | 14 | 21 |
| H-10 | 12 | 18 |
| H-11 | 17 | 25.5 |
| H-12 | 16 | 24 |
| H-13 | 14 | 21 |
| FN-01 | 18 | 27 |
| FN-02 | 20 | 30 |
| FN-03 | 18 | 27 |
| FN-04 | 18 | 27 |
| FN-05 | 17 | 25.5 |
| I-01 | 23 | 34.5 |
| I-02 | 15 | 22.5 |
| I-03 | 24 | 36 |
| I-04 | 12 | 18 |
| I-05 | 12 | 18 |
| J-01 | 12 | 18 |
| J-02 | 13 | 19.5 |
| J-03 | 11 | 16.5 |
| L-01 | 16 | 24 |
| L-02 | 10 | 15 |
| L-03 | 9 | 13.5 |
| L-04 | 6 | 9 |
| R-01 | 12 | 18 |
| R-02 | 13 | 19.5 |
| K-04 | 9 | 13.5 |
| K-06 | 12 | 18 |
| K-07 | 22 | 33 |
| K-08 | 16 | 24 |
| K-10 | 10 | 15 |
| G-04 | 12 | 18 |
| G-07 | 12 | 18 |
| G-08 | 21 | 31.5 |
| E-05 | 22 | 33 |
| **Total** | **623** | **934.5** |

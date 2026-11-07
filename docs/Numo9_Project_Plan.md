# NUMO9 — Accounting, Tax, Payroll & Inventory Platform for Accountants and their Clients
## Project Plan

| | |
|---|---|
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment), Amman, Jordan |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada (product owner of Numo9) |
| **Document** | Numo9 Project Plan v2.0 (supersedes Profitex Project Plan v1.0 of 22 October 2026) |
| **Date** | 27 October 2026 |
| **Reference** | GMA-PFX-2026-001 (revision 2 — product renamed Numo9) |
| **Inputs** | Profitex Project Plan v1.0 · Quotation GMA-PFX-2026-001 · Xero functional teardown of 26 October 2026 · Client notes of 26 October 2026 |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE (applied to the whole project and separately to every atomic task and every Git branch) |

---

## 0. How to read this plan

| Stage | Section | What it answers |
|---|---|---|
| UNDERSTAND | §1 | What changed since v1.0, who uses Numo9, business model, client decisions, Xero gaps to close, business rules, risks, smallest useful implementation |
| DECOMPOSE | §2 | Objective → Components → Atomic tasks, with dependencies |
| PLAN | §3 | Task cards: current vs expected behaviour, steps, acceptance criteria, test approach, risks |
| Gap closure | §4 | Xero teardown gap → Numo9 task traceability matrix |
| BUILD | §5 | Delivery phases, sprint order, stack, environments, Git branch policy |
| TEST | §6 | Test categories, coverage targets, failure handling |
| IMPROVE | §7 | Post-verification review, hardening, warranty |
| Governance | §8–§11 | Risks, reporting template, deliverables, change control |

Nothing in §3 is coded until its task card has been restated, decomposed and planned. Nothing is declared complete until its acceptance criteria have been observed.

---

## 1. UNDERSTAND

### 1.1 What changed between v1.0 and this plan

| Area | v1.0 (Profitex Platform) | v2.0 (Numo9) |
|---|---|---|
| Product identity | Internal platform for one firm at profitex.ca | **Numo9** — a branded, multi-tenant SaaS product owned by Profitex, used by many accountants and the organisations they manage |
| Who pays | The firm (replacing its Xero subscription) | **Accountants never pay.** Each accountant manages organisations; **each organisation pays a package subscription.** |
| Commercial model | None (internal) | Packages built on four main products — **Accounting, Tax, Payroll, Inventory** — 30-day free trial, free demo account, founding offer: the first 1,000 organisations receive the full product set |
| Accountant workspace | Simple organisation switcher | Organisation directory with **search, grouping, bulk edit** for accountants managing many organisations |
| Invoices | Posted invoices immutable; corrections by void (Xero model) | **Posted invoices are editable; every edit creates a revision (101 → 101-1 → 101-2)** with full ledger re-posting and audit trail |
| Bank accounts | Standard | **Never locked**: bank accounts are usable with or without feeds, reconciliation or journal entries; balance is ledger-driven |
| Financial statements | Accounting basis only | **Two books**: Balance Sheet and Income Statement for *accounting* purposes and for *tax* purposes, with the tax amount computed from the tax set |
| Fixed assets | Book depreciation + CCA report | **Straight-line and declining-balance methods**, Canadian CCA classes (e.g., furniture Class 8 at 20%), client-supplied templates, **option to claim full CCA even where it creates a loss** |
| Tax payment | Out of scope | **Pay taxes from inside the system** (CRA / Revenu Québec remittances) |
| GST/HST filing | Fixed filing period | **Monthly / quarterly / annual with switching, out-of-cycle filing periods, and stop-filing** |
| Third-party integrations | Bank-feed adapter, Shopify/WooCommerce connectors (deferred) | **No third-party app marketplace.** Numo9 builds its own companion apps in later phases of this same project (e-commerce, etc.) |
| French UI, native mobile apps | Deferred to a separate quotation | **Included in this project** as named phases (see §5.2) |
| Xero parity | Feature parity | Feature parity **plus closure of every product gap found in the Xero teardown** (§4) |

### 1.2 What currently exists

Profitex runs on Xero for its own books and its clients' bookkeeping. The Xero teardown of 26 October 2026 (organisation "REFINED", Canada) confirms what Xero gives and, more importantly, what it does not:

- Two UI generations (legacy ASP.NET and new React pages) with different grids, date formats and empty states between the invoice editor, bill editor and repeating-invoice editor.
- Core accounting actions (approving invoices, credit notes, bank feeds, reminders, repeating invoices) are plan-gated with generic "upgrade" banners that never say which plan unlocks what; the credit-note page silently redirects.
- Tax handling is weak for Canada: no place-of-supply automation (36 manually chosen codes), expired rates (MB pre-2019, NS pre-April-2025) selectable forever, no zero-rated vs exempt split, no partial ITC (50 % meals), every account defaulting to Tax Exempt, a single "Sales Tax" control account for GST/HST/PST/QST/ITCs, tax settings split across four pages, and **no GST/HST return or sales-tax report at all** on the plan inspected.
- Controls are missing: Petty Cash sat at −994.17 with no warning; expenses were booked by manual journal with no contact, receipt or ITC; no lock dates; the General Ledger Exceptions report flagged nothing; Assurance checks ignore manual journals; conversion-balance differences are silently pushed to "Historical Adjustment".
- Localisation errors for a Canadian organisation: "State / ZIP Code" address fields, "Value added tax", "annual leave", a New Zealand sample customer on the invoice theme, US Letter page with metric margins, "Organization/organisation" and "Checks/Cheques" spelling flips.
- Fixed assets are unusable until a start date is set; no real CCA tax book; 0 of 139 accounts mapped to GIFI.
- Inventory tracking blocked by chart-of-accounts typing; no units of measure, locations, costing choice, reorder levels or categories.
- Contacts import matches on name (renames create duplicates) and blank columns destructively delete people; customer/supplier role is inferred, not set.
- Global search does not cover manual journals, accounts, settings or reports; the AI assistant can read journals that search cannot find.
- Reporting: no indirect-method cash flow, no AR/AP control vs sub-ledger reconciliation, trial balance not sorted by code, negative cash presented as a negative asset, statements headed by a number instead of the company name.

Xero does a few things well that Numo9 matches conceptually (never by copying UI or text): per-organisation inbound email for bills with extraction, duplicate-bill review, bank rules with fixed + percentage allocations, find-and-recode with an audit report, user-activity heatmaps, report layout editor with notes and draft/published versions, adviser report templates (NTR / Review / Compilation), keyboard shortcuts on quick-create, column chooser and saved views, and an AI assistant that can query the ledger.

### 1.3 What needs to change

Numo9 must be **one platform, owned by Profitex, sold as packages to organisations and operated by their accountants**, that:

1. Delivers Xero-equivalent core accounting in a single, consistent, Canada-localised UI generation.
2. Closes every product gap listed in the teardown (§4), with tax/compliance as the main differentiator.
3. Adds what Xero does not give a Canadian practice: native Canadian payroll, HR, inventory with quantity management, working papers, a two-book (accounting vs tax) reporting engine, CCA with straight-line and declining-balance methods, tax payment from the system, flexible GST/HST filing cycles.
4. Runs a SaaS business: accountant practices (free), organisations (paying), packages, 30-day trial, demo account, founding-1,000 offer, subscription billing, plan/feature matrix visible inside the app.
5. Gives accountants an organisation directory with search, grouping and bulk management.
6. Ships French UI and native mobile apps inside this project, and leaves room for Numo9's own companion apps (e-commerce first) in later phases instead of third-party connectors.

### 1.4 Problem definition (the seven questions)

**1. Who uses this functionality?**

| Actor | Description |
|---|---|
| Platform Owner (Profitex) | Owns Numo9: packages and prices, founding-offer counter, demo data, platform settings, all practices and organisations, platform analytics, billing oversight. |
| Accountant (Practice member) | Free account. Belongs to a Practice (a firm or a sole accountant). Manages many organisations: books, tax, payroll, working papers, period close. Uses the organisation directory with grouping and search. |
| Practice Admin | Accountant who also manages the practice's staff, groups, client invitations and practice-level templates. |
| Organisation Owner (paying client) | Business owner. Subscribes to a package, invites their accountant, sees their books, invoices, bills, payroll, taxes; approves work; pays taxes and subscription from the system. |
| Organisation User | Staff of a client organisation with limited roles (sales clerk, purchasing, payroll officer, HR, employee self-service). |
| Employee (self-service) | Pay stubs, T4s, leave, expense claims, timesheets. |
| Trial / Demo visitor | Opens a free demo organisation (sample data, resettable) or a 30-day trial organisation (own data, converts to paid). |
| Public visitor | Browses the Numo9 website: products, packages, pricing, signs up, requests demo. |
| System | Scheduled jobs: recurring documents, reminders, FX rates, trial expiry, subscription renewals and dunning, filing-deadline and remittance reminders, backups, depreciation runs, usage metering. |

**2. What is the desired outcome?**
A hosted, multi-practice, multi-organisation, role-based SaaS in which accountants run all accounting, tax, payroll, inventory and HR work for the organisations they manage, where organisations pay for packages, and from which taxes and subscriptions are paid online.

**3. What are the inputs?**
Package definitions and prices; practice and organisation sign-ups; chart of accounts, opening balances, contacts, invoices (including revisions), quotes, bills, purchase orders, bank statements (CSV/OFX/QBO import or manual entry), receipts and documents, inventory items and stock movements, fixed-asset data and client-supplied depreciation templates, employee master data, timesheets, leave, pay-run inputs, tax codes and rates, GST/HST filing-cycle settings, tax-book adjustments, CRA/Revenu Québec remittance instructions, card/PAD payment details (tokenised by the gateway, never stored by us), Xero export files for migration.

**4. What are the outputs?**
Posted ledger and journals, invoices and invoice revisions (PDF, email), credit notes, statements, bank balances and optional reconciliation state, financial reports in two books (accounting and tax) including the computed tax amount, GST/HST and QST return worksheets per filing cycle (including out-of-cycle periods), tax payment records and confirmations, CCA schedules (SL and DB), inventory valuation and stock reports, pay stubs, payroll registers, remittance summaries, T4/T4 Summary XML, ROE data, HR records, subscription invoices and receipts, usage/entitlement state, audit log, exports (CSV/XLSX/PDF/JSON).

**5. What are the business rules?**
Double-entry integrity (every JE balances; the ledger is append-only — an invoice revision reverses the prior posting and posts the new one, both linked to the revision chain); period and lock dates per module; role-based permissions per practice and per organisation; entitlement rules per package (a feature outside the organisation's package is visible but gated, never silently redirected); accountants never billed; organisations billed per package per month/year; 30-day trial with grace and conversion; demo organisations isolated and resettable; founding-1,000 counter is atomic and auditable; Canadian sales tax by place of supply, effective-dated, with zero-rated vs exempt and partial-ITC rules; GST/HST filing cycle changeable with out-of-cycle periods and stop-filing; payroll statutory calculations per CRA T4127 and Revenu Québec rules with versioned constants; two books with tax adjustments reconciling accounting net income to net income for tax purposes; CCA by class with SL/DB, half-year rule, and discretionary claim up to the full available amount even where a loss results; negative cash/bank balances warned on and reportable, never silently accepted; CRA six-year record retention; PCI scope kept outside our servers; PIPEDA; immutable audit trail.

**6. What could go wrong?**
Invoice revisions that leave the ledger or AR out of step with the printed document; subscription entitlement leaks (a lapsed organisation keeps paid features, or a paid organisation loses them); trial/demo data leaking into production reports; founding-offer counter over-allocating under concurrency; accountant seeing an organisation they were removed from; two books drifting (tax book not reconciling to accounting book); wrong CCA rate or half-year treatment; wrong GST/HST period after a cycle switch; a stopped HST registration still accruing filing periods; tax payment initiated twice; payroll constants out of date; double-charging on payment webhooks; bank duplicate transactions on re-import; stock going negative; migration mismatch from Xero; timezone/date errors at period ends; email deliverability; performance on large ledgers; French translation gaps breaking layouts; mobile apps diverging from web behaviour.

**7. What is the smallest useful implementation?**
A platform with packages and one paying organisation managed by one free accountant: chart of accounts, journal engine, contacts, editable-with-revisions invoices, bills, usable bank accounts with statement import, GST/HST codes with a switchable filing cycle, and the core reports in the accounting book — the walking skeleton. Phase 1 builds exactly this so a real organisation can run real books early.

### 1.5 Restated objective

**Currently:** Profitex and its clients run on Xero plus separate tools; Xero's Canadian tax handling, controls, localisation, inventory and fixed-asset tax book are weak; there is no product Profitex owns or sells.

**Change:** Build **Numo9** — a Django + Next.js multi-practice, multi-organisation SaaS with four main products (Accounting, Tax, Payroll, Inventory) sold as packages, free accountant accounts with an organisation directory, editable invoices with revisions, never-locked bank accounts, two-book reporting with computed tax, CCA with SL/DB methods, in-system tax payment, flexible GST/HST cycles, HR, working papers, practice management and portal, subscription billing with trial/demo/founding offer, a public product website, French UI and native mobile apps — and a roadmap for Numo9's own companion apps.

**Why:** To own the data and the product, remove Xero's gaps for Canadian accountants, open a recurring-revenue channel where organisations pay and accountants bring them in.

**Done means:** Every component in §2 passes its acceptance criteria in §3; every gap in §4 has an observed closing behaviour; Profitex's own books and at least one client organisation are migrated and reconciled to the cent against Xero; a live pay run matches the CRA calculator; an invoice has been revised to 101-1 with the ledger re-posted and AR correct; both books render with reconciling tax adjustments and a computed tax figure; a GST/HST cycle switch and an out-of-cycle period have been filed on fixtures; a tax payment and a subscription payment have been collected and reconciled; a demo and a trial organisation have converted; the Numo9 website, French UI and mobile apps are live.

### 1.6 Client decisions recorded (26 October 2026) and their design response

| # | Client note | Design response (where it lands) |
|---|---|---|
| 1 | Accountants do not pay. Each accountant has clients; the clients (organisations) pay a subscription. | Tenancy is **Practice → Organisation**; practices and accountant users are always free; billing attaches to the organisation only (A-01, U-01…U-06). |
| 2 | A free demo account for a client to test the system manually. | Demo organisation with seeded sample data, isolated, resettable, no billing, watermarked (U-07). |
| 3 | Grouping / search grouping for organisations an accountant manages, with easy search and edit. | Organisation directory for accountants: full-text search, filters, custom groups and tags, saved views, bulk edit and bulk actions (V-01…V-04). |
| 4 | No connection with other apps as in Xero; Numo9 will build those apps in future phases. | No third-party connector marketplace or bank-feed aggregator work. Open internal API + companion-app roadmap owned by Numo9 (W-01…W-03, §5.2 Phase 8). |
| 5 | Edit an invoice after posting; the edited version is 101-1 so the accountant knows it was edited (not void-only like Xero). | Invoice revision engine: revision suffix, reversal + re-post, revision history, PDF stamped with revision, AR and tax reports follow the current revision (D-03a, D-03b). |
| 6 | In Xero bank accounts are locked without reconciliation or JEs; fix this. | Bank accounts are first-class ledger accounts: usable immediately, spend/receive/transfer without a feed, balance from the ledger, reconciliation optional and never blocking (F-01, F-07). |
| 7 | Balance sheet and income statement for accounting purposes and for tax purposes; from the tax set extract the amount of tax. | Two-book engine: accounting book + tax book with tax-adjustment journals (Schedule 1-style reconciliation), tax-purpose BS/IS and a tax computation line (K-07, K-08, G-08). |
| 8 | Furniture in Canada is 20 % depreciation; straight-line and declining-balance methods; client provides templates and methods. | Fixed assets with CCA classes seeded (Class 8 furniture 20 % DB), SL and DB methods for book and tax, client-template importer for depreciation methods (I-01…I-04). |
| 9 | Option to claim the full CCA as a loss. | CCA claim per class per year is discretionary from 0 to the maximum available; a "claim maximum even if it creates/increases a loss" toggle; loss carried to the tax book (I-03). |
| 10 | Give the client the ability to pay taxes from the system itself. | Tax Payments module: GST/HST, payroll source deductions, corporate instalments, QST; payment via a CRA-accepted payment provider or bank-file route chosen at kickoff; posting and confirmation (G-09, P-06). |
| 11 | HST monthly, quarterly or yearly with the option to switch; out-of-cycle filing (switch the dates). | Filing-cycle engine: frequency per registration, effective-dated switches, out-of-cycle (custom-dated) periods, period regeneration without touching filed periods (G-03a). |
| 12 | Stop the HST if switched from monthly/quarterly/yearly. | Stop-filing action: closes the open period on an end date, blocks generation of new periods, keeps history and allows restart (G-03b). |
| 13 | 30-day free trial. | Trial organisation: full package for 30 days, reminders at 7/3/1 days, read-only grace, conversion without data loss (U-05). |
| 14 | First 1,000 get the full user apps; marketing strategy for later clients provided later. | Founding offer: atomic counter, entitlement "all products" for the first 1,000 paying organisations, visible on the website and in the app; marketing hooks (promo codes, referral attribution) left configurable (U-08). |
| 15 | The system is package-based; main products are Payroll, Inventory, Tax and Accounting. | Product catalogue with four products, packages composed of products, entitlement checks per feature, plan/feature matrix inside the app (U-02, U-03). |
| 16 | Items the old quotation listed as "available under a separate quotation" (French UI, native mobile apps, e-commerce connectors) belong to this project. | French UI = Phase 6 (X-01…X-03); native mobile apps = Phase 7 (Y-01…Y-04); e-commerce = Numo9's own app, Phase 8 roadmap (W-02). |

### 1.7 Compliance and domain constraints the design must respect

| Area | Constraint (as currently published for 2026) | Design response |
|---|---|---|
| Sales tax | GST 5 % (AB, BC, MB, NT, NU, QC, SK, YT); HST 13 % (ON), 14 % (NS), 15 % (NB, NL, PE); PST 7 % (BC, MB), 6 % (SK); QST 9.975 % (QC). | Table-driven by province, effective-dated, combined tax groups; zero-rated vs exempt vs out-of-scope; partial-ITC percentage per account (e.g., 50 % meals and entertainment); separate control accounts for GST/HST payable, ITC receivable, PST payable, QST payable/ITR. |
| GST/HST filing | Reporting periods monthly, quarterly or annual by threshold or election; election changes take effect at the start of a fiscal year unless CRA approves otherwise; filing/remittance due one month after period end (quarterly/monthly) or three months (annual, with instalments). | Filing-cycle engine with effective-dated frequency, out-of-cycle periods, stop/restart, due-date and instalment calendar; the accountant confirms CRA approval dates; the system never files on the client's behalf — it produces the return and, where configured, initiates the payment. |
| CPP (2026) | YMPE $74,600; basic exemption $3,500; 5.95 % employee / employer; max $4,230.45. CPP2 4.00 % between $74,600 and YAMPE $85,000, max $416.00. | Payroll constants keyed by tax year; CPP2 as a separate line. |
| EI (2026) | MIE $68,900; employee 1.63 % (max $1,123.07); employer 1.4×; Quebec employee 1.30 %. | Same constants table; Quebec flag switches EI rate and adds QPIP/QPP. |
| QPP / QPIP (2026) | QPP 6.3 % (max $4,479.30) + QPP2 4 %; QPIP employee 0.430 %, employer 0.602 % up to $103,000. | Province of employment drives plan selection. |
| Income tax | Federal + provincial per CRA T4127 (July 2026 edition). | T4127 Option 1 formula with TD1 claim codes; constants versioned by edition. |
| Remittances | Quarterly / regular / accelerated 1 and 2 by AMWA. | Remittance calendar and in-system payment (G-09). |
| Year-end | T4/T4 Summary and RL-1 due last day of February; e-filing mandatory above 5 slips. | T4 XML (CRA schema) and RL-1 export. |
| CCA | Classes and rates per Income Tax Regulations Schedule II (e.g., Class 8 furniture 20 % DB, Class 10 30 %, Class 10.1, Class 12 100 %, Class 13 leasehold SL, Class 14.1 5 %, Class 50 55 %, Class 53/54/55); half-year rule and Accelerated Investment Incentive where applicable; CCA is discretionary (any amount from nil to maximum). | Class table editable and effective-dated; SL and DB methods; per-class discretionary claim; client-supplied templates imported (I-01…I-04). |
| Two books | Accounting book under ASPE/IFRS presentation; tax book reconciles accounting net income to net income for tax via Schedule 1-type adjustments (CCA vs amortisation, non-deductible meals 50 %, reserves, etc.). | Tax-adjustment journal type posts only to the tax book; reports run in either book; tax computation line uses federal/provincial small-business and general rates as editable data (K-07, K-08, G-08). |
| Tax payments | CRA accepts payment via financial-institution online banking, pre-authorised debit set up in CRA My Business Account, CRA My Payment (Interac/Visa Debit), and CRA-accepted third-party service providers; Revenu Québec similar. There is no public CRA API for a software vendor to push payments directly. | Numo9 implements a `TaxPaymentProvider` interface; the production provider (a CRA-accepted third-party payment service or a bank bulk bill-payment file) is selected at kickoff and recorded in ADR-003; every payment is recorded, posted and reconciled whichever route is used (G-09, P-06). |
| Payments | Stripe Canada: cards 2.9 % + $0.30; PAD 1 % + $0.40 capped at $5; international +0.8 %. | Stripe for subscription billing and invoice pay links; fees are the client's. |
| Bank data | No aggregator contracts (client decision 4). | CSV/OFX/QFX/QBO import and manual entry; bank accounts never depend on a feed. |
| Records | CRA: six years. | Soft-delete only; archived organisations retained; backups retained. |
| Privacy | PIPEDA; SIN sensitive. | Field-level encryption, masking, never logged. |
| Language | Canada is bilingual; Quebec clients expect French documents. | i18n from day one; French UI and French documents in Phase 6. |
| Hosting | Canadian data residency preferred. | Canadian region (ADR-001 at kickoff). |

### 1.8 Assumptions and interpretation (documented, simplest reasonable)

1. **Numo9 is the product; Profitex is its owner and first practice.** The Profitex firm site (profitex.ca) is unchanged by this project; the Numo9 product website lives on a Numo9 domain supplied by the client.
2. "Accountants don't pay" means every practice-level account is free with no seat limit; only organisations carry a subscription.
3. "Packages" are bundles of the four products; the exact package names, product mixes and prices are data entered by the Platform Owner, not code.
4. "First one thousand get the full user apps" means the first 1,000 paying organisations receive the entitlement to all four products (and later companion apps) at their package price; the marketing strategy for organisation 1,001 onward is out of this plan's scope and will be supplied by the client.
5. "Edit the invoice … 101-1" means the revision suffix is appended to the original number; the original document remains viewable as a superseded revision; AR, tax and reports follow the latest revision; a filed-period invoice revision requires an unlocked period or a late-adjustment flag.
6. "Bank accounts are locked" refers to Xero's dependence on a bank feed / reconciliation to use the bank module; Numo9 treats a bank account as a normal ledger account with optional reconciliation.
7. The client supplies depreciation templates and methods (the SL/DB formulas, conventions and class list they want); Numo9 ships Schedule II classes as a starting point and the template importer makes the client's versions the default.
8. "Pay taxes from the system" is delivered through a provider interface (§1.7); if no provider is contracted at go-live, Numo9 still produces the payment instruction, deep-links to the CRA payment route and records the payment.
9. Native mobile apps are built with a cross-platform framework (React Native) sharing the web API; initial scope is the organisation-owner and employee experience (dashboard, invoices, bills, receipts capture, approvals, pay stubs, leave), not the full accountant workstation.
10. French UI covers all app screens, emails, PDFs (invoices, statements, pay stubs) and the website; tax terminology follows CRA/Revenu Québec French terms.
11. Migration: one-time import from Xero CSV exports for Profitex's own books plus one pilot client organisation; the same importer is then self-service for any organisation.
12. Practice management (engagements, document requests, deadline calendar, pay-per-service checkout) from v1.0 is retained as the **Practice** product set available free to every practice, because it is how accountants bring organisations in.

---

## 2. DECOMPOSE

### Level 1 — Objective

**Numo9:** a multi-practice, multi-organisation accounting, tax, payroll, inventory, HR and practice-management SaaS with package-based subscriptions, free accountant accounts, demo/trial organisations, two-book reporting, in-system tax payment, public website, French UI and native mobile apps.

### Level 2 — Components

| ID | Component | Purpose |
|---|---|---|
| A | Platform Core | Practice and organisation tenancy, users, roles, audit, settings, periods, per-module lock dates, files, notifications, jobs |
| U | SaaS, Packages & Billing | Products, packages, entitlements, subscription billing (Stripe), 30-day trial, demo organisations, founding-1,000 offer, in-app plan/feature matrix |
| V | Accountant Workspace | Organisation directory with search, grouping, tags, saved views, bulk edit; practice staff and client assignment; cross-organisation dashboards |
| B | Contacts | Customers, suppliers, explicit roles, stable-ID import, statements, credit control |
| C | General Ledger & Journals | CoA with sub-accounts and GIFI mapping, posting engine, journal types, approvals, negative-balance controls, period close, conversion balances |
| D | Sales | Quotes, invoices **with revisions**, recurring invoices, credit notes, payments, reminders (before/after due), pay links |
| E | Purchases | POs with receiving and 3-way match, bills with duplicate detection and inbound email capture, supplier credits, expense claims, batch payments |
| F | Banking | **Never-locked** bank/credit-card/cash accounts, manual and imported transactions, rules, optional reconciliation, transfers, cheques |
| G | Tax Engine & Tax Payments | Effective-dated codes, place of supply, zero-rated/exempt/partial ITC, **filing-cycle engine (switch, out-of-cycle, stop)**, GST/HST and QST returns, tax reports, corporate tax computation, **tax payments** |
| H | Inventory & Quantity Management | Items, UoM, categories, locations, movements, costing, reorder, batch/serial, valuation |
| I | Fixed Assets & CCA | Register, SL/DB book depreciation, CCA tax book by class, discretionary claim incl. full-CCA-as-loss, client templates, disposals |
| J | Projects & Time | Engagements, timesheets, billable time to invoice |
| K | Reporting (two books) | Report engine, accounting-book and tax-book statements, tax computation, exceptions engine, adjusted TB, management pack, adviser templates |
| L | Sheets (Working Papers) | Grid, GL-linked functions, templates, versions |
| M | Staff & HR | Employee master, leave, onboarding, documents, self-service |
| N | Payroll (Canada) | Pay runs, statutory calculations, stubs, EFT, remittances, T4/RL-1, ROE |
| O | Practice Management & Client Portal | Service catalog, engagements, document requests, deadline calendar, portal, task board |
| P | Online Payments | Stripe: subscription billing, invoice pay links, pay-per-service, PAD, refunds, **tax-payment provider adapter** |
| Q | Public Website (Numo9) | Product site: products, packages, pricing, trial/demo sign-up, founding offer, CMS, SEO |
| R | Multi-currency | Currencies, rates, FX gains/losses |
| S | Infrastructure & Security | Docker, CI/CD, environments, backups, monitoring, encryption, tenant-isolation sweeps |
| T | Migration, Training & Handover | Xero importer, UAT, training, docs, go-live, warranty |
| W | Open API & Companion-App Roadmap | Versioned public API, webhooks, app-registration for Numo9's own future apps (e-commerce first) |
| X | French Language | i18n infrastructure, French UI, French documents and emails, bilingual website |
| Y | Native Mobile Apps | React Native iOS/Android apps for organisation owners and employees |

### Level 3 — Atomic tasks and dependencies

Dependency rule: **A → U → (V, B, C) → (D, E, F, G) → (H, I, J, K, L, R) → (M → N) → (O, P) → Q → (X, Y, W) → T**, with S running from day one.

```
A Core ── U SaaS/Billing ──┬─ V Accountant Workspace ─────────────┐
                           ├─ B Contacts ─┬─ D Sales ────┬─ P Payments ─┬─ Q Website
                           │              ├─ E Purchases │              │
                           └─ C Ledger ───┼─ F Banking   ├─ K Reporting │
                                          ├─ G Tax ──────┤  (2 books)   ├─ X French
                                          ├─ H Inventory ┤              ├─ Y Mobile
                                          ├─ I Assets/CCA├─ O Practice ─┤
                                          ├─ J Projects ─┤              └─ W Open API / companion apps
                                          ├─ L Sheets    │
                                          ├─ R Multi-ccy │
                                          └─ M HR ── N Payroll
S Infrastructure (continuous)  →  T Migration / Training / Handover (last)
```

Atomic tasks are listed per component in §3 as task cards, sized to a focused one-to-two-hour session where possible.

---
## 3. PLAN — Task cards

Format for every task: **ID · Objective · Current → Expected · Depends on · Steps · Acceptance criteria · Test approach · Risks.** Tasks sharing current/expected behaviour and risks are grouped on one card with numbered steps; each numbered step is still implemented and verified on its own. Cards marked **[NEW]** did not exist in v1.0; cards marked **[GAP]** close a specific Xero teardown finding (traced in §4).

### Component A — Platform Core

**A-01 · Practice and Organisation tenancy** [NEW – replaces v1.0 A-01]
- Current: nothing exists. Expected: two tenant levels — `Practice` (accountant firm or sole accountant, always free) and `Organisation` (the paying business). A practice is linked to many organisations through `PracticeAssignment` (with assigned staff and role); an organisation can have zero practices (self-managed), one, or several (e.g., bookkeeper + tax accountant). Every business record belongs to exactly one organisation; all queries are organisation-scoped; practice-level queries fan out only over assigned organisations.
- Depends on: none.
- Steps: (1) `Practice`, `PracticeMember`, `Organisation`, `OrganisationMember`, `PracticeAssignment` models. (2) Tenant-scoping manager and middleware resolving the active organisation and the acting practice. (3) `OrgOwnedModel` base (organisation FK, created_by, timestamps, soft-delete). (4) DRF permission class denying cross-organisation access and denying practice access to unassigned organisations. (5) Lint rule: business models must inherit `OrgOwnedModel`.
- Acceptance: a practice member removed from an organisation receives 404 on every record of it within one request; a user in Org 1 requesting any Org 2 record by ID receives 404; the automated sweep over the router proves it for every endpoint.
- Test: unit tests for the manager; router sweep; property test over random membership graphs.
- Risks: unscoped `objects.all()` — lint + sweep.

**A-02 · Authentication, sessions and sign-up flows** — email + password, email verification, password reset, TOTP 2FA (mandatory for Platform Owner and Practice Admin when enabled), session list, invitations (practice → staff; practice → organisation owner; organisation → user; organisation → accountant), social sign-in optional. Acceptance: unverified users cannot log in; invitation links single-use; an organisation owner can invite an accountant by email and the accountant lands assigned to that organisation.

**A-03 · Roles and permissions (RBAC with approval limits)** [GAP] — platform roles (Platform Owner, Platform Support), practice roles (Practice Admin, Accountant, Reviewer, Payroll Specialist, Read-only Staff), organisation roles (Owner, Admin, Accountant-delegate, Sales, Purchasing, Payroll, HR, Employee); fine-grained flags; **custom roles**; **approval limits by amount per user** (JEs, bills, POs, pay runs); permission catalogue exported. Acceptance: parameterised test over (role × endpoint × method); a custom role with a $5,000 bill limit cannot approve a $5,001 bill; an undeclared-permission endpoint fails CI.

**A-04 · Audit log and history** [GAP] — append-only, field-level before/after diffs, IP/device, per record and global viewer with date presets, user and type filters, default range 90 days, export CSV/XLSX/PDF. Acceptance: editing an invoice amount shows old and new value; UPDATE on the audit table rejected at DB level; export matches on-screen rows.

**A-05 · Organisation settings, fiscal year and per-module lock dates** [GAP] — legal name, display name, Canadian address with **Province picker and Postal code**, BN and program accounts (RT GST/HST, RP payroll, RC corporate), QST number, fiscal year end, base currency CAD, time zone, numbering, default terms; **lock dates per module** (GL, AR, AP, Bank, Payroll, Tax) with "advisers only" and "everyone" levels; every statutory setting lives on one Tax Registrations page (no split across pages). Acceptance: posting dated before a module lock is refused with a message naming the lock; lock change audited; registration-status changes always carry a user attribution.

**A-06 · File storage and documents inbox** — upload, attach to any record, preview, virus-scan hook, S3-compatible storage, per-organisation inbound email address for documents and bills (E-05), tagging by period/tax year, Inbox/Archive, "create bill / expense / asset from file". Acceptance: file from Org 1 unreachable from Org 2; 25 MB limit; MIME validated; inbound email lands in the right organisation's inbox within 60 s.

**A-07 · Notifications, email and custom sending domain** [GAP] — in-app centre, branded templates per practice/organisation, EN/FR template variants (X-02), bounce tracking, per-organisation custom sending domain (SPF/DKIM/DMARC guidance and verification). Acceptance: email from a verified organisation domain passes DMARC in the test harness; bounced addresses flagged on the contact.

**A-08 · Background jobs and scheduling** — Celery + Redis; beat for recurring documents, reminders, FX, trial expiry, subscription renewals, filing/remittance reminders, depreciation runs, backups, usage metering; job dashboard; idempotency keys. Acceptance: failed job retried with backoff and visible; two workers cannot run the same schedule tick twice.

**A-09 · Global search and quick-create** [GAP] — search across contacts, invoices, bills, POs, quotes, bank transactions, **manual journals, accounts, fixed assets, employees, settings pages, reports and navigation**; keyboard-driven quick-create (invoice, bill, contact, quote, PO, journal, spend/receive/transfer money, upload). Acceptance: searching a journal narration returns the journal; searching "lock date" opens the settings page; every quick-create has a shortcut documented in the UI.

**A-10 · Single design system and localisation baseline** [GAP] — one component library (grids, forms, pickers, empty states, date/number formatting) used by every module; Canadian English spelling and terms throughout (organisation, cheque, GST/HST, vacation pay, Province, Postal code); one date format per locale; Letter page size with inch margins for documents; no promotional banners inside working screens. Acceptance: visual regression suite passes on every list/editor; a lint rule rejects hard-coded strings not in the i18n catalogue; the invoice, bill, PO and quote editors share one grid component.

### Component U — SaaS, Packages & Billing [NEW]

**U-01 · Product catalogue** — four main products (Accounting, Tax, Payroll, Inventory) plus free product sets (Practice, Portal) and future companion apps; each product maps to a set of feature keys.
- Acceptance: every feature-gated endpoint and screen declares the feature key it needs; the key → product mapping is exported as the in-app feature matrix.

**U-02 · Packages and pricing** — packages composed of products; monthly and annual prices in CAD; per-package limits (users, organisations are never limited for practices); effective-dated price changes; promo codes; founding-offer flag. Acceptance: a price change dated next month does not alter current subscriptions; a package can be retired without affecting subscribers.

**U-03 · Entitlement engine** — resolves (organisation → subscription → package → products → features) in one cached call; UI shows gated features with an explicit "included in package X" prompt instead of hiding or redirecting; API returns 402 with the required product. Acceptance: downgrading removes write access to the removed product immediately while keeping read access to historical data; gated screens never silently redirect.

**U-04 · Subscription billing (Stripe)** — organisation subscribes with card or PAD; proration on upgrade/downgrade; renewals; invoices and receipts issued by the platform organisation; dunning (retry 3, 5, 7 days; read-only after grace); cancellation with data export; accountants never carry a subscription object. Acceptance: webhook replay creates no duplicate; a failed renewal moves the organisation to grace then read-only exactly on schedule; a practice user never sees a billing screen for their own account.

**U-05 · 30-day free trial** — any new organisation starts a trial of a configurable package; reminders at 7/3/1 days and on expiry; conversion keeps all data; one trial per organisation BN/email; trial organisations excluded from the founding counter until paid. Acceptance: conversion on day 30 at 23:59 organisation-local time retains every record; a second trial with the same BN is refused.

**U-06 · Platform owner console** — all practices and organisations, subscription state, MRR/churn/trial funnel metrics, package editor, founding-offer counter, demo-data manager, impersonation with consent and audit, feature flags. Acceptance: impersonation sessions are time-boxed and listed in the organisation's audit log.

**U-07 · Demo organisation** — free, instant, seeded Canadian sample dataset (contacts, invoices incl. a revised invoice, bills, bank transactions, payroll employees, assets, two filed GST periods, both books), resettable, watermarked, excluded from analytics and emails, auto-purged after 30 days of inactivity; "convert demo to trial" wipes sample data. Acceptance: demo creation under 10 s; demo data never appears in platform metrics; reset restores the seed exactly.

**U-08 · Founding offer (first 1,000)** — atomic counter incremented on first successful payment; founding organisations entitled to all products regardless of package; badge in app and on the website ("x of 1,000 remaining"); counter and entitlements auditable; marketing hooks (promo codes, referral source on sign-up) stored for the later strategy. Acceptance: 1,500 concurrent first payments yield exactly 1,000 founding entitlements; an organisation that churns and returns keeps or loses founding status per a configurable rule.

### Component V — Accountant Workspace [NEW]

**V-01 · Organisation directory** — list of all organisations assigned to the practice with full-text search (name, BN, owner, tags, industry, province), filters (package, trial/paid/demo, fiscal year end, GST cycle, payroll yes/no, overdue items, unfiled returns), sortable columns, column chooser, saved views, keyboard navigation. Acceptance: 2,000 organisations search in under 300 ms (p95); saved view persists per user.

**V-02 · Groups and tags** — practice-defined groups (hierarchical: e.g., "Toronto office → Retail clients"), colour tags, an organisation in many groups; group by group in the directory; group-level staff assignment. Acceptance: assigning staff to a group grants access to every organisation in it and revoking removes it (A-01 sweep).

**V-03 · Bulk edit and bulk actions** — select many organisations → change group, tags, assigned staff, fiscal settings where safe, send message, export list; preview before apply; audit per organisation. Acceptance: bulk edit of 200 organisations completes in one job with per-row result and no partial silent failure.

**V-04 · Cross-organisation dashboards** — practice home: deadlines across organisations (GST/HST, payroll remittances, T2, T4), unreconciled bank lines, unfiled returns, trials expiring, items awaiting the accountant's approval; per-staff workload. Acceptance: every figure drills down to the organisation list that produced it.

**V-05 · Practice staff management** — invite accountants, roles (A-03), per-organisation or per-group assignment, dormant-user alert (no login 60 days), activity heatmap per user. Acceptance: dormant alert fires at 60 days; heatmap matches audit-log counts.

### Component B — Contacts

**B-01 · Contact model** [GAP] — explicit roles (customer, supplier, both, employee, government agency), billing/shipping addresses with Province, default sales/purchase accounts, default tax code derived from province, **payment-terms master list**, credit limit with "warn" or "block" mode and override approval, currency per contact, T4A/withholding flag, tax-exempt certificate upload, portal access flag, statement preferences, custom fields. Acceptance: Quebec contact defaults to GST+QST; duplicate name/email/tax-ID warning while typing; merge preserves history inside a transaction.

**B-02 · Contact activity and statements** — timeline; customer and supplier statements (outstanding/activity); supplier statement reconciliation against bills. Acceptance: statement total equals AR aging total for that contact on the same date.

**B-03 · Import/export** [GAP] — CSV and XLSX import with column mapping, **stable external ID matching** (never by name), **non-destructive updates** (blank columns leave fields untouched), dry-run validation report, unlimited additional people. Acceptance: re-importing the same file creates zero duplicates and changes zero fields; a renamed contact updates in place.

### Component C — General Ledger & Journal Entries

**C-01 · Chart of accounts** [GAP] — account types and sub-types; **parent/child sub-accounts**; codes unique per organisation; 4-digit system accounts that fit the user's scheme and can be renumbered; Canadian template shipped with **correct typing** (Inventory typed Inventory; intangibles under non-current assets), **separate control accounts** for GST/HST payable, ITC receivable, PST payable, QST payable, QST ITR, payroll liabilities by type; default purchase-tax code per expense account (home-province rate, not Exempt); **default GIFI mapping** shipped with the template; per-account "require contact / require tracking category / require attachment" flags; archive instead of delete. Acceptance: template loads with 0 unmapped GIFI accounts; a system account cannot be archived; renumbering updates every reference.

**C-02 · Journal entry posting engine** — unchanged in intent from v1.0: ≥2 lines, balanced to the cent, atomic post, append-only, `reverse()` linked to original, states Draft → Awaiting approval → Posted → Reversed; **book dimension** on every line (accounting / tax / both) for K-07. Acceptance: unbalanced rejected; 1,000 concurrent postings produce gap-free sequence; trial balance of each book sums to zero.

**C-03 · Journal types, contacts on lines and negative-balance controls** [GAP] — journal types (general, adjusting, closing, reclass, **tax-adjustment** (tax book only), payroll, depreciation); optional contact per line (feeds sub-ledgers); **warning on any journal that drives a cash/bank account negative** with reason required; **attachment and contact required** on expense journals (configurable per organisation); auto-reversing date. Acceptance: a journal crediting Petty Cash below zero is blocked for non-advisers and warned for advisers; an expense journal without attachment refused when the rule is on.

**C-04 · Manual, recurring and approval workflow** — manual JE UI with line autocomplete; recurring templates; threshold-based approval; approver ≠ creator. Acceptance: recurring JE created once per period; self-approval impossible.

**C-05 · Conversion balances** [GAP] — opening trial balance as at conversion date; AR/AP opening by document; suspense must be zero — **finalisation blocked while unbalanced** (no silent "historical adjustment"); lock balances option. Acceptance: conversion cannot be finalised while difference ≠ 0.00; the blocked state names the difference.

**C-06 · Period close and year-end** — close month/year per module; retained-earnings roll-over; reopen with reason. Acceptance: closed-period posting blocked; year-end roll correct on fixture.

**C-07 · Find and recode with undo** [GAP] — search transaction lines by conditions; recode account/tax/tracking/contact; preview; audit report; **undo of a recode batch** within the open period. Acceptance: recode of 500 lines produces one audit batch; undo restores every line.

### Component D — Sales

**D-01 · Sales document grid (shared)** [GAP] — one grid for quotes, invoices, recurring invoices and credit notes: item, description, qty, price, line discount, **document-level discount**, account (filtered to revenue/other-income types), tax code (filtered to sales codes, effective on the document date), tax amount, amount; tax exclusive/inclusive; column chooser; required due date with default terms. Acceptance: purchase tax codes and expense accounts are not offered on a sales line; an expired rate cannot be selected; totals match a reference sheet for 50 fixture documents.

**D-02 · Quotes** — create/send/accept/decline (portal or public link), optional lines and alternative options, deposit request, e-signature acceptance, convert to invoice, expiry with "Expired" status consistently in list and overview. Acceptance: accepted quote converts with identical lines; expired quote cannot be accepted.

**D-03a · Invoices and posting** — draft → approved → sent → partially paid → paid; branded PDF; numbering; attachments; copy; posting AR/revenue/tax. Acceptance: approving posts a balanced JE; PDF matches fixture.

**D-03b · Invoice revisions (editable posted invoices)** [NEW]
- Current (Xero): a posted invoice can only be voided and re-created. Expected: an approved or sent invoice can be **edited**; saving creates revision `101-1` (then `101-2` …); the prior revision is reversed in the ledger and the new revision posted in one transaction; the revision chain is visible on the invoice, in the audit log and on the PDF ("Revision 1 of invoice 101, supersedes version issued on …"); payments already allocated stay allocated and any over-allocation becomes customer credit; reminders, statements, AR aging and tax reports follow the current revision; a revision dated in a filed GST period requires the period to be unlocked or carries a late-adjustment flag that posts the tax difference into the next open period; "void" remains available as a separate action.
- Depends on: C-02, D-03a, G-03.
- Steps: (1) `InvoiceRevision` model (parent invoice, revision_no, snapshot of lines, reason, created_by). (2) Edit action builds the new revision from the current one. (3) Post: reverse previous JE, post new JE, link both to the revision. (4) Re-allocate payments; compute credit if overpaid. (5) PDF template stamp and revision history panel. (6) Reports read `current_revision`. (7) Portal shows the latest revision with a "revised" badge and a link to superseded versions.
- Acceptance: editing invoice 101 (CAD 1,130.00) to CAD 1,017.00 produces 101-1; AR for the contact changes by exactly −113.00; the GL has two linked JEs (reversal + repost); the tax report for the period reflects 1,017.00 only; 101 remains viewable and marked superseded; a 1,000-run property test over random edits never leaves AR ≠ sum of open current revisions.
- Test: unit tests on the revision state machine; property-based test on AR consistency; concurrency test (two users editing the same invoice → second gets a conflict, never a lost update); functional test through the UI and the portal.
- Risks: revision in a filed period — handled by G-03 late-adjustment rules; numbering collisions — suffix allocation inside the posting transaction.

**D-04 · Recurring invoices** — same grid as D-01; schedule; placeholders; proration flag; auto-send or draft. Acceptance: exactly one invoice per tick after worker restart.

**D-05 · Payments received and allocation** — against one or many invoices; overpayment to credit; prepayments; bank account selection. Acceptance: AR decreases by exactly the payment.

**D-06 · Credit notes** — full page, never a silent redirect; apply or refund. Acceptance: applying reduces balance and posts reversal of revenue/tax.

**D-07 · Reminders and statements** [GAP] — schedule with **before-due and after-due** steps, escalation (notify owner, block credit), per-contact opt-out, late-fee/interest line option, email and SMS/WhatsApp channel hooks (provider optional), statement runs. Acceptance: no reminder for paid or disputed invoices; before-due reminder sent on schedule.

**D-08 · Online invoice pay link** — see P-02.

**D-09 · Sales overview and lists** — one overview page pattern shared with purchases: status tiles incl. Overdue, credit-notes tab, saved filters, column chooser, bulk send statements, "show deleted/voided", revision badge. Acceptance: overview counts equal list counts for every tile.

### Component E — Purchases

**E-01 · Purchase orders with receiving and 3-way match** [GAP] — create/send; **goods received (partial) with GRN**, statuses Draft / Awaiting approval / Approved / Partially received / Received / Billed; convert to bill with match of PO qty vs received vs billed; PO approval limits per user (A-03); commitment report against budget. Acceptance: receiving 6 of 10 leaves 4 outstanding and increases stock by 6; a bill for 12 against a 10-unit PO is flagged.

**E-02 · Bills** [GAP] — same grid component as sales (discount and tax-amount columns included); draft → awaiting approval → awaiting payment → paid; **supplier invoice number uniqueness check at entry**; duplicate-bill review (amount/date/supplier similarity); approval routing by amount and department; holdback field; attachments; posting AP/expense or asset/ITC. Acceptance: duplicate supplier invoice number blocked; approval threshold respected.

**E-03 · Recurring bills and supplier credits** — same pattern as D-04/D-06.

**E-04 · Expense claims** — receipt photo, category, tax, mileage (CRA per-km rate configurable), approval, reimbursement bill. Acceptance: submitter cannot approve own claim.

**E-05 · Receipt and bill capture (inbound email + extraction)** — per-organisation forwarding address (A-06); extraction (pluggable provider or on-server OCR) proposing supplier, date, total, tax **with per-field confidence shown before creation**; every suggestion requires confirmation. Acceptance: ≥ 80 % field accuracy on fixtures; confidence displayed per field.

**E-06 · Batch payments and cheques** [GAP] — batch bills → EFT file (CPA 005) or cheque print; cheque register with void/stale-dated tracking; positive-pay export; consistent "cheque" spelling. Acceptance: batch total equals bills; file validates against CPA 005 layout; a voided cheque reverses its payment.

**E-07 · Early-payment discount capture** — terms like 2/10 net 30 on bills and invoices; discount taken posts to a discount account. Acceptance: paying inside the window posts the discount automatically.

### Component F — Banking

**F-01 · Never-locked bank, credit-card and cash accounts** [NEW/GAP]
- Current (Xero): the bank module depends on a feed/plan and offers only "Credit card / Other" types; no bank account existed yet the ledger ran. Expected: bank accounts are ledger accounts of types **Chequing, Savings, Credit card, Line of credit, Loan, Cash/Petty cash, Clearing**; created in seconds with no feed; usable immediately for spend money, receive money, transfers, payments and payroll; balance is the ledger balance; a "statement balance" is optional; reconciliation (F-05) is optional and never blocks any other action; no plan gate.
- Acceptance: a new organisation records a spend-money transaction from a new chequing account with no import and no reconciliation and sees it on the Balance Sheet; deleting an account with transactions is refused; an organisation with no bank account at all gets a persistent set-up prompt (not a hard block).

**F-02 · Statement import (CSV/OFX/QFX/QBO/XLSX)** — saved mappings for major Canadian banks (RBC, TD, Scotiabank, BMO, CIBC, Desjardins, National Bank, Tangerine, credit unions), duplicate detection, preview. Acceptance: same file twice adds zero lines.

**F-03 · (removed)** — bank-feed aggregator adapter dropped by client decision 4; replaced by an internal `BankStatementSource` interface used by import and, later, by Numo9's own banking companion app (W-02).

**F-04 · Bank rules** [GAP] — conditions incl. contains / does not contain / regex / amount range; fixed + percentage allocations; **priority ordering**; test-against-history preview; auto-apply option. Acceptance: rule order respected; preview shows affected historical lines.

**F-05 · Optional reconciliation** — match statement lines to transactions; split; find & match; reconciliation report; unreconcile with audit; works on any subset of accounts; an account can be marked "not reconciled" without affecting posting. Acceptance: reconciled balance equals statement balance; a line matched once only.

**F-06 · Transfers** — between accounts; auto-match both sides. Acceptance: nets to zero in the GL.

**F-07 · Negative-balance and cash controls** [GAP] — warn/block (configurable) when a transaction drives cash or bank negative; Balance Sheet presents overdrawn bank as a current liability (K-02); exceptions engine rule (K-09). Acceptance: the teardown scenario (Petty Cash −994.17) is caught at entry and listed by the exceptions engine.

### Component G — Tax Engine & Tax Payments

**G-01 · Tax codes and rates** [GAP] — effective-dated table seeded with GST, HST 13/14/15, PST BC 7 / MB 7 / SK 6, QST 9.975; tax groups; **zero-rated, exempt, out-of-scope as distinct types**; recoverable vs non-recoverable per component; **partial ITC/ITR percentage** per account or code (e.g., 50 % meals and entertainment); sales and purchase codes are separate lists; expired rates hidden after their end date and never selectable on a later document. Acceptance: every provincial combination computes to the cent on 2026 fixtures; MB RST 8 % pre-2019 cannot be selected on a 2026 document; 50 % ITC posts half the tax to expense.

**G-02 · Place-of-supply defaulting** — tax code from contact province and organisation registrations; override per line; warning when selling into a province without PST registration; zero-rated default for exports. Acceptance: Ontario customer → HST 13 %; US customer → zero-rated.

**G-03 · GST/HST return worksheet** — lines 101, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112, 113 A/B/C, 114/115; quick-method flag; mark filed; period locking; late adjustments to next open period; available on every package that includes Tax. Acceptance: line 105 equals tax collected per tax report; filed period refuses back-dated documents without the late-adjustment flag.

**G-03a · Filing-cycle engine (switch and out-of-cycle periods)** [NEW]
- Expected: each registration (GST/HST, QST) has a filing frequency (monthly / quarterly / annual) with an **effective-from date**; changing frequency generates future periods from that date without touching filed periods; **out-of-cycle periods**: the accountant may define a custom period (start/end) — e.g., switching from annual to quarterly mid-year creates a short stub period — and the system renumbers subsequent periods; annual filers get instalment dates; due dates and payment dates computed per frequency; history of cycle changes kept with CRA approval reference and date.
- Acceptance: switching quarterly → monthly effective 1 July produces Jul, Aug, Sep … periods and leaves Q1/Q2 filed periods intact; an out-of-cycle period 1 Jan–15 Mar followed by regular quarters from 16 Mar is accepted and every document falls into exactly one period; no overlapping or missing days across the year (property test).

**G-03b · Stop and restart filing** [NEW] — "Stop filing" closes the open period at an end date (deregistration or suspension), blocks further period generation and tax-code defaults flip to out-of-scope for sales after that date (configurable); "Restart" resumes from a given date with a chosen frequency; both audited with reason. Acceptance: after stop on 30 June no July period exists; a document dated 15 July with a GST code raises a warning; restart on 1 January recreates periods.

**G-04 · QST return worksheet** — FPZ-500 equivalent, same cycle engine. Acceptance: parallel to G-03.

**G-05 · Tax reports** — tax by code, by document, audit report, ITC/ITR detail, tax-to-GL tie-out; available on every package with Tax. Acceptance: totals tie to the GL control accounts.

**G-06 · Tax settings on one page** [GAP] — registrations, numbers, frequencies, accounting basis for tax, defaults — single page with history. Acceptance: no tax setting exists on more than one page.

**G-07 · GIFI and T2 export** [GAP] — default GIFI mapping from the CoA template; mapping editor; GIFI export (schedule 100/125/141 data) for T2 preparation software. Acceptance: export balances to the tax-book trial balance.

**G-08 · Corporate tax computation (tax book)** [NEW] — from the tax-book Income Statement: net income for tax, Schedule 1-type adjustments list, CCA (I-03), non-capital loss application, federal rate (small-business deduction limit and general rate) and provincial rate as effective-dated data, computed current tax, instalment schedule; posts a tax provision JE to the accounting book on confirmation. Acceptance: fixture corporation with known T2 result computes to the dollar; rates are data, never code.

**G-09 · Tax Payments** [NEW]
- Expected: a Tax Payments screen lists every amount owing by registration and period (GST/HST net tax, QST, payroll source deductions by remittance due date, corporate instalments and balance due, provincial payroll taxes where configured); the user chooses the payment route configured for the organisation: (a) **provider route** — a CRA-accepted third-party payment service or bank bulk bill-payment file via the `TaxPaymentProvider` interface (P-06), with account, amount, period and program account pre-filled; (b) **assisted route** — a pre-filled remittance voucher plus a deep link to CRA My Payment / Revenu Québec and a "record payment" step. Every payment: idempotency key, status (initiated → submitted → confirmed → failed), confirmation number, posting (Dr liability / Cr bank or clearing), reminder before due date, receipt in the organisation's documents.
- Acceptance: a GST period net tax of 1,234.56 paid through the test provider posts exactly that to GST/HST payable and the chosen bank account, marks the period paid and stores the confirmation; a second click on "pay" for the same period is refused; the assisted route records the same posting; the payroll remittance calendar shows "paid" after confirmation.
- Test: provider sandbox integration tests; idempotency tests; functional test per registration type.
- Risks: provider availability and fees are the client's (ADR-003); regulatory route changes — provider behind an interface.

### Component H — Inventory & Quantity Management

**H-01 · Items catalog** [GAP] — tracked/untracked items and services; SKU and barcode separate from code; **categories/groups**; multiple price lists and customer-specific pricing; accounts; tax codes; images; supplier links; inventory account auto-created on first tracked item. Acceptance: SKU unique; service items never affect stock; price list applies on a document for a contact assigned to it.

**H-02 · Units of measure** — base/purchase/sales units and conversions. Acceptance: 2 boxes of 12 add 24.

**H-03 · Locations and stock on hand** — multiple locations; stock card; negative stock blocked unless back-ordering enabled. Acceptance: on-hand equals sum of movements.

**H-04 · Stock movements** — receipts (PO/GRN/bill), issues, adjustments, transfers; every movement posts. Acceptance: GL inventory equals valuation report.

**H-05 · Costing** — moving average default; FIFO option; landed cost. Acceptance: fixtures with known answers.

**H-06 · Batch/serial and expiry** [GAP] — optional per item; traceability on movements. Acceptance: a serial can exist in one location only.

**H-07 · Reorder and stock reports** — reorder points, suggested POs, valuation, movement, aging, stock-take. Acceptance: alert when on-hand < reorder point.

**H-08 · Simple assemblies (BOM)** — build item from components posting component issues and finished-goods receipt. Acceptance: build of 10 units consumes components per BOM and increases finished stock by 10.

### Component I — Fixed Assets & CCA

**I-01 · Asset register with book and tax settings** [GAP] — purchase from bill or manual; cost, in-service date, location, serial; **book method: straight-line or declining-balance** with rate/useful life, residual, convention (full-month, half-month); **tax: CCA class** from a seeded Schedule II table (Class 8 furniture 20 % DB, 10 30 %, 10.1, 12 100 %, 13 SL over lease, 14.1 5 %, 43, 50 55 %, 53, 54/55 …), half-year rule, AII/immediate-expensing flags, editable and effective-dated; module usable immediately (no mandatory "start date" wall — the conversion date is used by default). Acceptance: asset from a bill links back; a Class 8 asset of 10,000 bought mid-year shows CCA 1,000 (half-year) in year 1 and 1,800 in year 2 on fixtures; module opens on a fresh organisation without setup.

**I-02 · Book depreciation runs (SL and DB)** — monthly/annual runs posting depreciation JEs to the accounting book; schedule preview; continuity report (cost, additions, disposals, accumulated). Acceptance: JE totals match schedule; SL and DB fixtures match the client-supplied templates to the cent.

**I-03 · CCA claim with discretionary amount and full-CCA-as-loss** [NEW] — per class per tax year: UCC opening, additions, dispositions, half-year adjustment, maximum CCA, **claim amount from 0 to maximum chosen by the accountant**, with a one-click "claim maximum even if it creates or increases a non-capital loss" option; recapture and terminal loss; the claim posts to the tax book only (C-03 tax-adjustment journal) and flows into G-08 and the loss carry-forward table. Acceptance: on a fixture with net income 500 and max CCA 1,800, choosing full claim yields net income for tax −1,300 and a carry-forward of 1,300; choosing 500 yields 0 and a UCC carry-forward higher by 1,300; the accounting book is unchanged by either choice.

**I-04 · Client depreciation templates importer** [NEW] — the client supplies templates (methods, rates, conventions, class list) as XLSX/CSV; importer validates and loads them as the organisation's or the practice's default method set; templates versioned by tax year. Acceptance: importing the client's furniture template sets Class 8 DB 20 % as default for new furniture assets; schedule output equals the template's worked example.

**I-05 · Disposals** — sale/scrap with gain/loss JE (book) and proceeds vs UCC (tax). Acceptance: fixtures correct in both books.

### Component J — Projects & Time

**J-01 · Projects/engagements**, **J-02 · Timesheets**, **J-03 · Time and expense to invoice** — as v1.0. Acceptance unchanged (project P&L; approved billable time invoiced once only; billed entries excluded from the next pull).

### Component K — Reporting (two books)

**K-01 · Report engine** — date ranges and presets, comparison periods, cash vs accrual, **book selector (accounting / tax)**, tracking categories, drill-down, layout editor with notes, Draft/Published/Custom versions, export PDF/XLSX/CSV/Google Sheets format; statement header always prints the organisation display name and legal name (validated at settings). Acceptance: 12-month report on a 100k-line GL renders under 3 s (p95); a numeric-only legal name is rejected at settings.

**K-02 · Core financial statements (accounting book)** [GAP] — P&L, Balance Sheet (always prints Assets, Liabilities, Equity sections; **overdrawn bank/cash reclassified to current liabilities** for presentation; contra accounts beside their assets), Cash Flow **indirect and direct**, Trial Balance **sorted by code** with opening/movement/closing columns, GL detail, Journal report (with order direction), Movements in Equity, Account transactions. Acceptance: BS balances; P&L net income equals change in retained earnings; every figure drills down.

**K-03 · Receivables/payables reports** — AR/AP aging summary/detail; **AR/AP control account vs sub-ledger reconciliation report**. Acceptance: aging total equals control balance; reconciliation report shows zero difference on fixtures and names the offending journal when not.

**K-04 · Budgets** — budget vs actual with variance. Acceptance: variance = actual − budget.

**K-05 · Dashboard** — bank balances widget by default, cash in/out, invoices owed, bills to pay, upcoming tax and payroll deadlines, P&L snapshot, account watchlist, widgets per role, no advertising. Acceptance: dashboard figures equal report totals; empty charts show 0, never "—k".

**K-06 · Management pack and adviser templates** — one-click pack; Canadian engagement report templates (Notice to Reader/Compilation under CSRS 4200, Review, NTR variants) as editable layouts under Numo9's own wording. Acceptance: pack under 10 s; templates editable per practice.

**K-07 · Two-book engine** [NEW]
- Expected: every journal line carries `book ∈ {accounting, tax, both}`; ordinary postings are `both`; tax-adjustment journals (C-03) are `tax` only; book-only adjustments (e.g., accounting-only accruals the accountant excludes from tax) are `accounting` only; the report engine filters by book; a **Book Reconciliation** report lists every difference between the books by account with the adjustment that caused it.
- Acceptance: accounting net income − tax adjustments = tax-book net income on every fixture; the reconciliation report nets to zero against the two P&Ls.

**K-08 · Tax-purpose Balance Sheet and Income Statement with tax amount** [NEW] — the tax book's IS and BS with: amortisation replaced by CCA, non-deductible items removed (50 % meals, fines, etc.), reserves and other adjustments; a **"Income tax" line computed by G-08** shown on the tax IS and a current-tax liability on the tax BS; side-by-side view (accounting vs tax) with the adjustments column between them; export to PDF/XLSX. Acceptance: on the T2 fixture the tax IS shows net income for tax and the computed tax equal to the known answer; the side-by-side columns reconcile per line.

**K-09 · Exceptions engine (assurance)** [GAP] — rules: negative cash/bank balances, journals to cash/bank accounts, expense journals without contact or attachment, Tax Exempt on normally taxable accounts, backdated journals/invoices/bills (> N days between document date and posting), round-amount journals, weekend postings, same creator and approver, duplicate payments, unmapped GIFI accounts, missing BN, missing lock date, dormant users; per-rule severity; user-activity heatmap; contact bank-detail change list. Acceptance: the teardown organisation's issues (negative petty cash, journal-only expenses, all-exempt tax, no BN, no lock date, 0 GIFI) are all flagged by the engine on the migrated fixture.

**K-10 · Adjusted trial balance** [GAP] — TB with proposed-adjustment columns and adjusted balances; adjustments post from the working paper to the chosen book. Acceptance: adjusted TB equals TB + adjustments per line.

### Component L — Sheets (Working Papers)

**L-01 · Grid editor**, **L-02 · GL-linked functions** (with a `book` argument: `=GL("1000","2026-01-01","2026-12-31","tax")`), **L-03 · Templates and versioning** (adds CCA continuity and book-reconciliation templates), **L-04 · Import/export** — as v1.0 with the book dimension. Acceptance unchanged plus: a lead schedule in the tax book equals the tax-book TB.

### Component M — Staff & HR

**M-01 · Employee master** (SIN/bank encrypted and masked), **M-02 · Departments, positions and org chart**, **M-03 · Leave management** (provincial accrual rules), **M-04 · Onboarding/offboarding** (TD1 federal/provincial, direct deposit, acknowledgements), **M-05 · HR documents and letters** (EN/FR templates), **M-06 · Self-service** — as v1.0. Acceptance unchanged.

### Component N — Payroll (Canada)

**N-01 · Constants by tax year**, **N-02 · Pay schedules and runs**, **N-03 · Earnings/deductions/benefits**, **N-04 · Statutory calculations** (40-scenario CRA fixture), **N-05 · Stubs and register**, **N-06 · EFT file**, **N-07 · Remittances** (now **payable from the system** through G-09), **N-08 · Year-end T4/RL-1**, **N-09 · ROE data**, **N-10 · Payroll by the practice inside client organisations** — as v1.0. Added acceptance: a remittance paid via G-09 is marked paid on the PD7A-style summary and posted.

### Component O — Practice Management & Client Portal (free "Practice" product set)

**O-01 · Service catalog**, **O-02 · Engagements**, **O-03 · Document requests**, **O-04 · Deadline calendar** (now driven by each organisation's filing-cycle engine and remittance type), **O-05 · Client portal** (adds: subscription and package view, tax payments view, invoice revision badges), **O-06 · Staff task board** — as v1.0. Acceptance unchanged plus: a cycle switch in G-03a updates the calendar within one job cycle.

### Component P — Online Payments

**P-01 · Stripe connection** — platform account for subscriptions (U-04) and Stripe Connect or per-organisation keys for the organisation's own invoice payments; test/live; PAD enabled. Acceptance: test-mode checkout end to end on both.

**P-02 · Invoice payment**, **P-03 · Pay-per-service checkout**, **P-04 · PAD mandates and recurring billing**, **P-05 · Refunds and disputes** — as v1.0 (P-02 follows the current invoice revision; paying a superseded revision's link redirects to the current one).

**P-06 · Tax-payment provider adapter** [NEW] — `TaxPaymentProvider` interface (`quote()`, `initiate()`, `status()`, `cancel()`), sandbox/stub provider for tests, production provider per ADR-003, bank bulk-bill-payment file generator as the fallback implementation. Acceptance: swapping providers changes no screen in G-09; stub provider drives the full state machine in CI.

### Component Q — Public Website (Numo9 product site)

**Q-01 · Site design and content** — original Numo9 brand (yellow/black identity supplied by the client); pages: Home, Products (Accounting, Tax, Payroll, Inventory), Packages & Pricing (live from U-02), Founding offer counter (U-08), For Accountants (free account), Demo, Start free trial, Resources/Blog, About, Contact, Legal; sign-up funnels for accountant and organisation; EN/FR (X-03). Acceptance: Lighthouse ≥ 90; WCAG 2.1 AA; trial sign-up to first screen under 2 minutes.

**Q-02 · Lead capture and demo requests**, **Q-03 · CMS**, **Q-04 · SEO, analytics, domain, mail DNS** — as v1.0 on the Numo9 domain.

### Component R — Multi-currency

**R-01 · Currencies and rates**, **R-02 · Foreign documents and FX** — as v1.0; currency per contact (B-01); always-show-currency-code document option.

### Component S — Infrastructure & Security

**S-01 · Repository, CI/CD, environments** (adds `mobile/` workspace and i18n extraction job), **S-02 · Hosting and data residency** (ADR-001), **S-03 · Security baseline**, **S-04 · Monitoring and logging**, **S-05 · Backups and retention**, **S-06 · Multi-tenant scale** [NEW] — connection pooling, per-organisation partitioning of posting tables, read replicas for reporting, rate limits per organisation, usage metering for billing. Acceptance: 500 organisations × 100k lines reporting p95 < 3 s on staging data; restore drill within 1 hour.

### Component T — Migration, Training & Handover

**T-01 · Xero importer** (self-service for any organisation; maps Xero tax codes to effective-dated Numo9 codes; retypes mis-typed accounts with a review list; imports fixed assets into I-01 with CCA class suggestions), **T-02 · UAT**, **T-03 · Training** (adds accountant-workspace and SaaS-admin sessions), **T-04 · Documentation** (adds ADR-002 invoice revisions, ADR-003 tax-payment route, ADR-004 two-book model), **T-05 · Go-live and warranty** — as v1.0. Acceptance: TB difference 0.00 for Profitex and the pilot client; exceptions engine report produced on import.

### Component W — Open API & Companion-App Roadmap [NEW]

**W-01 · Versioned public API and webhooks** — OpenAPI 3 spec, API keys and OAuth clients per organisation, scopes mapped to feature keys, webhooks (invoice.posted, invoice.revised, payment.received, stock.moved, payrun.posted …), rate limits, full-ledger JSON/CSV export. Acceptance: contract tests from the spec; a webhook replay is idempotent.

**W-02 · Companion-app registry (Numo9-owned apps only)** — app registration, install per organisation, entitlement as a product; first planned apps: **Numo9 Commerce** (e-commerce storefront posting sales and stock to the ledger), Numo9 Bank (statement sourcing through `BankStatementSource`), Numo9 Receipts (mobile capture — delivered within Y). Acceptance: installing an app grants exactly its scopes; uninstalling revokes them; no third-party marketplace surface exists.

**W-03 · Phase 8 discovery for Numo9 Commerce** — requirements, data model (products from H, orders → invoices D, stock H, payments P), estimate and plan delivered as a change-controlled annex to this plan. Acceptance: annex approved by the client before build.

### Component X — French Language [NEW]

**X-01 · i18n infrastructure** — message catalogues (backend and frontend), locale per user and per organisation, French number/date/currency formats (1 234,56 $), pluralisation, extraction in CI, missing-key report. Acceptance: 0 missing keys for `fr-CA` at release; layouts hold with 30 % longer strings.

**X-02 · French UI, emails and documents** — all app screens, notifications, PDF templates (invoice, revision stamp, credit note, statement, quote, PO, pay stub, T4 cover, remittance summary, tax reports) with CRA/Revenu Québec French terminology; per-contact document language. Acceptance: a Quebec contact with language FR receives a French invoice from an English-UI user; glossary reviewed by the client.

**X-03 · Bilingual website and portal** — Q-01 pages in FR with hreflang; portal language per user. Acceptance: Lighthouse SEO ≥ 90 on both locales.

### Component Y — Native Mobile Apps [NEW]

**Y-01 · Mobile foundation** — React Native (iOS/Android) sharing the API and auth (biometric unlock, secure token storage), push notifications, offline queue for captures. Acceptance: login, org switch and dashboard on both platforms; tenant-isolation sweep executed through the mobile client.

**Y-02 · Organisation-owner app** — dashboard, invoices (create, send, revise, pay link), bills approval, bank transactions (spend/receive), receipt capture to E-05, tax payments status, subscription status, notifications. Acceptance: an invoice created on mobile and revised on web shows the revision on mobile within one sync.

**Y-03 · Employee app** — pay stubs, T4s, leave requests, expense claims with camera, timesheets. Acceptance: employee sees only their own records.

**Y-04 · Store release and maintenance** — Apple App Store and Google Play listings under the client's developer accounts, crash reporting, release pipeline, EN/FR store copy. Acceptance: both apps approved and published; crash-free sessions ≥ 99 % in hypercare.

---
## 4. Xero gap closure matrix

Every gap recorded in the Xero teardown (26 October 2026) and the Numo9 task that closes it. "Teardown ref" is the section of the teardown file.

| # | Teardown ref | Xero gap | Numo9 closing task(s) | Observable closing behaviour |
|---|---|---|---|---|
| 1 | §0 | Two UI generations; inconsistent grids, dates, empty states, breadcrumbs | A-10, D-01, E-02 | One component library; invoice/bill/PO/quote share one grid; one date format per locale |
| 2 | §0 | Root URL 404 instead of redirect | S-01, A-10 | Every root and legacy-style URL redirects to Home or the right module |
| 3 | §0 | Module "Settings" links all go to one generic page | A-05, G-06 | Settings deep-link per module; tax settings on one page |
| 4 | §1 | No bank-balance widget by default; "—k" on empty charts; advertising widget | K-05 | Bank balances widget default; zero rendered as 0; no ads |
| 5 | §2.1 | "Online payments" card failed to load; "Expired" status inconsistent | D-09, D-02 | Error states retried and reported; one status model across overview, lists and tabs |
| 6 | §2.2 | Approval paywalled; no Overdue / Credit-notes tab; no saved filters | U-03, D-09 | Approval never gated; Overdue and Credit notes tabs; saved views and column chooser |
| 7 | §2.3 | Sales tax picker shows purchase codes; account picker unfiltered | D-01, G-01 | Pickers filtered by document side and account type |
| 8 | §2.3 | Expired rates selectable; no effective-date validation | G-01 | Effective-dated codes; expired rates hidden on later dates |
| 9 | §2.3 | No place-of-supply logic | G-02 | Default tax code from contact province and registrations |
| 10 | §2.3 | Line discount only; no document discount; no early-payment terms | D-01, E-07 | Document-level discount; 2/10 net 30 terms |
| 11 | §2.3 | No multi-currency on plan | R-01, U-03 | Multi-currency included in Accounting product |
| 12 | §2.3 | Due date empty, not required; banners push form down | D-01, A-10 | Required due date from terms; no banners in editors |
| 13 | §2.4 | Repeating-invoice editor legacy/disabled; no proration, subscription object | D-04, U-04 | Same grid; proration flag; subscription object for recurring billing |
| 14 | §2.5 | Credit note silently redirects | D-06, U-03 | Full credit-note page; gating is explicit, never a redirect |
| 15 | §2.6 | Import CSV only, no mapping, no dry-run | B-03, T-01 | CSV/XLSX, column mapping, dry-run report |
| 16 | §2.7 | Reminders overdue-only; no escalation, SMS, late fees | D-07 | Before/after-due steps, escalation, late-fee option, SMS/WhatsApp hook |
| 17 | §2.9 | Quote: inconsistent date format, no tax column, no optional lines/deposit/e-sign | D-01, D-02 | Shared grid with tax; optional lines; deposit; e-signature |
| 18 | §2.10 | Inventory blocked by CoA typing; no UoM, categories, SKU/barcode, price lists, costing, locations, reorder, lot/serial, BOM | C-01, H-01…H-08 | All present; inventory account auto-created |
| 19 | §3.1 | Customer/Supplier lists identical; role inferred | B-01 | Explicit roles; titled lists |
| 20 | §3.2 | No contact currency, terms master, withholding flag, exemption certificate, duplicate warning, credit "warn vs block" | B-01, R-01 | All fields present with warning on duplicates |
| 21 | §3.3 | Import matches on name; blank columns delete; 5-people cap | B-03 | Stable external ID; non-destructive; unlimited people |
| 22 | §4.1 | Purchases overview legacy vs Sales overview modern | A-10, D-09 | One overview pattern |
| 23 | §4.2 | No supplier-statement reconciliation; no early-payment discount; no routing by amount/department | B-02, E-07, E-02 | Supplier statement reconciliation; discount capture; routing rules |
| 24 | §4.3 | Bill grid lacks discount/tax-amount/column chooser; no invoice-number uniqueness at entry; no holdback; no 3-way match | E-01, E-02 | Shared grid; uniqueness check; holdback; PO–GRN–bill match |
| 25 | §4.5 | No partial receipt / GRN; POs non-posting, no commitment report; no PO approval limits | E-01, A-03 | Receiving statuses; commitment report; limits per user |
| 26 | §4.6–4.7 | Checks/Cheques spelling; no positive pay, register void/stale tracking | E-06, A-10 | Consistent "cheque"; positive-pay export; register |
| 27 | §5.1 | Bank module plan-locked; only Credit card/Other types; org runs with no bank | F-01, F-07 | Never-locked accounts with full type list; set-up prompt |
| 28 | §5.3 | Rule conditions lack regex/not-contains/ranges; no priority; no auto-reconcile; no test preview | F-04 | All present |
| 29 | §5.4 | System accounts un-renumberable; no sub-accounts; mis-typed template; single Sales Tax control; mixed code lengths | C-01 | Sub-accounts; renumbering; correct typing; separate control accounts; consistent codes |
| 30 | §5.5 | 0/139 GIFI mapped; period confusion between pages | C-01, G-07 | Default GIFI mapping; one balance basis |
| 31 | §5.6 | "Value added tax", "annual leave" labels | A-10 | Canadian terms everywhere |
| 32 | §5.7 | Documents page slow; no period tagging; no OCR confidence | A-06, E-05 | Tagging by period/tax year; per-field confidence |
| 33 | §5.8–5.9 | Journals bypass AP/receipts/ITC; no contact on lines; no negative-cash warning; no approval; no journal type | C-03, C-04, F-07 | Contact per line; attachment/contact rules; negative-balance control; approval; journal types |
| 34 | §5.10 | Fixed assets unusable until start date; hard 404 URL; no real CCA tax book; register not linked to CoA | I-01…I-05 | Usable immediately; SL/DB; CCA classes; register ties to GL |
| 35 | §5.11 | Recode has no undo; lock interaction unclear | C-07 | Undo of batch; lock respected and explained |
| 36 | §5.12 | Assurance ignores journals; no SoD, round-number, weekend, duplicate-payment checks | K-09 | Exceptions engine with all rules |
| 37 | §5.13 | History default 7 days; no diffs; no CSV | A-04 | 90-day default; field diffs; CSV/XLSX/PDF |
| 38 | §6 | Spelling flips (Organization/organisation) | A-10 | Single spelling standard enforced by lint |
| 39 | §6.1 | "State/ZIP" for Canada; no province picker; BN split across pages | A-05 | Province/Postal code; BN on one registrations page |
| 40 | §6.2 | Coarse roles; no custom roles or approval limits; dormant subscriber | A-03, V-05 | Custom roles; limits; dormant alerts |
| 41 | §6.3 | Advisor can't see plan; generic upgrade banners | U-03, U-06 | In-app plan/feature matrix; explicit gating |
| 42 | §6.5 | No custom sending domain; no per-contact language | A-07, X-02 | Custom domain; FR/EN per contact |
| 43 | §6.6–6.7 | Three template systems; US Letter with cm margins; NZ sample customer; no RTL/bilingual; no custom fields | A-10, D-03a, X-02, B-01 | One template system; Letter with inches; Canadian sample; FR; custom fields |
| 44 | §6.8 | No lock dates; no BN; silent "GST Type removed"; tax defaults "based on last"; config split over 4 pages; two lock levels only; "16:33PM" | A-05, G-06, C-01 | Per-module locks; attribution on every change; account-based tax defaults; one tax page; correct time format |
| 45 | §6.9 | All accounts default Exempt; no zero-rated vs exempt; no effective dates; no partial ITC; manual code choice | C-01, G-01, G-02 | Province-rate defaults; distinct types; effective dates; partial ITC; auto selection |
| 46 | §6.10 | No tracking hierarchy or mandatory tracking | C-01, K-01 | Hierarchy; per-account required tracking |
| 47 | §6.11 | Unbalanced conversion pushed to adjustment silently; Adviser/Advisor spelling | C-05, A-10 | Finalisation blocked while unbalanced |
| 48 | §6.12 | No generic ledger export / open API | W-01 | Full-ledger CSV/JSON; public API |
| 49 | §6.14 | Report basis and tax basis on different pages can disagree | G-06, K-01 | One basis setting with explicit override per report |
| 50 | §6.16 | Closed Xero-to-Xero network | W-01 | Open API/webhooks; e-invoicing via Numo9's own apps (roadmap) |
| 51 | §7 | Projects, Expenses, document capture are paid add-ons | U-01, J, E-04, E-05 | Included in the Accounting product |
| 52 | §8.1 | Search misses journals, accounts, settings, reports | A-09 | Global search covers all |
| 53 | §8.2 | AI flags symptoms, not fixes | K-09 | Exceptions engine proposes the correcting entry as a draft journal |
| 54 | §9.1 | No sales-tax report; no indirect cash flow; no AR/AP control reconciliation; two report engines | G-03, G-05, K-02, K-03, K-01 | All present in one engine |
| 55 | §9.2 | Statement header prints a number; empty sections print "–"; future period end unlabeled | K-01, A-05 | Name validation; "no activity" hint; "year-to-date" label |
| 56 | §9.3 | Negative cash as negative asset; no Liabilities section; contra naming | K-02 | GAAP presentation |
| 57 | §9.4 | TB unsorted; YTD only; no adjusted TB | K-02, K-10 | Sorted; opening/movement/closing; adjusted TB |
| 58 | §9.5 | Journal order direction missing | K-02 | Sort direction control |
| 59 | §9.6 | GL Exceptions flags nothing | K-09 | Rule set catches the teardown scenario |
| 60 | §9.7 | Closing bank balance ignores petty cash; accessibility label leak | K-05, A-10 | Cash definition configurable; a11y suite |
| 61 | §10.B | Clear plan/feature matrix; one UI; localisation; Arabic/MENA noted as future | U-03, A-10, X-01 | Matrix in-app; i18n ready for a later Arabic locale (not in this scope) |

---

## 5. BUILD — Delivery plan

### 5.1 Technology stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3.12, Django 5, DRF, Celery, Redis | GMA core stack; transactional ORM for ledger integrity |
| Database | PostgreSQL 16 (numeric(18,2), organisation-scoped tables, partitioned posting and audit tables, read replica for reporting) | Correctness, PITR, multi-tenant scale |
| Frontend | Next.js 15 (App Router), TypeScript, React Query, Tailwind, one design-system package, virtualised grid for Sheets | One UI generation across every module |
| Mobile | React Native (Expo), TypeScript, shared API client and i18n catalogues | iOS + Android from one codebase |
| i18n | ICU message format; `en-CA`, `fr-CA` catalogues; CI extraction and missing-key gate | French in this project; Arabic-ready later |
| Website | Next.js ISR pages + headless CMS in Django admin, prices read live from U-02 | One deployment, one design system |
| Billing & payments | Stripe Canada (Billing, Checkout, Payment Intents, ACSS Debit, Connect, Webhooks) | Subscriptions + organisation invoice payments |
| Tax payments | `TaxPaymentProvider` adapter; provider per ADR-003; CPA 005 / bank bill-payment file fallback | Route can change without UI change |
| PDFs | WeasyPrint / headless Chromium templates (EN/FR) | Branded documents incl. revision stamps |
| Files | S3-compatible object storage (Canadian region) | Signed URLs, lifecycle rules |
| Infra | Docker Compose, Caddy, GitHub Actions, Canadian-region cloud | Matches GMA's operational pattern |
| Observability | Sentry-compatible error tracking, Prometheus/Grafana or hosted equivalent, mobile crash reporting | Alerting per S-04 |

### 5.2 Phases and sprint order

Phases 0–5 keep the sequence agreed in quotation GMA-PFX-2026-001; Phases 6–8 are the items the client moved into this project (French UI, native mobile apps, Numo9's own companion apps). Each phase is a release point usable on its own. Durations for Phases 6–8 are proposed here and are priced in the revised Numo9 quotation.

| Phase | Components / tasks | Exit demonstration |
|---|---|---|
| **0 — Foundation & SaaS core** | S-01…S-03, S-06 baseline, A-01…A-10, U-01…U-08, V-01…V-05, B-01…B-03, C-01, C-02 | Accountant signs up free, opens a demo org, creates a trial org, groups and searches organisations; packages and founding counter live; balanced JE posting under concurrency |
| **1 — Walking skeleton (core books)** | C-03…C-07, D-01…D-07, D-09, E-01…E-04, E-06, E-07, F-01, F-02, F-04…F-07, G-01…G-03, G-03a, G-03b, G-05, G-06, K-01…K-03, K-05, K-09 | A paying org runs real books: invoice → revise to 101-1 → pay → spend money from a never-locked bank account → switch GST cycle, file an out-of-cycle period → P&L/BS with the exceptions engine clean |
| **2 — Operations & two books** | H-01…H-08, I-01…I-05, J-01…J-03, L-01…L-04, R-01, R-02, K-04, K-06, K-07, K-08, K-10, G-04, G-07, G-08, E-05 | Stock-controlled sales with COGS; SL/DB depreciation; CCA full-claim-as-loss; accounting vs tax statements side by side with computed tax; working papers tying to both books |
| **3 — People** | M-01…M-06, N-01…N-10 | Pay run across provinces matching the CRA calculator; stubs; EFT; T4 XML validates |
| **4 — Practice, payments, tax payments, website** | O-01…O-06, P-01…P-06, G-09, D-08, Q-01…Q-04, W-01 | Org subscribes and pays; invoice paid online; GST and payroll remittance paid from the system via the sandbox provider; Numo9 site live on staging with trial/demo funnels |
| **5 — Migration, UAT, go-live** | T-01…T-05, S-04, S-05 | TB reconciles to Xero for Profitex and the pilot client; parallel payroll/GST period; production cut-over |
| **6 — French** | X-01…X-03 | Full FR app, documents, emails and site; Quebec contact receives French invoice |
| **7 — Native mobile apps** | Y-01…Y-04 | Owner and employee apps in both stores; invoice revised on web appears on mobile |
| **8 — Companion apps (roadmap)** | W-02, W-03; Numo9 Commerce build under its approved annex | Companion-app registry live; Commerce annex approved and scheduled |
| **Hypercare + warranty** | T-05 | Two weeks hypercare after Phase 5 and after Phase 7; 12-month warranty per quotation |

Phase ordering note: the founding-1,000 counter (U-08) and the trial (U-05) are live from Phase 0 so marketing can start before the full product set is released; founding organisations receive every product as each phase ships.

### 5.3 Build rules applied inside every sprint

1. Each task card is worked UNDERSTAND → PLAN → BUILD → TEST → IMPROVE on its own branch.
2. Smallest working piece first (model → service → endpoint → UI → mobile where applicable), executed and verified before the next.
3. Mocks allowed for unavailable dependencies (Stripe test mode, stub tax-payment provider, fixture OCR) and replaced by the real integration before the task is declared complete.
4. No unrelated changes in a branch; reuse the JE engine, tax engine, entitlement engine, notification service and design system instead of duplicating.
5. Every new screen is built from the design system and ships with EN and FR keys from day one (FR translations filled in Phase 6).
6. Every feature-gated endpoint declares its feature key; every business endpoint passes the tenant-isolation sweep.
7. "Make it work, then make it right, then make it fast."

### 5.4 Git branch policy

- Base branch `main` (protected); release tags `vX.Y.Z`; mobile releases tagged `mobile-vX.Y.Z`.
- Branch per task card: `feature/D-03b-invoice-revisions`, `feature/G-03a-filing-cycles`, `fix/F-07-negative-balance`, `improvement/K-01-report-speed`.
- Before starting: `git status`, pull base, restate objective and acceptance criteria in the PR description.
- Before declaring complete: acceptance criteria observed, CI green (incl. isolation sweep, i18n missing-key gate, compliance fixtures), no unrelated changes, no debug code, no secrets, docs updated, second-engineer review.
- No merge to `main`, production deploy or store submission without the project lead's authorisation.

### 5.5 Team and roles (GMA)

| Role | Responsibility |
|---|---|
| Project lead (Obadah Abu Odeh) | Scope, architecture, ADRs, client communication, acceptance |
| Backend engineer(s) | Ledger, two-book engine, tax and filing cycles, payroll, inventory, billing, tax payments |
| Frontend engineer(s) | Design system, app UI, accountant workspace, Sheets grid, portal, website |
| Mobile engineer | React Native apps, store releases |
| QA engineer | Fixture sets (incl. revision, CCA, two-book, cycle-switch fixtures), automated suites, UAT |
| DevOps | Infrastructure, CI/CD, backups, monitoring, multi-tenant scale |
| Localisation reviewer (client-side, French) | Glossary and translation sign-off |

### 5.6 Client responsibilities

Numo9 brand assets (logo supplied, yellow/black identity) and domain; package names, product mixes and prices; founding-offer wording; demo sample-data sign-off; depreciation templates and methods (SL/DB, class list, conventions); choice of tax-payment route/provider and the related account (ADR-003); Stripe Canada account; Xero exports and CRA/Revenu Québec numbers for Profitex and the pilot client; anonymised past payroll runs; French glossary review; Apple and Google developer accounts; UAT testers and feedback within five business days per review cycle; the marketing strategy for organisations beyond the first 1,000 (later, outside this plan).

---

## 6. TEST — Strategy

### 6.1 Categories

| Category | Scope in this project | Tooling | Target |
|---|---|---|---|
| Unit | JE validation, revision state machine, entitlement resolution, tax calculation incl. partial ITC, filing-cycle generation, CCA (SL/DB, half-year, discretionary claim), two-book reconciliation, payroll formulas, costing, formula engine, date/period logic | pytest, Hypothesis, Vitest, Jest (mobile) | ≥ 85 % on `ledger`, `revisions`, `tax`, `cca`, `payroll`, `inventory`, `billing` packages |
| Integration | Endpoint ↔ DB ↔ JE engine; Stripe webhooks; tax-payment provider sandbox; import pipelines; email; object storage; inbound email | pytest + DRF client, Stripe CLI, provider stub, MinIO | Every endpoint has one happy-path and one failure test |
| Functional (E2E) | Role workflows: accountant onboarding and org grouping; trial → paid; demo reset; invoice-to-cash incl. revision; bill-to-pay with 3-way match; spend money with no feed; cycle switch and out-of-cycle filing; stop/restart filing; tax payment; CCA full-claim; two-book statements; pay run; service purchase; mobile owner and employee flows | Playwright, Detox (mobile) | One scripted scenario per §3 component |
| Regression | Full suite on every PR; nightly on `main` with the large fixture practice (500 organisations) | GitHub Actions | Zero known regressions at release |
| Data validation | Migration TB = 0.00; report tie-outs (aging = control; BS balances; tax report = GL tax accounts; accounting NI − adjustments = tax NI; AR = sum of open current revisions) | Automated reconciliation scripts | Before every release and after migration |
| Security | Tenant-isolation sweep (web and mobile clients), practice-assignment revocation, RBAC matrix incl. approval limits, entitlement leak tests, OWASP ZAP, dependency audit, secrets scan, SIN/bank masking, webhook signatures, impersonation audit | Custom sweeps, ZAP, pip-audit/npm audit, gitleaks | No high findings |
| Performance | Report p95 < 3 s on 100k-line GL; directory search < 300 ms over 2,000 orgs; dashboard < 1.5 s; grid 200×50; 50 concurrent users per org, 500 orgs nightly | k6, Lighthouse | Targets met on staging-sized data |
| Compliance fixtures | 40 payroll scenarios vs CRA calculator; provincial tax matrix; GST return lines incl. out-of-cycle periods; CCA class fixtures incl. client templates; T2 fixture for G-08; CPA 005 and T4 XML schema validation | `tests/fixtures/compliance` | 100 % pass; updated at each constants release |
| Localisation | Missing-key gate; pseudo-localisation layout test; FR document snapshot tests | CI extraction, Playwright | 0 missing keys; no clipped layouts |
| Gap closure | One automated or scripted check per row of §4 | Playwright + pytest, tagged `gap-NN` | Every row observed before Phase 5 exit |

### 6.2 Failure handling (applies to every task)

1. Stop progressing to dependent tasks. 2. Identify the exact failing condition. 3. Determine whether it is code, data, configuration or a wrong assumption. 4. Apply one focused correction. 5. Re-run affected tests, then the regression suite. 6. Continue only when acceptance criteria are met.

A failing test is never hidden, skipped to make the build pass, or reported as passed without execution. If a required test cannot run (provider sandbox down), the report states what prevented verification.

### 6.3 Structured debugging

Reproduce → expected vs actual → inspect logs/data → most likely cause → test the hypothesis → one change → verify → regression. The 30-minute principle applies.

---

## 7. IMPROVE — After verification

Once a task is verified correct, it is reviewed for correctness against all requirements, readability, maintainability, measurable performance, reliability of failure handling, security, and consistency with the architecture. Improvements are made only where meaningful, followed by re-running the relevant tests.

Project-level checkpoints:

- End of each phase: module boundaries, query performance on the growing fixture practice, UI consistency against the design system, accessibility, i18n key hygiene, entitlement matrix review.
- Post go-live (hypercare after Phase 5 and after Phase 7): defect trends, slow queries, user feedback, trial-conversion funnel, improvement backlog.
- Warranty (12 months): defect fixes and minor adjustments; quarterly review of payroll constants, tax rates, CCA class table and the GST/HST threshold rules (the July T4127 edition and January year changes are planned events); store compliance updates for the mobile apps.

Items outside this plan's scope: third-party app marketplace and bank-feed aggregator contracts (replaced by Numo9's own companion apps, W-02); electronic filing to CRA/Revenu Québec/ROE Web on the client's behalf (the system produces filing-ready data and initiates payments only); Arabic/MENA localisation (architecture ready); the marketing strategy for organisations after the first 1,000; the build of Numo9 Commerce beyond its discovery annex (W-03).

---

## 8. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Scope breadth vs schedule (SaaS + French + mobile added) | High | High | Phased releases; founding offer live from Phase 0; strict change control |
| 2 | Invoice revisions leaving AR/tax inconsistent | Medium | High | Reversal + repost in one transaction; AR property test; filed-period rules |
| 3 | Entitlement leak between packages or after churn | Medium | High | Single entitlement engine; leak tests per feature key; 402 contract |
| 4 | Founding counter over-allocation | Low | Medium | Atomic DB counter; concurrency test at 1,500 |
| 5 | Two books drifting | Medium | High | Book dimension on every line; reconciliation report as a release gate |
| 6 | CCA/tax computation errors | Medium | High | Client templates as fixtures; T2 fixture; rates as data; accountant confirmation step |
| 7 | GST cycle switch producing overlapping/missing periods | Medium | High | Property test over random switch sequences; filed periods immutable |
| 8 | Tax-payment route unavailable or provider changes terms | Medium | Medium | Adapter interface; assisted route always available; ADR-003 at kickoff |
| 9 | Payroll calculation errors | Medium | High | Versioned constants; 40-scenario fixtures; parallel run |
| 10 | Tenant/practice data leak | Low | Critical | Scoped managers; assignment-revocation sweep; mobile sweep |
| 11 | Payment double-processing (subscriptions, invoices, taxes) | Medium | High | Idempotency keys everywhere; Stripe balance reconciliation |
| 12 | Migration mismatch with Xero | Medium | High | Dry-run; TB tie-out 0.00; exceptions report on import |
| 13 | French translation gaps or layout breaks | Medium | Medium | Keys from day one; pseudo-localisation; client glossary review |
| 14 | App-store rejection or delays | Medium | Medium | Early TestFlight/internal track; store guidelines checklist |
| 15 | Email deliverability | Medium | Medium | Transactional provider; custom domains with DMARC verification |
| 16 | Client feedback delays | Medium | Medium | Five-business-day review windows in the quotation |
| 17 | Performance at 500+ organisations | Medium | Medium | Partitioning, read replica, nightly scale run |

---

## 9. Reporting template (per task and per sprint)

**Before implementation** — 1. Problem understanding. 2. Task breakdown. 3. Implementation plan with acceptance criteria and test strategy.

**After implementation** — 1. Changes made. 2. Testing results (executed, passed, failed, not executed and why). 3. Remaining issues. 4. Final status — Complete / Partially complete / Blocked.

Sprint reports are delivered to Profitex every two weeks with a staging demo link and, from Phase 7, TestFlight/internal-track builds.

---

## 10. Deliverables and acceptance

| Deliverable | Acceptance evidence |
|---|---|
| Source code (private repository; transferred to Profitex at final payment) incl. `backend/`, `frontend/`, `mobile/`, `infra/`, `docs/` | Repository access; CI green on release tags |
| Production deployment on the Numo9 domain (app, portal, website, API) | HTTPS live; monitoring active |
| Components A–Y per §3 | Each component's acceptance criteria observed in the UAT sign-off sheet |
| Gap closure | §4 checklist with evidence per row |
| Packages, pricing, trial, demo and founding offer configured | Platform console screenshots; test purchases |
| Migrated data (Profitex + one pilot client) | TB tie-out report = 0.00; exceptions report |
| Compliance fixtures and results (payroll, tax, CCA, T2, cycle switches) | Reports attached to the release |
| French UI, documents and site | Missing-key report = 0; client glossary sign-off |
| Native mobile apps | Published store listings; crash-free ≥ 99 % in hypercare |
| Documentation (admin guide, platform-owner guide, accountant guide, runbook, API docs, ADR-001…004, data dictionary) | In `docs/` and as PDF |
| Training (recorded sessions, quick guides) | Attendance and recordings |
| Numo9 Commerce discovery annex | Approved annex document |
| 12-month warranty | Warranty terms in the quotation |

---

## 11. Change control

Any request outside §2/§3 is logged as a change request with description, affected components, effort, schedule and price impact, approved in writing by both parties before work starts. Small clarifications within an existing task card's intent are not changes. The companion-app builds after W-03 are handled as annexes under this clause.

---

## 12. Mandatory execution checklist (tracked per task in the repository)

**UNDERSTAND** — investigated existing implementation · identified user and outcome · defined inputs/outputs · identified business rules · considered edge cases · restated objective.
**PLAN** — decomposed into atomic tasks · identified dependencies · ordered logically · defined acceptance criteria · defined testing procedures.
**BUILD** — implemented smallest functional piece · followed existing architecture · avoided unnecessary changes · preserved existing functionality · declared feature key and i18n keys.
**TEST** — verified behaviour · tested edge cases · investigated and resolved failures · checked regressions · ran tenant-isolation sweep · recorded unverified conditions.
**IMPROVE** — reviewed code quality · removed temporary artifacts · improved readability where needed · confirmed behaviour remains correct.
**COMPLETE** — reviewed final diff · updated documentation · reported changes and results · confirmed acceptance criteria · reported final status.

---

*Reference figures in §1.7 reflect published 2026 Canadian rates and rules at the time of writing and are implemented as editable, effective-dated data in Numo9, not as fixed code. Numo9 screens, naming and documents are original work; the Xero teardown was used as a functional specification only.*

— Gray Matter AI · Amman, Jordan · graymatterai2003@gmail.com · +962 79 770 7154

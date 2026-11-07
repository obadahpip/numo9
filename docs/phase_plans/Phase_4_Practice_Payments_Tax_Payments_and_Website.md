# NUMO9 — PHASE 4 IMPLEMENTATION PLAN
## Practice Management, Online Payments, Tax Payments, Open API & Public Website (Week 7)

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | 4 — Practice, Payments, Tax Payments & Website |
| **Weeks** | Week 7 of 13 (from kickoff) |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment), Amman, Jordan |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada (product owner of Numo9) |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §1.6 (decisions 1, 4, 10, 14), §1.7 (tax payments, payments), §3 Components O, P, G-09, D-08, Q, W-01; §4 gap matrix rows 5, 6, 11, 13, 41, 42, 48, 50, 51, 61; §5.2 Phase 4 · Project_Phases.md Phase 4 · Quotation GMA-PFX-2026-003 §4–§7 · Agreement GMA-PFX-2026-003-A §06, §07, 9.1 · xero_teardown.md §1, §2.1, §2.3, §6.3, §6.4, §6.12, §6.16, §7 · AI Coding Agent — Mandatory Engineering Workflow (Rules 1–11) |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE, applied to the phase, to every deliverable (one Git branch each) and separately to every atomic task |
| **Deliverables** | 21 — O-01…O-06, P-01…P-06, G-09, D-08, Q-01…Q-04, W-01 |
| **Exit demonstration** | Organisation subscribes and pays; an invoice is paid online; a GST/HST net tax and a payroll remittance are paid from the system through the sandbox provider; the Numo9 website is live on staging with trial/demo funnels |

---

## 0. How to use this file

1. Every deliverable in §6 is worked on its own branch `feature/<ID>-<short-name>` cut from `main`.
2. Inside a branch, every atomic task (`<ID>-Tnn`) is executed as its own mini-cycle: **UNDERSTAND** (re-read the card, inspect the code that already exists from Phases 0–3) → **PLAN** (confirm steps and acceptance) → **BUILD** (smallest working piece) → **TEST** (run the stated test immediately) → **IMPROVE** (only after it passes).
3. Tasks are ordered; a task never starts before every task in its *Depends* column passes its acceptance check.
4. Mocks are allowed (Stripe test mode, `StubTaxPaymentProvider`, fixture CMS content) but every mock is replaced by the real integration before the deliverable is declared complete; tests that passed against mocks are not reported as proof of the real integration.
5. A deliverable is complete only when every atomic task's acceptance is observed, the deliverable acceptance criteria are observed on staging and the §11 checklist is ticked. The phase is complete only when the §7.4 exit demonstration is observed on staging (Agreement §07).
6. Nothing is merged to `main`, deployed to production or pointed at live Stripe/provider keys without the project lead's written authorisation.

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase

Phase 4 starts on a codebase that already contains (Phases 0–3, verified at Phase 3 exit):

| Area | Already built (to reuse, never duplicate) |
|---|---|
| Tenancy & security | `Practice`, `PracticeMember`, `Organisation`, `OrganisationMember`, `PracticeAssignment`; `OrgOwnedModel`; tenant-scoped managers/middleware; cross-org permission class; router isolation sweep (A-01); auth, 2FA, invitations (A-02); RBAC with custom roles and amount limits, permission catalogue (A-03); append-only audit log (A-04); settings + per-module lock dates (A-05) |
| Platform services | File storage + documents inbox (A-06); notification centre, branded email templates EN/FR keys, custom sending domain (A-07); Celery/beat with idempotency keys and job dashboard (A-08); global search (A-09); design system `@numo9/ui` with grids, forms, empty states, Letter/inch PDF base (A-10) |
| SaaS core | Product catalogue with feature keys (U-01), packages and effective-dated prices (U-02), entitlement engine + 402 contract (U-03), **Stripe subscription billing** — platform Stripe account, card/PAD, proration, dunning (U-04), trial (U-05), platform console (U-06), demo org (U-07), founding counter (U-08) |
| Accountant workspace | Directory, groups/tags, bulk actions, cross-org dashboards, staff management (V-01…V-05) |
| Books | Contacts (B), CoA + posting engine with book dimension (C), sales incl. invoices, **invoice revisions 101-1** (D-03b), payments & allocation (D-05), credit notes (D-06), reminders (D-07); purchases (E); never-locked banking incl. Clearing account type (F-01), import, rules, reconciliation (F); tax engine incl. **filing-cycle engine G-03a**, stop/restart G-03b, GST/HST return G-03, QST return G-04, tax reports G-05, tax settings G-06, GIFI/T2 G-07, **corporate tax computation & instalments G-08** |
| Operations | Inventory H, analytics H-09…H-13, finance FN-01…FN-05 (loans), assets/CCA I, projects J, Sheets L, multi-currency R, two-book reporting K |
| People | HR M-01…M-06; payroll N-01…N-13 incl. **remittance calendar N-07** (built with a "paid" state awaiting G-09 confirmation) and T4/T4A/T5 |
| Infra | Monorepo, CI/CD, staging on HTTPS in Canadian region, security baseline, scale baseline (S-01, S-02, S-03, S-06) |

What does **not** exist yet: practice service catalogue, engagements, document-request checklists, deadline calendar, client portal, staff task board, Stripe Connect for organisations' own invoice payments, public invoice pay page, pay-per-service checkout, PAD mandates for organisation customers, refund/dispute handling, the `TaxPaymentProvider` interface and any tax-payment screen, the public website, the CMS, the public versioned API/OAuth/webhooks.

### 1.2 Problem definition — the seven questions for Phase 4

**1. Who uses this functionality?**

| Actor | Phase 4 use |
|---|---|
| Practice Admin / Accountant | Defines services and prices (O-01), runs engagements (O-02), sends document requests (O-03), works from the deadline calendar (O-04) and task board (O-06), prepares tax payments for client approval (G-09) |
| Organisation Owner | Uses the client portal (O-05): approves work, signs, uploads requested documents, buys services (P-03), pays taxes (G-09), sees subscription, loans, invoice revisions |
| Organisation User (Accountant-delegate, Payroll) | Initiates tax and remittance payments within approval limits (A-03) |
| Organisation's customer (external payer) | Opens an invoice pay link, pays by card/PAD (P-02, D-08), receives receipt |
| Platform Owner (Profitex) | Configures platform Stripe, Connect onboarding, tax-payment provider (ADR-003), CMS pages, API rate limits; watches payment and webhook health |
| Public visitor | Browses the Numo9 website, compares packages, signs up as accountant or organisation, requests demo/trial (Q) |
| Developer / Numo9 companion app | Uses OAuth/API keys, versioned endpoints, webhooks (W-01) |
| System | Webhook processing (Stripe, provider), payment status polling, reminders before tax due dates, payout reconciliation, calendar regeneration, CMS publishing, sitemap rebuild |

**2. Desired outcome.** Accountants run their practice inside Numo9 and bring organisations in; organisations collect customer payments online and pay CRA/Revenu Québec obligations from the system with every payment posted and reconciled; the public can discover, price and start Numo9 without a sales call; Numo9's own future apps and integrations use one open, versioned API.

**3. Inputs.** Service definitions and prices; engagement data; checklist templates; filing-cycle periods (G-03a), remittance schedules (N-07), corporate instalments (G-08), T2/T4 deadlines; Stripe account IDs, Connect onboarding results, payment intents, webhook events; PAD mandate confirmations; tax liabilities by registration/period; provider responses (quote, status, confirmation); CMS content and media; lead/demo form submissions; OAuth client registrations, API requests, webhook subscriptions.

**4. Outputs.** Engagement pipeline and audit trail; document requests and uploads in the org's documents inbox; deadline calendar (with iCal feed); portal views; staff tasks; pay pages and receipts; posted payment JEs (Dr Stripe Clearing / Cr AR; Dr bank / Dr fees / Cr clearing on payout); refund/dispute postings; tax-payment records with confirmation number, posted JE (Dr GST/HST payable or source-deductions payable / Cr bank or clearing), receipts filed in documents, remittance calendar "paid"; website pages, sitemap, structured data; leads; OpenAPI 3 spec, API responses, webhook deliveries with signatures; full-ledger export.

**5. Business rules.**
- Accountants never pay; pay-per-service charges are the **organisation's** purchase of a **practice** service (O-01/P-03) and are billed by the practice, not by Numo9.
- Every payment flow (subscription, invoice, service, tax) is idempotent: one idempotency key per business intent; a webhook replay never posts twice.
- Card data never touches Numo9 servers (Stripe Elements/Checkout only; PCI SAQ-A scope); PAD mandates stored at Stripe only.
- Pay links always resolve to the **current invoice revision**; a superseded revision link redirects (HTTP 302 with explanatory banner) to the current revision; the amount charged is the current balance due.
- Tax payments: one active payment per (registration, period, obligation); "pay" refused while one is initiated/submitted/confirmed; amounts never exceed the liability unless the user explicitly records an overpayment/instalment; posting uses the liability account mapped for the registration (C-01 control accounts); approval limits apply (A-03); the system never files returns on the client's behalf.
- The assisted route is always available, even when a provider is configured.
- Portal users see only their own organisation (A-01 sweep); practice staff see only assigned orgs.
- Calendar is derived data: regenerated from G-03a/N-07/G-08 within one job cycle of any change; never edited by hand except "custom deadline" entries.
- Public API scopes map 1:1 to feature keys (U-01); an org without the product gets 402 from the API exactly as from the UI.
- Website prices are read live from U-02; the founding counter from U-08; nothing is hard-coded.
- Feature gating is explicit — never a silent redirect (gap #14, #41).

**6. What could go wrong.** Double charge on webhook replay or double click; payment posted against a superseded revision; Connect account not onboarded → payment fails silently; payout fees not reconciled → clearing account drifts; tax payment initiated twice or for the wrong period/program account (RT vs RP); provider returns "pending" forever; provider route down on due date; user pays via CRA directly and records it twice; calendar shows stale deadlines after a cycle switch; portal leaks another org's documents; document request upload lands in the wrong org; e-signature without audit evidence; website shows a stale price or wrong founding count (cached); SEO-blocking misconfig (noindex on prod, missing hreflang); spam leads; OAuth token leakage; API scope mismatch letting a key write data beyond its product; webhook endpoint of a subscriber slow/failing → retries storm; time zones on due dates (org-local 23:59); French string growth breaking the pricing table.

**7. Smallest useful implementation.** One practice service bought by one organisation through Stripe test checkout; one invoice paid through a pay link with JE posted; one GST period paid through the stub provider and through the assisted route with identical postings; a portal page showing the org's invoices, tax payments and subscription; a calendar fed by one org's filing cycle; a staging website with Home, Pricing (live) and trial sign-up; one versioned read endpoint with an API key and one signed webhook. Everything else in §6 extends these walking-skeleton slices.

### 1.3 Restated objective

- **Currently:** Numo9 can keep books, compute tax and payroll, and bill its own subscriptions, but organisations cannot be paid online by their customers, cannot pay CRA/RQ from the system, accountants have no practice tooling or client portal, there is no public site to acquire customers and no open API.
- **Change:** Build the free Practice product set (O-01…O-06) and client portal, Stripe Connect payments for organisations (P-01…P-05, D-08), the `TaxPaymentProvider` adapter (P-06) and the Tax Payments module (G-09), the public Numo9 website with CMS and SEO (Q-01…Q-04) and the versioned public API with webhooks (W-01).
- **Why:** Decision 10 (pay taxes from the system), decision 1 (accountants bring organisations in — the practice tooling is the acquisition engine), decision 4 (no third-party marketplace — an open API for Numo9's own apps instead), decision 14 (founding offer must be visible publicly), and the revenue model (organisations subscribe from the website).
- **Done means:** all 21 deliverables meet their acceptance criteria on staging; the §7.4 exit demonstration is observed; gap rows 5, 6, 11, 13, 41, 42, 48, 50, 51, 61 have passing `gap-NN` tests for their Phase-4 parts; Lighthouse ≥ 90 and WCAG 2.1 AA on the website; OpenAPI contract tests green; no high security findings.

### 1.4 Assumptions & interpretations

1. **Stripe topology:** the platform Stripe account (from U-04) is reused; organisations' own customer payments use **Stripe Connect (Express accounts)** with direct charges so funds and fees belong to the organisation. Per-organisation API keys (Standard accounts connected via OAuth) are supported as an alternative configuration, behind the same `OrgPaymentGateway` service.
2. **Pay-per-service (P-03):** the practice is the seller; the practice gets its own Connect account (practices are free on Numo9 but can still receive money from their clients). Numo9 takes no application fee unless the Platform Owner sets one (default 0).
3. **Tax-payment provider:** until ADR-003 is decided at kickoff, the `StubTaxPaymentProvider` (sandbox) and the `BankBillPaymentFileProvider` (fallback — generates a bank bill-payment/EFT file with CRA as payee) are implemented; the production provider is a third adapter added under the same interface without screen changes.
4. **Assisted route** = pre-filled remittance details + deep link to CRA My Payment / Revenu Québec online payment + "record payment" step that posts the same JE.
5. **Client portal** is part of the main Next.js app under `/portal` (same design system, separate navigation shell), not a separate deployment.
6. **E-signature** for engagements/approvals uses an in-house click-to-sign with audit evidence (signer, timestamp, IP, document SHA-256, consent text) behind an `ESignatureProvider` interface; a paid provider can be plugged in later (fee is the client's — Quotation §6).
7. **Website** is a Next.js route group (`apps/web`) in the same monorepo using ISR; CMS lives in Django admin (headless, versioned pages, media in S3). Content and legal text are client inputs; placeholder copy is written by GMA as original Numo9 wording and marked for client review.
8. **Public API v1** covers the resources that exist at Phase 4 (contacts, items, invoices incl. revisions, bills, payments, accounts, journals read, bank transactions, tax payments read, reports read, full-ledger export). Writes are limited to contacts, items, invoices, bills, payments and attachments in v1.
9. **Webhooks** are delivered at-least-once with HMAC-SHA256 signatures and event IDs; consumers deduplicate on event ID.

**Open questions for the client (do not block build; defaults above apply):** ADR-003 provider choice and account; whether Numo9 takes an application fee on practice service sales (default 0 %); final website copy, legal pages (Terms, Privacy/PIPEDA, Acceptable Use, Cookie notice) and blog articles; analytics tool preference (default: self-hosted Plausible for privacy).

### 1.5 Client inputs required (Phase 4)

| Input | Needed for | Due |
|---|---|---|
| Tax-payment route/provider and account (ADR-003) | P-06 production adapter, G-09 provider route | Start of Phase 4 (week 7, day 1); stub + bank-file fallback proceed without it |
| Stripe live access (platform account, Connect enabled, ACSS Debit enabled) | P-01 live mode, P-04 | Before Phase 5 go-live; test mode used in Phase 4 |
| Website content, brand assets (logo, yellow/black palette), legal pages | Q-01, Q-03 | Week 7, day 2 (placeholder copy until then) |
| Numo9 domain DNS access | Q-04 | Week 7, day 1 |
| Practice service list and prices for Profitex | O-01 seed | Week 7, day 3 |

---

## 2. BETTER THAN XERO — gap analysis for this phase

### 2.1 Gap rows closed (or completed) in Phase 4

| Gap # | Teardown ref | What Xero does / fails to do | What Numo9 does instead (better) | Observable proof (test tag) |
|---|---|---|---|---|
| 5 | §2.1 | "Online payments" card showed "Unable to load – Refresh"; no reason, no retry | Online-payments status card reads from local payment tables (never a live Stripe call on render); background health check; explicit error state with cause, retry button and incident ID; Connect onboarding status always shown | `gap-05` — Stripe API down in test → card still renders cached totals + "Stripe unreachable since hh:mm, retrying" |
| 6 | §2.2 | Approval and payments paywalled with generic banners | Payment acceptance is part of Accounting product; any gated item shows "Included in <package> — compare packages" with link to the in-app matrix | `gap-06` — no route redirects silently; gated payment screen renders explicit gate |
| 11 | §2.3 | No multi-currency on plan | Pay links accept the invoice currency (CAD/USD via Stripe presentment), FX posting via R-02 | `gap-11` — USD invoice paid via link posts FX difference |
| 13 | §2.4 | No subscription object / recurring billing for organisations' customers | P-04 PAD mandates + recurring charges tied to D-04 recurring invoices | `gap-13` — recurring invoice auto-charges mandate once per tick |
| 41 | §6.3 | Advisor cannot see which plan the org is on | Portal and practice views show package, products, renewal date, founding badge; website pricing = same live data | `gap-41` — portal subscription panel equals U-02/U-03 data |
| 42 | §6.5 | Emails from Xero's domain, no per-contact language | Pay-link, receipt, document-request and tax-payment emails go from the org's verified domain (A-07) in the contact's language (X-02 keys) | `gap-42` — DMARC pass in harness; FR contact gets FR receipt template key |
| 48 | §6.12 | No generic ledger export / open API | W-01 versioned REST API + full-ledger JSON/CSV export | `gap-48` — export endpoint TB equals UI TB |
| 50 | §6.16 | Closed Xero-to-Xero network | Open API, OAuth, signed webhooks; companion apps (Phase 8) use the same API — no lock-in | `gap-50` — webhook `invoice.revised` delivered and verifiable by any HTTP consumer |
| 51 | §7 | Projects, Expenses, document capture are paid add-ons; Hubdoc payment wall | Practice set (O-01…O-06) and portal are free for every practice; document requests included | `gap-51` — new practice with no subscription uses O-01…O-06 fully |
| 61 | §10.B | Want a clear plan/feature matrix | Public pricing page renders the same feature matrix as the in-app matrix (U-01 export) | `gap-61` — website matrix JSON equals in-app matrix JSON |

### 2.2 Beyond-Xero additions in this phase (Xero has none of these)

- **Pay taxes from inside the system** (GST/HST, QST, payroll source deductions, corporate instalments) with provider and assisted routes, idempotency, posting, receipts and remittance-calendar sync (G-09, P-06).
- **Practice management set** (services, engagements pipeline, document-request checklists, deadline calendar from filing cycles, staff task board) free for accountants — Xero's equivalent lives in separate partner tools.
- **Pay-per-service checkout**: an organisation buys "Year-end package" or "T2 preparation" from its accountant in the portal.
- **Revision-aware pay links** — a link sent for 101 always collects the balance of 101-1.
- **Deadline calendar driven by the filing-cycle engine** — switching GST from quarterly to monthly moves every deadline automatically.
- **Public website with live pricing and founding counter**, sign-up straight into trial or demo.

### 2.3 Xero strengths matched conceptually (original design)

- Online invoice with pay button and receipt → Numo9 hosted pay page (own layout, Numo9 wording).
- Practice "adviser" tooling → Numo9 Practice set designed around Canadian deadlines.
- Keyboard-driven quick-create → portal and practice screens register their shortcuts in A-09.

### 2.4 [EXTRA] improvements (inside Schedule A scope)

| # | [EXTRA] improvement | Where |
|---|---|---|
| E1 | "Pay later" scheduling of a tax payment for the due date with a reminder 3 business days before and on the day | G-09 |
| E2 | Tax-payment **pre-flight check**: shows return filed? period locked? bank balance sufficient (ledger balance)? approval needed? before "Pay" is enabled | G-09 |
| E3 | Penalty-risk badge on calendar items (due ≤ 3 days and unpaid → amber; overdue → red with estimated CRA late-remittance penalty band shown as information, not advice) | O-04 |
| E4 | iCal subscription URL per staff member for the deadline calendar (read-only, tokenised) | O-04 |
| E5 | Document-request **smart reminders** (2 / 5 / 10 days) and per-item "not applicable" with reason so the checklist can close | O-03 |
| E6 | Engagement letter template per service with e-signature; signed PDF stored in org documents | O-02 |
| E7 | Pay page shows a QR code on the invoice PDF and supports Apple Pay / Google Pay via Stripe Payment Element (no extra integration) | P-02 |
| E8 | Payout reconciliation: Stripe payouts auto-match to bank import lines (F-05) using amount + date window | P-01/P-02 |
| E9 | API "sandbox org" per developer (demo org seed, U-07) and request log viewer with replay | W-01 |
| E10 | Webhook delivery dashboard with manual redeliver and automatic disable after 3 days of failures (owner notified) | W-01 |
| E11 | Website "package recommender" (3 questions → suggested package) using live U-02 data | Q-01 |
| E12 | Status page link in footer and in-app (`status.<numo9-domain>`) fed by S-04 checks | Q-04 |

---

## 3. UI/UX DESIGN PLAN

### 3.1 UX principles applied in this phase

1. **Money moves only with explicit confirmation**: every pay action shows a review screen with amount, period, program account (e.g. `123456789 RT0001`), source account, route and fees before the single confirm button; the button label states the amount ("Pay $1,234.56 to CRA").
2. **Idempotent UI**: the confirm button disables on click, shows progress, and a second click (or tab refresh) shows the existing payment instead of a new one.
3. **Status is always visible, never inferred**: payments use one status chip vocabulary — Scheduled, Initiated, Submitted, Confirmed, Failed, Cancelled, Refunded, Disputed — same colours everywhere (design tokens `status.*`).
4. **No silent redirects, explicit gating** (gaps #6, #14, #41): gated screens render a gate panel naming the product and package, never redirect.
5. **Task-first portal**: the portal home leads with "What needs you" (approvals, signatures, document requests, payments due) before reports.
6. **Progressive disclosure**: provider/assisted route details hidden behind "How this payment is sent"; advanced API settings behind "Advanced".
7. **Forgiving inputs**: amounts accept `1234.56`, `1,234.56`, `1 234,56` (fr-CA); dates accept typed and picker input; BN program account validated with checksum feedback inline.
8. **Undo over confirm where safe** (archive service, dismiss task, remove tag) — but **never** for money, signatures or API key revocation (those use confirm dialogs with typed confirmation for revocation).
9. **Keyboard-first for accountants**: calendar (← → weeks, `t` today), task board (`n` new, `j/k` move, `e` edit), engagements (`g e`), all registered in A-09 shortcut help (`?`).
10. **Responsive & mobile-ready**: pay page, portal and website are mobile-first (360 px), touch targets ≥ 44 px; practice screens desktop-first but usable at 768 px.
11. **Accessibility**: WCAG 2.1 AA — contrast ≥ 4.5:1 (yellow brand used on black/dark or as accent with black text only, never yellow text on white), focus rings visible, all charts with table alternative, form errors linked via `aria-describedby`, live regions for payment status.
12. **Localisation ready**: every string is an ICU key in `en-CA` and `fr-CA` catalogues; layouts tested with +30 % pseudo-locale; currency `$1,234.56` / `1 234,56 $`; dates `2026-11-07` short ISO in tables, long form in documents per locale.
13. **Trust signals on payment surfaces**: org's logo and legal name, Numo9 "secured by Stripe" note, invoice number and revision badge, receipt by email.
14. **Performance budgets**: website LCP < 2.0 s on 4G, CLS < 0.05, JS < 170 kB gz on marketing pages; pay page interactive < 2.5 s; portal home < 1.5 s.

### 3.2 Information architecture / navigation added

```
App (practice context)           App (organisation context)          Portal (/portal, org owner/users)     Public
Practice ▸ Home (V-04)           Sales ▸ Invoices ▸ Pay link (D-08)  Home — What needs you                 numo9 site (/)
Practice ▸ Services (O-01)       Payments ▸ Online payments (P-01)   Invoices & revisions                  Products ▸ Accounting/Tax/Payroll/Inventory/Finance
Practice ▸ Engagements (O-02)    Payments ▸ Refunds & disputes (P-05)Taxes ▸ Tax payments (G-09 view)      Packages & Pricing
Practice ▸ Doc requests (O-03)   Tax ▸ Tax Payments (G-09)           Loans (FN view)                       For Accountants
Practice ▸ Calendar (O-04)       Settings ▸ Payments (P-01, P-04)    Documents & requests (O-03)           Demo / Start free trial
Practice ▸ Tasks (O-06)          Settings ▸ Tax payment route (P-06) Services ▸ Buy (P-03)                 Resources / Blog
Practice ▸ Settings ▸ Payouts    Settings ▸ Developers ▸ API (W-01)  Messages · Approvals · Sign           About · Contact · Legal
                                                                     Subscription & package                Pay page /pay/<token> (public)
Developer portal: /developers (docs, OpenAPI, sandbox keys)
```

### 3.3 Screen inventory

| Screen | Primary user | Purpose | Key components (design system) | States | Keyboard |
|---|---|---|---|---|---|
| Services list & editor (O-01) | Practice Admin | Define services, prices, tax code, deliverables checklist | DataGrid, Drawer form, MoneyInput, TaxCodePicker | empty (with "Add your first service" + 5 suggested Canadian services), loading, error, archived | `n` new, `/` search |
| Engagements board/list (O-02) | Accountant | Pipeline Proposed → Engaged → In progress → Review → Completed → Billed | Kanban, DataGrid toggle, StatusChip, Avatar stack | empty, filtered-empty, drag-blocked (permission) | `g e`, `j/k`, `→` advance |
| Engagement detail | Accountant | Scope, letter, e-signature, tasks, requests, invoices | Tabs, Timeline, SignatureBlock | draft, awaiting signature, signed (locked) | `e` edit |
| Document request builder (O-03) | Accountant | Build checklist from template, send | ChecklistEditor, TemplatePicker, DueDatePicker | draft, sent, partially fulfilled, complete | `n` item |
| Deadline calendar (O-04) | Accountant / Practice Admin | All org deadlines | Calendar (month/week/agenda), FilterBar, RiskBadge | empty, loading skeleton, stale-data warning | `← →`, `t`, `m/w/a` views |
| Task board (O-06) | Staff | Tasks per staff/org | Kanban, Assignee picker, Org chip | empty, filtered | `n`, `j/k`, `x` complete |
| Portal home (O-05) | Org owner | What needs you; balances; deadlines | ActionCard list, KPI tiles, ActivityFeed | nothing-to-do (positive empty state), gated tile | `?` |
| Portal invoices | Org owner | Invoices with revision badges and superseded links | DataGrid, RevisionBadge | revised, superseded view (read-only watermark) | — |
| Portal tax payments | Org owner | Owing / scheduled / paid; approve & pay | ObligationCard, PaymentReview, StatusChip | none owing, pending provider, failed (retry) | — |
| Portal subscription | Org owner | Package, products, renewal, founding badge, invoices | PlanCard, FeatureMatrix | trial, grace, read-only, founding | — |
| Portal services shop (P-03) | Org owner | Buy practice services | ServiceCard, Checkout | none offered | — |
| Portal messages & approvals | Org owner / Accountant | Threaded messages, approve items | MessageThread, ApprovalCard | — | `r` reply |
| Online payments settings (P-01) | Org Admin | Connect onboarding, methods (card, PAD, Apple/Google Pay), fees account, clearing account | StepIndicator, StatusPanel | not connected, onboarding incomplete (with Stripe reason), active, restricted | — |
| Public pay page `/pay/<token>` (P-02/D-08) | External payer | Pay invoice | InvoiceSummary, Stripe Payment Element, ReceiptPanel | paid, partially paid, superseded→redirect banner, voided, expired link, gateway down | Enter submits |
| Refunds & disputes (P-05) | Org Admin | Refund, track disputes, evidence | DataGrid, RefundDialog, EvidenceUpload | none, needs response (deadline) | — |
| Tax Payments (G-09) | Accountant / Owner | Obligations, schedule, pay, record, history | ObligationTable, PreflightChecklist, PaymentReview, Receipt | nothing owing, return not filed (warn), insufficient balance (warn), awaiting approval, provider pending, failed | `p` pay selected |
| Tax payment route settings (P-06) | Org Admin / Platform Owner | Choose route, provider credentials (platform-level), bank file format | RadioCards, SecretInput | provider unavailable | — |
| Website pages (Q-01) | Public | Acquire | Hero, ProductTiles, PricingTable, FoundingCounter, FAQ accordion, CTA bands | price loading fallback (static ISR snapshot), counter sold-out state | — |
| Sign-up funnels (Q-01) | Public | Accountant / organisation sign-up, trial, demo | Stepper (max 3 steps), PasswordStrength | email exists, BN already trialled (U-05) | — |
| CMS (Q-03) | Platform Owner | Edit pages | Django admin + live preview | draft, scheduled, published, revision history | — |
| Developers settings (W-01) | Org Admin / Developer | API keys, OAuth clients, webhooks, logs | SecretReveal-once, ScopePicker (feature-keyed), DeliveryLog | none, key revoked, endpoint disabled | — |
| Developer portal `/developers` | Developer | Docs, OpenAPI, quick start | Redoc/Scalar render, CodeTabs | — | — |

### 3.4 Key user flows (targets)

**F1 — Organisation pays GST/HST from the system (provider route), ≤ 4 clicks, < 60 s**
1. Tax ▸ Tax Payments → "GST/HST Q3 2026 — $1,234.56 due 31 Oct" card (pre-flight ticks: return marked filed ✓, period locked ✓, chequing ledger balance $8,200 ✓).
2. Click **Pay** → Review: program account `RT0001`, period 2026-07-01–2026-09-30, from Chequing ••1234, route "Provider (sandbox)", provider fee shown, payment date (today / schedule).
3. Click **Pay $1,234.56 to CRA** → status Initiated → Submitted (live region announces).
4. Provider confirms → Confirmed with confirmation number; receipt PDF stored in Documents; JE posted (Dr 2310 GST/HST payable 1,234.56 / Cr 1010 Chequing 1,234.56); period chip "Paid"; calendar item green.

**F2 — Assisted route**: steps 1–2 same → "Pay on CRA My Payment" opens new tab with deep link + copy buttons for BN/program account/period/amount → back in Numo9 "I've paid — record it" (date, confirmation no., source account) → identical posting and status Confirmed (manual).

**F3 — Customer pays invoice 101 after it was revised to 101-1**: customer opens original email link → banner "This invoice was updated to 101-1 on 2026-11-02. You're paying the current version." → Payment Element (card / Apple Pay / PAD) → Pay $1,017.00 → receipt screen + email → AR reduced, JE posted to Stripe Clearing.

**F4 — Organisation subscribes from the website** (U-04 reused): Pricing → choose package (monthly/annual toggle, founding badge "412 of 1,000 left") → sign-up (email, password, organisation name, province) → trial starts or "Subscribe now" → Stripe Checkout → app dashboard. Target: trial sign-up to first screen < 2 min (Q-01 acceptance).

**F5 — Accountant onboarding a client with an engagement**: Engagements ▸ New → choose org + service "Year-end T2 package" → engagement letter auto-filled → send for e-signature → portal: owner signs → document request checklist auto-sent (T-slips, bank statements) → owner uploads → items tick → tasks generated for staff → calendar shows T2 deadline.

**F6 — Organisation buys a service** (P-03): Portal ▸ Services → "Bookkeeping catch-up — $450" → Buy → Stripe Checkout on practice Connect account → invoice created in the **practice's** books and in the org's bills (payable marked paid) → engagement auto-created.

**F7 — Developer connects**: Settings ▸ Developers → Create OAuth client / API key (scopes shown as products: Accounting read/write …) → key revealed once → Quick-start curl with real org ID → Webhooks → add endpoint → "Send test event" → delivery log shows 200.

### 3.5 Microcopy & error-message rules

Rules: plain language; say what happened, why, and what to do; never blame the user; never show raw codes without a human sentence; include a support reference for system errors; money and tax terms in Canadian usage (GST/HST, program account, remittance, cheque).

| Situation | Message |
|---|---|
| Second click on pay | "This payment is already in progress (started 10:42 by Sara). We'll update this page when CRA's provider confirms it." |
| Return not filed (pre-flight) | "The GST/HST return for Jul–Sep 2026 isn't marked as filed yet. You can still pay, but CRA matches payments to returns — mark it filed first if you've submitted it." |
| Insufficient ledger balance | "Chequing shows $820.00 in your books — less than this payment. Pay anyway if the bank balance is higher, or choose another account." |
| Provider down | "The payment provider isn't responding. Nothing was charged. Try again in a few minutes or use 'Pay on CRA My Payment' and record it here." |
| Superseded pay link | "This invoice was updated to 101-1 on 2 Nov 2026. You're paying the current version — the amount below is what's owed now." |
| Connect onboarding incomplete | "Stripe needs one more detail before you can accept payments: business representative's date of birth. Finish setup →" |
| Gated portal tile | "Payroll isn't in your current package (Essentials). It's included in Growth and Complete. Compare packages →" |
| API 402 | `{"error":"product_not_in_package","product":"payroll","message":"This organisation's package does not include Payroll."}` |
| Webhook endpoint disabled | "We stopped sending events to https://… after 3 days of failed deliveries. Fix the endpoint, then re-enable it — we'll resend the last 72 h." |

### 3.6 Accessibility & usability test plan

| Usability task (5 participants: 2 accountants, 2 owners, 1 external payer) | Success metric |
|---|---|
| Pay this quarter's GST from Tax Payments | ≥ 4/5 unaided, median < 60 s, 0 wrong-period payments |
| Record a payment made on CRA My Payment | ≥ 4/5, < 90 s |
| As a customer, pay a revised invoice from the old email link | 5/5 understand which amount they paid (post-task question) |
| Send a document request to a client and see what's still missing | ≥ 4/5, < 2 min |
| Find every deadline due next week across all clients | ≥ 4/5, < 30 s |
| From the website, start a free trial | 5/5, < 2 min |
| Find which package includes Payroll | 5/5, < 20 s |

Automated: axe-core in Playwright on every new screen (0 serious/critical), Lighthouse CI (Performance/SEO/Accessibility/Best practices ≥ 90 website), keyboard-only run of F1, F3, F4, screen-reader smoke (NVDA + VoiceOver) on pay page and Tax Payments.

---

## 4. TOOLS & TECHNOLOGY FOR THIS PHASE

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| Backend | Django 5 / DRF / Python 3.12 | All new apps (`practice`, `portal`, `payments`, `taxpayments`, `website_cms`, `public_api`) | Existing stack |
| Backend | `stripe` (Python SDK, pinned) | Connect accounts, PaymentIntents, Checkout, SetupIntents (ACSS Debit), Refunds, Disputes, Payouts, webhooks | Fees client's |
| Backend | `dj-stripe` — **not used** (explicit decision) | Avoid duplicating U-04 models; thin own models + SDK | ADR note |
| Backend | `django-oauth-toolkit` | OAuth 2.0 authorisation-code + PKCE, client credentials for W-01 | — |
| Backend | `drf-spectacular` | OpenAPI 3.1 generation for `/api/public/v1` | Contract source |
| Backend | `django-filter`, `drf-nested-routers` | Public API filtering, nested revisions | — |
| Backend | `django-ratelimit` / Redis token bucket (S-06 limiter) | Per-key and per-org rate limits | Reuse S-06 |
| Backend | `celery`, `celery-beat`, `redbeat` | Webhook processing, provider polling, calendar regeneration, reminders, webhook delivery with retries | Existing A-08 |
| Backend | `tenacity` | Retry/backoff on provider and outbound webhook calls | — |
| Backend | `httpx` | Provider HTTP client (timeouts, mTLS if provider requires) | — |
| Backend | `python-dateutil` (rrule), `holidays` (CA + provinces) | Business-day due-date roll-forward, reminders | Confirm with CRA rules |
| Backend | `icalendar` | iCal feed for O-04 | — |
| Backend | `WeasyPrint` | Receipts, engagement letters, signed-certificate PDFs (Letter/inch) | Existing A-10 base |
| Backend | `qrcode` | QR pay link on invoice PDFs | — |
| Backend | `django-reversion` or own `PageRevision` model | CMS page versioning | Own model preferred (append-only) |
| Backend | `bleach` / `nh3` | Sanitise CMS rich text and messages | Security |
| Backend | `Pillow`, `django-storages` (S3) | CMS media, portal uploads | Existing A-06 |
| Backend | `pyotp` (existing) | Step-up 2FA for high-value tax payments and API key creation | Reuse A-02 |
| Backend | `cryptography` (Fernet / KMS) | Encrypt provider credentials, webhook secrets at rest | S-03 key mgmt |
| Backend | `standardwebhooks` style HMAC signing (own impl) | Outbound webhook signatures `Numo9-Signature: t=…,v1=…` | — |
| Frontend | Next.js 15 App Router, TypeScript, React Query, Tailwind, `@numo9/ui` | Practice, portal, pay page, developers, website | Existing |
| Frontend | `@stripe/stripe-js`, `@stripe/react-stripe-js` (Payment Element, Connect embedded onboarding components) | Pay page, service checkout, PAD mandate collection | PCI SAQ-A |
| Frontend | `@fullcalendar/react` (MIT core) or own calendar on `date-fns` | O-04 calendar | Licence check: premium plugins not used |
| Frontend | `@dnd-kit/core` | Kanban drag for engagements/tasks | Accessible DnD |
| Frontend | `react-hook-form` + `zod` | All forms; schemas shared with OpenAPI-generated types | — |
| Frontend | `openapi-typescript` / `orval` | Typed API client from spec | — |
| Frontend | `next-intl` (ICU) | en-CA/fr-CA routing and messages on website and app | Existing X-01 base |
| Frontend | `next-sitemap`, `schema-dts` | Sitemap, hreflang, JSON-LD (`Organization`, `SoftwareApplication`, `Offer`, `FAQPage`, `BreadcrumbList`) | Q-04 |
| Frontend | `@vercel/og`-style / `satori` (self-hosted) | Open Graph images per page | Original artwork |
| Frontend | Scalar or Redoc | Developer portal API reference | — |
| Design | Figma (Numo9 file, brand library), FigJam | Wireframes, hi-fi, flows, website art direction | Original — no reference site copied |
| Design | Storybook 8 + Chromatic (or Loki/Playwright snapshots self-hosted) | Component states incl. StatusChip, PaymentReview, PricingTable | Visual regression (A-10) |
| Design | Stark / Figma contrast plugins, `@axe-core/react` | Contrast and a11y during design and dev | Yellow/black contrast checks |
| Testing | pytest, pytest-django, factory_boy, Hypothesis | Unit/property tests (idempotency, state machines, calendar generation) | — |
| Testing | `stripe-mock`, Stripe CLI (`stripe listen`, `stripe trigger`), Stripe test clocks | Webhook and recurring PAD tests | — |
| Testing | `respx` / `responses`, VCR.py | Provider HTTP mocking and recorded sandbox cassettes | — |
| Testing | Schemathesis | Property-based contract tests from OpenAPI spec | W-01 |
| Testing | Playwright (+ axe), Lighthouse CI, k6 | E2E flows F1–F7, a11y, website perf, API load | — |
| Testing | `pytest-freezegun` / `time-machine` | Due dates, 23:59 org-local edge cases | — |
| Testing | Mailpit | Email capture (pay links, receipts, requests) | Existing |
| Testing | `webhook.site`-style local receiver (own `devtools/webhook_sink`) | Outbound webhook tests | Built in this phase |
| Quality | ruff, mypy (strict on `payments`, `taxpayments`), eslint, prettier, import-linter (layer contracts: `taxpayments` may import `providers` interface only), pre-commit, semgrep (Stripe secret leakage rules) | — | — |
| Security | OWASP ZAP (pay page, portal, public API), pip-audit, npm audit, gitleaks, Trivy (images), CSP evaluator, securityheaders check | — | No high findings |
| Observability | Sentry (backend, frontend), Prometheus metrics (`payments_webhook_lag_seconds`, `taxpayment_status_total`, `webhook_delivery_failures_total`, `api_requests_total{scope}`), Grafana dashboards, structured logs with correlation IDs | — | S-04 finalised in Phase 5; metrics added now |
| Analytics | Plausible (self-hosted) or client's choice | Website funnels without cookies banner | Cost client's if hosted |
| Anti-spam | Cloudflare Turnstile or hCaptcha + honeypot + rate limit | Lead/demo/sign-up forms | — |
| DNS / mail | Caddy (TLS), DNS provider of client, SPF/DKIM/DMARC records, `checkdmarc` | Q-04 | — |
| Docs | MkDocs Material (`docs/`), ADR template (MADR) — ADR-003 tax-payment route, ADR-005 Stripe Connect topology, ADR-006 public API versioning & webhooks | — | — |
| Dev productivity | Docker Compose services: `stripe-mock`, `mailpit`, `minio`, `webhook-sink`, `provider-stub`; Makefile targets `make stripe-listen`, `make seed-phase4`; ngrok/cloudflared for webhook testing on dev | — | — |
| Internal tools to build | `seed_practice_demo` (services, engagements, requests), `generate_obligations_fixture` (GST/QST/payroll/instalments), `taxpayment_provider_stub` service (Django app + admin control panel to force Confirmed/Failed/Pending), `replay_stripe_events` command, `reconcile_stripe_clearing` command/report, `regenerate_calendar --org`, `webhook_redeliver`, `api_key_rotate`, `cms_export/import` JSON, Lighthouse budget file, `gap_check phase4` runner | — | — |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 objective

Give accountants a free practice workspace with a client portal, let organisations accept online payments and pay their taxes from Numo9 with exact posting, publish the Numo9 product website that sells packages live, and expose an open, versioned API with webhooks.

### 5.2 Level 2 components

| Component | Deliverables | Purpose |
|---|---|---|
| O — Practice Management & Client Portal | O-01 Service catalog, O-02 Engagements, O-03 Document requests, O-04 Deadline calendar, O-05 Client portal, O-06 Staff task board | Free Practice product set; how accountants work with and bring in organisations |
| P — Online Payments | P-01 Stripe connection, P-02 Invoice payment, P-03 Pay-per-service checkout, P-04 PAD mandates & recurring billing, P-05 Refunds & disputes, P-06 Tax-payment provider adapter | Money in (Stripe) and tax money out (provider adapter) |
| G — Tax Payments | G-09 Tax Payments | Pay GST/HST, QST, payroll remittances, corporate instalments from the system |
| D — Sales | D-08 Online invoice pay link | Pay link on invoice documents/emails (delivered through P-02) |
| Q — Public Website | Q-01 Site design & content, Q-02 Lead capture, Q-03 CMS, Q-04 SEO/analytics/domain/mail DNS | Acquisition |
| W — Open API | W-01 Versioned public API & webhooks | Open integration surface; foundation for Phase 7 mobile & Phase 8 companion apps |

### 5.3 Dependency graph and execution order

```
Phases 0–3 (A, U-04, D-03b, D-05, G-03/G-03a/G-04/G-08, N-07, F-01, A-06, A-07)
   │
   ├─ P-01 Stripe connection ──┬─ P-02 Invoice payment ── D-08 Pay link
   │                           ├─ P-04 PAD & recurring
   │                           ├─ P-05 Refunds & disputes (needs P-02/P-03)
   │                           └─ P-03 Pay-per-service ◄── O-01 Services
   │
   ├─ P-06 Provider adapter ── G-09 Tax Payments ──► N-07 "paid", O-04 calendar status
   │
   ├─ O-01 ── O-02 Engagements ── O-03 Doc requests
   ├─ O-04 Calendar (G-03a, N-07, G-08) ◄── G-09 paid status
   ├─ O-06 Task board (O-02 generates tasks)
   └─ O-05 Portal (aggregates O-02, O-03, P-02/P-03, G-09, U-04, FN, D-03b)
   │
   ├─ W-01 Public API & webhooks (events from D-03b, P-02, G-09, H, N)
   │
   └─ Q-03 CMS ── Q-01 Site ── Q-02 Leads ── Q-04 SEO/DNS (U-02 prices, U-08 counter, U-05/U-07 funnels)
```

Execution order (parallel lanes; BE = backend, FE = frontend, WEB = website engineer):

1. **Day 1** — P-01 (BE+FE) ‖ P-06 (BE) ‖ O-01 (BE+FE) ‖ Q-03 (BE) + Q-01 design (Figma) ‖ W-01 foundation (spec, auth).
2. **Day 2** — P-02 → D-08 ‖ G-09 (on P-06) ‖ O-02 ‖ Q-01 build ‖ W-01 resources.
3. **Day 3** — P-03 (on O-01, P-01) ‖ G-09 assisted route + payroll/instalment obligations ‖ O-03 ‖ O-04 ‖ Q-02 ‖ W-01 webhooks.
4. **Day 4** — P-04 ‖ P-05 ‖ O-06 ‖ O-05 portal (aggregation) ‖ Q-04.
5. **Day 5** — Integration, gap tests, exit-demonstration rehearsal on staging, security scans, Lighthouse, fixes, phase report.

---

## 6. PLAN — Deliverable cards with ATOMIC TASKS (Rule 3)

Common rules for every card: every new model inherits `OrgOwnedModel` (or `PracticeOwnedModel` for practice-level records, which carries `practice_id` and is swept by the A-01 practice sweep); every endpoint declares a permission (A-03 catalogue) and a feature key (U-01) — Practice-set features use keys `practice.*` which resolve to "always included" for practices; every mutating action writes an audit entry (A-04); every string is an ICU key (`en-CA` filled, `fr-CA` key created); every screen has Storybook stories for empty/loading/error/gated states.

### 6.1 Component O — Practice Management & Client Portal

### O-01 · Service catalog
- **Branch:** `feature/O-01-service-catalog`
- **Objective:** a practice defines the services it sells to its organisations (e.g. Monthly bookkeeping, GST/HST filing, T2 year-end, Payroll run, T4 slips), with price, billing type, tax code and a deliverables checklist that later drives engagements, document requests and tasks.
- **Current behaviour:** none; practices bill clients outside Numo9.
- **Expected behaviour (better than Xero):** catalogue inside the free Practice set, priced in CAD with GST/HST code from the practice's own registration (place-of-supply via G-02 on checkout), purchasable from the portal (P-03), re-usable templates; Xero has no practice service catalogue in the ledger app.
- **Gap #s closed:** 51 (practice tools not a paid add-on).
- **Business rules:** service belongs to a practice; price ≥ 0.00, `numeric(18,2)`; billing type ∈ {one-off, monthly, quarterly, annual, per-unit}; tax code must be a **sales** code effective today; archived services cannot be bought but remain on historical engagements; price changes are effective-dated (never rewrite past engagements); a service may be "portal-visible" or "internal only".
- **Edge cases:** practice not GST-registered (tax code forced out-of-scope, warning); price change while a checkout is open (checkout uses the price at session creation); duplicate service names (warn, allow); deleting a service used by an engagement (refused → archive).
- **UI/UX notes:** list with search, category filter, "portal visible" toggle column; drawer editor with live "client sees" preview card; suggested starter services on empty state (one click adds 5 Canadian practice services, editable).
- **Dependencies:** A-01, A-03, A-04, G-01, G-02, U-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| O-01-T01 | Write UNDERSTAND note + Figma wireframes for list, editor drawer, empty state and portal preview card | UX | — | Wireframes reviewed by project lead; states listed | Design review |
| O-01-T02 | `PracticeOwnedModel` base (practice FK, created_by, timestamps, soft-delete) if not present + practice-scoped manager | DB | — | Base model used by practice tables; manager filters by active practice | Unit |
| O-01-T03 | `ServiceCategory` and `Service` models (name, code, description, category, billing_type, unit_label, default_tax_code, portal_visible, deliverables JSON schema, archived_at) + migration | DB | T02 | Migration applies/rolls back cleanly | Migration test |
| O-01-T04 | `ServicePrice` effective-dated model (service, amount, currency CAD, effective_from, effective_to) with no-overlap DB exclusion constraint | DB | T03 | Overlapping price rows rejected by DB | Unit (IntegrityError) |
| O-01-T05 | `ServiceCatalogService` (create/update/archive, `price_on(date)`) with validation: sales tax code, amount ≥ 0, archived not purchasable | BE | T04 | `price_on` returns correct row across boundaries; invalid tax code raises | Unit + Hypothesis on dates |
| O-01-T06 | Register permissions `practice.services.view/manage` and feature key `practice.services` (always-on for practices) | BE | T05 | Undeclared-permission CI check passes | CI check |
| O-01-T07 | DRF endpoints `/api/v1/practice/services/` (list/create/retrieve/update/archive) + `/prices/` sub-resource; filters, search | API | T06 | CRUD works; cross-practice ID → 404 | Integration + practice sweep |
| O-01-T08 | Audit hooks for service and price changes (field diffs) | BE | T07 | Price change shows old/new in audit viewer | Integration |
| O-01-T09 | Seed command `seed_practice_services --starter` (Monthly bookkeeping, GST/HST return, T2 year-end, Payroll run, T4/T4A slips) with en-CA/fr-CA keys | BE | T05 | Command idempotent; re-run creates 0 duplicates | Unit |
| O-01-T10 | Services list screen (DataGrid, search `/`, category filter, portal-visible chip, archived toggle) | FE | T07 | Matches wireframe; empty state offers starter set | Storybook + Playwright |
| O-01-T11 | Service editor drawer (react-hook-form + zod; MoneyInput, TaxCodePicker filtered to sales codes, billing type, deliverables checklist editor, price schedule with future price) | FE | T10 | Purchase tax codes not offered; future price shows "from 2027-01-01" | Playwright |
| O-01-T12 | "Client sees" live preview card (same component the portal uses) | FE | T11 | Preview equals portal card snapshot | Visual regression |
| O-01-T13 | Archive with undo toast; delete refused when referenced (message names engagements) | FE/BE | T11 | Archive undo restores; delete of used service refused with count | Playwright |
| O-01-T14 | i18n keys for all strings (en-CA filled, fr-CA keys) | FE | T10–T13 | i18n lint passes; pseudo-locale layout holds | i18n CI |
| O-01-T15 | Register shortcuts (`n`, `/`) and search entries ("services") in A-09 | FE | T10 | Global search "services" opens list | Playwright |
| O-01-T16 | Tests: price boundary, archived not purchasable, non-registered practice tax warning | QA | T05–T13 | All green | pytest |
| O-01-T17 | Docs: accountant guide page "Set up your services" | DOC | T13 | Page in MkDocs | Review |

- **Deliverable acceptance:** services purchasable via P-03 (verified in P-03-T12); price changes dated in the future don't affect open engagements; cross-practice access 404.
- **Testing approach:** unit (pricing), integration (API + sweep), functional (create → portal visible), regression (G-01 pickers), i18n.
- **Risks & mitigations:** price drift between catalogue and checkout → checkout snapshots price; tax code expiry → effective-date validation reused from G-01.

### O-02 · Engagements
- **Branch:** `feature/O-02-engagements`
- **Objective:** an engagement pipeline linking a practice, an organisation and one or more services, with an engagement letter, e-signature, status transitions, generated tasks and billing.
- **Current behaviour:** none.
- **Expected behaviour:** statuses `proposed → awaiting_signature → engaged → in_progress → in_review → completed → billed` (+ `cancelled`); every transition audited with actor and reason; engagement letter generated from template, signed in the portal with evidence; deliverables checklist from the service spawns O-06 tasks and optionally an O-03 request; billing creates an invoice in the **practice's** books (practice billing org) on completion or schedule.
- **Gap #s closed:** 51.
- **Business rules:** only staff assigned to the org (A-01/V-02) can create engagements for it; transitions follow the state machine; signed letter immutable (new version → re-sign); recurring services create one engagement per period (idempotent per period); billing amount = service price on engagement date unless overridden with reason.
- **Edge cases:** org loses practice assignment mid-engagement (engagement read-only for removed staff, visible to remaining); signature by a user without Owner role (refused); cancel after partial billing (requires credit note via D-06).
- **UI/UX notes:** Kanban with WIP counts per column and list toggle; drag to advance only to allowed next states (disallowed columns dim with tooltip reason); detail page tabs: Overview, Letter & signature, Tasks, Requests, Billing, Activity.
- **Dependencies:** O-01, A-04, A-06, A-07, D-03a (practice invoice), V-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| O-02-T01 | UNDERSTAND note + Figma: Kanban, list, detail tabs, letter preview, signature block | UX | — | Reviewed | Design review |
| O-02-T02 | `Engagement` model (practice, organisation, services M2M through `EngagementLine` with price snapshot, status, period_start/end, owner_staff, due_date, cancelled_reason) + migration | DB | O-01 | Migration clean | Migration test |
| O-02-T03 | `EngagementTransition` append-only table + state machine service (allowed transitions table, guard functions) | BE | T02 | Disallowed transition raises `InvalidTransition`; every transition row written | Unit (parameterised all pairs) |
| O-02-T04 | `EngagementLetterTemplate` (practice-level, ICU placeholders, EN/FR body, version) + seed default original template | DB/BE | T02 | Template renders with org/service placeholders | Unit |
| O-02-T05 | `ESignatureProvider` interface + `InHouseClickToSign` implementation (signer user, timestamp, IP, UA, document SHA-256, consent text, certificate PDF) | BE | T04 | Signing stores evidence; hash mismatch on altered PDF detected | Unit |
| O-02-T06 | Letter generation: render PDF (WeasyPrint, Letter/inch), store in org Documents (A-06) tagged with engagement | BE | T04 | PDF stored; preview equals file | Integration |
| O-02-T07 | Signature flow service: send for signature → portal task → sign → status `engaged`; re-issue invalidates prior pending signature | BE | T03, T05, T06 | Signed letter immutable; new version requires new signature | Integration |
| O-02-T08 | Task spawning from service deliverables (calls O-06 service when available; until then queued domain event `engagement.engaged`) | BE | T03 | Event emitted once per transition | Unit |
| O-02-T09 | Recurring engagement generator (beat job per service billing type, idempotency key `org:service:period`) | BE | T02, A-08 | Two workers → one engagement per period | Integration (concurrency) |
| O-02-T10 | Billing: on `completed` or schedule create invoice in practice billing org (D-03a service) with lines from snapshot; status `billed`; link stored | BE | T03, D-03a | Invoice totals = snapshot; second bill refused | Integration |
| O-02-T11 | Endpoints `/api/v1/practice/engagements/` + `/transition/`, `/send-for-signature/`, `/bill/`; permissions `practice.engagements.*` | API | T03–T10 | Unassigned org → 404; transition errors return 409 with reason | Integration + sweep |
| O-02-T12 | Kanban board (dnd-kit, keyboard move with `→`, column WIP counts, allowed-target highlighting) | FE | T11 | Drag to disallowed column impossible; keyboard advance works | Playwright + axe |
| O-02-T13 | List view with filters (org, group, service, status, staff, due) + saved views (V-01 component) | FE | T11 | Saved view persists per user | Playwright |
| O-02-T14 | Detail page tabs (Overview, Letter & signature with PDF preview, Tasks, Requests, Billing, Activity timeline from transitions + audit) | FE | T11 | All tabs render; activity equals transition rows | Playwright |
| O-02-T15 | Cancel flow with reason; partially billed → prompt to issue credit note (link to D-06) | FE/BE | T10 | Cancel billed engagement requires credit-note decision | Playwright |
| O-02-T16 | Notifications: owner notified on "awaiting signature", staff on "engaged" (A-07 templates EN/FR keys) | BE | T07 | Emails in Mailpit with correct language key | Integration |
| O-02-T17 | i18n + shortcuts (`g e`, `j/k`, `→`) registered | FE | T12–T14 | i18n lint passes | CI |
| O-02-T18 | Tests: state machine matrix, signature evidence, recurring idempotency, assignment revocation | QA | all | Green | pytest |
| O-02-T19 | Docs + ADR note on e-signature evidence model | DOC | T05 | Docs merged | Review |

- **Deliverable acceptance:** status transitions audited (each transition visible with actor/time/reason); signed letter stored with evidence; billing once only.
- **Testing:** unit (state machine), integration (billing, signature), functional (F5), security (sweep, role on signature).
- **Risks:** legal weight of click-to-sign → evidence certificate + provider interface for a paid provider later; practice billing org not configured → onboarding check blocks billing with clear message.

### O-03 · Document requests
- **Branch:** `feature/O-03-document-requests`
- **Objective:** accountants send checklists of documents/information to organisations; owners upload in the portal; uploads land in the org's Documents inbox, tagged by period/tax year.
- **Current behaviour:** documents arrive by email outside Numo9 (Xero: no request checklist; documents page slow, no period tagging — gap #32 area).
- **Expected behaviour:** templates (Year-end, GST quarter, Payroll onboarding, New client), per-item due date, required/optional, "not applicable" with reason, smart reminders 2/5/10 days [EXTRA E5], completion %, accountant review (accept/reject with comment).
- **Gap #s closed:** 32 (period tagging on requested docs), 51.
- **Business rules:** upload goes only to the requesting org (A-06 isolation, 25 MB, MIME validated, virus-scan hook); item accepted only by practice staff; request closes when all required items accepted or N/A; reminders stop when complete or cancelled.
- **Edge cases:** owner uploads wrong file (replace keeps history); request to org with no portal user (prompt to invite owner — A-02); duplicate file (SHA-256 match warns).
- **UI/UX notes:** builder with template picker and drag reorder; client side shows one clear list with big upload zones and progress, mobile-friendly camera upload.
- **Dependencies:** A-06, A-07, O-02 (optional link), A-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| O-03-T01 | Figma: builder, request status view, portal checklist (mobile + desktop) | UX | — | Reviewed | Design review |
| O-03-T02 | Models `DocumentRequestTemplate`, `DocumentRequestTemplateItem`, `DocumentRequest` (org, engagement?, title, tax_year/period, status, due_date), `DocumentRequestItem` (label, required, due_date, status pending/uploaded/accepted/rejected/na, na_reason) + migration | DB | — | Migration clean | Migration test |
| O-03-T03 | Link `DocumentRequestItem` ↔ A-06 `Document` (M2M with uploaded_by, version); period/tax-year tag copied to document | DB/BE | T02, A-06 | Upload tagged with request period | Integration |
| O-03-T04 | Seed four original templates (Year-end, GST/HST quarter, Payroll onboarding, New client) EN/FR keys | BE | T02 | Seed idempotent | Unit |
| O-03-T05 | Request service: create from template, send (notify), item state machine, completion % computed, close rule | BE | T02 | Closes only when required items accepted/N/A | Unit |
| O-03-T06 | Upload endpoint (portal) with size/MIME validation, virus-scan hook, SHA-256 duplicate warning | API | T03 | 26 MB rejected; .exe rejected; duplicate warns | Integration |
| O-03-T07 | Review endpoints accept/reject(comment)/N/A; permission practice staff only | API | T05 | Owner cannot accept own upload | Integration (RBAC) |
| O-03-T08 | Reminder beat job (2/5/10 days before/after due; stop rules) with idempotency | BE | T05, A-08 | One reminder per step; none after completion | Integration (time-machine) |
| O-03-T09 | Practice builder screen (template picker, add/reorder items, due dates, preview as client) | FE | T05 | Matches Figma | Playwright |
| O-03-T10 | Request status view for accountant (per-item status chips, review actions, completion bar) | FE | T07 | Accept updates bar in place | Playwright |
| O-03-T11 | Portal checklist with drag-drop / camera upload, progress, replace, N/A with reason | FE | T06 | Mobile 360 px usable; axe 0 serious | Playwright mobile + axe |
| O-03-T12 | Auto-create request on engagement `engaged` when service has a linked template | BE | T05, O-02-T08 | One request per engagement | Integration |
| O-03-T13 | Cross-practice dashboard tile "Outstanding document requests" (V-04 drill-down) | FE/BE | T05 | Tile count = list count | Integration |
| O-03-T14 | i18n, audit hooks, A-09 search entries | FE/BE | all | Lint passes; audit rows present | CI |
| O-03-T15 | Tests: isolation (upload to Org 2 impossible), state machine, reminders | QA | all | Green | pytest + sweep |

- **Deliverable acceptance:** uploads land in the org's documents (tagged), never in another org; reminders stop on completion.
- **Testing:** integration, security (isolation, file validation), functional (F5), mobile usability.
- **Risks:** large uploads on mobile → chunked upload with resume; malware → scan hook mandatory before accept.

### O-04 · Deadline calendar
- **Branch:** `feature/O-04-deadline-calendar`
- **Objective:** one calendar of every statutory and practice deadline across all assigned organisations, derived from each org's filing-cycle engine (G-03a), remittance type (N-07), corporate instalments/balance due (G-08), T2/T4/T4A/T5/RL-1 year-end dates and engagement due dates.
- **Current behaviour:** deadlines tracked manually; Xero has none in the ledger.
- **Expected behaviour:** `Deadline` read model regenerated by events and nightly; statuses upcoming / due soon / overdue / filed / paid (paid comes from G-09); filters by org/group/staff/type; risk badge [EXTRA E3]; iCal feed per staff [EXTRA E4]; G-03a cycle switch updates calendar within one job cycle.
- **Gap #s closed:** supports gap #4 (deadlines on dashboard) and V-04.
- **Business rules:** due dates computed in org-local time zone, end of day 23:59; weekend/holiday roll-forward per CRA rule (configurable table, default: next business day); derived entries cannot be edited (only custom entries); regenerating never duplicates (natural key `org:type:registration:period`).
- **Edge cases:** stub period from G-03a; stopped filing (G-03b) → no new deadlines after stop; annual filer instalments; accelerated remitters (multiple per month); org without assignment disappears from staff calendars immediately.
- **UI/UX notes:** month/week/agenda views; agenda default for density; colour by type plus icon (not colour alone); click → side panel with org, amount (if known), actions "Open return", "Pay" (G-09).
- **Dependencies:** G-03a, G-03b, G-08, N-07, O-02, A-08, V-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| O-04-T01 | Figma: month/week/agenda, side panel, filter bar, risk badges | UX | — | Reviewed | Design review |
| O-04-T02 | `Deadline` model (org, type enum gst_hst_return, gst_hst_payment, qst_return, qst_payment, payroll_remittance, corp_instalment, corp_balance_due, t2, t4, t4a, t5, rl1, engagement, custom; registration ref, period_start/end, due_at, status, source_ref, natural_key unique) + migration | DB | — | Unique natural key enforced | Migration test |
| O-04-T03 | `BusinessDayCalendar` service (CA federal + provincial holidays table, roll-forward rule configurable) | BE | — | 2026 fixtures: holiday due dates roll correctly | Unit |
| O-04-T04 | Generator: GST/HST & QST deadlines from G-03a periods (return + payment, monthly/quarterly 1 month, annual 3 months + instalments) | BE | T02, T03 | Fixture org quarterly→monthly switch from 1 Jul yields correct set | Unit (fixtures) |
| O-04-T05 | Generator: payroll remittances from N-07 remitter type (quarterly/regular/accelerated 1 & 2) | BE | T02 | Accelerated-2 fixture yields 4 per month | Unit |
| O-04-T06 | Generator: corporate instalments and balance-due from G-08; T2 filing 6 months after FYE | BE | T02 | Fixture FYE 31 Dec → T2 30 Jun | Unit |
| O-04-T07 | Generator: year-end slips (T4/T4A/T5/RL-1 last day of February rolled) + engagement due dates + custom entries | BE | T02 | Fixtures pass | Unit |
| O-04-T08 | Upsert engine with natural key; removes obsolete derived entries for unfiled periods only | BE | T04–T07 | Regeneration twice → 0 changes; filed history preserved | Property test (Hypothesis random switch sequences) |
| O-04-T09 | Event subscriptions: G-03a cycle change, G-03b stop/restart, N-07 schedule change, G-08 instalment change, G-09 paid, O-02 due change → enqueue regenerate for org | BE | T08, A-08 | Cycle switch reflected within one job cycle | Integration |
| O-04-T10 | Nightly full regeneration job + metrics (`calendar_regen_seconds`, changes count) | BE/OPS | T08 | Dashboard metric visible | Integration |
| O-04-T11 | Status resolver (filed from G-03/G-04 mark-filed, paid from G-09, overdue by now > due_at) | BE | T08 | Status matches source on fixtures | Unit |
| O-04-T12 | API `/api/v1/practice/deadlines/` (range, filters org/group/staff/type/status) scoped to assignments | API | T11 | Revoked assignment removes entries in next request | Integration + sweep |
| O-04-T13 | iCal feed `/ical/<token>.ics` per staff (read-only token, revocable) [EXTRA E4] | API | T12 | Feed validates (icalendar); revoke → 404 | Integration |
| O-04-T14 | Calendar UI (month/week/agenda; keyboard ← → t m w a; filter bar; colour+icon legend) | FE | T12 | Keyboard nav works; axe 0 serious | Playwright + axe |
| O-04-T15 | Side panel with actions (Open return, Pay → G-09, Open engagement) and risk badge [EXTRA E3] | FE | T14 | Actions open correct screens | Playwright |
| O-04-T16 | Org-level mini-calendar widget for dashboard (K-05) and portal (O-05) | FE | T12 | Widget equals list | Visual + integration |
| O-04-T17 | i18n (type labels CRA/RQ terms EN/FR keys), docs | FE/DOC | T14 | Lint passes | CI |

- **Deliverable acceptance:** G-03a cycle switch updates calendar within one job cycle; no duplicate deadlines after repeated regeneration; deadlines respect org time zone.
- **Testing:** unit + property (generation), integration (events), functional (switch → calendar), perf (2,000 orgs agenda < 1 s p95).
- **Risks:** CRA rule nuances → rules as data (`DeadlineRule` table) with accountant confirmation; event storm on bulk changes → debounce per org (30 s).

### O-05 · Client portal
- **Branch:** `feature/O-05-client-portal`
- **Objective:** a task-first portal for organisation owners/users: what needs them (approvals, signatures, document requests, payments due), invoices with revision badges, tax payments, loans [v2.1], subscription/package, messages, services shop.
- **Current behaviour:** owners use the full app or nothing; Xero has no client portal tied to the practice.
- **Expected behaviour:** `/portal` shell with simplified navigation; home "What needs you"; each item one click to act; all data read through the same services with tenant scoping; current revision shown with badge and link to superseded versions; explicit gating panels.
- **Gap #s closed:** 41 (package visible), 6/14 (explicit gating), supports D-03b revision visibility.
- **Business rules:** portal users see only their org; practice staff can "view as client" (read-only, audited); approvals respect A-03 limits; messages are per org thread with practice participants; e-signature evidence per O-02.
- **Edge cases:** user belongs to several orgs (org switcher in portal); trial/grace/read-only states (banner explaining state and action, not blocking reads); org with no practice (portal still works, practice sections hidden with explanation).
- **UI/UX notes:** max 6 nav items; large action cards; mobile-first; positive empty state "You're all caught up".
- **Dependencies:** O-02, O-03, O-04, P-02, P-03, G-09, U-03/U-04, FN-05 (loan view), D-03b, A-07.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| O-05-T01 | UX research note (owner jobs-to-be-done) + Figma portal shell, home, each section, mobile | UX | — | Reviewed with project lead | Design review |
| O-05-T02 | Portal route group `/portal` with shell layout, org switcher, 6-item nav, auth guard (OrganisationMember with portal flag) | FE | — | Non-member → 404 page | Playwright |
| O-05-T03 | `PortalActionFeed` aggregation service (pending approvals, signatures, document request items, tax payments awaiting approval, invoices awaiting approval/payment, subscription issues) with priority ordering | BE | O-02, O-03 | Feed lists all pending items from fixtures in order | Unit |
| O-05-T04 | API `/api/v1/portal/home/` (feed + KPI tiles: cash, owed to you, to pay, next deadline) | API | T03 | Org 2 data never returned | Integration + sweep |
| O-05-T05 | Home screen (action cards, KPI tiles, mini-calendar O-04-T16, "all caught up" state) | FE | T04 | Matches Figma; LCP < 1.5 s on fixture | Playwright + Lighthouse |
| O-05-T06 | Invoices section: list, current revision with RevisionBadge, superseded versions read-only with watermark, pay link copy | FE/API | D-03b | 101 shows "Revised → 101-1"; superseded watermark | Playwright |
| O-05-T07 | Tax payments section (read + approve/pay entry point into G-09 flow for authorised users) | FE | G-09 | Unauthorised role sees view-only | Playwright (RBAC) |
| O-05-T08 | Loans section [v2.1] (FN-05 summaries: balance, next payment, YTD interest) | FE/API | FN-05 | Figures equal FN-05 report | Integration |
| O-05-T09 | Subscription & package panel (package, products, renewal, trial days, founding badge, feature matrix, platform invoices) | FE/API | U-03, U-04 | Equals U-03 resolution | Integration (`gap-41`) |
| O-05-T10 | Messages: `PortalThread`, `PortalMessage` models (org, participants, body sanitised, attachments A-06) + API + UI with unread counts | DB/BE/FE | — | Message visible only to org + assigned practice | Integration + sweep |
| O-05-T11 | Approvals inbox: approve/reject items (bills, pay runs, tax payments, engagements) via existing approval services with A-03 limits | FE/BE | A-03 | $5,001 over limit refused with message | Integration |
| O-05-T12 | Signature UI (SignatureBlock, consent text, typed name, evidence summary) using O-02-T05 | FE | O-02 | Signed → engagement `engaged` | Playwright |
| O-05-T13 | Documents & requests section (O-03-T11 embedded) | FE | O-03 | Upload path works from portal | Playwright |
| O-05-T14 | Gated tiles: explicit gate panel with package names and compare link (never redirect) | FE | U-03 | No portal route returns redirect for gated feature | Playwright (`gap-06`) |
| O-05-T15 | State banners for trial / grace / read-only (explain + action) | FE | U-05, U-04 | Read-only org can still view and export | Playwright |
| O-05-T16 | "View as client" for practice staff (read-only session flag, audited, banner) | BE/FE | A-04 | Write attempts blocked; audit entry written | Integration |
| O-05-T17 | Notification preferences per portal user (email/in-app per event type) | BE/FE | A-07 | Opt-out respected | Integration |
| O-05-T18 | i18n (language per user), mobile responsive pass, axe pass | FE | all | 0 serious axe; 360 px no horizontal scroll | Playwright mobile |
| O-05-T19 | Tests: portal tenant sweep (every portal endpoint), RBAC per portal role | QA | all | Sweep green | Security suite |
| O-05-T20 | Docs: "Your Numo9 portal" owner guide | DOC | all | Merged | Review |

- **Deliverable acceptance:** client sees only own org; current revision shown with badge; subscription panel equals entitlement data.
- **Testing:** security sweep, functional (F5, approvals), usability tasks §3.6, performance.
- **Risks:** feature creep in portal → scope fixed to the listed sections; aggregation slowness → cached feed per org invalidated by domain events.

### O-06 · Staff task board
- **Branch:** `feature/O-06-task-board`
- **Objective:** tasks per staff member and organisation, created manually or generated from engagements, document requests and deadlines.
- **Current behaviour:** none (Xero home "Tasks" widget is a simple list without org/staff dimension).
- **Expected behaviour:** board (To do / Doing / Waiting on client / Done) and list; filter by staff and org/group; due dates; checklist; links to source (engagement, deadline, request); bulk reassign; workload per staff feeds V-04.
- **Business rules:** task belongs to a practice and optionally an org; assignee must have access to that org; generated tasks idempotent per source; completing a source (e.g. deadline paid) can auto-complete linked tasks (configurable).
- **Edge cases:** assignee loses org access → task flagged "needs reassignment"; deleted source → task keeps snapshot label.
- **UI/UX notes:** keyboard `n`, `j/k`, `x`; quick-add with natural due date ("fri", "2026-11-14"); "My tasks" default view.
- **Dependencies:** O-02, O-03, O-04, V-02, V-05.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| O-06-T01 | Figma board/list/quick-add | UX | — | Reviewed | Design review |
| O-06-T02 | `PracticeTask` model (practice, org?, title, description, status, assignee, due_date, priority, source_type/source_id, checklist JSON, completed_at) + migration | DB | — | Migration clean | Migration test |
| O-06-T03 | Task service (create, move, assign with access check, complete, idempotent generate from source) | BE | T02 | Assign to user without org access refused | Unit |
| O-06-T04 | Generators: from engagement deliverables (O-02-T08 event), from deadlines due in N days (O-04), from document requests needing review | BE | T03 | One task per source; re-run 0 new | Integration |
| O-06-T05 | Auto-complete rule on source completion (setting per practice) | BE | T04 | Deadline paid → linked task done when rule on | Integration |
| O-06-T06 | Access-loss handler: on assignment revocation flag tasks "needs reassignment" | BE | T03, A-01 | Flag set within same request cycle | Integration |
| O-06-T07 | API `/api/v1/practice/tasks/` (+ bulk reassign) with filters staff/org/group/status/due | API | T03 | Filters correct; sweep passes | Integration + sweep |
| O-06-T08 | Board UI (dnd-kit, keyboard, columns, WIP counts) | FE | T07 | Keyboard-only move works | Playwright + axe |
| O-06-T09 | List UI + quick-add with natural-date parsing (`chrono-node`) | FE | T07 | "fri" resolves to next Friday in org TZ | Unit (Vitest) + Playwright |
| O-06-T10 | Bulk select + reassign with preview and per-row result (V-03 pattern) | FE/BE | T07 | 50 tasks reassigned; per-row results | Integration |
| O-06-T11 | Workload widget data for V-04 (open tasks per staff, overdue) | BE | T07 | Counts equal list | Integration |
| O-06-T12 | i18n, shortcuts in A-09 help, audit hooks | FE/BE | all | Lint passes | CI |
| O-06-T13 | Tests: filters by staff and org (acceptance), generator idempotency | QA | all | Green | pytest |

- **Deliverable acceptance:** tasks filter by staff and org; generated tasks never duplicate.
- **Testing:** unit, integration, functional, a11y.
- **Risks:** task noise from generators → per-practice generator toggles and lead time setting.

### 6.2 Component P — Online Payments

### P-01 · Stripe connection
- **Branch:** `feature/P-01-stripe-connection`
- **Objective:** connect organisations (and practices, for service sales) to Stripe so they can accept their own customers' payments; keep the platform account (U-04) for Numo9 subscriptions; support test/live modes and PAD (ACSS Debit).
- **Current behaviour:** only the platform account exists (subscriptions).
- **Expected behaviour (better than Xero):** guided Connect Express onboarding embedded in Numo9 (embedded onboarding components), live status always visible with Stripe's requirement messages translated to plain language; payment health read from local tables so the dashboard card never fails to load (gap #5); clearing account `Stripe Clearing` created automatically (F-01 type Clearing); fee expense account mapping; payout reconciliation [EXTRA E8].
- **Gap #s closed:** 5, 6.
- **Business rules:** one active `PaymentGatewayAccount` per org (and per practice); test and live keys separated by environment, live only in production; secrets encrypted; webhook endpoints verified by signature; events processed exactly once (`StripeEvent` table keyed by event ID); fees posted to configured fee account; organisations are the merchant of record.
- **Edge cases:** onboarding abandoned; account restricted later (requirements due) → banner + email; disconnect while payments pending (refused until settled); currency other than CAD (R-02 FX).
- **UI/UX notes:** Settings ▸ Payments: 3-step indicator (Connect → Verify → Choose methods), status panel with next action, methods toggles (Card, Apple Pay/Google Pay, PAD), accounts mapping (clearing, fees).
- **Dependencies:** U-04, F-01, C-01, A-05, A-07, S-03.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| P-01-T01 | ADR-005 Stripe Connect topology (Express + direct charges; Standard OAuth alternative; application fee default 0) | DOC | — | ADR approved by project lead | Review |
| P-01-T02 | Figma: Payments settings, onboarding steps, status panel, health card | UX | — | Reviewed | Design review |
| P-01-T03 | `PaymentGatewayAccount` model (owner org or practice, provider stripe, stripe_account_id, mode test/live, charges_enabled, payouts_enabled, requirements JSON, methods enabled, clearing_account, fee_account, status) + migration | DB | — | One active per owner enforced | Migration test |
| P-01-T04 | `OrgPaymentGateway` service interface + `StripeConnectGateway` impl (create account, account link / embedded session, refresh status) | BE | T03 | Test-mode account created and stored | Integration (stripe-mock + test mode) |
| P-01-T05 | Secrets & config: environment-separated keys, encrypted storage of any per-org keys (Standard mode), key rotation command | BE/OPS | S-03 | gitleaks clean; keys never logged | Security test |
| P-01-T06 | Webhook endpoint `/webhooks/stripe/connect/` with signature verification, `StripeEvent` (event_id unique, type, payload, processed_at, attempts) and Celery dispatcher | BE | T03 | Replayed event processed once | Integration (Stripe CLI replay) |
| P-01-T07 | Handlers `account.updated`, `capability.updated` → status/requirements refresh; notify org admin when restricted | BE | T06 | Restricted account → banner + email | Integration |
| P-01-T08 | Auto-create `Stripe Clearing` (type Clearing) and `Payment processing fees` accounts on connect, mapped by C-01 template codes; editable mapping | BE | T04, C-01 | Accounts exist once; renumberable | Integration |
| P-01-T09 | Payout handler `payout.paid` → JE Dr bank / Dr fees / Cr Stripe Clearing using balance transactions; `StripePayout` record | BE | T06, T08 | Clearing nets to 0 after payout on fixture | Integration |
| P-01-T10 | Payout ↔ bank statement auto-match suggestion (F-05) by amount ± 0.00 and date window 3 days [EXTRA E8] | BE | T09, F-05 | Imported payout line suggested once | Integration |
| P-01-T11 | `reconcile_stripe_clearing` command + report (clearing balance vs Stripe balance) | BE | T09 | Report difference 0.00 on fixture | Integration |
| P-01-T12 | Health card data: local aggregates (last 30 days volume, pending, failed, last webhook at) + background ping; never calls Stripe on render | BE | T06 | Stripe down → card renders cached data + reason | Integration (`gap-05`) |
| P-01-T13 | API `/api/v1/payments/gateway/` (status, start onboarding, refresh, methods, mapping), permission `payments.gateway.manage`, feature key `accounting.online_payments` | API | T04–T12 | Gated org → explicit 402 | Integration |
| P-01-T14 | Settings ▸ Payments UI with embedded Connect onboarding, step indicator, plain-language requirements, methods toggles, account mapping | FE | T13 | Onboarding completes in test mode | Playwright (test mode) |
| P-01-T15 | Online-payments status card on Sales overview / dashboard (states: not connected, onboarding, active, restricted, unreachable) | FE | T12 | All states in Storybook | Visual regression |
| P-01-T16 | Disconnect flow (refused while payments pending; confirm dialog) | FE/BE | T13 | Pending payment → refusal message | Integration |
| P-01-T17 | Practice Connect account (same service, owner practice) for P-03 | BE/FE | T04 | Practice can onboard | Integration |
| P-01-T18 | Metrics `payments_webhook_lag_seconds`, `stripe_events_failed_total`; Sentry tags | OPS | T06 | Visible in Grafana | Manual check |
| P-01-T19 | Test-mode end-to-end checkout harness (fixture org, test card 4242…, test PAD account) | QA | T14 | Harness passes in CI | Playwright |
| P-01-T20 | Docs: admin guide "Accept online payments", runbook "Stripe webhook failures" | DOC | all | Merged | Review |

- **Deliverable acceptance:** test-mode checkout end to end on both platform (subscription) and Connect (invoice) accounts; webhook replay → no duplicate; clearing reconciles after payout.
- **Testing:** integration with stripe-mock + Stripe test mode, security (signature, secrets), functional, resilience (Stripe down).
- **Risks:** Connect onboarding rejection → assisted messaging + support link; fee/topology change → ADR-005, gateway interface.

### P-02 · Invoice payment
- **Branch:** `feature/P-02-invoice-payment`
- **Objective:** a public, tokenised pay page for every approved invoice that always charges the current revision's balance due, posts and allocates the payment, and issues a receipt.
- **Current behaviour:** payments recorded manually (D-05).
- **Expected behaviour:** `/pay/<token>` page; Stripe Payment Element (card, Apple/Google Pay, PAD); amount = current revision balance (partial payments allowed if org enables); superseded revision link → 302 to current with banner; on success: D-05 payment created against current revision, JE Dr Stripe Clearing / Cr AR, receipt email (contact language) and PDF; idempotent across webhook and client confirmation; FX via R-02 for USD invoices.
- **Gap #s closed:** 5, 11, 42.
- **Business rules:** token is random (≥ 128 bits), scoped to invoice chain, revocable, optional expiry; paid/voided invoices show status, no charge; amount cannot exceed balance; payment intent metadata includes org, invoice chain, revision, idempotency key; one PaymentIntent per (revision, balance snapshot); PAD payments are "processing" until succeeded (AR reduced only on success; shows "payment pending" on invoice).
- **Edge cases:** invoice revised while payer is on the page (server re-validates at confirm; if changed → page refreshes with banner, no charge); 3-D Secure; PAD failure after days (reverse allocation, notify); dispute (P-05); duplicate tabs.
- **UI/UX notes:** mobile-first, org branding, invoice summary collapsible, line items expandable, one primary button "Pay $1,017.00", trust note, receipt view with download.
- **Dependencies:** P-01, D-03a, D-03b, D-05, R-02, A-07, X keys.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| P-02-T01 | Figma: pay page (mobile/desktop), states (paid, partially paid, superseded banner, voided, expired, gateway down, processing PAD), receipt | UX | — | Reviewed | Design review |
| P-02-T02 | `InvoicePayLink` model (invoice chain root, token hash, created_by, expires_at, revoked_at, allow_partial) + migration; tokens stored hashed | DB | — | Token lookup by hash only | Unit |
| P-02-T03 | Link resolver: token → chain → current revision; superseded → redirect target; voided/paid → status | BE | T02, D-03b | 101 link resolves 101-1 | Unit |
| P-02-T04 | `OnlinePayment` model (org, invoice revision, payment_intent_id unique, amount, currency, method, status requires_payment/processing/succeeded/failed/refunded/disputed, idempotency_key unique, d05_payment FK) + migration | DB | P-01 | Unique constraints enforced | Migration test |
| P-02-T05 | Create/refresh PaymentIntent on connected account (direct charge) with amount = balance snapshot, metadata, idempotency key `org:rev:balance_hash` | BE | T04 | Two calls → same intent | Integration (test mode) |
| P-02-T06 | Confirm-time re-validation: revision/balance unchanged else cancel intent and return `revision_changed` | BE | T05 | Revision during checkout → no charge | Integration |
| P-02-T07 | Webhook handlers `payment_intent.succeeded/processing/payment_failed` → status, D-05 payment + allocation to current revision, JE to Stripe Clearing; exactly once | BE | T04, P-01-T06 | Replay ×3 → one payment | Integration |
| P-02-T08 | PAD async handling: processing state on invoice ("Payment pending"), failure → reverse allocation and notify org + payer | BE | T07 | Failed PAD restores AR | Integration (test clock) |
| P-02-T09 | FX: foreign-currency invoices charged in invoice currency; realised FX on payout via R-02 | BE | T07, R-02 | USD fixture posts FX gain/loss | Integration (`gap-11`) |
| P-02-T10 | Receipt: PDF (Letter/inch, EN/FR keys) stored in org Documents, emailed from org domain in contact language | BE | T07, A-07 | Receipt in Mailpit with FR key for FR contact | Integration (`gap-42`) |
| P-02-T11 | Public endpoints `/api/public/pay/<token>/` (GET summary, POST intent, GET status) with rate limiting, no auth, minimal data exposure | API | T03–T07 | No PII beyond invoice face; rate limit 30/min | Security test |
| P-02-T12 | Pay page UI with Payment Element, branding, line items, primary pay button with amount, live status region | FE | T11 | Card 4242 test payment succeeds | Playwright (test mode) |
| P-02-T13 | Superseded banner + redirect handling; paid/voided/expired/gateway-down states | FE | T11 | Each state renders per Figma | Playwright |
| P-02-T14 | Receipt screen + "download receipt" | FE | T10 | Download equals stored PDF | Playwright |
| P-02-T15 | Org-side: invoice page shows online payments, pending PAD, link management (copy, revoke, regenerate, expiry) | FE | T02 | Revoked link → expired state | Playwright |
| P-02-T16 | Security: CSP for Stripe domains only, no card data in logs, ZAP scan on pay page | QA | T12 | ZAP no high | Security suite |
| P-02-T17 | Accessibility & mobile pass (axe, 360 px, screen-reader announcement of status) | QA | T12 | axe 0 serious | Playwright + axe |
| P-02-T18 | Tests: AR decreases by exactly payment; property test random revisions + payments keeps AR = sum open current revisions | QA | T07 | Property test 1,000 runs green | Hypothesis |
| P-02-T19 | Docs: "Get paid online" guide | DOC | all | Merged | Review |

- **Deliverable acceptance:** payment posts and allocates; old revision link → current; webhook replay no duplicate; AR change = payment amount.
- **Testing:** integration (test mode), property (AR), security (ZAP, data exposure), functional (F3), a11y.
- **Risks:** race between revision and payment → confirm-time revalidation + row lock on invoice chain; PAD delays → explicit pending state.

### P-03 · Pay-per-service checkout
- **Branch:** `feature/P-03-service-checkout`
- **Objective:** an organisation buys a practice service from the portal; checkout on the practice's Connect account creates the practice's invoice + payment and the organisation's paid bill, and starts an engagement.
- **Current behaviour:** none.
- **Expected behaviour:** portal shop of portal-visible services (O-01); Stripe Checkout (card/PAD) on practice account; on success: practice-side invoice (D-03a) + payment (D-05) in the practice billing org; org-side bill (E-02) marked paid with supplier = practice contact; engagement (O-02) created; receipt.
- **Business rules:** price snapshot at session creation; tax via G-02 (practice registrations, org province); one fulfilment per Checkout session (idempotent on session ID); org-side bill creation optional per org setting (default on).
- **Edge cases:** practice not onboarded to Connect (shop shows "Contact your accountant to buy", no checkout); price changed mid-session; checkout expired; org without Accounting product (bill skipped, notice).
- **UI/UX notes:** service cards with price, billing type, what's included, "Buy" → Checkout → success page linking to engagement.
- **Dependencies:** O-01, O-02, P-01-T17, D-03a, D-05, E-02, G-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| P-03-T01 | Figma: portal shop, service detail, success/failure pages | UX | — | Reviewed | Design review |
| P-03-T02 | `ServicePurchase` model (org, practice, service, price snapshot, tax snapshot, checkout_session_id unique, status, invoice FK, bill FK, engagement FK) + migration | DB | O-01 | Unique session | Migration test |
| P-03-T03 | Checkout session creation on practice Connect account with tax lines from G-02, success/cancel URLs, idempotency key | BE | T02, P-01-T17 | Session created in test mode | Integration |
| P-03-T04 | Fulfilment handler `checkout.session.completed` / `async_payment_succeeded` → practice invoice + payment (D-03a/D-05) | BE | T03 | One invoice per session even on replay | Integration |
| P-03-T05 | Org-side bill creation (E-02) from practice invoice, marked paid via Stripe clearing/card account mapping; setting toggle | BE | T04 | Bill exists, paid, supplier = practice | Integration |
| P-03-T06 | Engagement auto-creation (O-02) from purchase, status `engaged` (purchase = acceptance) with letter if template requires signature | BE | T04, O-02 | Engagement linked | Integration |
| P-03-T07 | Failure/expiry handling (`checkout.session.expired`, async failure) → status + notify | BE | T03 | Expired session leaves no records | Integration |
| P-03-T08 | Portal API `/api/v1/portal/services/` (list portal-visible, buy) | API | T03 | Archived/internal services not listed | Integration |
| P-03-T09 | Portal shop UI + detail + success page | FE | T08 | F6 flow passes | Playwright (test mode) |
| P-03-T10 | Practice view: purchases list with status and links | FE | T02 | List equals records | Playwright |
| P-03-T11 | Not-onboarded and gated states (explicit messages) | FE | T08 | No silent redirect | Playwright |
| P-03-T12 | Tests: acceptance "checkout creates invoice and payment"; tax correct for ON org (HST 13 %) and QC org (GST+QST) | QA | all | Green | pytest + Playwright |
| P-03-T13 | Docs: "Sell your services through the portal" | DOC | all | Merged | Review |

- **Deliverable acceptance:** checkout creates invoice and payment (practice side), bill (org side), engagement.
- **Testing:** integration (test mode), functional F6, data validation (both ledgers balance).
- **Risks:** two ledgers to post → single fulfilment transaction per side with outbox; tax mistakes → G-02 reuse + fixtures.

### P-04 · PAD mandates & recurring billing
- **Branch:** `feature/P-04-pad-mandates`
- **Objective:** organisations collect from their customers by pre-authorised debit (ACSS Debit) with stored mandates and automatic charges for recurring invoices (D-04).
- **Current behaviour:** recurring invoices (D-04) are generated but not auto-collected.
- **Expected behaviour:** customer authorises PAD once on a mandate page (Stripe SetupIntent, Canadian PAD agreement wording handled by Stripe); mandate reference stored at Stripe only (Numo9 stores mandate ID, status, last4/bank name display only); recurring invoice tick → charge mandate for current revision balance → P-02 posting path; card-on-file alternative.
- **Gap #s closed:** 13.
- **Business rules:** mandate per (org, contact, method); charge only on approved invoices with auto-collect enabled; one charge attempt per invoice revision per day; failure retries per org setting (default 2 retries, 3 days apart) then notify; PCI/PAD data never stored by Numo9.
- **Edge cases:** mandate revoked by customer (webhook `mandate.updated`) → auto-collect off + notify; invoice revised after charge processing (handled by P-02-T06 revalidation; if processing, revision allowed and difference becomes credit/balance); micro-deposit verification pending.
- **UI/UX notes:** contact page "Payment method on file" panel; invoice/recurring editor toggle "Collect automatically"; mandate page for payer (mobile-first).
- **Dependencies:** P-01, P-02, D-04, B-01.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| P-04-T01 | Figma: mandate setup page, contact panel, auto-collect toggle | UX | — | Reviewed | Design review |
| P-04-T02 | `PaymentMandate` model (org, contact, stripe_customer_id, payment_method_id, mandate_id, method acss_debit/card, status, display_last4, bank_name, revoked_at) + migration | DB | P-01 | No raw bank data columns | Schema review + test |
| P-04-T03 | Stripe Customer per contact on connected account (idempotent create) | BE | T02 | One customer per contact | Integration |
| P-04-T04 | SetupIntent flow (ACSS Debit with micro-deposit/instant verification; card) via public tokenised mandate link | BE/API | T03 | Test-mode mandate becomes active | Integration (test mode) |
| P-04-T05 | Handlers `setup_intent.succeeded`, `mandate.updated`, `payment_method.detached` → mandate status | BE | T04 | Revoked mandate → auto-collect disabled + notify | Integration |
| P-04-T06 | Auto-collect setting on contact, recurring template (D-04) and invoice | DB/BE | D-04 | Setting persisted and inherited | Unit |
| P-04-T07 | Charge job: after recurring invoice approval, create off-session PaymentIntent (reuse P-02-T05) with idempotency `mandate:rev:date` | BE | T05, P-02 | One charge per revision per day | Integration (test clock) |
| P-04-T08 | Retry policy + failure notifications (org + payer) | BE | T07 | Retries at configured intervals; stops after max | Integration |
| P-04-T09 | Mandate setup page UI (public) + success | FE | T04 | Test PAD verification completes | Playwright |
| P-04-T10 | Contact "Payment method on file" panel (status, last4, send setup link, remove) + invoice toggle | FE | T05, T06 | Matches Figma | Playwright |
| P-04-T11 | Security review: no mandate/bank numbers stored or logged | QA | T02–T08 | grep + log scan clean | Security test |
| P-04-T12 | Tests: recurring invoice auto-charges once per tick after worker restart (`gap-13`) | QA | T07 | Green | Integration |
| P-04-T13 | Docs: "Collect by pre-authorised debit" | DOC | all | Merged | Review |

- **Deliverable acceptance:** mandate stored at Stripe only (PCI out of scope); recurring charge once per tick.
- **Testing:** integration with Stripe test clocks, security, functional.
- **Risks:** PAD return codes days later → P-02-T08 reversal; consumer protection rules → Stripe-hosted mandate text.

### P-05 · Refunds & disputes
- **Branch:** `feature/P-05-refunds-disputes`
- **Objective:** refund online payments (full/partial) and handle disputes with correct ledger postings and evidence submission.
- **Current behaviour:** none.
- **Expected behaviour:** refund from the online payment or invoice; posting reverses the payment (Cr Stripe Clearing / Dr AR or customer credit via D-06 refund path); disputes tracked with deadline, evidence upload (invoice PDF, revision history, receipts, communications) submitted to Stripe; dispute lost → reversal + dispute fee to fee account; won → reinstated.
- **Business rules:** refund ≤ captured − already refunded; permission `payments.refund` with A-03 amount limits; refund in a locked period posts in the open period with reference (A-05); all actions audited.
- **Edge cases:** refund on PAD still processing (refused); partial refund after revision; dispute on a payment already refunded.
- **UI/UX notes:** Refunds & disputes list with "Needs response by" countdown; refund dialog with amount, reason, posting preview.
- **Dependencies:** P-02, P-03, D-05, D-06, A-03, A-05.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| P-05-T01 | Figma: list, refund dialog with posting preview, dispute detail with evidence checklist | UX | — | Reviewed | Design review |
| P-05-T02 | `OnlineRefund` (payment, amount, reason, stripe_refund_id unique, status, je FK) and `PaymentDispute` (payment, stripe_dispute_id unique, reason, amount, status, evidence_due_by, outcome, fee) models + migration | DB | P-02 | Unique IDs | Migration test |
| P-05-T03 | Refund service: validate limits/permissions, create Stripe refund (idempotency), posting reversal via D-05/D-06, locked-period rule | BE | T02 | Refund reverses payment posting exactly | Integration |
| P-05-T04 | Handlers `charge.refunded`, `refund.updated` (incl. refunds created in Stripe dashboard) → reconcile local records | BE | T03 | Dashboard-created refund appears once | Integration |
| P-05-T05 | Dispute handlers `charge.dispute.created/updated/closed` → status, notifications, posting on lost (reverse + fee), reinstate on won | BE | T02 | Lost dispute posts reversal + fee | Integration |
| P-05-T06 | Evidence pack builder (invoice PDF current revision + revision history, receipt, emails log, signed engagement if service) and submit to Stripe | BE | T05 | Evidence uploaded in test mode | Integration |
| P-05-T07 | API `/api/v1/payments/refunds/`, `/disputes/` + permissions | API | T03–T06 | Over-limit refund refused 403 with reason | Integration |
| P-05-T08 | UI: list with countdown, refund dialog with posting preview, dispute detail | FE | T07 | Matches Figma | Playwright |
| P-05-T09 | Dashboard/notification: dispute needs response | BE/FE | T05 | Notification within one job cycle | Integration |
| P-05-T10 | Tests: refund > remaining refused; PAD processing refund refused; locked period behaviour | QA | all | Green | pytest |
| P-05-T11 | Docs + runbook "Responding to a dispute" | DOC | all | Merged | Review |

- **Deliverable acceptance:** refund reverses payment posting; disputes post correctly on outcome.
- **Testing:** integration (Stripe triggers), data validation (clearing reconciliation), RBAC.
- **Risks:** dashboard-side actions bypassing Numo9 → webhook reconciliation; fee mapping wrong → posting preview.

### P-06 · Tax-payment provider adapter
- **Branch:** `feature/P-06-tax-payment-provider`
- **Objective:** a `TaxPaymentProvider` interface with `quote()`, `initiate()`, `status()`, `cancel()` so G-09 never depends on a specific provider; ship a sandbox stub, the bank bill-payment file fallback and the production adapter per ADR-003.
- **Current behaviour:** none (Xero offers no tax payment at all).
- **Expected behaviour:** provider registry selects the provider configured per organisation; stub drives the full state machine in CI (initiated → submitted → confirmed / failed / cancelled, with configurable delays and forced outcomes); bank-file provider generates a CRA/RQ bill-payment file (CPA 005 credit or bank's bulk bill-payment CSV) for upload to online banking, then confirmation is recorded; production provider plugs in without UI change.
- **Business rules:** every call carries the G-09 idempotency key; provider responses stored raw (encrypted) and normalised; credentials platform-level, encrypted; timeouts 10 s; retries with backoff only for idempotent operations; amounts in cents integers at the boundary; payee program accounts validated (BN 9 digits + RT/RP/RC + 4 digits).
- **Edge cases:** provider returns unknown status (→ `needs_review`); timeout after initiate (status poll, never re-initiate without same key); cancel after submit (provider may refuse → shown).
- **UI/UX notes:** Settings ▸ Tax payment route: radio cards (Provider / Bank file / Assisted only), status of provider, test connection button.
- **Dependencies:** S-03, A-08, ADR-003 (client input).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| P-06-T01 | ADR-003 draft (options: CRA-accepted third-party provider, bank bill-payment file, assisted-only; decision recorded when client chooses) | DOC | — | ADR file with decision status | Review |
| P-06-T02 | Interface `TaxPaymentProvider` (abstract): `quote(obligation) → Quote`, `initiate(request, idempotency_key) → ProviderPayment`, `status(ref) → ProviderStatus`, `cancel(ref) → CancelResult`; dataclasses with typed money (int cents) | BE | — | mypy strict passes | Unit |
| P-06-T03 | Normalised status enum + mapping table (provider-specific → initiated/submitted/confirmed/failed/cancelled/needs_review) | BE | T02 | Unknown maps to needs_review | Unit |
| P-06-T04 | `ProviderRegistry` (by key, per-org config, feature flag) + `TaxPaymentRouteConfig` model (org, route provider/bank_file/assisted_only, provider_key, source_account default) + migration | DB/BE | T02 | Org config resolves provider | Unit |
| P-06-T05 | `ProviderCall` log model (org, operation, idempotency_key, request hash, response encrypted, status, latency) + migration | DB | T02 | Every call logged; secrets redacted | Unit |
| P-06-T06 | Program-account validator (BN checksum Luhn-style per CRA, program identifiers RT/RP/RC configurable as data, reference number format) | BE | — | Invalid BN rejected with message | Unit (fixtures) |
| P-06-T07 | `StubTaxPaymentProvider` (deterministic; controls: delay, forced outcome, fail-on-nth; respects idempotency) | BE | T02 | Same key twice → same ref | Unit |
| P-06-T08 | Stub control panel (Django admin page + management command) to force Confirmed/Failed/Pending for demos | BE/OPS | T07 | Admin action changes stub status | Manual + integration |
| P-06-T09 | `provider-stub` docker-compose service exposing stub over HTTP (to exercise HTTP client path) | OPS | T07 | Compose up; health 200 | Integration |
| P-06-T10 | HTTP client base (httpx, timeout 10 s, tenacity retries on idempotent ops, mTLS option, request signing hook) | BE | T02 | Timeout raises typed error; no retry on initiate without key | Unit (respx) |
| P-06-T11 | `BankBillPaymentFileProvider`: generate file (CPA 005 credit or configurable bank CSV) with payee CRA/RQ and remittance reference; file stored in Documents; status `submitted` on download, `confirmed` on user confirmation | BE | T02, E-06 CPA 005 lib | File validates against CPA 005 layout | Unit (layout validator) |
| P-06-T12 | Production provider adapter skeleton per ADR-003 (behind feature flag; contract tests from provider sandbox when available) | BE | T01, T10 | Contract test suite runs against sandbox or is reported "not executed — no provider" | Integration |
| P-06-T13 | Status poller job (every 5 min for submitted, backoff to 1 h after 24 h; stop at final) | BE | T03, A-08 | Poller moves stub payment to confirmed | Integration |
| P-06-T14 | Provider webhook endpoint (if provider supports) with signature verification and dedupe | BE | T05 | Replay processed once | Integration |
| P-06-T15 | Route settings API + UI (radio cards, test connection, default source account) | API/FE | T04 | Test connection shows provider health | Playwright |
| P-06-T16 | Contract test suite every provider must pass (idempotency, status transitions, cancel semantics, amount rounding) | QA | T07, T11 | Stub and bank-file pass | pytest parametrised |
| P-06-T17 | Import-linter contract: `taxpayments` imports only `providers.interface` | QA | T02 | CI fails on direct adapter import | CI |
| P-06-T18 | Security: credentials encrypted, provider logs redacted, semgrep rule | QA | T05 | Scan clean | Security suite |
| P-06-T19 | Docs: provider integration guide (how to add an adapter) + runbook | DOC | all | Merged | Review |

- **Deliverable acceptance:** swapping providers changes no G-09 screen; stub drives the full state machine in CI.
- **Testing:** unit, contract suite, integration (HTTP stub), resilience (timeouts), security.
- **Risks:** no provider contracted by go-live → bank-file + assisted routes still complete G-09; provider API changes → adapter isolated + contract tests.

### 6.3 Components G and D

### G-09 · Tax Payments
- **Branch:** `feature/G-09-tax-payments`
- **Objective:** list every tax amount owing by registration and period and pay or record it from Numo9 with idempotency, status tracking, confirmation, posting, reminders and receipts.
- **Current behaviour:** liabilities exist in the ledger (G-03/G-04 returns, N-07 remittances, G-08 instalments) but payment is outside the system; Xero has no tax payment.
- **Expected behaviour:** Tax Payments screen with tabs Owing / Scheduled / In progress / Paid; obligations from GST/HST net tax (G-03 line 109/113 balance), QST (G-04), payroll source deductions by remittance due date (N-07: CPP + EI + income tax, employee+employer), corporate instalments and balance due (G-08), provincial payroll taxes where configured; pre-flight checklist [EXTRA E2]; provider route (P-06) and assisted route (deep link + record); schedule for due date [EXTRA E1]; posting Dr liability / Cr bank or clearing; receipt PDF in Documents; N-07 calendar marked paid; O-04 deadline paid; approval limits; step-up 2FA above threshold.
- **Gap #s closed:** none in matrix (beyond-Xero decision 10); supports gap #4 deadlines.
- **Business rules:** one active payment per obligation (DB partial unique index on obligation where status in initiated/submitted/confirmed/scheduled); amount defaults to obligation balance; partial payments allowed (balance remains owing); overpayment only via explicit "record overpayment/credit"; liability account by obligation type (C-01 control accounts: GST/HST payable net of ITC receivable — posting to the net payable/clearing per G-03 close JE, QST payable, CPP/EI/income tax payable, corporate tax payable); period lock respected (A-05 — payment date in open Bank/Tax period); never files returns; refunds from CRA (negative net tax) shown as "refund expected" not payable.
- **Edge cases:** return not filed (warn not block); amount changed after scheduling (late adjustment) → scheduled payment flagged for review; provider failure on due date → assisted route suggestion; user already paid outside Numo9 → record path detects duplicate amount/date and asks; payroll remittance for accelerated remitters (several per month); stopped registration (G-03b) still shows final period owing.
- **UI/UX notes:** see F1/F2 flows, microcopy §3.5; obligation cards grouped by due date; review screen; status timeline; receipt.
- **Dependencies:** P-06, G-03, G-04, G-03a/b, G-08, N-07, F-01, C-02, A-03, A-05, A-06, A-07, A-08, O-04.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| G-09-T01 | UNDERSTAND note: obligation sources, posting rules per type, confirmed with project lead (accounting rules table) | DOC | — | Rules table approved | Review |
| G-09-T02 | Figma: Tax Payments tabs, obligation card, pre-flight checklist, review screen, assisted route panel, status timeline, receipt, portal variant | UX | — | Reviewed + usability script ready | Design review |
| G-09-T03 | `TaxObligation` read model (org, type gst_hst/qst/payroll_remittance/corp_instalment/corp_balance/prov_payroll, registration, program_account, period_start/end, due_at, amount_due, amount_paid, balance, source_ref, natural_key unique, status) + migration | DB | — | Unique natural key | Migration test |
| G-09-T04 | Obligation builder: GST/HST from G-03 worksheets (net tax, refund case), QST from G-04 | BE | T03, G-03, G-04 | Fixture period net 1,234.56 → obligation 1,234.56 | Unit |
| G-09-T05 | Obligation builder: payroll remittances from N-07 (per remitter type due dates, components CPP/CPP2/EI/tax employee+employer) | BE | T03, N-07 | PD7A-style fixture totals match | Unit |
| G-09-T06 | Obligation builder: corporate instalments and balance due from G-08; provincial payroll taxes (configurable, e.g. ON EHT if enabled) | BE | T03, G-08 | Fixture instalments match G-08 schedule | Unit |
| G-09-T07 | Obligation refresh on events (return marked filed, late adjustment, pay run posted, G-08 confirmed) + nightly; refresh never alters paid amounts | BE | T04–T06, A-08 | Late adjustment updates balance, paid unchanged | Integration |
| G-09-T08 | `TaxPayment` model (org, obligation, amount, currency CAD, route provider/bank_file/assisted, provider_key, provider_ref, status scheduled/initiated/submitted/confirmed/failed/cancelled/needs_review, scheduled_for, idempotency_key unique, confirmation_no, source_account, je FK, receipt doc FK, initiated_by, approved_by) + partial unique index (one active per obligation) + migration | DB | T03 | Second active payment → IntegrityError | Unit |
| G-09-T09 | `TaxPaymentEvent` append-only status history | DB | T08 | Every transition recorded | Unit |
| G-09-T10 | State machine service (allowed transitions, guards) | BE | T08, T09 | Parameterised transition matrix passes | Unit |
| G-09-T11 | Pre-flight service: return filed?, period locked?, ledger balance of source account ≥ amount?, approval required?, provider healthy?, program account valid? → list of checks with severity | BE | T04, P-06-T06 | Fixture shows each warning correctly | Unit |
| G-09-T12 | Idempotency: key = `org:obligation:amount_cents:attempt_no`; double submit returns existing payment | BE | T08 | Second click refused / returns same | Unit + concurrency test |
| G-09-T13 | Approval integration: amount over user's A-03 limit → `awaiting_approval`; approver ≠ initiator | BE | T10, A-03 | Self-approval impossible | Integration |
| G-09-T14 | Step-up 2FA for payments ≥ configurable threshold (default $10,000) | BE | A-02 | Without TOTP → 403 step_up_required | Integration |
| G-09-T15 | Provider route: initiate via registry (P-06) with obligation data, persist provider_ref, status `submitted`; error mapping to user messages | BE | T10, P-06 | Stub payment reaches submitted | Integration |
| G-09-T16 | Status updates from P-06 poller/webhook → `confirmed` with confirmation_no or `failed` with reason | BE | T15, P-06-T13 | Stub confirm moves to confirmed | Integration |
| G-09-T17 | Posting on confirmation: JE Dr liability (per type) / Cr source bank or clearing, dated payment date, book `both`, linked to payment; obligation paid amount updated | BE | T16, C-02 | 1,234.56 posts exactly; TB balanced | Integration |
| G-09-T18 | Bank-file route: generate file (P-06-T11), status submitted, "confirm when bank processed" action → confirmed + posting | BE | T15, P-06-T11 | Same posting as provider route | Integration |
| G-09-T19 | Assisted route: build deep link + copy payload (BN, program account, period end, amount), `record payment` endpoint (date, confirmation no., source account) → confirmed + same posting; duplicate-record detection (same obligation/amount within 7 days) | BE | T10, T17 | Assisted posting identical to provider posting | Integration |
| G-09-T20 | Scheduling: `scheduled_for` date, beat job initiates on date (provider route) or reminds (assisted), reminders 3 business days before and on due date [EXTRA E1] | BE | T15, A-08 | Scheduled stub payment initiates on date once | Integration (time-machine) |
| G-09-T21 | Change-after-schedule handling: obligation amount changed → scheduled payment `needs_review` + notify | BE | T07, T20 | Flag set; not auto-initiated | Integration |
| G-09-T22 | Cancel: allowed in scheduled/initiated (and submitted if provider allows); reverses nothing (not posted) | BE | T10 | Cancel confirmed payment refused | Unit |
| G-09-T23 | Failure handling: failed → obligation owing again, notify, suggest assisted route | BE | T16 | Failed stub → owing + notification | Integration |
| G-09-T24 | Receipt PDF (Letter/inch, EN/FR keys: obligation, period, program account, amount, route, confirmation no., JE ref) stored in Documents tagged with tax period | BE | T17, A-06 | Receipt stored once | Integration |
| G-09-T25 | Downstream sync: N-07 remittance marked paid; O-04 deadline status paid; G-03/G-04 period shows paid; events `tax_payment.confirmed` for W-01 | BE | T17 | Remittance calendar shows "paid" after confirmation | Integration |
| G-09-T26 | Audit entries for every action (initiate, approve, cancel, record, confirm) with actor/IP | BE | T10 | Audit viewer shows chain | Integration |
| G-09-T27 | API `/api/v1/tax-payments/obligations/`, `/payments/` (create, approve, cancel, record, status), permissions `tax.payments.view/initiate/approve`, feature key `tax.payments` (payroll obligations also require `payroll`) | API | T08–T25 | Gated org → 402 with product | Integration + sweep |
| G-09-T28 | Tax Payments screen: tabs, obligation cards grouped by due date, filters (type, registration, status), bulk select for schedule | FE | T27 | Matches Figma | Playwright |
| G-09-T29 | Pre-flight checklist component + review screen with amount-labelled pay button, disabled-on-click, live status region | FE | T11, T27 | Double click creates one payment | Playwright |
| G-09-T30 | Assisted route panel (copy buttons, deep link opens new tab, "I've paid — record it" form) | FE | T19 | F2 under 90 s in rehearsal | Playwright |
| G-09-T31 | Payment detail: status timeline (events), confirmation, receipt, JE link, cancel/retry | FE | T27 | Timeline equals events | Playwright |
| G-09-T32 | Portal variant (O-05-T07) and dashboard widget "Taxes due" (K-05) | FE | T27 | Widget totals = Owing tab | Integration |
| G-09-T33 | Notifications (due soon, needs approval, confirmed, failed) EN/FR keys, org domain | BE | A-07 | Emails in Mailpit | Integration |
| G-09-T34 | i18n keys incl. CRA/RQ terms (fr-CA keys: "versement", "acomptes provisionnels" placeholders for Phase 6), a11y pass | FE | all | Lint + axe pass | CI |
| G-09-T35 | Compliance fixtures: GST quarterly, QST monthly, regular/accelerated payroll remitter, annual GST filer instalments, corporate instalments | QA | T04–T06 | Fixture obligations match hand-computed answers | pytest fixtures |
| G-09-T36 | Acceptance tests: 1,234.56 via stub posts exactly and marks period paid; second pay refused; assisted route same posting; remittance calendar paid | QA | all | Green | pytest + Playwright |
| G-09-T37 | Concurrency test: 20 parallel pay requests for one obligation → 1 payment | QA | T12 | Exactly one row | Integration |
| G-09-T38 | Docs: accountant/owner guide "Pay your taxes from Numo9" with disclaimer (software, not tax advice); runbook "Provider outage on due date" | DOC | all | Merged | Review |

- **Deliverable acceptance:** a GST period net tax of 1,234.56 paid through the test provider posts exactly that to GST/HST payable and the chosen bank account, marks the period paid and stores the confirmation; a second "pay" for the same period is refused; the assisted route records the same posting; the payroll remittance calendar shows "paid" after confirmation.
- **Testing:** unit (state machine, builders), property (idempotency), integration (stub, bank file), concurrency, functional (F1/F2), security (RBAC, step-up, sweep), usability (§3.6).
- **Risks:** wrong liability account → rules table + fixtures + posting preview on review screen; provider unavailable → assisted route always available; user pays twice (inside and outside) → duplicate-record detection.

### D-08 · Online invoice pay link
- **Branch:** `feature/D-08-invoice-pay-link`
- **Objective:** put the P-02 pay link on invoice emails, PDFs (with QR [EXTRA E7]), portal and statements, following the current revision.
- **Current behaviour:** invoices emailed without payment option.
- **Expected behaviour:** "Pay now" button in invoice/reminder/statement emails; link + QR on PDF; link regenerated never on revision (same chain token); setting per org/contact to include or not.
- **Business rules:** included only when P-01 gateway active and invoice approved; superseded PDFs keep the same chain link (resolves to current).
- **Dependencies:** P-02, D-03a, D-07, B-02, A-07.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| D-08-T01 | Figma: email button block, PDF payment box with QR | UX | — | Reviewed | Design review |
| D-08-T02 | Auto-create chain pay link on invoice approval when gateway active | BE | P-02-T02 | One link per chain | Unit |
| D-08-T03 | Email templates (invoice, reminder, statement) include "Pay now" block (EN/FR keys) | BE | T02, A-07 | Mailpit shows button | Integration |
| D-08-T04 | PDF template payment box with URL + QR (`qrcode`), Letter/inch layout check | BE | T02 | QR decodes to link | Unit (decode) |
| D-08-T05 | Revision PDF keeps chain link; superseded banner handled by P-02 | BE | D-03b | 101 PDF QR → 101-1 page | Integration |
| D-08-T06 | Settings: include pay link (org default, contact override, per-invoice toggle) | DB/FE | — | Toggle respected in email/PDF | Playwright |
| D-08-T07 | Statement (B-02) pay link pays oldest-first allocation across open invoices (P-02 multi-invoice intent) | BE | P-02 | Allocation equals oldest-first | Integration |
| D-08-T08 | Invoice editor/viewer: copy link, QR preview, link status | FE | T02 | Copy works | Playwright |
| D-08-T09 | Tests + docs | QA/DOC | all | Green; merged | pytest |

- **Deliverable acceptance:** as P-02 — link delivered on invoice channels and follows the current revision.
- **Risks:** QR on dense invoices → reserved payment box in layout.

### 6.4 Component Q — Public Website (Numo9 product site)

Design rule for the whole component: the site is an **original Numo9 design** built from the client's brand assets (logo, yellow/black identity). No layout, copy, illustration or code is taken from any other company's site (including Xero or any GMA client site used as a quality reference). Yellow is used as a brand surface/accent with black text (contrast ≥ 7:1), never as text colour on white.

### Q-01 · Site design & content
- **Branch:** `feature/Q-01-website`
- **Objective:** the public Numo9 website that explains the products, shows live packages and pricing with the founding counter, and converts visitors into accountant sign-ups, trial organisations and demo users.
- **Current behaviour:** no website.
- **Expected behaviour:** pages — Home, Products (Accounting, Tax, Payroll, Inventory, Finance), Packages & Pricing (live from U-02 with monthly/annual toggle and feature matrix from U-01 = in-app matrix), Founding offer counter (U-08), For Accountants (free account, workspace), Demo (instant demo org U-07), Start free trial (U-05), Resources/Blog, About, Contact, Legal (Terms, Privacy/PIPEDA, Acceptable use, Cookies, Security); sign-up funnels for accountant and organisation; EN/FR routing ready (FR copy Phase 6).
- **Gap #s closed:** 61, 41 (public matrix).
- **Business rules:** prices and counter read live via public API with ISR revalidation (60 s) and a static fallback snapshot; prices displayed exclusive of GST/HST with note; sign-up creates practice or organisation via A-02/U-05 rules (one trial per BN/email); demo creation < 10 s (U-07); no tracking cookies without consent.
- **Edge cases:** counter reaches 1,000 (badge switches to "Founding offer closed" + strategy hook); price API down (static snapshot with "prices as of" date); package retired (removed at next revalidation).
- **UI/UX notes:** hero with single primary CTA "Start free trial" + secondary "Try the demo"; accountant path clearly separated ("I'm an accountant — free forever"); pricing table mobile = stacked cards with sticky package selector; FAQ; package recommender [EXTRA E11]; performance budgets §3.1.
- **Dependencies:** U-01, U-02, U-05, U-07, U-08, A-02, Q-03 (content), brand assets.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| Q-01-T01 | Content strategy & sitemap (audiences: accountants, owners; key messages: free for accountants, Canadian tax, revisions, never-locked bank, two books) — original wording | UX/DOC | — | Sitemap + message map approved | Review |
| Q-01-T02 | Brand system for web: tokens (yellow/black, neutrals, type scale, spacing), contrast audit, iconography style, illustration direction (original) | UX | brand assets | Token file; all pairs ≥ 4.5:1 | Stark/contrast check |
| Q-01-T03 | Wireframes (mobile + desktop) for every page and both funnels | UX | T01 | Reviewed | Design review |
| Q-01-T04 | Hi-fi Figma for Home, Products template, Pricing, For Accountants, Demo/Trial, Blog, Legal template | UX | T02, T03 | Approved by project lead / client | Design review |
| Q-01-T05 | `apps/web` route group setup: Next.js ISR, next-intl locale routing (`/en`, `/fr`, default en-CA), shared `@numo9/ui` + web tokens, security headers | FE | — | Build + deploy to staging | CI |
| Q-01-T06 | Public catalogue API `/api/public/v1/catalogue/` (packages, products, prices monthly/annual, feature matrix, founding remaining) cached 60 s | API | U-01, U-02, U-08 | JSON equals in-app matrix (`gap-61`) | Integration |
| Q-01-T07 | Static fallback snapshot generation at build + "prices as of" display when API unavailable | FE | T06 | API down → snapshot rendered | Playwright (network block) |
| Q-01-T08 | Layout components: header with locale switch, mega-nav (Products), footer (legal, status link [EXTRA E12]), cookie-less analytics hook | FE | T05 | Keyboard nav, axe 0 serious | Playwright + axe |
| Q-01-T09 | Home page (hero, product tiles, differentiators, accountant band, founding counter band, social proof placeholder for client-supplied genuine testimonials only, CTA band) | FE | T04, T06 | Lighthouse ≥ 90 all categories | Lighthouse CI |
| Q-01-T10 | Product page template ×5 (Accounting, Tax, Payroll, Inventory, Finance) driven by CMS blocks | FE | Q-03 | 5 pages render from CMS | Playwright |
| Q-01-T11 | Packages & Pricing page: monthly/annual toggle, package cards, full feature matrix (sticky header, expandable groups), GST/HST note, FAQ | FE | T06 | Matrix = in-app; mobile stacked cards | Playwright + visual |
| Q-01-T12 | Founding counter component (live remaining "x of 1,000 left", closed state) | FE | T06 | Counter = U-08 value | Integration |
| Q-01-T13 | Package recommender (3 questions → suggested package from live data) [EXTRA E11] | FE | T06 | Recommendation rules unit tested | Vitest |
| Q-01-T14 | For Accountants page (free account, workspace, portal, practice tools) + accountant sign-up CTA | FE | T04 | Renders; CTA → funnel | Playwright |
| Q-01-T15 | Accountant sign-up funnel (≤ 3 steps: account, practice name/province, verify email) via A-02 | FE/BE | A-02 | Completes; practice created free | Playwright |
| Q-01-T16 | Organisation trial funnel (≤ 3 steps: account, organisation + province + BN optional, package) via U-05; duplicate BN/email messages | FE/BE | U-05 | Trial sign-up to first screen < 2 min | Playwright timed |
| Q-01-T17 | "Subscribe now" path from pricing → U-04 Stripe Checkout | FE | U-04 | Test-mode subscription completes | Playwright (test mode) |
| Q-01-T18 | Demo page → instant demo org (U-07) with progress state | FE/BE | U-07 | Demo created < 10 s | Playwright timed |
| Q-01-T19 | Resources/Blog list + article template (CMS), About, Contact (Q-02 form), Legal template ×5 | FE | Q-03 | All pages render | Playwright |
| Q-01-T20 | Error pages (404 with search + key links, 500), redirects for root/legacy paths (gap #2 pattern) | FE | T05 | No dead ends | Playwright |
| Q-01-T21 | Original OG images per page (satori) and favicon set from logo | FE | T02 | OG validates | Manual + unit |
| Q-01-T22 | Performance pass: image optimisation (AVIF/WebP), font subsetting, JS budget 170 kB gz, no layout shift | FE | T09–T19 | Budgets met in Lighthouse CI | Lighthouse CI |
| Q-01-T23 | Accessibility pass WCAG 2.1 AA (focus order, landmarks, reduced motion, alt text, form labels) | QA | T09–T19 | axe 0 serious; manual SR smoke | axe + NVDA/VoiceOver |
| Q-01-T24 | i18n: all copy via CMS locale fields or message keys; pseudo-locale +30 % layout check | FE | all | No clipped text | Playwright pseudo-locale |
| Q-01-T25 | Content entry of client-supplied copy and legal pages (placeholder original copy marked "for client review" until supplied) | DOC | Q-03 | All pages have content | Review checklist |
| Q-01-T26 | Funnel analytics events (page → CTA → sign-up step → completed) without cookies | FE | Q-04 | Events visible in analytics | Manual |
| Q-01-T27 | Usability test with 3 visitors (find Payroll package, start trial) | QA | all | Metrics in §3.6 met | Moderated test |
| Q-01-T28 | Docs: website content-editing guide | DOC | Q-03 | Merged | Review |

- **Deliverable acceptance:** Lighthouse ≥ 90; WCAG 2.1 AA; trial sign-up to first screen < 2 min.
- **Testing:** E2E funnels, Lighthouse CI, axe, visual regression, network-failure fallbacks.
- **Risks:** copy late → placeholder original copy; brand contrast with yellow → token rules; IP risk → original design rule + review checklist "no copied assets".

### Q-02 · Lead capture & demo requests
- **Branch:** `feature/Q-02-leads`
- **Objective:** capture contact/demo/accountant-partnership enquiries, store them, route notifications, and attribute source/referral for the founding/marketing hooks (U-08).
- **Expected behaviour:** forms (Contact, Book a guided demo, Partner/accountant enquiry, Newsletter opt-in); `Lead` stored with UTM/referral; spam protection; routing rules (by type/province) to Platform Owner inbox and in-app console list; auto-reply EN/FR; CASL-compliant consent capture for newsletter.
- **Business rules:** consent explicit and timestamped (CASL); PII minimal; retention configurable; leads visible only to Platform Owner roles.
- **Dependencies:** Q-01, A-07, U-06, U-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| Q-02-T01 | Figma form designs (inline validation, success states) | UX | — | Reviewed | Design review |
| Q-02-T02 | `Lead` model (type, name, email, phone, company, province, message, utm_*, referral_code, consent flags + timestamp + text version, status, assigned_to) + migration (platform-level, not org-owned) | DB | — | Migration clean | Migration test |
| Q-02-T03 | Public endpoint `/api/public/v1/leads/` with validation, honeypot, Turnstile/hCaptcha verify, rate limit per IP | API | T02 | Bot submission rejected; 10/min limit | Integration |
| Q-02-T04 | Routing rules (type/province → recipients) + notification email + console entry | BE | T02, A-07 | Notification in Mailpit within 1 min | Integration |
| Q-02-T05 | Auto-reply templates EN/FR keys | BE | T04 | Auto-reply sent once | Integration |
| Q-02-T06 | UTM/referral capture on site (first-touch cookie-less via sessionStorage → form hidden fields) and on sign-up (U-08 hooks) | FE/BE | Q-01 | Lead and sign-up carry source | Playwright |
| Q-02-T07 | Forms UI (Contact, Demo request with preferred time, Partner enquiry, Newsletter) | FE | T03 | axe 0 serious | Playwright + axe |
| Q-02-T08 | Platform console leads list (status, assign, export CSV) | FE/BE | U-06 | Export equals list | Integration |
| Q-02-T09 | Retention job (delete/anonymise after configurable months) | BE | A-08 | Old leads anonymised | Integration |
| Q-02-T10 | Tests + docs | QA/DOC | all | Leads stored and notified | pytest |

- **Deliverable acceptance:** leads stored and notified.
- **Risks:** spam → captcha + honeypot + rate limit; CASL → explicit consent records.

### Q-03 · CMS
- **Branch:** `feature/Q-03-cms`
- **Objective:** a headless CMS in Django admin so the Platform Owner edits pages, blog posts, FAQs and legal pages without a deploy.
- **Expected behaviour:** `Page` with typed blocks (hero, feature grid, comparison, FAQ, CTA, rich text, image, product highlight, pricing embed), locale variants (en-CA, fr-CA), draft/scheduled/published with append-only revisions and rollback, live preview, media library on S3, on-publish ISR revalidation webhook.
- **Business rules:** only Platform Owner/Content Editor roles; rich text sanitised; slug unique per locale; published page change triggers revalidation within 60 s.
- **Dependencies:** A-03, A-06 storage, Q-01 block components.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| Q-03-T01 | Content model design (block schema JSON Schema per block type) | BE/UX | — | Schema reviewed | Review |
| Q-03-T02 | Models `Page`, `PageLocale`, `PageRevision` (append-only), `BlogPost`, `FAQItem`, `MediaAsset` + migrations | DB | T01 | Migration clean | Migration test |
| Q-03-T03 | Block validation service (JSON Schema) + rich-text sanitiser (nh3) | BE | T02 | Script tags stripped; invalid block rejected | Unit |
| Q-03-T04 | Admin UI: page editor with block inline forms, reorder, locale tabs, status, schedule | BE | T02 | Editor saves revision per save | Manual + integration |
| Q-03-T05 | Revisions: history list, diff view, rollback creates new revision | BE | T02 | Rollback restores content | Integration |
| Q-03-T06 | Scheduled publishing job | BE | A-08 | Page goes live at scheduled minute | Integration (time-machine) |
| Q-03-T07 | Public content API `/api/public/v1/cms/pages/<locale>/<slug>/`, blog, FAQ (published only, cached) | API | T02 | Draft never returned publicly | Integration |
| Q-03-T08 | Preview mode (signed token → Next.js draft mode) | FE/BE | T07 | Editor sees draft; public does not | Playwright |
| Q-03-T09 | Revalidation webhook on publish → Next.js on-demand ISR | BE/FE | T07 | Change visible < 60 s | Integration |
| Q-03-T10 | Media library (upload to S3, alt text required, image renditions) | BE | A-06 | Upload without alt text refused | Integration |
| Q-03-T11 | Role `content_editor` (platform level) + audit | BE | A-03, A-04 | Non-editor 403 | Integration |
| Q-03-T12 | Seed command importing initial page set (`cms_import`) + `cms_export` JSON | BE | T02 | Round-trip identical | Unit |
| Q-03-T13 | Front-end block renderer mapping block types to `@numo9/ui` web components | FE | T07 | Every block type has a story | Storybook |
| Q-03-T14 | Tests + editor guide | QA/DOC | all | Pages editable without deploy | pytest + Playwright |

- **Deliverable acceptance:** pages editable without deploy.
- **Risks:** XSS via rich text → sanitiser + CSP; editor breaking layout → typed blocks only.

### Q-04 · SEO, analytics, domain, mail DNS
- **Branch:** `feature/Q-04-seo-dns`
- **Objective:** make the site discoverable and measurable on the Numo9 domain with TLS and authenticated email.
- **Expected behaviour:** domain + subdomains (`www`, `app`, `api`, `pay`, `status`, `developers`) on Caddy with TLS/HSTS; SPF/DKIM/DMARC for platform sending domain; sitemap.xml, robots.txt (noindex on staging, index on prod), canonical URLs, hreflang (en-CA/fr-CA), JSON-LD (Organization, SoftwareApplication with Offers from U-02, FAQPage, BreadcrumbList, Article); cookie-less analytics with funnel goals; Search Console verification.
- **Dependencies:** Q-01, Q-03, S-02, A-07.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| Q-04-T01 | DNS plan document (records table for all subdomains, mail, verification) | OPS/DOC | client DNS access | Plan approved | Review |
| Q-04-T02 | Caddy config for subdomains, TLS, HSTS preload-ready, redirects apex → www | OPS | S-02 | SSL Labs A+; securityheaders A | External scan |
| Q-04-T03 | Mail DNS: SPF, DKIM (transactional provider), DMARC p=quarantine with rua reporting; verify with `checkdmarc` | OPS | A-07 | DMARC pass in harness | Integration |
| Q-04-T04 | robots.txt per environment (staging noindex + basic auth) | FE/OPS | Q-01 | Staging not indexable | Automated check |
| Q-04-T05 | next-sitemap with locale alternates; canonical tags | FE | Q-01 | Sitemap validates | Unit |
| Q-04-T06 | hreflang en-CA/fr-CA/x-default on every page | FE | Q-01 | hreflang checker passes | Automated check |
| Q-04-T07 | JSON-LD generators (schema-dts typed) — Organization, SoftwareApplication+Offers from live prices, FAQPage, BreadcrumbList, Article | FE | Q-01-T06 | Rich results test passes | Validator |
| Q-04-T08 | Meta titles/descriptions from CMS with length validation | FE/BE | Q-03 | Missing meta flagged in CMS | Unit |
| Q-04-T09 | Analytics (Plausible self-hosted or client choice) with goals: trial started, accountant sign-up, demo created, subscription started | OPS/FE | Q-01-T26 | Goals recorded on staging | Manual |
| Q-04-T10 | Search Console + Bing verification records, sitemap submission (prod only) | OPS | T01 | Verified | Manual |
| Q-04-T11 | Lighthouse SEO ≥ 90 gate in CI; broken-link checker (lychee) | QA | Q-01 | CI gate passes | Lighthouse CI + lychee |
| Q-04-T12 | Status page `status.<domain>` (Uptime Kuma or hosted) linked in footer/app [EXTRA E12] | OPS | S-04 | Status page live | Manual |
| Q-04-T13 | Docs: DNS & SEO runbook | DOC | all | Merged | Review |

- **Deliverable acceptance:** DNS verified; SEO checks pass.
- **Risks:** DNS propagation delays → start day 1; accidental noindex in prod → automated check in deploy pipeline.

### 6.5 Component W — Open API

### W-01 · Versioned public API & webhooks
- **Branch:** `feature/W-01-public-api`
- **Objective:** a versioned, documented public API (`/api/public/v1`) with API keys and OAuth clients per organisation, scopes mapped to feature keys, signed webhooks, rate limits and full-ledger export.
- **Current behaviour:** internal `/api/v1` used by the web app only; no external access (Xero: closed network, no generic ledger export — gaps #48, #50).
- **Expected behaviour:** OpenAPI 3.1 spec generated and published at `/developers`; auth by API key (org-scoped, hashed, prefix-identifiable `n9_live_…`/`n9_test_…`) or OAuth 2.0 (auth code + PKCE for apps acting for users; client credentials for org-owned integrations); scopes `accounting:read`, `accounting:write`, `tax:read`, `payroll:read`, `inventory:read/write`, `finance:read`, `files:write`, `webhooks:manage`, each mapped to U-01 feature keys → 402 when product missing; cursor pagination, filtering, `Idempotency-Key` header on POST, ETag/If-Match for updates (revision-aware for invoices); webhooks for `invoice.posted`, `invoice.revised`, `invoice.voided`, `payment.received`, `payment.refunded`, `bill.approved`, `stock.moved`, `payrun.posted`, `tax_payment.confirmed`, `contact.updated` delivered at-least-once with HMAC signatures, retries (exponential up to 72 h), replay protection (timestamp tolerance 5 min), delivery log and redeliver [EXTRA E10]; full-ledger export (JSON/CSV, async job, by book and date range); sandbox org per developer [EXTRA E9]; per-key and per-org rate limits with `RateLimit-*` headers.
- **Gap #s closed:** 48, 50.
- **Business rules:** every public endpoint passes the tenant sweep; API writes go through the same services as UI (no duplicate logic); invoice update via API on a posted invoice creates a revision (D-03b), never mutates; keys shown once; revocation immediate; audit entries carry `api_client_id`; versioning — additive changes only within v1, breaking changes → v2 with 12-month deprecation header `Sunset`.
- **Edge cases:** webhook endpoint returns 2xx slowly (timeout 10 s → retry); endpoint failing 3 days → disabled + owner notified; replayed webhook (consumer dedupes by `event_id`); scope downgrade after package change (immediate 402).
- **UI/UX notes:** Settings ▸ Developers: API keys (create with scope picker grouped by product, reveal once with copy, last used, revoke with typed confirm), OAuth clients, Webhooks (endpoint, events, secret rotate, test event, delivery log with request/response), request log viewer; Developer portal with quick start in curl/Python/JS.
- **Dependencies:** A-01, A-03, A-04, U-01, U-03, S-06 (rate limits), all resource services (B, C, D, E, F, G-09, H, N).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| W-01-T01 | ADR-006 Public API versioning, auth, pagination, errors (RFC 7807 problem+json), webhooks | DOC | — | ADR approved | Review |
| W-01-T02 | Figma: Developers settings (keys, OAuth clients, webhooks, logs), developer portal | UX | — | Reviewed | Design review |
| W-01-T03 | `public_api` app skeleton: URL namespace `/api/public/v1`, separate DRF settings (throttles, renderer, versioning), problem+json error handler | BE | T01 | 404/400/402/429 render problem+json | Unit |
| W-01-T04 | `ApiKey` model (org, name, prefix, key_hash argon2/sha256, scopes, mode test/live, created_by, last_used_at, revoked_at) + migration | DB | — | Plain key never stored | Unit |
| W-01-T05 | API-key authentication class (prefix lookup, constant-time hash compare, revoked/expired checks, sets org context) | BE | T04 | Revoked key → 401 immediately | Integration |
| W-01-T06 | OAuth 2.0 via django-oauth-toolkit: Application per org (owner), auth code + PKCE, client credentials, refresh rotation, consent screen listing scopes as products | BE/FE | T03 | OAuth flow completes in test client | Integration |
| W-01-T07 | Scope catalogue ↔ U-01 feature key mapping; scope permission class returning 402 when product missing, 403 when scope missing | BE | T05, T06, U-03 | Payroll scope on non-payroll org → 402 | Integration (`gap-48`) |
| W-01-T08 | Tenant sweep extended to every `/api/public/v1` route with API-key and OAuth clients | QA | T05 | Sweep green | Security suite |
| W-01-T09 | Rate limiting per key and per org (Redis token bucket, S-06) with `RateLimit-Limit/Remaining/Reset` headers | BE | T05 | 429 with headers beyond limit | Integration |
| W-01-T10 | Idempotency-Key middleware for POST (store key+request hash+response 24 h) | BE | T03 | Repeat POST returns same response, no duplicate | Integration |
| W-01-T11 | Cursor pagination + filtering conventions (`updated_since`, `status`, `contact_id`) shared mixins | BE | T03 | Stable pagination under inserts | Unit |
| W-01-T12 | Resources read: organisation, accounts, tax codes, tracking | API | T07, T11 | Contract tests pass | Schemathesis |
| W-01-T13 | Resources read/write: contacts (stable external_id upsert, non-destructive PATCH) | API | T12, B-03 | Re-upsert → 0 changes | Integration |
| W-01-T14 | Resources read/write: items (H-01) | API | T12 | Contract tests pass | Schemathesis |
| W-01-T15 | Resources: invoices incl. `/revisions/` (POST on posted invoice creates revision via D-03b; ETag/If-Match concurrency) | API | T12, D-03b | Stale If-Match → 412; edit → revision 101-1 | Integration |
| W-01-T16 | Resources: bills, payments (create/allocate), credit notes read | API | T12 | Payment via API reduces AR exactly | Integration |
| W-01-T17 | Resources read: journals, bank transactions, tax payments, payroll runs summary (no SIN/bank data), stock levels | API | T12 | Sensitive fields absent | Security test |
| W-01-T18 | Reports read: trial balance, P&L, BS by book and date | API | K-01 | TB via API = UI TB | Integration |
| W-01-T19 | Attachments upload (`files:write`) through A-06 validation | API | A-06 | 25 MB limit enforced | Integration |
| W-01-T20 | Full-ledger export job (JSON Lines/CSV, by book/date range, async with signed download URL, expiry 24 h) | BE/API | C-02 | Export TB equals UI TB (`gap-48`) | Data validation |
| W-01-T21 | Domain event outbox (`OutboxEvent` table written in same transaction as business change) for listed event types | BE | — | Event written iff transaction commits | Integration |
| W-01-T22 | `WebhookEndpoint` (org, url https only, events, secret encrypted, status, failure_count, disabled_at) and `WebhookDelivery` (event_id, attempt, status_code, latency, response excerpt) models + migration | DB | T21 | Non-HTTPS URL refused | Unit |
| W-01-T23 | Delivery worker: HMAC-SHA256 signature header `Numo9-Signature: t=<ts>,v1=<sig>`, `Numo9-Event-Id`, timeout 10 s, exponential retry up to 72 h, ordering by created_at per endpoint | BE | T22, A-08 | Signature verifies with published algorithm; retries recorded | Integration (webhook-sink) |
| W-01-T24 | Auto-disable after 3 days of failures + owner notification; re-enable resends last 72 h [EXTRA E10] | BE | T23 | Disabled endpoint stops deliveries | Integration |
| W-01-T25 | Secret rotation (dual-secret window 24 h) and "send test event" | BE | T23 | Both secrets valid during window | Integration |
| W-01-T26 | Webhook replay idempotency check (consumer guidance + our redeliver keeps event_id) | QA | T23 | Replay carries same event_id | Integration |
| W-01-T27 | Request log (per key: method, path, status, latency, request_id; 30-day retention; no bodies with PII) | BE | T05 | Log viewer lists calls | Integration |
| W-01-T28 | Developers settings UI: keys (scope picker by product, reveal once, revoke typed confirm), OAuth apps, webhooks (events, test, rotate, delivery log, redeliver), request log | FE | T04–T27 | F7 flow passes | Playwright |
| W-01-T29 | Sandbox org per developer from U-07 demo seed with test-mode keys [EXTRA E9] | BE | U-07 | Sandbox created < 10 s | Integration |
| W-01-T30 | OpenAPI generation (drf-spectacular) with examples, error schemas, webhook payload schemas (OpenAPI `webhooks`) | BE | T12–T23 | Spec lints (spectral) clean | CI |
| W-01-T31 | Contract tests from spec (Schemathesis) in CI against seeded org | QA | T30 | 0 schema violations | Schemathesis |
| W-01-T32 | Developer portal `/developers`: rendered reference (Scalar/Redoc), quick starts (curl, Python, JS), auth guide, webhooks guide with signature verification snippets, changelog, deprecation policy | FE/DOC | T30 | Pages live on staging | Playwright |
| W-01-T33 | Generated typed clients (openapi-typescript for internal use; publish later) and Postman/Bruno collection | BE/DOC | T30 | Collection runs green | Bruno CLI |
| W-01-T34 | Versioning headers (`Numo9-Api-Version`, `Deprecation`, `Sunset` support) | BE | T03 | Headers present | Unit |
| W-01-T35 | Security: ZAP API scan, key leakage semgrep rule, gitleaks pattern for `n9_live_` keys, audit entries carry api_client_id | QA | all | No high findings | Security suite |
| W-01-T36 | Load test: 50 rps per org mixed reads, p95 < 300 ms; webhook throughput 100 events/s | QA | all | Targets met on staging | k6 |
| W-01-T37 | Docs: API docs in `docs/` + runbook "Webhook backlog" | DOC | all | Merged | Review |

- **Deliverable acceptance:** contract tests from spec pass; webhook replay idempotent; scopes = feature keys (402 when product missing); full-ledger export ties to TB.
- **Testing:** contract (Schemathesis), integration, security (sweep, ZAP), load (k6), data validation (export).
- **Risks:** API bypassing business rules → API calls the same services; webhook storms → per-endpoint concurrency limit + backoff; breaking changes → versioning policy and contract tests gate.

---

## 7. TEST — Phase 4 test plan (Rules 5–6)

### 7.1 Test matrix

| Category | Phase 4 scope | Tooling | Target |
|---|---|---|---|
| Unit | Engagement / document-request / tax-payment state machines; price_on; deadline generators; business-day roll; idempotency key builders; provider status mapping; BN/program-account validator; webhook signature; scope→feature mapping; recommender rules | pytest, Hypothesis, Vitest | ≥ 85 % on `payments`, `taxpayments`, `public_api`; ≥ 80 % on `practice`, `portal`, `website_cms` |
| Property | Calendar regeneration under random G-03a switch sequences (no duplicates/gaps); AR = sum of open current revisions under random revisions + online payments; one active tax payment per obligation under random concurrent submits | Hypothesis | 1,000 runs each, 0 failures |
| Integration | Stripe Connect (stripe-mock + test mode + Stripe CLI triggers + test clocks); provider stub over HTTP; bank-file generation; email (Mailpit); S3 (MinIO); CMS publish → ISR revalidate; OAuth flows; webhook delivery to sink | pytest + DRF client, Stripe CLI, respx, webhook-sink | Every endpoint one happy + one failure test |
| Contract | Public API vs OpenAPI; provider contract suite (stub, bank file, production adapter when available) | Schemathesis, pytest parametrised | 0 violations |
| Functional (E2E) | F1–F7 flows; engagement → signature → request → upload; service purchase; refund; dispute (test mode); developer key + webhook | Playwright | One scripted scenario per deliverable |
| Regression | Full suite per PR; nightly on `main` with 500-org fixture practice | GitHub Actions | 0 known regressions |
| Data validation | Stripe clearing nets to 0 after payouts; tax payments post exactly the obligation; obligation balance = liability account balance per period; API full-ledger export TB = UI TB; P-03 both ledgers balanced | Reconciliation scripts (`reconcile_stripe_clearing`, `gap_check phase4`) | 0.00 differences |
| Security | Tenant sweep incl. portal + public API (API key, OAuth); RBAC + approval limits on tax payments/refunds; step-up 2FA; webhook signature verification (inbound Stripe/provider, outbound Numo9); PCI SAQ-A boundaries (no card/PAD data stored or logged); CSP on pay page; XSS on CMS and messages; rate limits; OWASP ZAP on pay page, portal, website, API; pip-audit, npm audit, gitleaks, Trivy | Custom sweeps, ZAP, semgrep | No high findings |
| Performance | Website LCP < 2.0 s 4G; pay page interactive < 2.5 s; portal home < 1.5 s; calendar agenda 2,000 orgs < 1 s p95; public API p95 < 300 ms at 50 rps/org; webhook 100 events/s | Lighthouse CI, k6 | Targets met on staging-sized data |
| Accessibility | All new screens; pay page and Tax Payments screen-reader smoke | axe-core, NVDA, VoiceOver | 0 serious/critical |
| Localisation | Missing-key gate (en-CA complete, fr-CA keys present); pseudo-locale +30 %; FR receipt/email template keys exist | CI extraction, Playwright | 0 missing en-CA; 0 clipped layouts |
| Usability | Tasks in §3.6 | Moderated sessions | Metrics met |
| Gap closure | `gap-05`, `gap-06`, `gap-11`, `gap-13`, `gap-41`, `gap-42`, `gap-48`, `gap-50`, `gap-51`, `gap-61` | pytest + Playwright tags | All pass |
| Resilience | Stripe API down; provider timeout after initiate; webhook endpoint failing; CMS API down; analytics blocked | Fault injection (respx, network blocking) | Graceful states shown; no double posting |

### 7.2 Compliance & domain fixtures (`tests/fixtures/compliance/phase4/`)

- GST/HST quarterly filer, net tax 1,234.56 (Q3 2026) — provider route, assisted route, bank-file route.
- GST/HST annual filer with quarterly instalments; refund-position period (negative net tax → "refund expected").
- QST monthly filer (QC org) — QST payable obligation.
- Payroll: regular remitter (monthly, due 15th), quarterly remitter, accelerated threshold 1 (twice monthly), accelerated threshold 2 (up to four per month) — obligations equal N-07 PD7A-style summaries.
- Corporate: FYE 31 Dec 2025, instalments from G-08 schedule, balance due date, T2 deadline 30 Jun 2026.
- Calendar: quarterly → monthly switch effective 1 Jul; stub period 1 Jan–15 Mar; stop filing 30 Jun / restart 1 Jan.
- Online payments: CAD invoice 101 (1,130.00) revised to 101-1 (1,017.00) paid by card; USD invoice paid with FX; PAD success and failure; partial refund; lost dispute with fee.
- Pay-per-service: ON org buys $450 service (HST 13 %), QC org (GST 5 % + QST 9.975 %).
- CPA 005 bank-file layout validation for tax bill payments.

### 7.3 Gap-closure checks (tag → check)

| Tag | Check |
|---|---|
| gap-05 | Stripe API blocked → online-payments card renders cached aggregates with explicit reason and retry |
| gap-06 | Crawl every Phase 4 route as a gated org → 0 redirects; explicit gate panel rendered |
| gap-11 | USD invoice paid via link → FX realised posting |
| gap-13 | Recurring invoice with mandate → exactly one charge per tick after worker restart |
| gap-41 | Portal subscription panel = U-03 resolution for 5 package fixtures |
| gap-42 | Receipt and pay-link emails sent from verified org domain (DMARC pass) using contact-language template key |
| gap-48 | Full-ledger export TB = UI TB; API 402 for product not in package |
| gap-50 | `invoice.revised` webhook delivered to an arbitrary HTTPS consumer and signature verified with published snippet |
| gap-51 | Practice with no subscription uses O-01…O-06 end to end |
| gap-61 | Website catalogue JSON = in-app feature matrix JSON |

### 7.4 Exit demonstration script (staging)

| # | Step | Expected result |
|---|---|---|
| 1 | Visit the Numo9 website on staging; open Packages & Pricing | Live packages and prices from U-02; founding counter shows current remaining; Lighthouse report ≥ 90 attached |
| 2 | Click "Start free trial", sign up as a new Ontario organisation | Trial org created; first app screen reached < 2 min (timer shown in recording) |
| 3 | From the app, choose "Subscribe now" and pay with Stripe test card | Subscription active (U-04); platform invoice and receipt issued; org leaves trial |
| 4 | Accountant (Profitex practice) opens Practice ▸ Services, sees starter services; owner buys "Bookkeeping catch-up" in the portal | Practice invoice + payment posted; org bill marked paid; engagement created in `engaged` |
| 5 | Accountant sends an engagement letter for "T2 year-end"; owner signs in the portal | Status `engaged`; signed PDF with evidence certificate in org Documents |
| 6 | Document request auto-sent; owner uploads a bank statement from mobile width | Upload in org Documents tagged with tax year; item awaiting review |
| 7 | Org connects Stripe (Connect test mode) in Settings ▸ Payments | Status Active; Stripe Clearing and fees accounts created |
| 8 | Approve invoice 101 for $1,130.00; revise to 101-1 ($1,017.00); open the original email link as the customer | Banner "updated to 101-1"; amount $1,017.00 |
| 9 | Pay with test card | AR for the customer reduced by exactly 1,017.00; JE Dr Stripe Clearing / Cr AR; receipt email in Mailpit; webhook replay via Stripe CLI creates no duplicate |
| 10 | Tax ▸ Tax Payments: GST/HST Q3 2026 obligation $1,234.56 (return marked filed) → Pay via sandbox provider | Pre-flight all green; status Initiated → Submitted → Confirmed (stub); JE Dr GST/HST payable 1,234.56 / Cr Chequing 1,234.56; period marked paid; receipt stored; calendar item paid |
| 11 | Click Pay again for the same period | Refused: "This payment is already confirmed…" — no second payment row |
| 12 | Pay the October payroll remittance via the assisted route (deep link + record) | Same posting pattern on source-deductions payable; N-07 remittance calendar shows "paid" |
| 13 | Switch the org's GST/HST cycle quarterly → monthly effective 1 Jan 2027 | Deadline calendar shows monthly deadlines from Jan 2027 within one job cycle |
| 14 | Settings ▸ Developers: create an API key (Accounting read), call `GET /api/public/v1/invoices`, subscribe a webhook to `invoice.revised`, revise an invoice | 200 with invoices; webhook delivered with valid signature; payroll endpoint returns 402 for a package without Payroll |
| 15 | Show test reports: CI green (sweeps, contract tests, gap tags), ZAP no high findings, Lighthouse, axe | Evidence attached to phase release notes |

### 7.5 Failure handling reminder

If any test fails: stop dependent tasks → identify the exact failing condition → classify (code / data / configuration / wrong assumption) → one focused correction → re-run affected tests then the regression suite → continue only when acceptance is met. Never skip or disable a test to pass the build; tests that could not run (e.g. production provider sandbox unavailable) are reported as **not executed** with the reason. Debug with: reproduce → expected vs actual → logs/data (StripeEvent, ProviderCall, WebhookDelivery tables) → hypothesis → one change → verify → regression; apply the 30-minute principle.

---

## 8. IMPROVE — post-verification review checklist (Rule 8)

| Area | Review question for Phase 4 |
|---|---|
| Correctness | Every acceptance number reproduced (1,234.56, 1,017.00, −113.00, < 2 min, < 10 s, Lighthouse ≥ 90)? All money paths idempotent under replay and double click? |
| Ledger integrity | Stripe Clearing, tax liabilities and AR reconcile to 0.00 on fixtures after every flow? |
| Readability | Payment services small and named by intent (`initiate_tax_payment`, `record_assisted_payment`)? No provider-specific code outside adapters (import-linter)? |
| Maintainability | Provider, e-signature and gateway behind interfaces; deadline rules as data; CMS blocks typed |
| Performance | Budgets met: website LCP < 2.0 s, pay page < 2.5 s, portal < 1.5 s, calendar < 1 s p95, API p95 < 300 ms; N+1 queries removed (django-silk / nplusone in dev) |
| Reliability | Retries with backoff only where idempotent; poller stops at final states; outbox guarantees events; dead-letter view for failed webhooks |
| Security | Secrets encrypted; no PAN/PAD/SIN in logs; CSP strict; scopes minimal; step-up 2FA on high-value payments; rate limits; sweeps green |
| UX consistency | One status chip vocabulary; explicit gating everywhere; microcopy follows §3.5; keyboard shortcuts registered; empty states present |
| i18n | No hard-coded strings; CRA/RQ terms in glossary for Phase 6 |
| Docs | ADR-003, ADR-005, ADR-006 recorded; guides and runbooks merged |

Improvements are made only where meaningful and followed by re-running the relevant tests.

---

## 9. Git branch plan (Rule 7)

| Branch | Base | Deliverable | Merge order |
|---|---|---|---|
| `feature/P-01-stripe-connection` | main | P-01 | 1 |
| `feature/P-06-tax-payment-provider` | main | P-06 | 1 |
| `feature/O-01-service-catalog` | main | O-01 | 1 |
| `feature/Q-03-cms` | main | Q-03 | 1 |
| `feature/W-01-public-api` | main | W-01 (foundation T01–T11 may merge early behind flag) | 1 (foundation), 6 (complete) |
| `feature/P-02-invoice-payment` | main (after P-01) | P-02 | 2 |
| `feature/G-09-tax-payments` | main (after P-06) | G-09 | 2 |
| `feature/O-02-engagements` | main (after O-01) | O-02 | 2 |
| `feature/Q-01-website` | main (after Q-03) | Q-01 | 2 |
| `feature/D-08-invoice-pay-link` | main (after P-02) | D-08 | 3 |
| `feature/P-03-service-checkout` | main (after O-01, P-01, O-02) | P-03 | 3 |
| `feature/O-03-document-requests` | main (after O-02) | O-03 | 3 |
| `feature/O-04-deadline-calendar` | main | O-04 | 3 |
| `feature/Q-02-leads` | main (after Q-01) | Q-02 | 3 |
| `feature/P-04-pad-mandates` | main (after P-02) | P-04 | 4 |
| `feature/P-05-refunds-disputes` | main (after P-02, P-03) | P-05 | 4 |
| `feature/O-06-task-board` | main (after O-02) | O-06 | 4 |
| `feature/Q-04-seo-dns` | main (after Q-01) | Q-04 | 4 |
| `feature/O-05-client-portal` | main (after O-02, O-03, O-04, P-02, P-03, G-09) | O-05 | 5 |

**Before starting a branch:** `git status` clean (never discard others' uncommitted work); pull `main`; restate objective + acceptance in PR description; list dependencies; confirm feature keys and permissions to declare.
**Before declaring a branch complete:** all atomic tasks' acceptance observed; CI green (unit, integration, tenant sweep incl. portal/public API, RBAC, i18n missing-key gate, gap tags, contract tests); no unrelated changes; no debug code or test keys; no secrets (gitleaks); docs/ADRs updated; final diff reviewed by a second engineer; merge only with project-lead authorisation; no live Stripe/provider keys outside production.

---

## 10. Phase risks register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Tax-payment provider not chosen/contracted (ADR-003) | High | Medium | Stub + bank-file + assisted routes complete G-09; production adapter behind same interface |
| 2 | Double charge / double tax payment | Medium | High | Idempotency keys on every intent; DB partial unique index; concurrency tests; disabled-on-click UI |
| 3 | Payment posted against superseded invoice revision | Medium | High | Chain resolver; confirm-time revalidation; AR property test |
| 4 | Stripe Connect onboarding friction or rejection | Medium | Medium | Embedded onboarding, plain-language requirements, assisted support; manual payment recording remains |
| 5 | Stripe clearing drift (fees/payouts) | Medium | Medium | Payout handler + `reconcile_stripe_clearing` report + bank match |
| 6 | Portal or API tenant leak | Low | Critical | Sweeps for portal and public API (both auth types); scoped services only |
| 7 | Wrong liability account on tax payment posting | Medium | High | Accounting rules table (G-09-T01), fixtures, posting preview on review |
| 8 | Stale or wrong deadlines | Medium | High | Event-driven + nightly regeneration; property tests; rules as data |
| 9 | Website copy/legal pages late | High | Medium | Original placeholder copy marked for review; CMS lets client edit without deploy |
| 10 | SEO/indexing mistakes (staging indexed / prod noindex) | Low | Medium | Automated robots/noindex checks in deploy pipeline |
| 11 | Brand contrast/accessibility issues with yellow | Medium | Medium | Token rules, contrast audits, axe gate |
| 12 | Webhook storms or slow consumers | Medium | Medium | Per-endpoint concurrency, backoff, auto-disable, delivery dashboard |
| 13 | API breaking changes later | Low | Medium | ADR-006 versioning, contract tests, Sunset headers |
| 14 | Week-7 capacity (21 deliverables) | High | High | Parallel lanes (§5.3), walking-skeleton first, strict scope, daily integration on staging |
| 15 | E-signature legal sufficiency | Low | Medium | Evidence certificate; provider interface for a paid e-sign service (client's fee) |

---

## 11. Phase completion checklist (Rule 11) and reporting template (Rule 10)

### 11.1 Mandatory execution checklist (per deliverable, tracked in the PR)

**UNDERSTAND**
- [ ] Investigated existing implementation from Phases 0–3 (services reused: posting, D-03b, D-05, G-03a, N-07, U-03, U-04, A-06, A-07).
- [ ] Identified the user and desired outcome.
- [ ] Defined inputs and outputs.
- [ ] Identified business rules (idempotency, scoping, gating, posting accounts).
- [ ] Considered edge cases (replays, revisions mid-checkout, provider timeouts, cycle switches).
- [ ] Restated the objective in the PR description.

**PLAN**
- [ ] Decomposed into the atomic tasks in §6.
- [ ] Identified dependencies.
- [ ] Ordered tasks logically.
- [ ] Defined acceptance criteria.
- [ ] Defined testing procedures.

**BUILD**
- [ ] Implemented the smallest functional piece first (model → service → API → UI).
- [ ] Followed existing architecture and design system.
- [ ] Avoided unnecessary changes.
- [ ] Preserved existing functionality.
- [ ] Declared feature keys, permissions and i18n keys.

**TEST**
- [ ] Verified implemented behaviour against acceptance.
- [ ] Tested edge cases (incl. webhook replay, double click, concurrency).
- [ ] Investigated and resolved failures.
- [ ] Checked regressions (full suite).
- [ ] Ran tenant-isolation sweep (app, portal, public API).
- [ ] Recorded unverified conditions (e.g. production provider not available).

**IMPROVE**
- [ ] Reviewed code quality (§8).
- [ ] Removed temporary artifacts, mocks replaced by real integrations where required.
- [ ] Improved readability where needed.
- [ ] Confirmed final behaviour remains correct.

**COMPLETE**
- [ ] Reviewed the final diff.
- [ ] Updated documentation (guides, runbooks, ADR-003/005/006).
- [ ] Reported changes and test results.
- [ ] Confirmed acceptance criteria on staging.
- [ ] Reported final status.

**Phase-level exit**
- [ ] All 21 deliverables Complete.
- [ ] §7.4 exit demonstration observed on staging and recorded.
- [ ] Gap tags in §7.3 all passing.
- [ ] ZAP / pip-audit / npm audit / gitleaks / Trivy: no high findings.
- [ ] Lighthouse ≥ 90 and WCAG 2.1 AA evidence for the website.
- [ ] Release notes, test results and exit demo delivered to Profitex for acceptance (Agreement 7.1–7.2).

### 11.2 Reporting template

**Before implementation (per deliverable)**
1. Problem understanding — objective; existing behaviour; expected behaviour.
2. Task breakdown — components; atomic tasks (IDs from §6); dependencies.
3. Implementation plan — execution order; acceptance criteria; testing strategy.

**After implementation (per deliverable and in the phase report)**
1. Changes made — completed tasks; files/components modified; important decisions (link ADRs).
2. Testing results — tests executed; passed; failed; not executed and why.
3. Remaining issues — known limitations; unresolved bugs; risks or dependencies (e.g. ADR-003 pending).
4. Final status — Complete / Partially complete / Blocked.

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| O-01 | 17 | 25.5 |
| O-02 | 19 | 28.5 |
| O-03 | 15 | 22.5 |
| O-04 | 17 | 25.5 |
| O-05 | 20 | 30 |
| O-06 | 13 | 19.5 |
| P-01 | 20 | 30 |
| P-02 | 19 | 28.5 |
| P-03 | 13 | 19.5 |
| P-04 | 13 | 19.5 |
| P-05 | 11 | 16.5 |
| P-06 | 19 | 28.5 |
| G-09 | 38 | 57 |
| D-08 | 9 | 13.5 |
| Q-01 | 28 | 42 |
| Q-02 | 10 | 15 |
| Q-03 | 14 | 21 |
| Q-04 | 13 | 19.5 |
| W-01 | 37 | 55.5 |
| **Total** | **345** | **517.5** |

# NUMO9 — PHASE 0 IMPLEMENTATION PLAN
## Foundation & SaaS Core (Week 1)

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | 0 — Foundation & SaaS Core |
| **Weeks** | Week 1 from kickoff |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment), Amman, Jordan |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada (product owner of Numo9) |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §1, §2, §3 (Components S, A, U, V, B, C), §4, §5.2–§5.4, §6 · Project_Phases.md (Phase 0) · Quotation GMA-PFX-2026-003 §4–§5 · Agreement GMA-PFX-2026-003-A §06, §07, 9.1 · xero_teardown.md (26 Oct 2026) · AI Coding Agent — Mandatory Engineering Workflow |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE, applied to the phase, to every deliverable (one Git branch each) and separately to every atomic task |
| **Deliverables** | 33 — S-01, S-02, S-03, S-06, A-01…A-10, U-01…U-08, V-01…V-05, B-01…B-03, C-01, C-02 |

---

## 0. How to use this file

1. Every deliverable in §6 is one Git branch: `feature/<ID>-<short-name>` cut from `main`.
2. Every atomic task in a deliverable card is worked on its own: **UNDERSTAND** (re-read the card, inspect what exists) → **PLAN** (confirm steps and acceptance) → **BUILD** (smallest working piece) → **TEST** (run it, edge cases, regression) → **IMPROVE** (only after it is correct).
3. Tasks are executed in the order listed; the `Depends` column must be satisfied before a task starts. Tasks with no dependency between them may run in parallel by different engineers.
4. Each atomic task is sized at 1–2 hours of focused work. If a task grows beyond that during UNDERSTAND, split it before coding and record the split in the PR description.
5. Nothing is reported complete until its acceptance criterion has been **observed** (test output, screenshot, log or demo). A phase is complete only when all 33 deliverables meet their acceptance and the Phase 0 exit demonstration (§7) is observed on staging (Agreement §07).
6. Every new endpoint declares its feature key (U-01) and is registered in the tenant-isolation sweep (A-01); every new screen uses the design system (A-10) and ships EN and FR i18n keys from day one (FR text filled in Phase 6).
7. Mocks are allowed (Stripe test mode, MinIO, Mailpit, fixture OCR) but are replaced by the real integration before a deliverable is declared complete.

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase

| Area | State on 7 November 2026 |
|---|---|
| Repository | **Greenfield.** The Numo9 folder contains only `docs/` (Project Plan v2.0, Project_Phases.md, xero_teardown.md, Quotation, Agreement, engineering workflow). No backend, frontend, mobile or infra code exists. |
| Infrastructure | No hosting account, no domain, no CI. GMA's operational pattern (Docker Compose + Caddy on Hetzner) is known but the hosting region must follow ADR-001 (Canadian data residency recommended). |
| Data | No chart of accounts, no tenants, no users. Profitex's live data sits in Xero (organisation "REFINED" inspected in the teardown) and is migrated only in Phase 5 (T-01). |
| Commercial setup | Package names/prices, founding-offer wording, Stripe Canada account and brand assets are **client inputs** still to be supplied. |
| Reference behaviour | Xero (functional reference only — no UI or text copied). The teardown is the specification of what to do better. |

Consequence: Phase 0 creates every foundation every later phase depends on. Anything built wrongly here (tenant scoping, money type, posting engine, design system, entitlement keys) multiplies its cost in every later phase — so this phase over-invests in tests, lint rules and sweeps.

### 1.2 Problem definition — the seven questions (Phase 0)

**1. Who uses this functionality?**

| Actor | Phase 0 interaction |
|---|---|
| Platform Owner (Profitex) | Defines products, packages, prices and the founding offer; watches MRR/trial funnel; manages demo data; impersonates with audit; toggles feature flags. |
| Accountant (Practice member) | Signs up free, creates or joins a practice, opens a demo organisation, creates a trial organisation for a client, searches/groups/bulk-edits organisations. |
| Practice Admin | Invites staff, assigns staff to organisations and groups, sets roles and approval limits, sees dormant-user alerts and heatmaps. |
| Organisation Owner | Starts a 30-day trial, subscribes with card/PAD, invites an accountant, sets organisation settings and lock dates, manages contacts and chart of accounts. |
| Organisation User | Logs in with a role (Sales, Purchasing, Payroll…), sees only the screens their role and package allow. |
| Trial / Demo visitor | Opens a resettable demo with Canadian sample data in under 10 s; converts a demo to a trial. |
| System | Celery jobs: trial reminders (7/3/1 days), renewals/dunning (3/5/7), demo purge (30 days), inbound email processing, usage metering, notification delivery. |

**2. What is the desired outcome?**
A running, secured, Canadian-hosted SaaS skeleton where a free accountant can sign up, a paying (or trialling) organisation exists inside a two-level tenancy, roles/entitlements/audit work, contacts and a correctly-typed Canadian chart of accounts exist, and the posting engine posts balanced, append-only journals with a book dimension under concurrency.

**3. What are the inputs?**
Sign-up data (email, password, name, practice name), invitations, organisation settings (legal/display name, Province, Postal code, BN + RT/RP/RC, QST no., fiscal year end, time zone, terms), lock dates per module, uploaded files and inbound emails, package/product/price definitions, Stripe card/PAD tokens (never raw card data), promo codes, contacts (manual + CSV/XLSX import), CoA template and edits, journal lines (account, debit, credit, book, contact).

**4. What are the outputs?**
Authenticated sessions and 2FA, tenant-scoped records, audit log entries with field diffs, notifications/emails, entitlement decisions (allow / 402 with required product), subscriptions, platform invoices/receipts, trial and demo organisations, founding entitlements, directory search results, saved views, bulk-job results, dashboards, contact statements, import dry-run reports, the chart of accounts with GIFI mapping, posted journal entries with a gap-free sequence, trial balance per book = 0.

**5. What are the business rules?**
- Accountants/practices are always free; billing attaches only to organisations.
- Every business record belongs to exactly one organisation; practice access fans out only over assigned organisations; removal revokes on the next request.
- A gated feature is visible with an explicit "included in package X" prompt — never hidden, never silently redirected; API returns HTTP 402 with the required product.
- Downgrade removes write access immediately, keeps read access to history.
- One trial per BN/email; conversion at day 30 23:59 organisation-local keeps all data.
- Founding counter: exactly 1,000, incremented atomically on first successful payment.
- Audit log append-only (DB rejects UPDATE/DELETE); 90-day default viewer range.
- Posting before a module lock date is refused with a message naming the lock.
- Journals: ≥ 2 lines, balanced to the cent, atomic, append-only, `reverse()` linked, states Draft → Awaiting approval → Posted → Reversed, book ∈ {accounting, tax, both}.
- Money is `numeric(18,2)` / Python `Decimal`, never float.
- Canadian English and terms everywhere (organisation, cheque, Province, Postal code, GST/HST, vacation pay).
- PIPEDA; CRA 6-year retention (soft-delete only); PCI scope stays at Stripe.

**6. What could go wrong?**
Unscoped queries leaking another organisation's data; removed practice member still seeing records via cache; entitlement cache stale after downgrade; webhook replay creating duplicate subscriptions/invoices; founding counter over-allocating under concurrency; trial conversion losing data at the timezone boundary; demo data polluting platform metrics; audit log tampered with by an ORM `update()`; lock date bypassed by a background job; posting sequence gaps or duplicates under concurrent load; float rounding in money; CoA renumbering leaving dangling references; contact import creating duplicates on rename; inbound email routed to the wrong organisation; email failing DMARC; design system drift (two grid components); hard-coded English strings; secrets committed to Git; Celery beat double-ticking with two workers.

**7. What is the smallest useful implementation?**
One practice with one free accountant, one trial organisation on one package, login + 2FA, tenant-scoped contacts, Canadian CoA loaded with GIFI, and a posting service that posts a balanced journal in each book with a gap-free sequence — deployed to HTTPS staging in Canada from a tagged CI build. Everything else in Phase 0 extends this skeleton.

### 1.3 Restated objective

- **Currently:** nothing is built; Profitex runs on Xero, whose shell mixes two UI generations, gates core actions behind generic upgrade banners, has coarse roles, no lock dates, 7-day history without diffs, name-matched contact import, a mis-typed chart with one "Sales Tax" control account and 0 of 139 accounts mapped to GIFI.
- **Change:** build the Numo9 foundation — infrastructure and security, two-level tenancy, auth/RBAC with approval limits, field-diff audit, Canadian organisation settings with per-module locks, documents inbox, notifications with custom sending domain, jobs, global search, one design system; the SaaS layer (products, packages, entitlements, Stripe billing, trial, owner console, demo, founding 1,000); the accountant workspace (directory, groups/tags, bulk edit, cross-org dashboards, staff management); contacts with explicit roles and stable-ID import; Canadian chart of accounts and the two-book posting engine.
- **Why:** every later phase (books, tax, payroll, inventory, portal, mobile) sits on these models, services and UI patterns; marketing can start the founding offer and trial from week 1.
- **Done means:** all 33 deliverables meet their acceptance criteria and, on staging: an accountant signs up free, opens a demo, creates a trial organisation, groups and searches organisations; packages and the founding counter are live; 1,000 concurrent postings produce a gap-free sequence and each book's trial balance = 0.

### 1.4 Assumptions & interpretations

1. Monorepo on GitHub (private), owned by GMA until final payment, then transferred (Agreement IP clause).
2. Hosting: Canadian region of a cloud provider chosen in ADR-001 (candidates: AWS ca-central-1 / ca-west-1, OVHcloud Beauharnois, DigitalOcean TOR1). Until the client account exists, staging runs in a GMA-held account in the same region.
3. Package names, mixes and prices are **data** entered in the owner console; Phase 0 ships seed data "Starter / Growth / Complete" marked `placeholder=True`, replaced when the client supplies them.
4. Founding rule on churn-and-return defaults to "keep founding status if the organisation returns within 90 days" (configurable, per U-08).
5. Social sign-in is optional and deferred behind a feature flag; email/password + TOTP is the baseline.
6. OCR/extraction provider is pluggable; Phase 0 only builds the inbox and file pipeline (extraction is E-05, Phase 2).
7. SMS/WhatsApp channels are hooks only (provider fees are the client's).
8. French text is not written in Phase 0; FR keys exist with the EN value and are flagged `needs_translation`.
9. Finance [v2.1] product key is created in the catalogue now (U-01) even though the module is built in Phase 2.
10. Time zone for organisation-local logic (trial expiry, lock dates) is the organisation's `time_zone` setting, defaulting to America/Toronto.

**Open questions for the client (do not block coding; defaults above apply):** final package names/prices; founding churn rule; Stripe Canada account owner; Numo9 domain; brand assets (logo, yellow/black palette values); demo dataset sign-off.

### 1.5 Client inputs required (Phase 0)

| Input | Needed for | Due |
|---|---|---|
| Hosting account in a Canadian region (ADR-001 decision) | S-02 | Day 1 |
| Numo9 domain + DNS access | S-02, A-07, Q-04 | Day 1 |
| Brand assets (logo, yellow/black values, typography preference) | A-10 | Day 2 |
| Stripe Canada account (test + live keys, Billing enabled, ACSS Debit) | U-04 | Day 3 |
| Package names, product mixes, monthly/annual CAD prices | U-02 | Day 3 |
| Founding-offer wording and churn rule | U-08 | Day 3 |
| Demo sample-data sign-off | U-07 | Day 5 |
| Transactional email provider account (e.g., Postmark/SES ca-central-1) | A-07 | Day 2 |

---

## 2. BETTER THAN XERO — gap analysis for Phase 0

| Gap # | Teardown ref | What Xero does / fails to do | What Numo9 does instead (better) | Observable proof |
|---|---|---|---|---|
| 1 | §0 | Two UI generations (legacy .aspx + React); grids, dates, empty states, breadcrumbs differ | One design-system package (`@numo9/ui`) used by every screen; one grid, one date formatter per locale, one empty-state component, one breadcrumb | `gap-01` visual regression + lint "no raw table/date" |
| 2 | §0 | Root URL returns 404 | Every root, legacy-style and module URL redirects (301) to Home or the right module; unknown routes show a helpful 404 with search | `gap-02` crawler test of root + 40 legacy-style paths |
| 3 | §0 | All module "Settings" links go to one generic page | Settings deep-link per module (`/settings/sales`, `/settings/tax`…); each module's gear opens its own section | `gap-03` link test |
| 6 | §2.2 | Approval paywalled | Entitlement engine never gates core workflow states (approve/void/credit); gating only at product level, explicit | `gap-06` entitlement matrix test |
| 11 | §2.3 | Multi-currency absent on plan | Multi-currency feature key belongs to Accounting product (built Phase 2; key declared now) | `gap-11` feature-matrix export |
| 12 | §2.3 | Three promotional banners push editors below the fold | A-10 rule: no promotional banners inside working screens; system notices go to the notification centre | `gap-12` layout lint + visual test |
| 13 | §2.4 | No subscription object | U-04 subscription model with proration, renewals, dunning | `gap-13` billing tests |
| 14 | §2.5 | Credit note silently redirects | Gated screens render a "Not in your package" panel naming the product; never redirect | `gap-14` route test: 0 silent redirects |
| 15 | §2.6 | Import CSV only, no mapping, no dry-run | B-03 CSV + XLSX, column mapping, dry-run report | `gap-15` |
| 19 | §3.1 | Customer/Supplier lists identical; role inferred | Explicit roles set on the contact; titled, filtered lists | `gap-19` |
| 20 | §3.2 | No contact currency, terms master, withholding flag, exemption certificate, duplicate warning, credit warn vs block | All fields present; duplicate warning while typing; credit warn/block with override approval | `gap-20` |
| 21 | §3.3 | Import matches on name; blank columns delete people; 5-people cap | Stable external ID; blank = untouched; unlimited people | `gap-21` re-import 0 changes |
| 25 | §4.5 | No PO approval limits per user | A-03 amount limits per user per document type | `gap-25` $5,001 bill blocked |
| 29 | §5.4 | System accounts un-renumberable; no sub-accounts; mis-typed template; single Sales Tax control; mixed code lengths | Renumberable system accounts, parent/child, correct typing (Inventory typed Inventory, intangibles non-current), separate GST/HST, ITC, PST, QST, QST-ITR, payroll controls; consistent 4-digit codes | `gap-29` |
| 30 | §5.5 | 0/139 GIFI mapped; period confusion between pages | Template ships 100 % GIFI-mapped; one balance-as-at basis | `gap-30` 0 unmapped |
| 31 | §5.6 | "Value added tax", "annual leave" | Canadian terms enforced by glossary lint | `gap-31` |
| 32 | §5.7 | Documents page slow/froze; no period tagging | Virtualised inbox, < 1 s first paint for 1,000 files; tag by period/tax year | `gap-32` perf test |
| 37 | §5.13 | History default 7 days; no diffs; no CSV | 90-day default, field-level old → new diffs, CSV/XLSX/PDF export equal to screen | `gap-37` |
| 38 | §6 | Organization/organisation spelling flips | Single en-CA spelling enforced by a CI glossary lint | `gap-38` |
| 39 | §6.1 | "State/ZIP" for Canada; no province picker; BN split across pages | Province picker, Postal code with A1A 1A1 validation; BN + RT/RP/RC on one Tax Registrations page | `gap-39` |
| 40 | §6.2 | Coarse roles; no custom roles/limits; dormant subscriber keeps Manage users | Custom roles, per-permission flags, amount limits; 60-day dormant alert; optional auto-suspend of admin rights | `gap-40` |
| 41 | §6.3 | Advisor can't see plan; generic upgrade banners | In-app plan/feature matrix visible to every role incl. accountant | `gap-41` |
| 42 | §6.5 | No custom sending domain | Per-organisation verified sending domain (SPF/DKIM/DMARC) with guided DNS checker | `gap-42` DMARC pass |
| 43 | §6.6–6.7 | Three template systems; US Letter with cm; NZ sample; no custom fields | One template system, Letter with inch margins, Canadian sample data, custom fields on contacts | `gap-43` |
| 44 | §6.8 | No lock dates; silent "GST Type removed"; "16:33PM"; 2 lock levels only | Per-module locks (GL/AR/AP/Bank/Payroll/Tax) × 2 levels; every change attributed; correct 24 h / 12 h time format | `gap-44` |
| 45 | §6.9 | All accounts default Exempt | CoA template: expense accounts default to home-province purchase rate (wired in Phase 1 G-01; field present now) | `gap-45` |
| 46 | §6.10 | No tracking hierarchy / mandatory tracking | Per-account "require tracking / contact / attachment" flags in C-01 | `gap-46` |
| 48 | §6.12 | No generic ledger export | Posting engine exposes a stable export query (W-01 later) | — |
| 51 | §7 | Projects/Expenses/capture are paid add-ons | Feature keys for these live in the Accounting product | `gap-51` matrix |
| 52 | §8.1 | Search misses journals, accounts, settings, reports | A-09 indexes all record types + settings + reports + navigation | `gap-52` |
| 55 | §9.2 | Statement header prints a number | A-05 rejects numeric-only legal name | `gap-55` |
| 60 | §9.7 | Accessibility label leak | axe-core a11y suite in CI from Phase 0 | `gap-60` |
| 61 | §10.B | No plan/feature matrix; localisation | Matrix in-app; i18n ICU from day one, RTL-ready tokens | `gap-61` |

**Beyond-Xero additions in this phase**
- Two-level tenancy Practice → Organisation with free accountants and paying organisations; organisation can have 0, 1 or several practices.
- Accountant workspace: directory with full-text search over 2,000 organisations < 300 ms, hierarchical groups, tags, saved views, bulk edit with preview and per-row results, cross-organisation deadline/workload dashboards.
- SaaS commercial layer: products, packages, effective-dated prices, promo codes, entitlement engine with 402 contract, Stripe card + PAD, dunning, 30-day trial, demo organisation in < 10 s, founding 1,000 atomic counter, owner console with MRR/churn/funnel, audited time-boxed impersonation, feature flags.
- Approval limits by amount per user; permission catalogue enforced in CI.
- Posting engine with book dimension (accounting/tax/both) ready for two-book reporting.

**Xero strengths matched conceptually (original design, no copied UI/text)**
- Per-organisation inbound email address for documents (A-06).
- Keyboard quick-create (A-09) — Numo9 uses its own shortcut scheme (`N` then a letter, plus `⌘/Ctrl+K` command palette).
- User-activity heatmap (V-05).
- Column chooser and saved views (V-01, A-10 data grid).

**[EXTRA] improvements beyond the gap report (inside Schedule A scope)**
- [EXTRA] Command palette (`Ctrl/⌘+K`) combining search, navigation and quick-create in one place.
- [EXTRA] "Why can't I?" explainer: any refused action (lock, permission, entitlement, approval limit) shows the exact rule, who can change it and a one-click request to that person.
- [EXTRA] Session security: new-device email alert, session list with revoke, idle timeout configurable per practice.
- [EXTRA] Postal-code-to-province consistency check on addresses (first letter → province) to catch tax-default errors early.
- [EXTRA] BN check-digit validation (Luhn on the 9-digit BN) and program-account format `123456789RT0001`.
- [EXTRA] Audit log "view as of date" for any record (reconstruct the record from diffs).
- [EXTRA] Lock-date "preview impact" (how many draft/unposted documents fall before the new lock date) before saving.
- [EXTRA] Trial health score in the owner console (logins, records created) to target conversion.
- [EXTRA] Demo "guided tour" checklist inside the demo organisation.
- [EXTRA] Directory "needs attention" smart view (overdue items, expiring trial, unfiled returns) pre-built for every accountant.
- [EXTRA] Contact merge with side-by-side field picker and undo within 24 h.
- [EXTRA] CoA "health check" panel (unmapped GIFI, mis-typed accounts, duplicate names) — the same rules later reused by K-09.
- [EXTRA] Posting engine idempotency key on every post call so retries never double-post.

---

## 3. UI/UX DESIGN PLAN (senior UI/UX expert view)

### 3.1 UX principles applied in this phase

| # | Principle | How it is applied in Phase 0 |
|---|---|---|
| 1 | One UI generation | Every screen is assembled from `@numo9/ui` (Storybook-documented). No module may introduce its own grid, picker, date or empty state. |
| 2 | Task-first navigation | Top nav by job, not by database table: Home · Sales · Purchases · Banking · Accounting · Tax · Payroll · Inventory · Reports · Contacts; accountants also get **Practice** (directory, dashboards, staff). |
| 3 | Zero silent redirects | Gated, missing or unauthorised routes render an explanatory panel (what, why, who can fix, one-click request). |
| 4 | Explicit, honest gating | "Included in **Payroll** — part of packages Growth, Complete" with a "See plans" link to the in-app feature matrix. Read-only after downgrade is labelled "Read-only — Payroll no longer in your package". |
| 5 | Progressive disclosure | Sign-up asks 4 fields; everything else (BN, fiscal year end, registrations) is asked in-context via a setup checklist on Home, never as a wall. |
| 6 | Keyboard-first for accountants | Command palette `Ctrl/⌘+K`; `N I` new invoice, `N B` bill, `N C` contact, `N Q` quote, `N P` PO, `N J` journal, `N S` spend money, `N R` receive money, `N T` transfer, `N U` upload; `G H` home, `G D` directory, `/` focus search, `?` shortcut sheet; arrow/Enter/Esc in every list and dialog. |
| 7 | Forgiving input | Amounts accept `1,234.5`, `1234.50`, `$1 234,50` (fr-CA); dates accept `26/10`, `oct 26`, `today`, `+30`; Postal code auto-uppercases and inserts the space. |
| 8 | Undo over confirm where safe | Archive, tag, group, bulk-edit and merge show an Undo toast (10 s, plus 24 h undo in history for merges/bulk edits); destructive irreversible actions (delete practice, cancel subscription) require typed confirmation. |
| 9 | Clear system status | Skeleton loaders (no spinners > 300 ms without skeleton), optimistic updates with rollback, background jobs show progress in the job tray. |
| 10 | Errors name cause and fix | See §3.5. Field errors inline, summary at top with anchor links, focus moves to the first error. |
| 11 | Accessibility WCAG 2.1 AA | Contrast ≥ 4.5:1 (yellow brand used for accents on black/white, never yellow text on white), focus rings, ARIA live regions for toasts, full keyboard paths, 44 px touch targets, reduced-motion support. |
| 12 | Localisation-ready | ICU messages, en-CA default, fr-CA keys from day one, layouts tested with +30 % string length (pseudo-locale), number/date/currency via `Intl`, no concatenated strings, RTL-safe logical CSS properties. |
| 13 | Density options | Comfortable / Compact density toggle per user (accountants prefer compact grids). |
| 14 | Consistent status model | One `StatusBadge` component and one status vocabulary per document type, identical on tiles, lists and detail pages. |
| 15 | No ads, no upsell banners in work screens | Commercial messages only in Settings → Subscription and the owner-controlled announcement slot on Home (dismissible). |
| 16 | Canadian documents | Letter (8.5 × 11 in) with inch margins; Canadian sample data in every preview. |
| 17 | Mobile-responsive web | Breakpoints 360 / 768 / 1024 / 1440; directory and settings fully usable at 360 px; grids switch to card lists below 768 px. |

### 3.2 Information architecture added in Phase 0

```
Public (auth)          /signup  /login  /verify  /reset  /invite/:token  /2fa
Practice workspace     /p/:practice/  → Directory (default) · Dashboard · Groups & tags · Staff · Practice settings
Organisation app       /o/:org/       → Home · Contacts · Accounting(Chart of accounts, Journals*) · Documents · Settings
  Settings             /o/:org/settings/{general, registrations(tax), lock-dates, users-roles, email-domain,
                                         subscription, numbering, custom-fields, audit-log}
Platform console       /console/      → Practices · Organisations · Products · Packages & prices · Promo codes ·
                                         Founding offer · Demo manager · Metrics · Feature flags · Impersonation log · Jobs
Global                 Command palette · Notification centre · Job tray · Org switcher · Help & shortcuts (?)
(* journal UI basic in Phase 0 for C-02 testing; full manual JE UI in Phase 1 C-04)
```
Org switcher: shows recent 5 organisations, a search box and "Open directory" — accountants never scroll a 2,000-item dropdown.

### 3.3 Screen inventory (Phase 0)

| Screen | Primary user | Purpose | Key components | States | Keyboard |
|---|---|---|---|---|---|
| Sign up (accountant / organisation) | Visitor | Create account in < 2 min | Form, PasswordStrength, Province select | default / error / email-sent | Enter submit |
| Verify email / Reset password | All | Account recovery | Form, Toast | expired-link / used-link / success | — |
| 2FA set-up & challenge | All | TOTP enrol, recovery codes | QR, CodeInput (6 boxes, paste-aware) | wrong code / locked 15 min | auto-advance |
| Invitation accept | Invitee | Join practice/org | Card, role summary | expired / already-used / wrong-account | — |
| Practice onboarding | Accountant | Name practice, open demo, create first org | Stepper (3 steps), skip allowed | — | — |
| Organisation directory | Accountant | Find and act on many orgs | DataGrid (virtualised), FilterBar, SavedViews, ColumnChooser, BulkBar, GroupTree | empty (first-run CTA) / no-results / loading skeleton / error retry | `/` search, ↑↓, Space select, Enter open, `B` bulk |
| Groups & tags manager | Practice Admin | Hierarchy and colours | TreeView (drag-drop), ColourPicker | empty | arrows, F2 rename |
| Bulk edit preview & result | Practice Admin | Safe mass change | DiffTable, JobProgress, ResultTable (per row ✓/✗) | running / partial failure / done | — |
| Practice dashboard | Accountant | Cross-org deadlines/workload | KPI tiles (drill-down), DeadlineList, Heat table | zero state "All caught up" | — |
| Staff management | Practice Admin | Invite, roles, assignment, heatmap | DataGrid, RoleSelect, AssignmentPicker, Heatmap | dormant badge | — |
| Organisation Home (setup checklist) | Owner | Guided set-up | Checklist, Tiles | trial banner (countdown), read-only banner | — |
| Settings → General | Owner/Admin | Legal/display name, address, FYE, TZ | Form sections with sticky Save bar | unsaved-changes guard | ⌘S save |
| Settings → Tax registrations | Owner/Accountant | BN, RT/RP/RC, QST — one page | Repeater rows, format masks, history drawer | — | — |
| Settings → Lock dates | Accountant | Per-module locks × 2 levels | Matrix table (module × level), Impact preview | — | — |
| Settings → Users & roles | Owner/Admin | Members, custom roles, limits | Permission matrix with search, LimitEditor | — | — |
| Settings → Email domain | Owner/Admin | Custom sending domain | DNS record cards with copy, live checker | pending / verified / failing | — |
| Settings → Subscription | Owner | Package, card/PAD, invoices, cancel | PlanCards, FeatureMatrix, Stripe Elements | trial / active / grace / read-only / cancelled | — |
| Feature matrix (in-app) | Everyone | What each package includes | Matrix table, "You are here" column | — | — |
| Audit log (global + per record) | Accountant/Owner | Who changed what | DataGrid, DiffViewer (old → new), DatePresets | empty for range | — |
| Documents inbox | Owner/Accountant | Upload, inbound email, tag, create-from | DropZone, VirtualList, Previewer (PDF/image), TagChips | uploading / scanning / infected / ready | `U` upload |
| Notification centre | All | In-app notices | Drawer, grouped by day, mark-read | empty | `Shift+N` |
| Command palette / global search | All | Search + navigate + create | Dialog, grouped results, recent | no-results with "create" suggestions | `Ctrl/⌘+K` |
| Contacts list & detail | Owner/Accountant | Customers, suppliers, both | DataGrid, Role tabs (titled), Timeline, Statement | empty CTA import/new | `N C` |
| Contact import wizard | Accountant | Map, dry-run, apply | Stepper, ColumnMapper, DryRunReport | errors per row | — |
| Chart of accounts | Accountant | Tree, types, GIFI, flags | TreeGrid, TypeBadge, GIFI picker, HealthCheck panel | archived toggle | `N A` |
| Journal (basic) | Accountant | Post/inspect for C-02 | LineGrid (shared grid), BalanceIndicator, BookSelect | unbalanced / posted / reversed | ⌘Enter post |
| Platform console pages | Platform Owner | Products, packages, founding, demo, metrics, flags, impersonation | DataGrid, Charts, Counter, Forms | — | — |
| Gated panel / 403 / 404 / 402 | All | Honest refusal | ExplainPanel | — | — |

### 3.4 Key user flows (with targets)

**F1 — Accountant signs up free and opens a demo (target ≤ 90 s, ≤ 6 clicks)**
1. `/signup` → choose "I'm an accountant" → name, email, password, practice name → Create (1 click).
2. Verification email (Mailpit in dev) → click link → lands in Practice onboarding.
3. Step 1 "Open a demo organisation" → demo created < 10 s with progress indicator → lands in demo Home with watermark ribbon "Demo — sample data".
4. Command palette or "Back to directory" returns to the practice.

**F2 — Accountant creates a trial organisation for a client (≤ 2 min)**
1. Directory → "New organisation" → legal name, Province, fiscal year end, package (default trial package) → Create.
2. Trial starts (30 days, countdown chip in header), setup checklist appears (BN, registrations, CoA, contacts, invite owner).
3. "Invite owner" → email → owner accepts → owner becomes Organisation Owner; accountant stays assigned.

**F3 — Accountant groups and searches organisations**
1. Directory → select 12 rows (Shift-click) → Bulk bar → "Add to group" → choose "Toronto office → Retail" → Preview diff → Apply → per-row results → Undo available.
2. Type "retail ON" in search → results < 300 ms; save as view "Ontario retail" → appears in Saved views sidebar.

**F4 — Owner converts trial to paid**
1. Trial chip "7 days left" → Subscription page → choose package & monthly/annual → card or PAD via Stripe Elements → Confirm.
2. Receipt email + platform invoice in Documents; founding badge if within first 1,000 ("You are founding organisation #214").

**F5 — Gated feature encountered**
1. User opens Payroll on an Accounting-only package → ExplainPanel: "Payroll isn't in your package (Starter). It's included in Growth and Complete." → [Compare packages] [Ask the owner to upgrade] (sends notification). No redirect.

**F6 — Accountant sets lock dates**
1. Settings → Lock dates → GL "Everyone except advisers" = 30 Jun 2026 → Impact preview "3 draft documents dated before this date" → Save → audit entry + notification to org admins.

**F7 — Post a balanced journal (C-02 test path)**
1. `N J` → lines → balance indicator turns green at 0.00 → Book = Both → ⌘Enter → number JE-000123 assigned → "Reverse" available.

### 3.5 Microcopy & error-message rules

Rules: (1) say what happened, why, and what to do; (2) name the record, rule, or person; (3) no codes alone, no blame; (4) Canadian English; (5) sentence case; (6) buttons are verbs ("Save settings", not "OK"); (7) never "Oops"; (8) every message is an i18n key.

| Situation | Message |
|---|---|
| Lock date | "This entry is dated 15 Jun 2026, before the General Ledger lock date (30 Jun 2026). Change the date, or ask an adviser to move the lock in Settings → Lock dates." |
| Approval limit | "Your approval limit for bills is $5,000.00. This bill is $5,001.00. Send it to Dana Lee (limit $25,000.00) for approval?" [Send for approval] |
| Entitlement (402) | "Inventory isn't included in your Starter package. It's part of Growth and Complete. Your existing data stays available to view." |
| Cross-org / removed | "You don't have access to this organisation. It may have been unassigned from you. Ask your practice admin, or open your directory." |
| Duplicate contact | "A contact named 'Maple Leaf Supply Ltd.' with the same email already exists. Open it, or continue to create a separate contact." |
| Unbalanced journal | "Debits ($1,250.00) and credits ($1,200.00) differ by $50.00. Adjust a line so the difference is $0.00." |
| Numeric legal name | "Legal name can't be only numbers — it prints on every statement. Enter the registered business name, e.g. 'Refined Interiors Inc.'" |
| File too large | "'receipts-oct.pdf' is 31 MB. The limit is 25 MB per file. Split the PDF or compress it, then upload again." |
| Postal code | "Postal code should look like 'M5V 2T6'. 'M5V2T' is missing a character." |
| Trial expiring | "Your free trial ends in 3 days (Nov 30 at 11:59 pm Eastern). Choose a package to keep working — nothing you've entered will be lost." |

### 3.6 Accessibility & usability test plan (Phase 0)

| Test | Method | Success metric |
|---|---|---|
| Automated a11y | axe-core in Playwright on every Phase 0 route | 0 serious/critical violations |
| Keyboard-only | Scripted: sign-up → demo → directory bulk group → settings lock date | Completable without mouse; visible focus at every step |
| Screen reader smoke | NVDA (Windows) + VoiceOver (macOS) on directory, settings, journal | All controls announced with name/role/state |
| Contrast | Token check script on brand palette | Every text/background pair ≥ 4.5:1 (large text ≥ 3:1) |
| Pseudo-locale | `en-XA` +30 % strings, accented | No clipped/overflowing labels on 1280 px and 360 px |
| Usability (5 participants: 3 accountants, 2 owners) | Moderated, think-aloud, 6 tasks (F1–F6) | Task success ≥ 90 %, SUS ≥ 80, F1 median ≤ 90 s, F3 search found first try ≥ 4/5 |
| Responsive | Playwright viewports 360/768/1024/1440 | No horizontal scroll; directory usable at 360 |
| Performance UX | Lighthouse CI on auth pages and directory | Performance ≥ 90; INP < 200 ms; LCP < 2.5 s |

---

## 4. TOOLS & TECHNOLOGY FOR PHASE 0

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| Language/runtime | Python 3.12, Node.js 22 LTS, TypeScript 5.x | Backend, frontend, tooling | Pinned via `.tool-versions` (asdf/mise) |
| Backend framework | Django 5.x, Django REST Framework | Models, admin, API | LTS track |
| API schema | drf-spectacular | OpenAPI 3 generation, contract tests, typed client | Spec published at `/api/schema/` |
| Typed API client | openapi-typescript + openapi-fetch | Frontend/mobile types from the spec | Regenerated in CI |
| Auth | django-allauth (headless), django-otp + TOTP, argon2-cffi | Sign-up, verification, 2FA, password hashing | Argon2id hasher |
| Sessions/tokens | Django sessions (web) + djangorestframework-simplejwt (mobile later) | Session list/revoke | Secure, HttpOnly, SameSite=Lax cookies |
| Rate limiting | django-ratelimit / Redis token bucket | Per-org and per-IP limits (S-06) | 429 with Retry-After |
| Permissions | DRF permission classes + rules (django-rules) | RBAC, approval limits | Permission catalogue in code |
| Tenancy | Custom `OrgScopedManager`, middleware, contextvars | Org/practice scoping | No third-party tenancy lib (row-level) |
| DB | PostgreSQL 16, psycopg 3, PgBouncer | Data, pooling | numeric(18,2); partitioning via pg_partman |
| DB safety | PostgreSQL row-level security (defence in depth), triggers | Audit append-only, tenant RLS on critical tables | `REVOKE UPDATE, DELETE` on audit |
| Migrations lint | django-migration-linter, squawk | Safe migrations | CI gate |
| Money | Python `Decimal`, py-moneyed (display only) | Exact amounts | Ban `float` on money fields via lint |
| Search | PostgreSQL full-text (tsvector, pg_trgm, unaccent) | A-09 and V-01 search | Meets 300 ms p95; OpenSearch only if needed later |
| Jobs | Celery 5, Redis 7, django-celery-beat, celery-singleton / redis lock | Background jobs, schedules, idempotency | Flower for job dashboard (internal) |
| Feature flags | django-waffle (or flags table) | U-06 flags | Per org/practice/user |
| Billing | Stripe Python SDK, Stripe Billing, Checkout/Elements, ACSS Debit (PAD), Stripe CLI | U-04 | Test mode until client keys |
| Files | django-storages + boto3, MinIO (dev), S3-compatible Canadian bucket | A-06 | Signed URLs 5 min |
| Virus scan | ClamAV (clamd) container + python-clamd | A-06 scan hook | Quarantine bucket |
| MIME | python-magic (libmagic), Pillow, pypdf (page count only) | Validate uploads, thumbnails | — |
| Inbound email | Provider inbound webhook (Postmark/SES/Mailgun) + `email` stdlib parser | Per-org inbox address | Address format `docs+<token>@in.numo9…` |
| Outbound email | django-anymail + provider; MJML for templates | A-07 | Bounce webhooks |
| DNS check | dnspython, checkdmarc | SPF/DKIM/DMARC verification | — |
| PDF (template baseline) | WeasyPrint | Letter-size templates baseline (A-10) | Full docs in Phase 1 |
| Spreadsheets | openpyxl, python-calamine (fast read), tablib | B-03 import/export, A-04 exports | — |
| CSV | `csv` stdlib, charset-normalizer | Encoding detection on imports | — |
| Validation | phonenumbers, custom BN/Postal-code validators | Contacts, settings | — |
| Time | zoneinfo, python-dateutil | Org-local time logic | America/Toronto default |
| Frontend | Next.js 15 (App Router), React 19, TanStack Query, React Hook Form + Zod | App UI | — |
| Styling | Tailwind CSS, CSS variables design tokens, Radix UI primitives, cmdk (command palette) | Design system | Logical properties for RTL |
| Data grid | TanStack Table + TanStack Virtual | Shared grid, directory | One `DataGrid` component |
| Charts | Recharts or visx | Dashboards, heatmap | Zero renders as 0 |
| i18n | ICU MessageFormat via next-intl (FE), Django gettext + ICU (BE), FormatJS CLI extraction | en-CA / fr-CA | Missing-key gate |
| Design | Figma (wireframes, components), FigJam (flows), Storybook 8 | Design system docs | Original Numo9 brand |
| Visual regression | Chromatic or Playwright screenshot diff | A-10 acceptance | Per component and per page |
| Unit tests | pytest, pytest-django, pytest-xdist, factory_boy, Faker (en_CA), Hypothesis, freezegun/time-machine | Backend | Coverage ≥ 85 % on ledger/billing |
| FE tests | Vitest, Testing Library, MSW (API mocks) | Frontend | — |
| E2E | Playwright (+ axe-core/playwright) | Flows, a11y, i18n layout | Trace on failure |
| Performance | k6, Locust (optional), pgbench, EXPLAIN ANALYZE, django-silk (dev) | 1,000 concurrent postings, directory p95 | — |
| Lint/format | ruff, black (via ruff format), mypy + django-stubs, eslint, prettier, stylelint | Code quality | pre-commit |
| Architecture lint | import-linter, custom Django check (`OrgOwnedModel` rule), eslint custom rules (no hard-coded strings, no raw `<table>`) | Boundaries | CI gate |
| Glossary lint | Custom script over i18n catalogues (en-CA spellings, banned terms: VAT, State, ZIP, annual leave, Organization, Check) | Gap #31, #38 | CI gate |
| Security | OWASP ZAP baseline, pip-audit, npm audit, gitleaks, Trivy (images), semgrep (Django/React rules), Bandit, Dependabot/Renovate | S-03 | No high findings |
| Secrets | Docker secrets / SOPS + age, provider secret manager | S-03 | Never in Git |
| Encryption | cryptography (Fernet/AES-GCM) via django-fernet-fields style custom field, key rotation | Field-level encryption | KMS-held master key |
| Containers | Docker, Docker Compose, BuildKit, multi-stage images | All envs | — |
| Reverse proxy | Caddy 2 | TLS, HSTS, CSP headers | Auto-TLS |
| CI/CD | GitHub Actions, GitHub Environments (staging/prod approvals), GHCR | S-01 | Tag-based deploy |
| IaC | Terraform (or OpenTofu) + Ansible | S-02 server/bucket/DNS | Canadian region |
| Observability (baseline) | Sentry (self-host or SaaS), structlog JSON logs, Prometheus client, Grafana | Errors, metrics | Full S-04 in Phase 5 |
| Dev env | Makefile, docker-compose.dev, Mailpit, MinIO, Stripe CLI, ngrok/cloudflared (webhooks), direnv | Local dev | `make up` one command |
| Docs | MkDocs Material, ADR template (MADR), Mermaid diagrams | `docs/` | ADR-001 in Phase 0 |
| Project tracking | GitHub Projects (issues per atomic task), PR template with Rule 10 report | Reporting | — |
| **Internal tools to build** | `manage.py tenant_sweep` (router sweep), `seed_demo` (U-07 dataset), `load_coa_template` (C-01), `make_fixture_practice --orgs 2000` (perf), `founding_race_test` (U-08 1,500 concurrent), `post_storm --n 1000` (C-02), `permcat_export` (A-03), `featurematrix_export` (U-01), `check_i18n` & `check_glossary`, `audit_verify` (hash-chain check), job dashboard page, owner-console impersonation tool | Verification and operations | Committed under `backend/tools/` |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 — Objective
Stand up the Numo9 foundation: secure Canadian infrastructure, two-level tenancy, authentication/RBAC/audit/settings/files/notifications/jobs/search/design system, the SaaS commercial layer, the accountant workspace, contacts, the Canadian chart of accounts and the two-book posting engine — so that the Phase 0 exit demonstration passes on staging.

### 5.2 Level 2 — Components

| Component | Deliverables | Purpose |
|---|---|---|
| S — Infrastructure & Security | S-01, S-02, S-03, S-06 | Repo, CI/CD, environments, Canadian hosting, security baseline, scale baseline |
| A — Platform Core | A-01 … A-10 | Tenancy, auth, RBAC, audit, settings/locks, files, notifications, jobs, search, design system |
| U — SaaS, Packages & Billing | U-01 … U-08 | Products, packages, entitlements, Stripe billing, trial, owner console, demo, founding offer |
| V — Accountant Workspace | V-01 … V-05 | Directory, groups/tags, bulk actions, cross-org dashboards, staff management |
| B — Contacts | B-01 … B-03 | Contact model, activity/statements, import/export |
| C — General Ledger foundation | C-01, C-02 | Chart of accounts, posting engine with book dimension |

### 5.3 Dependency graph and execution order

```
S-01 ─┬─ S-02 ─ S-03 ─ S-06(baseline)
      │
      └─ A-10(design tokens + shell)        (FE track starts day 1 in parallel)
A-01 ─ A-02 ─ A-03 ─┬─ A-04 ─┬─ A-05
                    │        ├─ A-06 ─ A-07
                    │        └─ A-08 (needed by A-06/A-07/U-04/U-05)
                    └─ U-01 ─ U-02 ─ U-03 ─┬─ U-04 ─ U-05 ─ U-08
                                           ├─ U-06
                                           └─ U-07 (needs B-01, C-01, C-02 for seed)
A-01 ─ V-01 ─ V-02 ─ V-03 ; V-04 (needs U-05 trials) ; V-05 (needs A-03, A-04)
A-01 ─ B-01 ─ B-02 ; B-03
A-01 ─ C-01 ─ C-02
A-09 (needs A-01, B-01, C-01, C-02 indexes) — last
```

**Execution order** (‖ = can run in parallel):
1. S-01 ‖ A-10 (tokens, shell, Storybook)
2. S-02 ‖ A-01
3. S-03 ‖ A-02
4. A-03 ‖ A-08
5. A-04 ‖ U-01 ‖ C-01
6. A-05 ‖ U-02 ‖ C-02 ‖ B-01
7. A-06 ‖ U-03 ‖ V-01 ‖ B-03
8. A-07 ‖ U-04 ‖ V-02 ‖ B-02
9. U-05 ‖ U-06 ‖ V-03 ‖ V-05
10. U-07 ‖ U-08 ‖ V-04 ‖ S-06 baseline
11. A-09 (indexes every record type) → phase exit rehearsal

---

## 6. PLAN — Deliverable cards with ATOMIC TASKS (Rule 3)

### 6.1 Component S — Infrastructure & Security

### S-01 · Repository, CI/CD, environments
- **Branch:** `feature/S-01-repo-ci-envs`
- **Objective:** a monorepo with working CI/CD and three environments so every later branch is built, tested and deployed the same way.
- **Current behaviour:** no repository. **Expected behaviour:** `main` protected; every PR runs lint, type check, unit, integration, i18n, glossary, isolation sweep and security scans; tags `vX.Y.Z` deploy to staging; production deploy requires manual approval; root and legacy-style URLs redirect.
- **Gap #s closed:** 2 (root/legacy URL redirects), groundwork for 1, 31, 38.
- **Business rules:** no merge without green CI + one reviewer; no secrets in repo; deploy only from tags; mobile tags `mobile-vX.Y.Z` reserved.
- **Edge cases:** flaky tests (quarantine label with issue, never silent skip); CI secrets missing on forks; long-running migrations on deploy.
- **UI/UX notes:** redirect map makes `/`, `/o/:org`, `/o/:org/settings`, `/login/` and typo variants land on the right page; custom 404 offers search + "Go to Home".
- **Dependencies:** none.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| S-01-T01 | Create GitHub repo, monorepo layout `backend/ frontend/ mobile/ infra/ docs/ tools/`, `.editorconfig`, `.gitignore`, `.tool-versions`, LICENSE placeholder, CODEOWNERS | OPS | — | Tree matches layout; `git status` clean | Manual review |
| S-01-T02 | Branch protection on `main` (PR required, 1 review, status checks, linear history, no force-push); branch naming rule documented | OPS | T01 | Direct push to main rejected | Attempt push |
| S-01-T03 | Backend skeleton: Django 5 project `numo9`, settings split (base/dev/test/staging/prod) via env vars, health endpoint `/healthz` | BE | T01 | `curl /healthz` → 200 `{"status":"ok"}` | pytest smoke |
| S-01-T04 | Frontend skeleton: Next.js 15 App Router + TS strict + Tailwind; `/` renders shell placeholder | FE | T01 | `pnpm build` passes | Vitest smoke |
| S-01-T05 | `mobile/` Expo placeholder workspace (pnpm workspace) so CI paths exist | FE | T01 | `pnpm -w install` succeeds | CI job |
| S-01-T06 | Docker: multi-stage images for backend/frontend; `docker-compose.dev.yml` with Postgres 16, Redis 7, MinIO, Mailpit, ClamAV; `make up` | OPS | T03,T04 | `make up` starts all services healthy | Compose healthchecks |
| S-01-T07 | pre-commit: ruff, ruff-format, mypy, eslint, prettier, gitleaks, end-of-file fixers | QA | T03,T04 | Commit with lint error blocked locally | Run pre-commit |
| S-01-T08 | GitHub Actions `ci.yml`: backend job (ruff, mypy, pytest + coverage, migration linter), frontend job (eslint, tsc, vitest, build), caching | OPS | T07 | PR shows all checks; green on main | CI run |
| S-01-T09 | CI security jobs: pip-audit, npm audit, gitleaks, Trivy image scan, semgrep | OPS | T08 | Jobs run on PR; fail on high | Inject known-vuln dep in test branch |
| S-01-T10 | i18n extraction job: FormatJS + Django makemessages; fail on missing en-CA or fr-CA key; glossary lint (banned terms list) | QA | T08 | PR with hard-coded string fails | Fixture PR |
| S-01-T11 | Placeholder jobs for tenant sweep and gap tests (wired to real ones in A-01 / later) | QA | T08 | Jobs exist and pass empty | CI run |
| S-01-T12 | Image build & push to GHCR on tag; `deploy-staging.yml` triggered by `v*` tag via SSH/Compose pull; migrations then health-gate; rollback to previous tag on failed health | OPS | T08, S-02-T06 | Tag `v0.0.1` deploys staging | Tag + observe |
| S-01-T13 | `deploy-prod.yml` with GitHub Environment manual approval (project lead only) | OPS | T12 | Prod job waits for approval | Dry run |
| S-01-T14 | Redirect map: root → Home, `/o/:org` → Home, legacy-style paths (`/dashboard`, `/settings`, `/home`, trailing slash/case variants) → correct module; custom 404 with search | FE | T04 | Crawler test: 0 404 on 40 listed paths | Playwright `gap-02` |
| S-01-T15 | PR template with Rule 10 sections (Problem understanding, Task breakdown, Plan, Changes, Testing results, Remaining issues, Status) + Rule 11 checklist; issue template per atomic task | DOC | T01 | New PR shows template | Open draft PR |
| S-01-T16 | Renovate/Dependabot config (weekly, grouped) | OPS | T08 | First update PR opened | Observe |
| S-01-T17 | `docs/` MkDocs site skeleton + ADR template + CONTRIBUTING (branch policy, commit style) | DOC | T01 | `mkdocs build` passes | CI docs job |

- **Deliverable acceptance:** CI green on `main`; staging deploy from tag; every root and legacy-style URL redirects (gap #2).
- **Testing approach:** CI self-tests (intentional failing PR per gate), deploy smoke on staging, Playwright redirect crawl.
- **Risks & mitigations:** CI too slow → caching, xdist, path filters; flaky deploy → health-gated with auto-rollback.

### S-02 · Hosting & data residency
- **Branch:** `feature/S-02-hosting-residency`
- **Objective:** staging (and prod skeleton) running on HTTPS in a Canadian region per ADR-001.
- **Current behaviour:** nothing hosted. **Expected:** Canadian-region servers, object storage and backups; Caddy with TLS; DNS on the Numo9 domain; reproducible via IaC.
- **Business rules:** all personal and financial data stored in Canada; GMA access from Jordan only under Agreement §14 safeguards (audited SSH, least privilege).
- **Edge cases:** client account not ready (GMA interim account, same region, migrated later); DNS propagation delay; certificate rate limits.
- **UI/UX notes:** none user-facing beyond a maintenance page served by Caddy during deploys.
- **Dependencies:** S-01 (T06).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| S-02-T01 | Write ADR-001 (hosting provider + region, residency, cost owner, alternatives) and get client sign-off | DOC | — | ADR-001 merged with decision + sign-off reference | Review |
| S-02-T02 | Terraform: VPC/network, staging VM(s), firewall (80/443 public, 22 restricted to bastion IPs) | OPS | T01 | `terraform plan/apply` reproducible | Apply in staging |
| S-02-T03 | Terraform: S3-compatible buckets (`files`, `quarantine`, `backups`) in Canadian region, versioning, lifecycle, encryption at rest | OPS | T02 | Bucket region = CA; SSE enabled | CLI inspect |
| S-02-T04 | Managed or self-hosted PostgreSQL 16 in region with PITR enabled; PgBouncer | OPS | T02 | `SELECT version()` from app; PITR window configured | Connect test |
| S-02-T05 | Ansible: harden host (unattended upgrades, fail2ban, non-root deploy user, SSH keys only, auditd) | OPS | T02 | CIS-lite checklist passes | Lynis scan |
| S-02-T06 | Production-like `docker-compose.staging.yml` (app, worker, beat, frontend, redis, caddy, clamav) with secrets from env/SOPS | OPS | T04, S-01-T06 | Stack up on staging host | Health checks |
| S-02-T07 | DNS records: `app.`, `api.`, `staging.`, `console.`, `in.` (inbound mail MX later) on Numo9 domain | OPS | T02 | `dig` resolves | dig |
| S-02-T08 | Caddyfile: automatic TLS, HTTP→HTTPS, HSTS (preload-ready), compression, maintenance page | OPS | T06,T07 | `https://staging…` valid cert; SSL Labs A+ | SSL Labs |
| S-02-T09 | Data-residency register in `docs/` (where every data class lives, sub-processors list: Stripe, email provider, Sentry region) | DOC | T03 | Register complete | Review |
| S-02-T10 | Access policy: named SSH accounts, session logging, break-glass procedure | OPS | T05 | SSH session logged | Log check |

- **Deliverable acceptance:** ADR-001 recorded; staging live on HTTPS in the Canadian region.
- **Testing approach:** infra smoke (TLS, health, region check), SSL Labs, Lynis.
- **Risks:** client account delay → interim account documented in ADR-001 with migration step.

### S-03 · Security baseline
- **Branch:** `feature/S-03-security-baseline`
- **Objective:** secure-by-default platform: transport, headers, secrets, field-level encryption, scanning.
- **Current:** none. **Expected:** TLS/HSTS/CSP, CSRF, secure cookies, secrets never in Git, encrypted sensitive fields with rotation, zero high findings in ZAP/pip-audit/npm audit/gitleaks.
- **Business rules:** PIPEDA; SIN/bank details encrypted + masked + never logged (used fully in M-01, field type built now); PCI out of scope (Stripe Elements only).
- **Edge cases:** CSP breaking Stripe Elements/Next.js inline scripts (nonces); key rotation without downtime; logs leaking PII via exceptions.
- **UI/UX notes:** masked fields show `•••• 1234` with a "Reveal" action requiring permission + re-auth, and reveal is audited.
- **Dependencies:** S-01, S-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| S-03-T01 | Django security settings per env (SECURE_*, SESSION/CSRF cookie Secure/HttpOnly/SameSite, X-Frame DENY, Referrer-Policy) | BE | S-01-T03 | `manage.py check --deploy` 0 warnings | CI |
| S-03-T02 | CSP with nonces (Next.js middleware) allowing Stripe domains only; report-uri endpoint | FE | S-01-T04 | No CSP violations on pages; Stripe loads | Playwright console check |
| S-03-T03 | Secrets management: SOPS + age for env files; runtime secrets via provider secret store; rotate-secret runbook | OPS | S-02-T06 | No plaintext secret in repo (gitleaks clean) | gitleaks |
| S-03-T04 | `EncryptedField` (AES-GCM, envelope key from KMS/secret, key id stored with ciphertext) + rotation command | BE | T03 | Value unreadable in DB; rotation re-encrypts | pytest |
| S-03-T05 | `MaskedValue` serializer + "reveal" endpoint with permission, re-auth and audit hook | BE | T04, A-03 | Reveal without permission → 403; reveal audited | pytest |
| S-03-T06 | Log scrubbing: structlog processor + Sentry `before_send` removing SIN, bank, card, tokens, passwords | BE | S-01-T03 | Test log with SIN shows `[REDACTED]` | pytest |
| S-03-T07 | Brute-force protection: login rate limits, account lockout 15 min after 10 fails, CAPTCHA hook | BE | A-02-T03 | 11th attempt locked | pytest |
| S-03-T08 | OWASP ZAP baseline scan job against staging (nightly + pre-release) | QA | S-02-T08 | Report artefact; 0 high | CI |
| S-03-T09 | Dependency & image scans gating (pip-audit, npm audit, Trivy) with allow-list file requiring justification | QA | S-01-T09 | High finding fails build | Test branch |
| S-03-T10 | Security headers test (securityheaders-style check) in CI | QA | T01,T02 | All headers present | pytest/Playwright |
| S-03-T11 | Threat model (STRIDE) for tenancy, billing, files, auth — `docs/security/threat-model.md` | DOC | — | Document reviewed | Review |
| S-03-T12 | Security policy: vulnerability disclosure, incident contact, `security.txt` | DOC | S-02-T08 | `/.well-known/security.txt` served | curl |

- **Deliverable acceptance:** no high findings in ZAP / pip-audit / npm audit / gitleaks; encrypted fields unreadable at DB level; logs scrubbed.
- **Testing approach:** security category (§6.1 of plan), unit tests on encryption/masking, scans in CI.
- **Risks:** CSP over-strict → report-only first week, then enforce.

### S-06 · Multi-tenant scale (baseline)
- **Branch:** `feature/S-06-scale-baseline`
- **Objective:** put in place the scale mechanisms now so they don't have to be retrofitted.
- **Current:** none. **Expected:** PgBouncer pooling, partitioned posting and audit tables, per-org rate limits, usage-metering hooks, a fixture practice generator; full 500 orgs × 100k lines target verified in Phase 5.
- **Business rules:** per-org rate limit default 600 req/min burst 100 (configurable per package); metering events never block a request.
- **Edge cases:** partition key on cross-org platform queries; partition creation ahead of time (monthly by `posted_at` + hash by org); metering backlog.
- **UI/UX notes:** 429 shows "You're going a little fast — retrying in 5 s" with automatic retry in the client.
- **Dependencies:** S-02, A-01, C-02 (table definitions), A-04.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| S-06-T01 | PgBouncer transaction pooling configured; Django `CONN_MAX_AGE` tuned; server-side cursors disabled where incompatible | OPS | S-02-T04 | 500 concurrent connections served by pool | pgbench |
| S-06-T02 | Partition strategy ADR (journal_line, audit_event: range by month + org_id index) | DOC | — | ADR merged | Review |
| S-06-T03 | pg_partman setup and migration creating partitioned `ledger_journalline` and `audit_event` parents | DB | T02, C-02-T01, A-04-T01 | Inserts route to correct partition | pytest |
| S-06-T04 | Celery beat job pre-creating partitions 3 months ahead + alert if missing | BE | T03, A-08 | Partition for month+3 exists | pytest |
| S-06-T05 | Per-org rate limiter (Redis token bucket) middleware with package-based limits | BE | A-01, U-03 | Exceeding returns 429 + Retry-After | pytest |
| S-06-T06 | Frontend 429 handling: backoff + friendly toast | FE | T05 | Toast and auto-retry observed | Vitest + MSW |
| S-06-T07 | Usage-metering event API (`meter(org, key, qty)`) async via Redis stream → daily aggregates table | BE | A-08 | 10k events aggregate correctly | pytest |
| S-06-T08 | `make_fixture_practice --orgs N --lines M` generator | QA | C-02 | Generates 2,000 orgs for V-01 perf | Run command |
| S-06-T09 | Baseline k6 scripts (directory search, post journal, list contacts) + results stored | QA | T08 | Baseline report committed | k6 |
| S-06-T10 | Read-replica routing stub (DB router for reporting queries; points to primary until replica exists) | BE | S-02-T04 | Router selects alias by `using_replica()` | pytest |

- **Deliverable acceptance:** pooling, partitioned posting/audit tables, per-org rate limits and metering hooks in place; baseline numbers recorded; full scale target verified in Phase 5.
- **Testing:** performance category; partition routing tests.
- **Risks:** partitioning complicating FK constraints → FKs from lines to header kept via composite key; documented in ADR.

### 6.2 Component A — Platform Core

### A-01 · Practice & Organisation tenancy
- **Branch:** `feature/A-01-tenancy`
- **Objective:** two tenant levels with strict scoping so no user ever sees a record outside their membership/assignment.
- **Current:** none (Xero: one org per subscription; partner access via separate hub). **Expected:** `Practice` (free) ↔ `Organisation` (paying) via `PracticeAssignment`; org can have 0..n practices; every business record inherits `OrgOwnedModel`; all queries scoped by active organisation; practice queries fan out only over assigned orgs.
- **Business rules:** removal of assignment or membership revokes access on the next request (no cache window); cross-org ID → 404 (not 403, to avoid existence leaks); platform staff access only through audited impersonation (U-06).
- **Edge cases:** user in both a practice and as an org owner; org with two practices (bookkeeper + tax); background jobs without request context (explicit org context required); admin site bypass; bulk queries via `.objects` unscoped.
- **UI/UX notes:** org switcher (recent 5 + search); header always shows the active organisation name + practice badge "via Profitex"; switching orgs keeps the user on the equivalent page.
- **Dependencies:** S-01.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-01-T01 | Models `Practice`, `PracticeMember`(role), `Organisation`(status: demo/trial/active/grace/read_only/cancelled, time_zone), `OrganisationMember`(role), `PracticeAssignment`(practice, org, assigned staff M2M, role, active) + migrations | DB | S-01-T03 | Migrations apply; constraints unique(practice, org) | pytest |
| A-01-T02 | Abstract `OrgOwnedModel` (organisation FK, created_by, created_at, updated_at, deleted_at soft-delete, `uuid` public id) | DB | T01 | Subclass gets fields | pytest |
| A-01-T03 | Request context: middleware resolving active org from URL `/o/:org` or header `X-Numo9-Org`, acting practice, into `contextvars` | BE | T01 | `current_org()` correct per request | pytest |
| A-01-T04 | `OrgScopedManager` default manager filtering by `current_org()`; raises if no context (except `unscoped()` explicit, logged) | BE | T02,T03 | Query without context raises `TenantContextMissing` | pytest |
| A-01-T05 | Access resolver `can_access(user, org)` = org member OR member of an assigned practice and (practice-wide role or assigned staff/group) | BE | T01 | Truth table test passes | pytest + Hypothesis |
| A-01-T06 | DRF permission `IsOrgMemberOrAssigned` + object-level check returning 404 on foreign objects | API | T04,T05 | Cross-org ID → 404 | pytest |
| A-01-T07 | Celery task base class requiring explicit `org_id` and setting context | BE | T03, A-08-T01 | Task without org_id rejected | pytest |
| A-01-T08 | Django system check + import-linter rule: every model in business apps inherits `OrgOwnedModel` (allow-list for platform models) | QA | T02 | Adding a plain model fails `manage.py check` | pytest |
| A-01-T09 | Router sweep tool `manage.py tenant_sweep`: enumerates every URL pattern, creates objects in Org 1, requests as Org 2 user → expects 404 for each verb | QA | T06 | Sweep report lists all endpoints, 0 leaks | CI job (replaces S-01-T11 placeholder) |
| A-01-T10 | Revocation test: remove assignment mid-session → next request 404 (no caching of access) | QA | T05,T06 | Test passes | pytest |
| A-01-T11 | Property test over random membership graphs (Hypothesis) vs. resolver | QA | T05 | 1,000 examples pass | Hypothesis |
| A-01-T12 | Postgres RLS policies on top 5 sensitive tables as defence in depth (`app.current_org` GUC set per transaction) | DB | T03 | Raw SQL without GUC returns 0 rows | pytest |
| A-01-T13 | API: `GET /api/v1/me/organisations` (memberships + assignments), `POST /api/v1/practices`, `POST /api/v1/organisations` | API | T06 | Endpoints documented in OpenAPI | pytest |
| A-01-T14 | Org switcher component (recent 5, search, "Open directory"), active-org header, practice badge | FE | T13, A-10-T05 | Switch keeps equivalent route | Playwright |
| A-01-T15 | Admin site scoping (Django admin restricted to platform staff; org-scoped admin views use explicit unscoped with audit) | BE | T04 | Non-staff cannot open admin | pytest |
| A-01-T16 | Doc: tenancy model diagram + rules in `docs/architecture/tenancy.md` | DOC | T01–T06 | Doc merged | Review |

- **Deliverable acceptance:** removed practice member gets 404 on every record; cross-org ID → 404; router sweep passes.
- **Testing:** unit (manager), router sweep, property test, revocation test, RLS test.
- **Risks:** unscoped `objects.all()` → default manager + lint + sweep + RLS.

### A-02 · Authentication, sessions & sign-up
- **Branch:** `feature/A-02-auth-signup`
- **Objective:** secure, fast sign-up and login for every actor with all invitation flows.
- **Current (Xero):** separate My Xero account; invitations with limited role options. **Expected:** email/password with verification, reset, TOTP 2FA (mandatory for Platform Owner and Practice Admin when enabled), session list with revoke, invitations practice→staff, practice→org owner, org→user, org→accountant.
- **Business rules:** unverified users cannot log in; invite links single-use, expire 7 days, bound to the invited email; accountant invited by an owner lands assigned to that org; passwords ≥ 12 chars checked against breached list (k-anonymity).
- **Edge cases:** invite accepted by a logged-in different account (prompt to switch); user already exists (attach, don't duplicate); 2FA device lost (recovery codes + admin reset with audit); clock skew on TOTP (±1 step).
- **UI/UX notes:** 4-field sign-up; password strength meter; "Remember this device 30 days"; session list shows device, city/IP, last active, "Sign out other sessions"; new-device email.
- **Dependencies:** A-01, A-07 (email; Mailpit until then).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-02-T01 | Custom `User` model (email as username, name, locale, time format pref) — created before first migration | DB | S-01-T03 | Migration applies | pytest |
| A-02-T02 | django-allauth headless: sign-up (accountant / organisation path), email verification required, Argon2id hashing, breached-password validator | BE | T01 | Unverified login refused | pytest |
| A-02-T03 | Login/logout API, session cookie hardening, login rate limit | API | T02 | Correct 200/401/429 | pytest |
| A-02-T04 | Password reset (token 1 h, single-use, invalidates sessions) | BE | T02 | Reused token refused | pytest |
| A-02-T05 | TOTP enrolment (QR, verify, 10 recovery codes hashed), challenge at login, "remember device" signed cookie 30 days | BE | T03 | Wrong code refused; recovery code single-use | pytest + freezegun |
| A-02-T06 | 2FA enforcement policy flags (platform owner always; practice admin when practice enables) | BE | T05, A-03 | Enforced role cannot skip enrolment | pytest |
| A-02-T07 | Session registry (device, IP, UA, last_seen) + revoke one / revoke others; new-device email | BE | T03, A-07 | Revoked session gets 401 next request | pytest |
| A-02-T08 | `Invitation` model (type, inviter, target practice/org, role, email, token hash, expires, accepted_at) | DB | A-01-T01 | Unique pending per email+target | pytest |
| A-02-T09 | Invitation service: create/send/resend/revoke/accept for the 4 flows; accept binds email; owner→accountant creates `PracticeAssignment` (or pending practice if accountant has none) | BE | T08, A-01-T05 | Owner invites accountant → assigned | pytest |
| A-02-T10 | Sign-up screens (choose path, form, verify-sent, verified) | FE | T02, A-10 | Flow F1 ≤ 90 s in usability test | Playwright |
| A-02-T11 | Login, 2FA challenge, reset screens with CodeInput (paste-aware) | FE | T05 | Keyboard-only completion | Playwright + axe |
| A-02-T12 | Invitation accept screen (wrong-account handling, expired, used) | FE | T09 | All states rendered | Playwright |
| A-02-T13 | Security settings page: 2FA, recovery codes, sessions list | FE | T07 | Revoke works from UI | Playwright |
| A-02-T14 | Audit hooks: login success/fail, 2FA change, invite events → A-04 | BE | A-04-T03 | Events visible in audit | pytest |
| A-02-T15 | i18n keys EN/FR for all auth emails and screens | FE | T10–T13 | Missing-key gate passes | CI |
| A-02-T16 | Optional social sign-in behind feature flag (Google/Microsoft) — disabled by default | BE | T02, U-06 flags | Flag off → buttons hidden | pytest |

- **Deliverable acceptance:** unverified users blocked; single-use invites; owner invites accountant → assigned.
- **Testing:** unit, integration (email via Mailpit), E2E flows, security (rate limits, token reuse).
- **Risks:** email deliverability during verification → Mailpit in dev, provider with DMARC in staging.

### A-03 · Roles & permissions (RBAC + approval limits)
- **Branch:** `feature/A-03-rbac-limits`
- **Objective:** fine-grained, declarative permissions with custom roles and amount-based approval limits.
- **Current (Xero):** coarse roles, one role on the plan inspected, no limits. **Expected:** platform roles (Platform Owner, Platform Support), practice roles (Practice Admin, Accountant, Reviewer, Payroll Specialist, Read-only Staff), org roles (Owner, Admin, Accountant-delegate, Sales, Purchasing, Payroll, HR, Employee); custom roles; approval limits per user per document type (JE, bill, PO, pay run); permission catalogue exported; undeclared permission fails CI.
- **Gap #s:** 25, 40.
- **Business rules:** effective permission = union of roles ∩ entitlements (U-03); approval limit = min(user limit, role limit); approver ≠ creator enforced where required; owner role cannot be removed from the last owner.
- **Edge cases:** user with practice and org roles in the same org (union); limit in another currency (compare in base CAD); role edited while user mid-action (checked at commit).
- **UI/UX notes:** permission matrix grouped by module with search and "Copy from role"; limit editor with currency input per document type; "Preview as role" to see what a role can do.
- **Dependencies:** A-01, A-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-03-T01 | Permission catalogue in code (`permissions.py` per app: key, label i18n key, module, risk level) + registry | BE | A-01 | `permcat_export` lists all | pytest |
| A-03-T02 | Models `Role`(scope platform/practice/org, system flag, owner org/practice), `RolePermission`, `RoleAssignment`, `ApprovalLimit`(user or role, doc_type, max_amount CAD) | DB | T01 | Migrations; seed system roles | pytest |
| A-03-T03 | Seed system roles with default permission sets (data migration) | DB | T02 | 15 system roles present | pytest |
| A-03-T04 | Resolver `has_perm(user, org, key)` with request-level cache; union of practice + org roles | BE | T02, A-01-T05 | Truth table passes | pytest |
| A-03-T05 | DRF `RequiresPermission(key)` decorator/class; every view must declare `required_permission` per method | API | T04 | Endpoint without declaration fails system check | pytest |
| A-03-T06 | CI check: undeclared permission on any endpoint fails | QA | T05 | Fixture view without key → CI red | CI |
| A-03-T07 | Approval limit service `assert_can_approve(user, doc_type, amount)` raising `ApprovalLimitExceeded` with next eligible approvers | BE | T02 | $5,000 limit blocks $5,001 | pytest |
| A-03-T08 | Segregation-of-duties helper `assert_not_creator(user, obj)` | BE | T04 | Self-approval refused | pytest |
| A-03-T09 | API: roles CRUD (custom only editable), assign/unassign, limits CRUD, `GET /permissions/catalogue` | API | T05 | OpenAPI documented | pytest |
| A-03-T10 | Parameterised matrix test (role × endpoint × method) generated from catalogue + router | QA | T05, A-01-T09 | Matrix passes | pytest |
| A-03-T11 | Users & roles screen: members list, role chips, invite (reuses A-02) | FE | T09 | Assign role via UI | Playwright |
| A-03-T12 | Role editor: permission matrix by module, search, copy from role, risk badges | FE | T09 | Create custom role in < 1 min | Playwright |
| A-03-T13 | Approval-limit editor per user/role per document type | FE | T09 | Limit saved and enforced | Playwright |
| A-03-T14 | "Why can't I?" ExplainPanel payload (rule, required permission, who has it) + request-access notification | FE/BE | T04, A-07 | Refusal shows names | Playwright |
| A-03-T15 | Audit hooks for role/limit changes | BE | A-04 | Diff visible | pytest |
| A-03-T16 | Docs: permission catalogue page auto-generated into MkDocs | DOC | T01 | Page builds | CI |

- **Deliverable acceptance:** role × endpoint × method matrix passes; $5,000 limit blocks $5,001 bill; undeclared permission fails CI.
- **Testing:** unit, matrix, E2E role editor, security.
- **Risks:** permission sprawl → module grouping + risk levels; performance → cached per request.

### A-04 · Audit log & history
- **Branch:** `feature/A-04-audit-log`
- **Objective:** append-only, tamper-evident history with field-level diffs and exports.
- **Current (Xero):** 7-day default, no diffs, PDF/Excel only; system changes without attribution. **Expected:** every create/update/delete/state change with old → new values, actor (user/system job/impersonator), IP, device, request id; per-record and global viewer; 90-day default; CSV/XLSX/PDF equal to screen; DB rejects UPDATE/DELETE.
- **Gap #s:** 37, 44 (attribution).
- **Business rules:** system changes attributed to `System: <job name>`; impersonation logs both identities; retention ≥ 6 years; SIN/bank never stored in diffs (masked).
- **Edge cases:** bulk operations (one batch id, many rows); very large text diffs (truncate + full in detail); clock/timezone display per viewer.
- **UI/UX notes:** timeline per record (drawer on every detail page), global viewer with presets (Today, Last 7/30/90 days, This month/quarter/fiscal year, custom), filters (user, type multi-select, action), DiffViewer red/green with accessible labels (not colour only); "View record as of" [EXTRA].
- **Dependencies:** A-01, A-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-04-T01 | `AuditEvent` table (org, actor_user, actor_kind user/system/impersonation, impersonator, action, object type/id, changes JSONB, ip, ua, request_id, batch_id, created_at, prev_hash, hash) partition-ready | DB | A-01 | Migration applies | pytest |
| A-04-T02 | DB trigger/permissions: REVOKE UPDATE/DELETE; trigger raising on UPDATE/DELETE | DB | T01 | UPDATE raises | pytest raw SQL |
| A-04-T03 | Audit service `record(event)` + model mixin capturing field diffs on save (pre/post snapshot, masked fields) | BE | T01 | Edit amount shows old/new | pytest |
| A-04-T04 | Request middleware populating actor, IP, UA, request_id; job context for Celery | BE | T03, A-08 | System job attributed | pytest |
| A-04-T05 | Hash chain per org (SHA-256 of prev_hash + payload) + `audit_verify` command | BE | T03 | Tampered row detected | pytest |
| A-04-T06 | Bulk/batch support (batch_id, summary event) | BE | T03 | 500-row op → one batch | pytest |
| A-04-T07 | API: list with filters (date range default 90 days, user, type, action, object), per-record timeline, cursor pagination | API | T03 | Default range = 90 days | pytest |
| A-04-T08 | Exports CSV/XLSX/PDF from the same query object as the screen | BE | T07 | Export rows = screen rows | pytest |
| A-04-T09 | Global audit viewer screen (DataGrid, presets, filters, DiffViewer, export menu) | FE | T07, A-10 | Filters work; a11y passes | Playwright |
| A-04-T10 | Record history drawer component reusable on every detail page | FE | T07 | Drawer on contact & account | Playwright |
| A-04-T11 | "View as of date" reconstruct endpoint + UI [EXTRA] | BE/FE | T03 | Reconstructed state = historical snapshot | pytest |
| A-04-T12 | Time display honours user preference (24 h or 12 h with am/pm, never "16:33PM") | FE | A-10-T08 | Snapshot test | Vitest |
| A-04-T13 | Tests: export equality, append-only, masking, performance (1M rows list < 1 s with index) | QA | T08 | All pass | pytest |

- **Deliverable acceptance:** old/new values shown; DB rejects UPDATE; export = screen.
- **Testing:** unit, DB integrity, export equality, perf.
- **Risks:** write amplification → async insert via same transaction (outbox) only for non-critical events; financial events synchronous.

### A-05 · Org settings, fiscal year, per-module lock dates
- **Branch:** `feature/A-05-org-settings-locks`
- **Objective:** Canadian-correct organisation settings on clear pages, with per-module lock dates.
- **Current (Xero):** State/ZIP, BN split across 3 pages, no lock dates set, only 2 levels, silent system change. **Expected:** legal/display name (numeric-only rejected), Canadian address (Province picker, Postal code), BN + RT/RP/RC program accounts, QST number on one Tax Registrations page, FYE, CAD, time zone, numbering, default terms; locks for GL/AR/AP/Bank/Payroll/Tax at two levels (advisers-only / everyone).
- **Gap #s:** 3, 39, 44, 55.
- **Business rules:** posting dated on/before applicable lock refused naming the lock; advisers (Accountant practice roles) bypass only the "everyone except advisers" level; every change audited and attributed; FYE change only if no closed year after it.
- **Edge cases:** lock date moved backwards (requires reason); org time zone boundary for "on or before"; BN check digit; Quebec org needs QST.
- **UI/UX notes:** settings left nav deep-linkable per module; sticky save bar with unsaved-changes guard; lock matrix with impact preview; registrations repeater with masks `123456789 RT 0001`.
- **Dependencies:** A-01, A-03, A-04.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-05-T01 | `OrganisationSettings` model (legal_name, display_name, industry, structure, addresses, phone, email, website, FYE month/day, base_currency CAD locked, time_zone, time_format, default terms) | DB | A-01 | Migration | pytest |
| A-05-T02 | Validators: legal name not numeric-only; Postal code `A1A 1A1` + province first-letter consistency [EXTRA]; phone (phonenumbers CA) | BE | T01 | "1001633222" rejected | pytest |
| A-05-T03 | `TaxRegistration` model (type BN/RT/RP/RC/QST/PST-BC/PST-SK/RST-MB, number, effective_from/to, status, CRA approval ref) + BN Luhn check [EXTRA] | DB | A-01 | Invalid BN rejected | pytest |
| A-05-T04 | `LockDate` model (module GL/AR/AP/BANK/PAYROLL/TAX, level advisers_only/everyone, date, reason) + history via audit | DB | A-01 | Migration | pytest |
| A-05-T05 | Lock service `assert_not_locked(org, module, date, user)` returning `LockViolation(module, level, date)` | BE | T04, A-03 | Message names the lock | pytest |
| A-05-T06 | Hook lock service into posting engine (C-02) and generic document save | BE | T05, C-02-T05 | Posting before lock refused | pytest |
| A-05-T07 | Lock impact preview endpoint (count of drafts/unposted dated before) [EXTRA] | API | T05 | Count correct on fixture | pytest |
| A-05-T08 | Numbering sequences model per doc type (prefix, next number, padding) with row-lock allocation | DB/BE | A-01 | Concurrent allocation unique | pytest |
| A-05-T09 | API endpoints for settings, registrations, locks, numbering | API | T01–T08 | OpenAPI documented | pytest |
| A-05-T10 | Settings shell: left nav with deep links `/settings/{general,registrations,lock-dates,numbering,…}`; each module gear links its section | FE | A-10 | `gap-03` link test passes | Playwright |
| A-05-T11 | General settings form (Province select, Postal code mask, time zone, FYE) | FE | T09 | Saves; validation inline | Playwright |
| A-05-T12 | Tax registrations page (single page, repeater, history drawer) | FE | T09 | No tax setting elsewhere (until G-06 extends it) | Playwright |
| A-05-T13 | Lock dates matrix page with impact preview and reason prompt | FE | T07 | Flow F6 works | Playwright |
| A-05-T14 | Audit/attribution test: system-initiated change shows `System: <job>` | QA | A-04 | `gap-44` passes | pytest |
| A-05-T15 | i18n keys + Canadian terminology check | FE | T11–T13 | Glossary lint passes | CI |

- **Deliverable acceptance:** posting before lock refused naming the lock; changes audited and attributed.
- **Testing:** unit (validators, lock service), integration with posting, E2E settings.
- **Risks:** time-zone boundary errors → all lock comparisons on organisation-local date, property-tested.

### A-06 · File storage & documents inbox
- **Branch:** `feature/A-06-files-inbox`
- **Objective:** a fast, safe documents inbox with per-org inbound email and "create from file".
- **Current (Xero):** slow page (froze), no period tagging. **Expected:** upload/attach to any record, preview, virus scan, S3 storage, per-org inbound email, period/tax-year tags, Inbox/Archive, create bill/expense/asset from file (actions wired as modules arrive).
- **Gap #s:** 32.
- **Business rules:** 25 MB per file; allowed MIME: PDF, PNG, JPEG, HEIC, TIFF, CSV, XLSX, DOCX, OFX/QFX/QBO; infected files quarantined and owner notified; inbound email lands < 60 s; signed URLs 5 min; files from Org 1 unreachable from Org 2.
- **Edge cases:** email with 10 attachments (one document each), email from unknown sender (accepted, flagged), duplicate file (hash match → link to existing), HEIC conversion for preview, password-protected PDF.
- **UI/UX notes:** drag-and-drop anywhere on the inbox; upload progress per file; virtualised list; side-by-side previewer; bulk tag; copy-address button for inbound email; empty state explains the three ways to add documents.
- **Dependencies:** A-01, A-03, A-04, A-08, S-02 (buckets).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-06-T01 | `Document` model (org, file key, name, mime, size, sha256, status uploading/scanning/clean/infected, source upload/email, sender, tags period/tax_year, inbox/archived) + `Attachment` generic link | DB | A-01 | Migration | pytest |
| A-06-T02 | Storage backend (django-storages S3, MinIO dev), org-prefixed keys, signed URL service (5 min) | BE | T01, S-02-T03 | URL expires | pytest |
| A-06-T03 | Upload API: direct-to-S3 presigned POST + finalize; 25 MB limit; libmagic MIME validation | API | T02 | 26 MB refused; renamed .exe refused | pytest |
| A-06-T04 | Virus-scan Celery task via clamd; infected → quarantine bucket + notification | BE | T03, A-08 | EICAR file quarantined | pytest |
| A-06-T05 | Thumbnail/preview generation (PDF first page, images incl. HEIC) | BE | T04 | Preview available < 5 s | pytest |
| A-06-T06 | Per-org inbound address generation (`docs+<token>@in.<domain>`), rotate address | BE | T01 | Unique per org | pytest |
| A-06-T07 | Inbound webhook (provider) → parse MIME → one Document per attachment; signature verification; idempotent by Message-ID | API | T06, T03 | Email lands < 60 s in right org | Integration |
| A-06-T08 | Duplicate detection by sha256 within org (link, don't store twice) | BE | T03 | Same file twice → one object | pytest |
| A-06-T09 | Attach/detach to any `OrgOwnedModel` record; list attachments API | API | T01 | Attach to contact works | pytest |
| A-06-T10 | Tagging API (period YYYY-MM, tax year, custom tags), archive/unarchive, bulk | API | T01 | Filter by tag works | pytest |
| A-06-T11 | "Create from file" action registry (modules register actions: bill, expense, asset — Phase 1/2) with disabled-explained state until available | BE/FE | T09 | Action list renders with explanations | Vitest |
| A-06-T12 | Inbox UI: DropZone, virtualised list, filters, previewer, bulk tag, copy address | FE | T03–T10, A-10 | 1,000 files first paint < 1 s | Playwright perf |
| A-06-T13 | Attachments panel component for detail pages | FE | T09 | Reused on contact | Playwright |
| A-06-T14 | Isolation & security tests (cross-org file id → 404, signed URL for other org refused) | QA | A-01-T09 | Sweep passes | pytest |
| A-06-T15 | Audit hooks + i18n keys | BE/FE | A-04 | Events present | pytest |

- **Deliverable acceptance:** org isolation; 25 MB limit; MIME validated; inbound email lands < 60 s.
- **Testing:** integration (MinIO, ClamAV, inbound webhook), perf on inbox, security.
- **Risks:** provider inbound limits → queue + retries; large PDFs → async preview.

### A-07 · Notifications, email & custom sending domain
- **Branch:** `feature/A-07-notifications-email`
- **Objective:** one notification service for in-app and email, with branded templates and per-org verified sending domains.
- **Current (Xero):** emails from vendor domain; no per-contact language. **Expected:** in-app centre; branded templates per practice/org; EN/FR variants; bounce tracking flags contacts; SPF/DKIM/DMARC guidance and verification per org.
- **Gap #s:** 42.
- **Business rules:** transactional only (no marketing from app); unverified domain falls back to Numo9 domain with Reply-To org; bounced address flagged on contact and not retried for 30 days; user notification preferences per category.
- **Edge cases:** DKIM rotation; DNS partially configured; template missing FR (fallback EN + flag); high-volume reminders throttled.
- **UI/UX notes:** bell with unread count, drawer grouped by day, mark all read; email-domain page shows each DNS record as a copyable card with live status ✓/✗ and plain-language fix.
- **Dependencies:** A-01, A-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-07-T01 | `Notification` model (recipient, org, category, title key, body params, link, read_at) + API list/mark-read | DB/API | A-01 | Unread count correct | pytest |
| A-07-T02 | Notification service `notify(event, recipients, channels)` with category preferences | BE | T01 | Prefs respected | pytest |
| A-07-T03 | Email sending via django-anymail through Celery with retries; message log table | BE | A-08 | Failed send retried | pytest |
| A-07-T04 | Template system: MJML base layout, branding (logo, colour) per practice/org, EN/FR variants by locale | BE | T03 | FR template chosen for fr-CA | Snapshot test |
| A-07-T05 | `SendingDomain` model + provider API to create domain, fetch DKIM records | BE | T03 | Records stored | pytest (mocked) |
| A-07-T06 | DNS verification job (dnspython/checkdmarc) for SPF, DKIM, DMARC, return-path; status per record | BE | T05 | Status updates | pytest |
| A-07-T07 | DMARC pass test harness (send to test mailbox, parse Authentication-Results) | QA | T06 | Verified domain passes DMARC | Integration |
| A-07-T08 | Bounce/complaint webhook → flag `Contact.email_status` (B-01 field) / user email | API | T03 | Bounce flagged on contact | pytest |
| A-07-T09 | Notification centre UI (bell, drawer, prefs page) | FE | T01 | a11y live region announces | Playwright |
| A-07-T10 | Email-domain settings UI with copyable DNS cards and live checker | FE | T06 | Status flips to verified | Playwright |
| A-07-T11 | System message catalogue (verification, invite, trial reminders, dunning, new device) seeded | BE | T04 | All templates render | Snapshot |
| A-07-T12 | SMS/WhatsApp channel interface (no provider) | BE | T02 | Interface + null provider | pytest |

- **Deliverable acceptance:** verified domain passes DMARC; bounces flagged on contact.
- **Testing:** integration with provider sandbox, snapshot templates, DNS checks.
- **Risks:** deliverability → provider with Canadian region, warm-up, DMARC monitoring.

### A-08 · Background jobs & scheduling
- **Branch:** `feature/A-08-jobs-scheduling`
- **Objective:** reliable, observable background work with idempotency.
- **Current:** none. **Expected:** Celery + Redis + beat; job dashboard; idempotency keys; retries with backoff; no double tick across workers.
- **Business rules:** every job is org-scoped or explicitly platform; schedule ticks protected by distributed lock; job results retained 30 days.
- **Edge cases:** worker crash mid-task (acks_late + idempotency), beat restart, clock drift, poison messages (dead-letter after N retries).
- **UI/UX notes:** user-facing job tray (bulk edits, imports, exports) with progress and download; internal dashboard for platform owner.
- **Dependencies:** S-01, A-01.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-08-T01 | Celery app config (Redis broker/result, acks_late, prefetch 1, time limits, queues: default/high/io/reports) | BE | S-01-T06 | Worker consumes test task | pytest |
| A-08-T02 | `JobRun` model (org, type, status, progress, result, error, idempotency_key unique, started/finished) | DB | A-01 | Duplicate key rejected | pytest |
| A-08-T03 | Base task class: idempotency key check, org context, JobRun lifecycle, structured logging | BE | T02, A-01-T07 | Same key runs once | pytest |
| A-08-T04 | Retry policy: exponential backoff + jitter, max retries, dead-letter queue, visible error | BE | T03 | Failed job retried & visible | pytest |
| A-08-T05 | django-celery-beat with Redis lock per tick (`schedule_key:tick_ts`) | BE | T01 | Two beats → one execution | Integration |
| A-08-T06 | Progress API + SSE/websocket-lite polling endpoint for job tray | API | T02 | Progress updates | pytest |
| A-08-T07 | Job tray UI (progress, result link, error with retry) | FE | T06 | Bulk job shows progress | Playwright |
| A-08-T08 | Internal job dashboard in console (queues, failures, retry, purge) or Flower behind SSO | OPS/FE | T04 | Platform owner sees failures | Manual |
| A-08-T09 | Worker-restart test (kill worker mid-task → completes once) | QA | T03 | Exactly-once effect | Integration |

- **Deliverable acceptance:** retry with backoff visible; no double tick across workers.
- **Testing:** integration with real Redis, chaos (kill worker), concurrency.
- **Risks:** Redis loss → persistence AOF; critical schedules re-derivable.

### A-09 · Global search & quick-create
- **Branch:** `feature/A-09-search-quick-create`
- **Objective:** one search that finds everything (records, journals, accounts, settings, reports, navigation) and keyboard quick-create.
- **Current (Xero):** search misses journals, accounts, settings, reports; AI can read journals search cannot. **Expected:** unified index over all record types incl. journal narration, accounts, settings pages, reports catalogue, navigation; command palette with quick-create shortcuts documented in-UI.
- **Gap #s:** 52.
- **Business rules:** results respect tenancy + permissions + entitlements (gated items appear with lock icon and explanation); search over the active org; accountants can switch to "all my organisations" for contacts/org names.
- **Edge cases:** French accents (unaccent), partial codes ("54" → 5400), amounts ("1,130" finds invoice 1,130.00), very fresh records (index on save, not batch).
- **UI/UX notes:** `Ctrl/⌘+K` palette: groups (Go to, Create, Records, Settings, Reports), recent items, typo tolerance (pg_trgm), Enter opens, `Ctrl+Enter` opens in new tab; `?` shows shortcut sheet.
- **Dependencies:** A-01, A-03, B-01, C-01, C-02 (record types existing in Phase 0); later modules register providers.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-09-T01 | `SearchDocument` table (org, type, object id, title, subtitle, body tsvector, amount, date, permission key, feature key) with GIN + trigram indexes | DB | A-01 | Migration | pytest |
| A-09-T02 | Provider registry: each model registers `to_search_document()`; signals update on save/delete (same transaction) | BE | T01 | Contact saved → indexed | pytest |
| A-09-T03 | Providers for contacts, accounts, journals (narration + line descriptions), organisations, users, documents | BE | T02, B-01, C-01, C-02 | Journal narration found | pytest |
| A-09-T04 | Static providers: settings pages (incl. synonyms "lock date", "BN", "fiscal year"), reports catalogue, navigation entries — i18n aware | BE | T02 | "lock date" → settings page | pytest |
| A-09-T05 | Search API with permission/entitlement filtering, amount/number parsing, ranking (exact code > prefix > fts > trigram) | API | T03,T04, A-03, U-03 | Results filtered by role | pytest |
| A-09-T06 | Quick-create registry (shortcut, permission, feature key, route) with documented shortcuts (N I, N B, N C, N Q, N P, N J, N S, N R, N T, N U) | FE | A-10 | Shortcut sheet lists all | Vitest |
| A-09-T07 | Command palette UI (cmdk) with groups, recents, gated items explained | FE | T05, T06 | Keyboard-only flow | Playwright + axe |
| A-09-T08 | Shortcut sheet (`?`) and inline shortcut hints on buttons | FE | T06 | Every quick-create shows its shortcut | Playwright |
| A-09-T09 | Backfill command `reindex_search --org` | BE | T03 | Reindex matches counts | pytest |
| A-09-T10 | Perf: 1M documents, p95 < 150 ms | QA | T05, S-06-T08 | k6 report | k6 |
| A-09-T11 | Isolation test: search never returns other-org records | QA | A-01-T09 | Sweep passes | pytest |

- **Deliverable acceptance:** journal narration found; "lock date" opens settings; shortcuts documented.
- **Testing:** unit (ranking, parsing), integration, perf, isolation.
- **Risks:** index drift → reindex command + nightly consistency check.

### A-10 · Design system & localisation baseline
- **Branch:** `feature/A-10-design-system`
- **Objective:** one component library and localisation rules so every module looks and behaves the same.
- **Current (Xero):** two UI generations, three template systems, mixed date formats, banners, spelling flips, US Letter with cm, NZ sample data, a11y label leak. **Expected:** `@numo9/ui` with tokens, layout shell, DataGrid, LineGrid (shared by invoice/bill/PO/quote editors), forms, pickers, empty/loading/error/gated states, date/number formatting per locale, Canadian English, Letter with inch margins, no banners in work screens.
- **Gap #s:** 1, 12, 22, 26, 31, 38, 43, 60 (+ 2 shell routes).
- **Business rules:** no hard-coded strings (lint); one date format per locale (en-CA `26 Oct 2026` display, ISO `2026-10-26` input accepted; fr-CA `26 oct. 2026`); money `$1,234.56` / `1 234,56 $`; Numo9 original brand (yellow/black) from client assets.
- **Edge cases:** colour contrast with yellow; long French labels; RTL future (logical CSS); print styles.
- **UI/UX notes:** Storybook with usage do/don't for each component; density toggle; dark-mode-ready tokens (not shipped).
- **Dependencies:** S-01.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| A-10-T01 | Figma: brand tokens (colour incl. accessible yellow/black pairs, type scale, spacing, radius, elevation) from client assets | UX | client brand | Tokens approved | Review |
| A-10-T02 | Figma: wireframes for shell, directory, settings, contacts, CoA, journal, console (Phase 0 screens) | UX | T01 | Walkthrough approved by project lead | Review |
| A-10-T03 | `packages/ui` workspace, Tailwind config from tokens, CSS variables, Storybook 8 | FE | S-01-T04, T01 | Storybook builds | CI |
| A-10-T04 | Contrast validation script for token pairs | QA | T03 | All pairs ≥ 4.5:1 | CI |
| A-10-T05 | App shell: top nav, org switcher slot, practice nav, breadcrumbs, user menu, notification bell, job tray slot, responsive | FE | T03 | Shell at 360–1440 px | Playwright |
| A-10-T06 | Primitives (Radix-based): Button, IconButton, Input, Select, Combobox, Checkbox, Radio, Switch, Dialog, Drawer, Tooltip, Toast (with Undo), Tabs, Badge, StatusBadge | FE | T03 | Storybook + a11y tests | Vitest + axe |
| A-10-T07 | Form kit: RHF + Zod field wrappers, inline errors, error summary, sticky save bar, unsaved-changes guard | FE | T06 | Focus moves to first error | Vitest |
| A-10-T08 | Formatters: `formatMoney`, `formatDate`, `formatTime` (user 12/24 h), `parseMoney`, `parseDate` (forgiving) per locale | FE | T03 | Unit tests en-CA/fr-CA | Vitest |
| A-10-T09 | Pickers: DatePicker (shortcuts: +7, +14, end of month, etc.), Province picker, PostalCode input, Currency input, Account picker (filter by type/side), Contact picker | FE | T08 | Keyboard-operable | Vitest + axe |
| A-10-T10 | DataGrid (TanStack Table + Virtual): sort, filter bar, column chooser, saved views hook, row selection, bulk bar, density, sticky header, empty/loading/error states | FE | T06 | 10k rows scroll at 60 fps | Playwright perf |
| A-10-T11 | LineGrid (document line editor) used by journal now and invoice/bill/PO/quote later: keyboard navigation, add rows, drag reorder, column chooser, totals footer | FE | T10 | Journal uses it; spec for D-01/E-02 | Vitest |
| A-10-T12 | State components: EmptyState (illustration + 1–3 actions), Skeletons, ErrorState with retry + report, ExplainPanel (gated/permission/lock/404) | FE | T06 | Used on every Phase 0 list | Visual regression |
| A-10-T13 | i18n setup: next-intl, ICU catalogues en-CA/fr-CA, pseudo-locale en-XA, eslint rule banning raw string literals in JSX | FE | T03 | Hard-coded string fails lint | CI |
| A-10-T14 | Backend i18n: Django locale middleware, user/org locale, gettext catalogues, error messages as keys | BE | S-01-T03 | API errors localised | pytest |
| A-10-T15 | Glossary lint (en-CA terms: organisation, cheque, Province, Postal code, GST/HST, vacation pay; banned: VAT, State, ZIP, annual leave, Organization, Check(s), Advisor) | QA | T13 | `gap-31`/`gap-38` pass | CI |
| A-10-T16 | Document template baseline (WeasyPrint): Letter 8.5×11 in, inch margins, Canadian sample data, brand header | BE | T01 | Rendered PDF dimensions = Letter | pytest |
| A-10-T17 | No-banner rule: eslint rule/component policy forbidding promo banners inside editor/list layouts; notices go to notification centre | QA | T05 | `gap-12` check | CI |
| A-10-T18 | Visual regression setup (Chromatic or Playwright snapshots) for components and Phase 0 pages | QA | T10–T12 | Baseline approved | CI |
| A-10-T19 | a11y suite: axe-core on all Storybook stories and Phase 0 routes; aria labels audit (no leaked hidden headers) | QA | T18 | 0 serious violations; `gap-60` | CI |
| A-10-T20 | Usage docs in Storybook (do/don't, microcopy rules §3.5) | DOC | T06–T12 | Docs published | Review |

- **Deliverable acceptance:** visual regression passes; i18n lint rejects hard-coded strings; editors share one grid (LineGrid).
- **Testing:** component tests, visual regression, a11y, pseudo-locale layout.
- **Risks:** design drift by module teams → CODEOWNERS on `packages/ui`, lint rules against raw tables/inputs.


---

### 6.3 Component U — SaaS, Packages & Billing

### U-01 · Product catalogue
- **Branch:** `feature/U-01-product-catalogue`
- **Objective:** a data-driven catalogue of sellable products (Accounting, Tax, Payroll, Inventory, Finance [v2.1]) plus free product sets (Practice, Portal) and placeholders for companion apps, each mapped to a set of feature keys that every gated endpoint and screen declares.
- **Current behaviour:** nothing exists. **Expected behaviour:** Platform Owner sees one catalogue; every feature key belongs to exactly one product; the full key → product matrix is exportable and shown inside the app ("What's in my package").
- **Gap #s closed:** #51 (Projects, Expenses, document capture sold as paid add-ons in Xero → included in the Accounting product), #41/#61 groundwork (in-app plan/feature matrix).
- **Business rules:** product codes immutable after first subscription (`accounting`, `tax`, `payroll`, `inventory`, `finance`, `practice`, `portal`); a feature key is `<product>.<area>.<action>` (e.g. `accounting.invoices.write`); read keys (`*.read`) are always granted for historical data of products once owned (U-03 rule); free sets are never billable; companion apps (`app.commerce` …) registered as products with `kind=companion`, `status=planned`.
- **Edge cases:** endpoint without a key (CI fail); a key declared twice in two products (DB unique constraint); renaming a product display name must not break keys; product retired while subscribed.
- **UI/UX notes:** Platform-owner "Products" screen (list + detail drawer); in-app "Package & features" page for organisation owners and accountants — a searchable matrix with ticks per package, grouped by product, in plain language ("Send invoice reminders before the due date"); no marketing banners.
- **Dependencies:** A-01, A-03 (permission catalogue pattern), S-01 (CI job).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| U-01-T01 | Design catalogue data model ERD (`Product`, `FeatureKey`, `ProductFeature`), naming convention for keys; record in `docs/architecture/feature-keys.md` | DOC | — | Reviewed doc merged; convention covers read/write/approve actions | Peer review |
| U-01-T02 | `Product` model (code, name_i18n_key, kind {main, free_set, companion}, status {active, planned, retired}, sort) + migration | DB | U-01-T01 | Migration applies; code unique; retired product cannot be deleted | Unit |
| U-01-T03 | `FeatureKey` model (key unique, description_i18n_key, product FK, is_read_only) + migration | DB | U-01-T02 | Duplicate key rejected by DB unique index | Unit |
| U-01-T04 | Data migration seeding 7 products and the Phase 0–1 feature keys (accounting.*, tax.*, practice.*, portal.*) | DB | U-01-T03 | Seed idempotent (run twice → same rows) | Unit |
| U-01-T05 | `@requires_feature("key")` DRF decorator + `RequiresFeature` permission class (resolution delegated to U-03 interface stub) | BE | U-01-T03 | Decorated view exposes `required_feature` attribute | Unit |
| U-01-T06 | Next.js `useFeature(key)` hook + `<Gated feature=…>` wrapper component (renders child or gated state from U-03) | FE | U-01-T05 | Storybook story shows allowed / gated states | Vitest + Storybook |
| U-01-T07 | CI check `manage.py check_feature_keys`: walks the URL router; fails if a business endpoint lacks a key or uses an unknown key | QA/OPS | U-01-T05, S-01 | CI red on an undeclared endpoint fixture, green otherwise | CI test |
| U-01-T08 | Frontend lint rule (eslint custom) — gated routes must declare `feature` in route metadata | QA | U-01-T06 | Lint fails on a route without metadata | Lint unit |
| U-01-T09 | API `GET /api/v1/catalogue/products` and `/feature-matrix` (key → product → packages) | API | U-01-T04 | JSON lists every key once; public-safe fields only | Integration |
| U-01-T10 | Feature-matrix export (CSV/XLSX via openpyxl) for platform owner | BE | U-01-T09 | Export rows = DB key count | Integration |
| U-01-T11 | Platform-owner Products screen (list, status chips, detail drawer showing keys) | FE/UX | U-01-T09 | Renders 7 products; planned companion apps shown greyed with "Planned" | Playwright |
| U-01-T12 | In-app "Package & features" page (searchable matrix, grouped, ticks per package, highlights current package) | FE/UX | U-01-T09, U-02 | Search "reminder" filters rows; current package column highlighted | Playwright + axe |
| U-01-T13 | i18n keys (en-CA, fr-CA placeholders) for all product and feature descriptions | FE | U-01-T04 | i18n lint passes; 0 hard-coded strings | i18n lint |
| U-01-T14 | Audit hooks on product/key changes (A-04) | BE | A-04, U-01-T02 | Changing product status writes audit row with diff | Integration |
| U-01-T15 | Docs: feature-key guide for developers (how to declare, how to test gating) | DOC | U-01-T07 | Doc in `docs/dev/` linked from README | Review |

- **Deliverable acceptance:** every gated endpoint/screen declares a feature key; matrix exported in-app; CI fails on an undeclared endpoint.
- **Testing approach:** unit (models, decorator), integration (APIs, export), CI-negative fixture, functional (matrix page), accessibility (axe).
- **Risks & mitigations:** key sprawl → naming convention + review; developers forgetting keys → CI router walk.

### U-02 · Packages & pricing
- **Branch:** `feature/U-02-packages-pricing`
- **Objective:** packages composed of products with monthly/annual CAD prices, effective-dated price versions, per-package limits, promo codes and a founding flag — all data entered by the Platform Owner.
- **Current:** nothing. **Expected:** owner builds "Starter / Growth / Complete" (names are client data) in a visual editor; price changes dated in the future never alter current subscriptions until renewal on/after the effective date (or never, if grandfathered); retiring a package hides it from sign-up but keeps subscribers running.
- **Gap #s:** #41 (plan clarity), #13 groundwork.
- **Business rules:** prices stored as integer cents in CAD; GST/HST on platform invoices computed by tax engine later (Phase 1) — Phase 0 stores `tax_behaviour=exclusive`; a `PackagePrice` row has `effective_from`, `effective_to` (null = open), no overlaps per (package, interval); price applied at renewal = price effective on renewal date unless `grandfathered=True` on subscription; promo codes: percent or fixed, duration (once / n months / forever), max redemptions, expiry, package restriction; limits: `max_org_users` (practice users never counted).
- **Edge cases:** overlapping price windows; retiring the only package; promo code race on last redemption; currency other than CAD (rejected); deleting a package with subscribers (refused, archive instead).
- **UI/UX notes:** Package editor with product toggles as cards, live preview of the public pricing card, price timeline visual (versions as a horizontal timeline with "today" marker), confirm dialog showing "N subscriptions affected at next renewal".
- **Dependencies:** U-01.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| U-02-T01 | Wireframes: package editor, price timeline, promo list (Figma) | UX | — | Approved frames for 3 screens incl. empty/error | Design review |
| U-02-T02 | `Package` model (code, name_i18n, description, status {draft, active, retired}, is_founding_eligible, limits JSON) + `PackageProduct` M2M | DB | U-01-T02 | Package with 0 products cannot be activated (validation) | Unit |
| U-02-T03 | `PackagePrice` model (package, interval {month, year}, amount_cents, currency='CAD', effective_from/to) + exclusion constraint (btree_gist) preventing overlaps | DB | U-02-T02 | Overlapping row rejected by DB | Unit |
| U-02-T04 | `price_for(package, interval, on_date)` service | BE | U-02-T03 | Returns version effective on date; raises if none | Unit + Hypothesis (random windows) |
| U-02-T05 | Package activation/retirement service with guards (no delete when subscribed; retire hides from sign-up) | BE | U-02-T02 | Retire keeps existing subscription status active | Unit |
| U-02-T06 | `PromoCode` model + `redeem()` with `SELECT … FOR UPDATE` on redemption counter | DB/BE | U-02-T02 | 50 concurrent redemptions on max=10 → exactly 10 | Concurrency test |
| U-02-T07 | Admin APIs CRUD packages/prices/promos (`/api/v1/platform/packages…`), platform-owner permission only | API | U-02-T04..06 | Non-owner gets 403; validation errors in field form | Integration |
| U-02-T08 | Public API `GET /api/v1/public/pricing` (active packages, current prices, founding badge data) consumed later by Q-01 | API | U-02-T04 | Response cached 60 s; excludes draft/retired | Integration |
| U-02-T09 | Package editor UI (product cards, limits, preview of pricing card) | FE | U-02-T07 | Owner creates package in < 2 min usability target | Playwright |
| U-02-T10 | Price timeline UI + future-dated price dialog showing affected subscriptions count | FE/UX | U-02-T07 | Dialog shows count from API; timeline marks today | Playwright |
| U-02-T11 | Promo code UI (create, usage bar, expire) | FE | U-02-T07 | Usage bar = redemptions/max | Playwright |
| U-02-T12 | Stripe Product/Price sync job (create Stripe Price per PackagePrice, never mutate existing) — stub until U-04 | BE | U-02-T03, A-08 | New version creates new Stripe price id; old untouched | Integration (stripe-mock) |
| U-02-T13 | Audit + i18n keys for packages/prices/promos | BE/FE | A-04 | Price change audited with old/new | Integration |
| U-02-T14 | Tests: future-dated price leaves current subscriptions unchanged (fixture with subscription renewing before effective date) | QA | U-02-T04, U-04 | Renewal before date uses old price | Integration |

- **Deliverable acceptance:** future-dated price change leaves current subscriptions; retiring a package is safe.
- **Testing:** unit + property tests on price windows, concurrency on promos, integration with stripe-mock, functional editor flows.
- **Risks:** Stripe price immutability → versioned prices; overlapping windows → DB exclusion constraint.

### U-03 · Entitlement engine
- **Branch:** `feature/U-03-entitlements`
- **Objective:** resolve organisation → subscription → package → products → features in one cached call; explicit gating everywhere (UI prompt naming the package; API 402 with required product); never a silent redirect.
- **Current:** nothing. **Expected:** downgrades remove write immediately, keep read of historical data; founding organisations (U-08) get all products; trial (U-05) and demo (U-07) resolve to their configured package; practice users acting inside an org inherit the org's entitlements, never their own.
- **Gap #s:** #6 (approval paywalled), #11, #14 (credit note silent redirect), #41 (generic upgrade banners), #61.
- **Business rules:** core accounting controls (approving invoices, credit notes, bank accounts, reminders, lock dates, audit) are NEVER gated inside the Accounting product — gating is per product, not per control; states: `trialing`, `active`, `past_due` (full access during grace), `read_only`, `cancelled` (read + export only), `demo`; `*.read` keys survive downgrade for data created while entitled; cache key `ent:{org_id}:{version}` invalidated on any subscription/package/override change; platform-owner override grants (time-boxed, audited).
- **Edge cases:** cache stale after webhook (version bump); org with no subscription (self-sign-up before choosing package → trial); practice-only user with no org selected; feature key unknown; clock skew at grace end.
- **UI/UX notes:** `<Gated>` renders an inline "locked" panel: icon, one sentence "Payroll runs are part of the Payroll product", buttons "See packages" / "Ask the owner" (accountants can't buy), never hides the nav item (shown with lock glyph + tooltip); read-only banner in the org header when `read_only` with the exact reason and date; 402 errors in forms show the same panel.
- **Dependencies:** U-01, U-02, A-01, A-03.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| U-03-T01 | ADR-005 entitlement resolution & caching (written, short) | DOC | — | ADR merged | Review |
| U-03-T02 | `Subscription` skeleton model (org, package, status, current_period_end, grace_until, founding flag, override JSON) — billing fields added in U-04 | DB | U-02-T02 | One active subscription per org (partial unique index) | Unit |
| U-03-T03 | `EntitlementOverride` model (org, product, granted_by, expires_at, reason) | DB | U-03-T02 | Expired override ignored | Unit |
| U-03-T04 | `resolve_entitlements(org)` service → `{products, features, mode: full/read_only/none, reason}` | BE | U-03-T02,T03 | Table-driven test over all statuses | Unit (parametrised) |
| U-03-T05 | Read-retention rule: products ever entitled stored in `OrgProductHistory`; read keys granted for them | BE | U-03-T04 | After downgrade Payroll read=true, write=false | Unit |
| U-03-T06 | Redis cache with version counter + invalidation signals on subscription/package/override save | BE | U-03-T04 | Change → next call returns new result (no TTL wait) | Integration |
| U-03-T07 | Wire `RequiresFeature` permission to engine; 402 payload `{code:"feature_not_in_package", feature, product, packages:[…]}` | API | U-01-T05, U-03-T06 | Gated endpoint returns 402 with product | Integration |
| U-03-T08 | Read-only mode middleware: unsafe methods → 402 `{code:"organisation_read_only", reason, since}` except billing/export endpoints | API | U-03-T04 | POST in read_only refused; export allowed | Integration |
| U-03-T09 | `GET /api/v1/orgs/{id}/entitlements` for frontend bootstrap | API | U-03-T06 | Response < 20 ms p95 cached | Integration + k6 micro |
| U-03-T10 | Frontend entitlement store (React Query) + `<Gated>` locked panel design | FE/UX | U-01-T06, U-03-T09 | Locked panel shows product name and CTA per role | Storybook + Vitest |
| U-03-T11 | Nav items with lock glyph + tooltip; no route redirects for gated routes (route renders locked panel) | FE | U-03-T10 | Visiting a gated URL shows panel, URL unchanged | Playwright (gap-14) |
| U-03-T12 | Read-only org header banner with reason/date and owner CTA | FE/UX | U-03-T10 | Banner text names reason | Playwright |
| U-03-T13 | Entitlement-leak test suite: for each feature key × status, assert allowed/denied | QA | U-03-T07 | Matrix test all green | Security test |
| U-03-T14 | Platform-owner override UI (grant product for N days with reason) | FE | U-03-T03, U-06 | Override visible in org audit log | Playwright |
| U-03-T15 | Gap-closure tests tagged gap-06/14/41 (approval never gated within Accounting; no redirect; explicit prompt) | QA | U-03-T11 | Tagged tests pass | Playwright |

- **Deliverable acceptance:** downgrade removes write, keeps read; no silent redirects; 402 API names product.
- **Testing:** parametrised unit matrix, leak suite, integration of cache invalidation, functional gating UI.
- **Risks:** stale cache → versioned keys; over-gating core controls → explicit rule + gap tests.

### U-04 · Subscription billing (Stripe)
- **Branch:** `feature/U-04-stripe-billing`
- **Objective:** organisations subscribe by card or PAD (ACSS Debit), with proration, renewals, platform invoices/receipts, dunning 3/5/7 days then read-only, cancellation with data export; accountants are never billed.
- **Current:** nothing. **Expected:** owner picks package + interval → Stripe Checkout/Payment Element → subscription active; webhooks idempotent; failed renewal → `past_due` (grace) → retries day 3, 5, 7 → `read_only` exactly at grace end; cancellation at period end with full export (ZIP: CSV/XLSX + PDFs + JSON ledger).
- **Gap #s:** #13 (subscription object), #41.
- **Business rules:** Stripe customer per organisation only (never per user/practice); webhook signature verified; `StripeEvent` table with unique `event_id` (idempotency); proration on upgrade immediate, downgrade at period end; platform invoices numbered by Stripe, mirrored locally; PAD mandate stored only at Stripe (PCI/PAD scope out); taxes: Stripe Tax off — platform GST/HST added as tax rate per province of the org (data).
- **Edge cases:** webhook arrives before checkout redirect; replayed events; out-of-order events (use Stripe object `created` + status precedence); card 3-D Secure; PAD 3–5 day settlement (status `processing` keeps access); org deleted at Stripe dashboard manually.
- **UI/UX notes:** "Billing" page for org owner only: current package card, next charge date & amount, payment method, invoices list with PDF; upgrade/downgrade comparison modal with proration preview ("You'll be charged $X today"); dunning banner with one-click "Update payment method"; practice users get no billing screen for themselves.
- **Dependencies:** U-02, U-03, A-08, A-07, S-03 (secrets).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| U-04-T01 | Stripe account config doc + env vars in secrets manager (test/live keys, webhook secret) | OPS/DOC | S-03 | Keys loaded from secrets; none in repo (gitleaks) | gitleaks |
| U-04-T02 | Extend `Subscription` with stripe_customer_id, stripe_subscription_id, interval, cancel_at_period_end, payment_method_type | DB | U-03-T02 | Migration applies | Unit |
| U-04-T03 | `StripeEvent` model (event_id unique, type, payload, processed_at, error) | DB | — | Duplicate event_id insert ignored | Unit |
| U-04-T04 | Customer creation service (one per org, metadata org_id) | BE | U-04-T02 | Second call returns same customer | Integration (stripe-mock) |
| U-04-T05 | Checkout session endpoint `POST /api/v1/orgs/{id}/billing/checkout` (card + acss_debit) owner-only | API | U-04-T04, U-02-T12 | Practice user → 403; owner gets session URL | Integration |
| U-04-T06 | Webhook endpoint with signature check, event persistence, Celery dispatch | API | U-04-T03, A-08 | Bad signature → 400; replay → no-op | Integration (Stripe CLI) |
| U-04-T07 | Handlers: `checkout.session.completed`, `customer.subscription.created/updated/deleted` → local state machine | BE | U-04-T06 | State transitions match table | Unit |
| U-04-T08 | Handlers: `invoice.paid`, `invoice.payment_failed`, `invoice.finalized` → `PlatformInvoice` mirror + receipt email | BE | U-04-T06, A-07 | Local invoice rows = Stripe invoices | Integration |
| U-04-T09 | Dunning scheduler: grace_until = failure + 7 d; reminder emails day 0/3/5/7; transition to read_only at grace end (beat job, idempotent) | BE | A-08, U-04-T08 | Fixture clock: read_only exactly at grace end | Unit (freezegun) |
| U-04-T10 | Upgrade/downgrade service with proration preview (`invoices.upcoming`) | BE/API | U-04-T07 | Preview amount equals Stripe upcoming invoice | Integration |
| U-04-T11 | Cancellation + export job (ZIP of CSV/XLSX/PDF/JSON) delivered as signed URL | BE | A-06, A-08 | ZIP contains every module dataset | Integration |
| U-04-T12 | Billing page UI (package card, method, invoices, cancel) | FE/UX | U-04-T05..T11 | Owner completes upgrade in ≤ 3 clicks | Playwright |
| U-04-T13 | Proration comparison modal + dunning banner | FE/UX | U-04-T10 | Banner appears in past_due with CTA | Playwright |
| U-04-T14 | Entitlement cache invalidation on every subscription change | BE | U-03-T06 | Entitlements reflect within one request | Integration |
| U-04-T15 | Out-of-order event resolution (precedence by `created`) | BE | U-04-T07 | Shuffled event fixture yields same final state | Property test |
| U-04-T16 | Security tests: practice user never sees billing endpoints for own account; webhook replay | QA | U-04-T12 | Tests pass | Security |
| U-04-T17 | Runbook section "Stripe billing incidents" | DOC | U-04-T09 | Runbook merged | Review |

- **Deliverable acceptance:** webhook replay → no duplicate; grace → read-only on schedule; practice users never billed.
- **Testing:** stripe-mock + Stripe CLI webhook forwarding, freezegun for dunning, property test on event ordering.
- **Risks:** double-processing → event table + idempotency; PAD settlement delay → `processing` state keeps access.

### U-05 · 30-day free trial
- **Branch:** `feature/U-05-free-trial`
- **Objective:** every new organisation starts a 30-day trial of a configurable package; reminders at 7/3/1 days and on expiry; loss-free conversion; one trial per BN/email.
- **Current:** nothing. **Expected:** sign-up → org created in `trialing` with full package → countdown chip in header → convert any time (data untouched) → if not converted at day 30 23:59 org-local time → `read_only` (data kept, export allowed) → reactivation by subscribing.
- **Gap #s:** #41 (clear plan state visible to all roles).
- **Business rules:** trial package set by Platform Owner (`TrialConfig`: package, days=30); uniqueness on normalised BN (9 digits) and owner email (lower-cased, plus-addressing stripped); trial orgs excluded from founding counter until first successful payment; reminders respect org time zone (A-05); accountant-created orgs also trial (owner invited later); trial converts when any payment succeeds.
- **Edge cases:** DST change in month of trial; BN entered after trial started (check then); org converts on last minute (race with expiry job → job re-checks status under lock); same person, different email (out of scope—BN catches business).
- **UI/UX notes:** header chip "Trial — 12 days left" (amber at ≤7, red at ≤1), click opens package comparison; trial-end screen is not a wall: books readable, banner "Your trial ended on … — choose a package to keep working"; reminder emails plain, with what happens to data.
- **Dependencies:** U-02, U-03, U-04, A-02, A-05, A-07, A-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| U-05-T01 | `TrialConfig` singleton model + admin field in U-06 | DB | U-02-T02 | One active config | Unit |
| U-05-T02 | `TrialRegistry` (normalised_bn, normalised_email, org, started_at) with unique indexes | DB | — | Second insert same BN → IntegrityError | Unit |
| U-05-T03 | Normalisers for BN and email (+tests incl. spaces, RT suffix, plus-addressing) | BE | — | Table test passes | Unit |
| U-05-T04 | `start_trial(org)` service: creates Subscription(trialing, trial_end = local 23:59:59 day 30) | BE | U-03-T02, A-05 | trial_end stored in UTC from org TZ | Unit (zoneinfo, DST fixture) |
| U-05-T05 | Hook into org creation (A-02 sign-up / accountant creates org) | BE | U-05-T04 | New org is trialing | Integration |
| U-05-T06 | Duplicate trial refusal with clear error (`trial_already_used`, shows masked existing org name to platform owner only) | API | U-05-T02 | 2nd trial same BN refused | Integration |
| U-05-T07 | Reminder job 7/3/1/0 days (idempotent per org+day) | BE | A-08, A-07 | Exactly one email per milestone | Unit (freezegun) |
| U-05-T08 | Expiry job with row lock; skips if converted | BE | A-08 | Convert at 23:59 local → stays active, all records intact | Integration (race test) |
| U-05-T09 | Conversion: first successful payment flips trialing→active without touching data; founding check (U-08) | BE | U-04-T07 | Record counts identical before/after | Data validation test |
| U-05-T10 | Header trial chip + comparison drawer | FE/UX | U-03-T10 | Colour thresholds correct; a11y contrast passes | Playwright + axe |
| U-05-T11 | Trial-ended read-only experience (banner, export button, subscribe CTA) | FE/UX | U-03-T12 | All lists readable; writes show locked panel | Playwright |
| U-05-T12 | Email templates EN (FR keys) for 4 reminders | FE/DOC | A-07 | Templates render with org name/date | Snapshot |
| U-05-T13 | Funnel events (trial_started, reminder_sent, converted, expired) for U-06 metrics | BE | U-06 | Events stored | Integration |

- **Deliverable acceptance:** conversion at day 30 23:59 local keeps all data; 2nd trial same BN refused.
- **Testing:** freezegun/DST fixtures, race test conversion vs expiry, data-count validation.
- **Risks:** timezone bugs → store UTC, compute from org TZ, DST fixtures.

### U-06 · Platform-owner console
- **Branch:** `feature/U-06-platform-console`
- **Objective:** one console for Profitex to see practices and organisations, subscription states, MRR/churn/trial funnel, edit packages, watch the founding counter, manage demos, impersonate with consent and audit, toggle feature flags.
- **Current:** nothing. **Expected:** platform-owner role only (2FA mandatory); every action audited; impersonation time-boxed (default 30 min, max 2 h), requires reason and (configurable) org-owner consent, appears in the org's audit log and shows a red banner to the impersonator.
- **Gap #s:** #41 (plan visible to support/advisers).
- **Business rules:** demo orgs excluded from all metrics; MRR = sum of active subscriptions normalised to monthly (annual/12) in CAD cents; churn = cancelled in period / active at start; feature flags via django-waffle (per org, per practice, %, global); impersonation cannot access billing payment methods or change passwords/2FA.
- **Edge cases:** impersonating a user who is themselves an owner of many orgs (scope to one org); session expiry mid-action; metrics with zero denominators.
- **UI/UX notes:** separate shell (`/platform`) with distinct accent colour so staff never confuse it with an org; KPI tiles (MRR, active orgs, trials, conversion %, churn, founding x/1,000) each drill down; tables with saved filters; impersonation start modal (reason, duration) and persistent red bar with countdown + "End session".
- **Dependencies:** A-01..A-04, U-01..U-05, U-07, U-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| U-06-T01 | Console IA + wireframes (dashboard, practices, orgs, packages, founding, demos, flags, impersonation) | UX | — | Frames approved | Review |
| U-06-T02 | Platform shell layout, route guard (platform roles + 2FA enforced) | FE | A-02, A-03 | Non-platform user → 404 page (no leak) | Playwright |
| U-06-T03 | Practices & organisations list APIs with filters (status, package, province, created) | API | A-01, U-03-T02 | Pagination, filters correct | Integration |
| U-06-T04 | Org detail view (subscription timeline, users, practices assigned, audit link) | FE | U-06-T03 | Shows state history | Playwright |
| U-06-T05 | Metrics service (MRR, active, trials, conversion, churn) excluding demo orgs; nightly snapshot table `PlatformMetricDaily` | BE | U-04, U-05 | Fixture metrics = hand calc; demo excluded | Unit |
| U-06-T06 | KPI tiles + trend charts (Recharts) with drill-down | FE | U-06-T05 | Tile count = drill-down list count | Playwright |
| U-06-T07 | Package editor integration (reuse U-02 screens) | FE | U-02-T09 | Accessible from console | Playwright |
| U-06-T08 | `ImpersonationSession` model (actor, target_user, org, reason, started, expires, ended) | DB | A-01 | Row created per session | Unit |
| U-06-T09 | Impersonation auth backend (django-hijack style, custom) with time-box, blocked endpoints list | BE | U-06-T08 | Expired session auto-ends; blocked endpoints 403 | Integration + security |
| U-06-T10 | Audit entries in target org log for start/end and every write during impersonation (`acting_as`) | BE | A-04, U-06-T09 | Org owner sees entries | Integration |
| U-06-T11 | Impersonation UI (modal, red bar, countdown, end) | FE/UX | U-06-T09 | Bar visible on every page | Playwright |
| U-06-T12 | Feature flags admin (django-waffle) UI per org/practice/% | FE/BE | — | Flag toggles reflect in `/me/flags` | Integration |
| U-06-T13 | Founding counter & demo manager panels (data from U-07/U-08) | FE | U-07, U-08 | Counter shows x/1,000 | Playwright |
| U-06-T14 | Security tests: RBAC on all /platform endpoints; impersonation limits | QA | U-06-T09 | All pass | Security |

- **Deliverable acceptance:** impersonation time-boxed and in org audit log; metrics exclude demo.
- **Testing:** metric fixtures, impersonation security suite, RBAC sweep.
- **Risks:** support abuse → consent, reason, audit, blocked endpoints.

### U-07 · Demo organisation
- **Branch:** `feature/U-07-demo-org`
- **Objective:** a free, instant, isolated demo org seeded with a Canadian dataset (Ontario retail company "Maple & Pine Supply Co." — fictional), resettable, watermarked, excluded from analytics and real emails, purged after 30 days of inactivity, convertible to trial (sample data wiped).
- **Current:** nothing. **Expected:** "Try the demo" → demo opens in < 10 s; reset restores the seed exactly; documents carry "DEMO — NOT A REAL DOCUMENT" watermark; outbound emails go to a sink (shown in an in-app "Demo outbox").
- **Gap #s:** #43 (Xero shows a New Zealand sample customer — Numo9 demo is Canadian: provinces, GST/HST/QST, BN format, Canadian banks), [EXTRA] guided demo tour.
- **Business rules:** seed defined as versioned fixture (`demo_seed_v1.json`) built through services (not raw inserts) so ledger invariants hold; Phase 0 seed covers contacts, CoA, opening JE; later phases extend seed (invoices incl. revision 101-1, bills, bank, payroll, assets, two filed GST periods, both books) — seed builder is plug-in per module; demo orgs flagged `is_demo`, no Stripe customer, excluded from founding counter & metrics; inactivity purge job.
- **Edge cases:** demo creation spike (template clone via `COPY`-style bulk create from a prebuilt template org for speed); user resets during another tab action; convert-to-trial when BN already trialled.
- **UI/UX notes:** diagonal subtle watermark on app header ("Demo"), persistent bar with "Reset demo" and "Start my free trial"; 6-step optional guided tour (Shepherd.js-like, own implementation styled to design system); demo outbox drawer.
- **Dependencies:** A-01, A-06, A-07, U-03, U-05, B-01, C-01, C-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| U-07-T01 | Demo dataset specification (company, 25 contacts across 6 provinces, CoA, opening TB) signed off by client | DOC | — | Client sign-off recorded (client input) | Review |
| U-07-T02 | `is_demo`, `demo_seed_version`, `last_active_at` fields on Organisation | DB | A-01 | Migration | Unit |
| U-07-T03 | Seed builder framework: registry of per-module seeders executed via services | BE | U-07-T02 | Seeder order resolved by dependencies | Unit |
| U-07-T04 | Phase 0 seeders: org settings, CoA template, contacts, opening balances JE | BE | B-01, C-01, C-02 | TB of seeded org = 0 | Data validation |
| U-07-T05 | Template-org cloning for speed (prebuilt hidden template refreshed on seed version change) | BE | U-07-T03 | Creation < 10 s p95 (k6) | Performance |
| U-07-T06 | Reset service (delete org data in FK-safe order, re-clone) | BE | U-07-T05 | Post-reset hash of seed tables = pristine hash | Data validation |
| U-07-T07 | Exclusions: metrics, founding, Stripe, real email (email backend routes demo to `DemoOutbox`) | BE | A-07, U-06-T05 | No outbound SMTP call for demo | Integration |
| U-07-T08 | PDF/print watermark hook in document renderer | BE | A-10 | Every demo PDF has watermark text | Snapshot |
| U-07-T09 | Inactivity purge job (30 days) | BE | A-08 | Fixture org purged at 30 d, not at 29 | Unit |
| U-07-T10 | Convert-demo-to-trial (new empty org + trial, demo deleted) | BE/API | U-05-T04 | New org has 0 sample records | Integration |
| U-07-T11 | Demo entry endpoint for website/public and for logged-in accountants | API | U-07-T05 | Anonymous demo gets limited-session user | Integration |
| U-07-T12 | Demo bar UI (reset, start trial, outbox) + watermark styling | FE/UX | U-07-T06..T10 | Bar visible; reset shows progress | Playwright |
| U-07-T13 | Guided tour (6 steps, skippable, remembers dismissal) | FE/UX | U-07-T12 | Tour completes; Esc closes | Playwright + axe |
| U-07-T14 | Seed extension contract doc for Phases 1–4 seeders | DOC | U-07-T03 | Doc lists required seed items per phase | Review |

- **Deliverable acceptance:** created < 10 s; never in metrics; reset restores seed exactly.
- **Testing:** k6 creation timing, hash-compare reset, exclusion tests.
- **Risks:** seed drifting from invariants → build via services + TB check in CI.

### U-08 · Founding offer (first 1,000)
- **Branch:** `feature/U-08-founding-offer`
- **Objective:** an atomic counter incremented on an organisation's first successful payment; founding orgs entitled to all products regardless of package; badge in app and website; auditable; marketing hooks stored.
- **Current:** nothing. **Expected:** 1,500 concurrent first payments → exactly 1,000 founding entitlements; counter "x of 1,000 remaining" live.
- **Business rules:** slot allocation in the same DB transaction that records the first payment, using a single-row `FoundingCounter` with `SELECT … FOR UPDATE` (or `UPDATE … WHERE allocated < 1000 RETURNING`); `FoundingSlot` (org unique, slot_no unique 1..1000); churn rule configurable (`keep_on_return` | `lose_on_cancel` | `keep_if_returns_within_days=N`); demo/trial never allocated; referral source + promo code stored on sign-up (`AcquisitionAttribution`).
- **Edge cases:** payment refunded within 24 h (configurable release); webhook replay must not double-allocate (unique org); counter at 999 with simultaneous payments.
- **UI/UX notes:** badge "Founding organisation #0427" on org profile and portal; website counter widget with live remaining number (cached 30 s) and graceful "Offer complete" state.
- **Dependencies:** U-03, U-04, U-05.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| U-08-T01 | `FoundingCounter` (single row, cap, allocated) + `FoundingSlot` models | DB | — | Unique constraints on org & slot_no | Unit |
| U-08-T02 | `allocate_founding_slot(org)` atomic SQL `UPDATE … WHERE allocated < cap RETURNING allocated` | BE | U-08-T01 | Returns slot or None | Unit |
| U-08-T03 | Hook into first-payment handler (U-04-T08) inside same transaction | BE | U-04-T08 | Replay does not allocate twice | Integration |
| U-08-T04 | Concurrency test: 1,500 parallel allocations (pytest-xdist / threads on real Postgres) | QA | U-08-T03 | Exactly 1,000 slots, no gaps | Concurrency |
| U-08-T05 | Entitlement: founding flag grants all products (incl. future products as they ship) | BE | U-03-T04 | Founding org on smallest package resolves all keys | Unit |
| U-08-T06 | Churn rule config + evaluation on cancel/return | BE | U-08-T05 | Each rule fixture behaves as configured | Unit |
| U-08-T07 | `AcquisitionAttribution` (referral source, utm, promo) captured at sign-up | DB/BE | A-02 | Stored for every new org | Integration |
| U-08-T08 | Public API remaining counter (cached) | API | U-08-T01 | Value = cap − allocated | Integration |
| U-08-T09 | Badge component + org profile display | FE/UX | U-08-T05 | Badge shows slot number | Storybook |
| U-08-T10 | Audit entries for each allocation/release | BE | A-04 | Audit lists every slot | Integration |
| U-08-T11 | Founding admin panel (list slots, export, release with reason) | FE | U-06 | Export count = allocated | Playwright |

- **Deliverable acceptance:** 1,500 concurrent payments → exactly 1,000 founding entitlements.
- **Testing:** real-Postgres concurrency test in CI service container.
- **Risks:** over-allocation → single atomic UPDATE; test at 1,500.

---

### 6.4 Component V — Accountant Workspace

### V-01 · Organisation directory
- **Branch:** `feature/V-01-org-directory`
- **Objective:** the accountant's home list of every organisation assigned to the practice, with full-text search (name, BN, owner, tags, industry, province), filters (package, trial/paid/demo, FYE, GST cycle, payroll yes/no, overdue items, unfiled returns), sortable columns, column chooser, saved views, keyboard navigation.
- **Current:** Xero offers a plain org-switcher list. **Expected:** 2,000 orgs searchable in < 300 ms p95; saved views per user; open an org in one keystroke.
- **Gap #s:** beyond Xero (client decision 3); #6 pattern (saved filters / column chooser) applied here.
- **Business rules:** only orgs assigned to the user (directly or via group, V-02) are listed; search uses PostgreSQL `tsvector` (simple + unaccent for French names) + trigram for partial BN; facets computed over the visible set; filters for GST cycle/overdue/unfiled are fed by denormalised `OrgDirectorySummary` (refreshed by signals/jobs) so later phases plug in.
- **Edge cases:** accented names (Québec), BN typed with spaces, user with 0 orgs (empty state with "Create organisation" and "Open demo"), archived orgs (hidden by default, toggle).
- **UI/UX notes:** dense table (40 px rows) with sticky header, quick filter chips, search box focused by `/`, `↑/↓` to move, `Enter` opens, `Ctrl/⌘+Enter` opens in new tab; column chooser drag-to-reorder; saved views in a left rail; status chips (Trial 12d, Paid, Demo, Read-only); org switcher (`Ctrl/⌘+K` "Go to organisation") reuses the same search.
- **Dependencies:** A-01, A-09, A-10, U-03.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| V-01-T01 | UX research brief + wireframes (directory, empty state, saved views rail, column chooser) | UX | — | Approved frames | Review |
| V-01-T02 | `OrgDirectorySummary` model (org, practice, search_vector, province, package, status, fye, gst_cycle, payroll_enabled, overdue_count, unfiled_count, tags cache) | DB | A-01 | Migration; GIN index on vector, trigram on bn | Unit |
| V-01-T03 | Summary refresh service + signals (org, subscription, tags changes) + nightly full rebuild job | BE | V-01-T02, A-08 | Change reflected < 5 s | Integration |
| V-01-T04 | Search/filter query builder (tsvector + trigram + facets), scoped to assigned orgs | BE | V-01-T02, A-01 | Unassigned org never returned (sweep) | Unit + security |
| V-01-T05 | API `GET /api/v1/practice/orgs` (q, filters, sort, page, columns) + facet counts | API | V-01-T04 | Contract per OpenAPI | Integration |
| V-01-T06 | Performance fixture: 2,000 orgs generator command `seed_practice --orgs 2000` | QA | V-01-T02 | Command creates data in < 2 min | — |
| V-01-T07 | k6 search benchmark p95 < 300 ms | QA | V-01-T05, V-01-T06 | Target met on staging-size DB | Performance |
| V-01-T08 | `SavedView` model (user, practice, name, filters JSON, columns, sort, is_default) + API | DB/API | — | Persists per user; not visible to others | Integration |
| V-01-T09 | Directory table UI (virtualised, sticky header, chips, row actions) | FE | V-01-T05 | Renders 2,000 rows smoothly (60 fps scroll) | Playwright |
| V-01-T10 | Search box with debounce (150 ms), highlighting matches | FE | V-01-T09 | Typing BN "123 456" finds 123456789 | Playwright |
| V-01-T11 | Filters panel + facet counts | FE/UX | V-01-T05 | Facet count = result count after applying | Playwright |
| V-01-T12 | Column chooser (shared design-system component) + saved views rail | FE | V-01-T08, A-10 | View persists after logout/login | Playwright |
| V-01-T13 | Keyboard navigation and `Ctrl/⌘+K` org switcher | FE/UX | V-01-T09 | All actions doable without mouse | Playwright + axe |
| V-01-T14 | Empty, loading (skeleton), error (retry) states | FE/UX | V-01-T09 | Snapshot for each state | Visual regression |
| V-01-T15 | i18n + accessibility (table semantics, aria-sort) | FE | V-01-T09 | axe 0 violations | axe |

- **Deliverable acceptance:** 2,000 orgs search < 300 ms p95; saved view persists per user.
- **Testing:** k6, isolation sweep on directory, functional keyboard flow.
- **Risks:** slow facets → denormalised summary + indexes.

### V-02 · Groups & tags
- **Branch:** `feature/V-02-groups-tags`
- **Objective:** practice-defined hierarchical groups ("Toronto office → Retail clients"), colour tags, many groups per org, group-by in directory, group-level staff assignment granting/revoking access.
- **Current:** none in Xero. **Expected:** assigning staff to a group grants access to every org in it (and orgs added later); removing revokes within one request (A-01 sweep).
- **Business rules:** groups are practice-scoped; tree via `django-treebeard` materialised path (max depth 5); effective access = direct assignments ∪ group assignments (including ancestor groups); tags: name unique per practice, 12-colour accessible palette; deleting a group requires choosing what happens to its staff access (remove) — confirm dialog shows affected orgs count.
- **Edge cases:** cycles (impossible with MP tree), moving a group subtree, staff in two groups covering same org (removal from one keeps access via other), org removed from practice (memberships cleaned).
- **UI/UX notes:** left rail tree with drag-and-drop (keyboard alternative "Move to…"), group badges in directory rows, tag picker with type-to-create, colour plus text (never colour alone).
- **Dependencies:** A-01, V-01.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| V-02-T01 | Wireframes: group tree, tag picker, group staff panel | UX | — | Approved | Review |
| V-02-T02 | `OrgGroup` tree model (treebeard MP_Node, practice FK) + `OrgGroupMembership` | DB | A-01 | Depth > 5 rejected | Unit |
| V-02-T03 | `Tag` + `OrgTag` models (practice-scoped, colour enum) | DB | A-01 | Unique name per practice | Unit |
| V-02-T04 | `GroupStaffAssignment` (group, practice_member, role) | DB | A-03 | Unique per group+member | Unit |
| V-02-T05 | Effective-access resolver update in A-01 scoping (direct ∪ group ∪ ancestors), cached per user | BE | V-02-T04, A-01 | Property test over random trees/assignments | Hypothesis |
| V-02-T06 | Cache invalidation on any membership/assignment change | BE | V-02-T05 | Revocation effective next request | Integration |
| V-02-T07 | APIs: groups CRUD/move, tags CRUD, assign orgs, assign staff | API | V-02-T02..T04 | Practice Admin only for structure changes | Integration |
| V-02-T08 | Directory "group by" + group filter + tag filter (V-01 extension) | BE/FE | V-01-T05 | Group-by headers show counts | Playwright |
| V-02-T09 | Group tree UI with drag-and-drop + keyboard "Move to…" | FE/UX | V-02-T07 | Move works by keyboard | Playwright + axe |
| V-02-T10 | Tag picker (type-to-create, colour + label) | FE | V-02-T07 | New tag created inline | Playwright |
| V-02-T11 | Delete-group dialog with affected org/staff counts | FE/UX | V-02-T07 | Counts match API | Playwright |
| V-02-T12 | Isolation sweep extension: group revocation → 404 on every org record | QA | V-02-T06, A-01 | Sweep passes | Security |
| V-02-T13 | Audit entries for group/tag/assignment changes | BE | A-04 | Audited | Integration |

- **Deliverable acceptance:** group assignment grants/revokes access to every org in it.
- **Testing:** property tests on access resolution, sweep.
- **Risks:** access leaks via stale cache → event-driven invalidation + sweep.

### V-03 · Bulk edit & bulk actions
- **Branch:** `feature/V-03-bulk-actions`
- **Objective:** select many orgs → change group, tags, assigned staff, safe settings (e.g., default payment terms, reminder defaults, FYE only if no posted transactions), send message, export list; preview before apply; per-org audit.
- **Current:** none in Xero. **Expected:** 200 orgs in one background job with per-row result (success / skipped with reason / failed with reason) — never a silent partial failure.
- **Business rules:** "safe settings" whitelist declared in code; each row applied in its own transaction; job resumable; result downloadable as CSV; user must have permission on every selected org (rows without permission → "skipped: no access").
- **Edge cases:** selection across pages ("select all 1,240 matching"), concurrent edits by others, job cancelled mid-run (completed rows stay, remaining "cancelled").
- **UI/UX notes:** selection bar appears at bottom ("27 selected · Select all 1,240"), action menu, preview step showing diff table (field / current → new per org, first 50 + count), progress drawer with live counters, result table filterable by outcome.
- **Dependencies:** V-01, V-02, A-04, A-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| V-03-T01 | Wireframes: selection bar, preview diff, progress, results | UX | — | Approved | Review |
| V-03-T02 | `BulkJob` + `BulkJobRow` models (action, params, status, outcome, message) | DB | — | Migration | Unit |
| V-03-T03 | Safe-settings whitelist registry + validators | BE | A-05 | Non-whitelisted field rejected | Unit |
| V-03-T04 | Preview service (computes diffs without writing) | BE | V-03-T03 | Preview writes 0 rows | Unit |
| V-03-T05 | Executor Celery task, per-row transaction, permission check per org, resumable | BE | V-03-T02, A-08 | Kill worker mid-job → resume completes rest once | Integration |
| V-03-T06 | Actions: group, tags, staff, settings, message (A-07), export (CSV/XLSX) | BE | V-03-T05, V-02 | Each action fixture passes | Integration |
| V-03-T07 | APIs: create preview, confirm, cancel, status stream (SSE/polling), results CSV | API | V-03-T04..T06 | Contract tests | Integration |
| V-03-T08 | Selection model in directory (page + "all matching" by query) | FE | V-01-T09 | Select-all uses server query, not ids | Playwright |
| V-03-T09 | Preview diff UI + confirm | FE/UX | V-03-T07 | Diff rows match API | Playwright |
| V-03-T10 | Progress drawer + results table | FE/UX | V-03-T07 | Counters update live | Playwright |
| V-03-T11 | Audit per org (actor, bulk_job_id) | BE | A-04 | 200 audit rows for 200 orgs | Integration |
| V-03-T12 | Load test: 200-org job completes, all rows have outcome | QA | V-03-T05 | 0 rows without outcome | Performance |

- **Deliverable acceptance:** 200 orgs in one job with per-row result; no silent partial failure.
- **Risks:** long transactions → per-row commits; partial failure → explicit outcomes.

### V-04 · Cross-organisation dashboards
- **Branch:** `feature/V-04-practice-dashboard`
- **Objective:** practice home showing deadlines across orgs (GST/HST, payroll remittances, T2, T4), unreconciled bank lines, unfiled returns, expiring trials, items awaiting the accountant's approval, per-staff workload; every figure drills down to the org list that produced it.
- **Current:** none. **Expected:** Phase 0 delivers the framework + widgets with available data (trials expiring, orgs without lock date, orgs without BN, dormant staff, assigned workload); later phases register data providers (deadlines from G-03a/N-07, unreconciled from F-05, approvals from C-04/E-02).
- **Business rules:** widget registry with provider interface `count(practice, user, filters)` + `orgs(...)`; figures computed from `OrgDirectorySummary`/provider tables, never sampled; "my orgs" vs "all practice" toggle per role.
- **Edge cases:** provider failure → widget error state with retry (Xero "Unable to load" gap #5 handled visibly and logged), 0 values render "0".
- **UI/UX notes:** grid of cards with large number + label + trend; click → directory pre-filtered (same URL params, shareable); deadline timeline (next 30 days) list; workload bar per staff; widget customise (reorder/hide) persisted per user.
- **Dependencies:** V-01, V-05, U-05, A-05.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| V-04-T01 | Wireframes practice home (cards, deadline timeline, workload) | UX | — | Approved | Review |
| V-04-T02 | Widget provider registry + interface | BE | — | Registering provider exposes widget | Unit |
| V-04-T03 | Phase 0 providers: trials expiring ≤7 d, orgs missing BN, orgs missing lock date, read-only orgs, dormant staff | BE | V-01-T02, V-05 | Counts = fixture | Unit |
| V-04-T04 | Workload provider (orgs per staff, open tasks placeholder) | BE | V-02-T05 | Matches assignments | Unit |
| V-04-T05 | Deadline provider interface + stub (filled by G-03a/N-07 later) | BE | V-04-T02 | Stub returns [] safely | Unit |
| V-04-T06 | API `GET /api/v1/practice/dashboard` with per-widget status (ok/error) | API | V-04-T02 | One failing provider doesn't fail the response | Integration |
| V-04-T07 | Drill-down: each widget returns directory filter params | BE | V-01-T05 | Drill list count = widget count | Integration |
| V-04-T08 | Cards UI + drill links + error/retry state | FE/UX | V-04-T06 | Zero renders "0" | Playwright |
| V-04-T09 | Customise dashboard (reorder/hide) persisted | FE | V-04-T08 | Persists per user | Playwright |
| V-04-T10 | Performance budget dashboard < 1.5 s on 2,000 orgs | QA | V-04-T06 | k6 target met | Performance |

- **Deliverable acceptance:** every figure drills down to its org list.
- **Risks:** heavy queries → summary table + caching 60 s.

### V-05 · Practice staff management
- **Branch:** `feature/V-05-practice-staff`
- **Objective:** invite accountants, assign practice roles (A-03), per-org/per-group assignment, dormant-user alert at 60 days without login, activity heatmap per user from the audit log.
- **Current (Xero):** subscriber not logged in for 4 months still held Manage users; coarse roles. **Expected:** dormant alert fires on day 60 to Practice Admins (in-app + email), with one-click "suspend access"; heatmap counts = audit counts.
- **Gap #s:** #40.
- **Business rules:** last_login tracked per user; dormant threshold configurable (default 60 d); suspended member keeps history; removing a member revokes all org access (A-01 sweep); last Practice Admin cannot be removed/downgraded.
- **Edge cases:** user invited but never accepted (expire invite after 14 d, show "Pending"); member also org owner elsewhere.
- **UI/UX notes:** staff table (name, role, orgs count, last active, status), detail page with 12-month heatmap (accessible: table alternative), assignment editor (orgs + groups with search).
- **Dependencies:** A-02, A-03, A-04, V-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| V-05-T01 | Wireframes staff list, detail with heatmap, assignment editor | UX | — | Approved | Review |
| V-05-T02 | Staff list API (role, orgs count, last_login, status) | API | A-01 | Practice-scoped | Integration |
| V-05-T03 | Invite flow reuse (A-02) with practice role selection + pending state/expiry | BE/FE | A-02 | Invite expires at 14 d | Integration |
| V-05-T04 | Assignment editor (orgs/groups) API + UI | API/FE | V-02 | Assignment grants access immediately | Playwright |
| V-05-T05 | Suspend/remove member service (last-admin guard) | BE | A-03 | Last admin removal refused | Unit |
| V-05-T06 | Dormant-user job (daily) → notification + dashboard widget | BE | A-07, A-08 | Alert at day 60 not 59 | Unit (freezegun) |
| V-05-T07 | Activity aggregation from audit log (daily counts per user) materialised | BE | A-04 | Heatmap counts = audit counts | Data validation |
| V-05-T08 | Heatmap component (SVG, colour scale + numeric tooltip, table fallback) | FE/UX | V-05-T07 | axe passes; table toggle | Storybook + axe |
| V-05-T09 | Staff list/detail UI | FE | V-05-T02 | Renders states | Playwright |
| V-05-T10 | Revocation sweep test after removal | QA | V-05-T05 | 404 everywhere | Security |

- **Deliverable acceptance:** dormant alert at 60 days; heatmap = audit counts.

---

### 6.5 Component B — Contacts

### B-01 · Contact model
- **Branch:** `feature/B-01-contact-model`
- **Objective:** one contact model with explicit roles (customer, supplier, both, employee, contractor, government agency), billing/shipping addresses with Province, default sales/purchase accounts, province-derived default tax, payment-terms master, credit limit warn/block with override approval, currency per contact, T4A/withholding flag, exemption certificate, portal access flag, statement preferences, custom fields, duplicate warning, merge.
- **Current (Xero):** roles inferred from transactions; Customers/Suppliers pages identical; no currency, terms master, withholding flag, exemption certificate, duplicate warning; credit limit block only. **Expected:** roles set explicitly; titled lists ("Customers", "Suppliers"); Quebec contact defaults to GST+QST; duplicate warning while typing (name/email/BN/tax ID); merge keeps full history inside one transaction.
- **Gap #s:** #19, #20, #43 (custom fields), #39 (Province/Postal code).
- **Business rules:** at least one role required; Canadian addresses validate postal code `A1A 1A1` and province enum (13); non-Canadian addresses use country + region free text; default tax code resolved later by G-02 from province — Phase 0 stores `tax_default_basis = province` and `province_tax_hint` (e.g., QC → GST+QST); `PaymentTerm` master per org (net N, day-of-next-month, EOM, 2/10 net 30 discount fields used by E-07/FN-04); credit mode `warn` | `block` (block requires approval by user with limit permission); currency ISO 4217, default org base CAD; custom fields typed (text, number, date, select) defined per org (max 30); contact soft-delete = archive; merge re-points all FKs (registry of referencing models) and keeps an alias of the merged contact number.
- **Edge cases:** same name different provinces (warn, not block); merging contacts with different currencies (refuse); employee role contact without HR record (allowed; HR links later); French accents in names (unaccent for duplicate detection).
- **UI/UX notes:** contact form as one page with section anchors (Details, People, Addresses, Financial, Sales defaults, Purchase defaults, Tax & compliance, Portal, Custom fields), role chips at top; Canadian address autocomplete (provider optional; manual entry always available with province dropdown); inline duplicate panel "Possible duplicate: Maple Supply Ltd (BN matches) — Open / Merge / Ignore"; credit-limit field with warn/block segmented control and explanation; lists titled per role with role tabs (All / Customers / Suppliers / Contractors / Agencies / Archived); people list unlimited.
- **Dependencies:** A-01, A-04, A-06 (certificate file), A-10, C-01 (default accounts).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| B-01-T01 | Wireframes: contact form (sections), list with role tabs, duplicate panel, merge dialog | UX | — | Approved | Review |
| B-01-T02 | `Contact` model (OrgOwnedModel: number, display_name, legal_name, roles ArrayField, bn, tax_id, currency, credit_limit, credit_mode, t4a_flag, portal_enabled, statement_pref, language, status) + migration | DB | A-01 | Role required validation | Unit |
| B-01-T03 | `ContactPerson` (unlimited, primary flag, email, phone, include_in_emails) | DB | B-01-T02 | >5 people allowed | Unit |
| B-01-T04 | `Address` (type billing/shipping, line1/2, city, province enum, postal_code, country) + postal-code/province validators | DB/BE | B-01-T02 | "M5V 2T6" valid; "12345" invalid for CA | Unit |
| B-01-T05 | `PaymentTerm` master per org (type, days, discount_pct, discount_days, late_interest_pct) + seeded defaults (Net 15/30/60, Due on receipt, 2/10 net 30, EOM) | DB | A-01 | Seed per new org | Unit |
| B-01-T06 | Sales/purchase defaults fields (account FKs to C-01, payment_term FK, amounts_are) | DB | C-01, B-01-T05 | Account picker validated by type (revenue vs expense) | Unit |
| B-01-T07 | Province tax hint resolver (QC → GST+QST, ON → HST13, BC → GST+PST …) exposed for G-02 | BE | B-01-T04 | Table test 13 provinces | Unit |
| B-01-T08 | Exemption certificate (file via A-06, number, expiry) + expiry reminder hook | DB/BE | A-06 | Expired certificate flagged | Unit |
| B-01-T09 | Custom field definitions + values (JSONB validated by definition schema) | DB/BE | A-01 | Type mismatch rejected | Unit |
| B-01-T10 | Duplicate detection service (trigram name similarity ≥0.6, exact email/BN/tax ID) | BE | B-01-T02 | Typing "Maple Suply" finds "Maple Supply" | Unit |
| B-01-T11 | API `/api/v1/orgs/{id}/contacts` CRUD + `/duplicates?q=` + list filters by role + feature key + tenant sweep registration | API | B-01-T02..T10, U-01 | Contract tests; sweep passes | Integration + security |
| B-01-T12 | Merge service: FK re-pointing via registry, history preserved, alias kept, single transaction, audit | BE | B-01-T11, A-04 | Failure mid-merge rolls back fully | Integration |
| B-01-T13 | Credit limit check service (warn/block + override approval request) used by D/E later | BE | A-03 | Block mode requires approver | Unit |
| B-01-T14 | Contact list UI (role tabs with titles, search, column chooser, saved views, archive) | FE | B-01-T11, A-10 | Tab title changes per role (gap-19) | Playwright |
| B-01-T15 | Contact form UI with section anchors, address entry, province picker, defaults | FE/UX | B-01-T11 | Create contact in < 60 s usability | Playwright |
| B-01-T16 | Live duplicate panel while typing (debounced) | FE/UX | B-01-T10 | Panel shows within 300 ms | Playwright |
| B-01-T17 | Merge dialog (side-by-side field chooser, preview of moved records count) | FE/UX | B-01-T12 | Merge keeps history visible on survivor | Playwright |
| B-01-T18 | i18n keys, Canadian terms (Province, Postal code), a11y review | FE | A-10 | i18n lint + axe pass | Lint/axe |
| B-01-T19 | Gap tests gap-19/20 + QC → GST+QST fixture | QA | B-01-T07 | Tagged tests pass | Integration |

- **Deliverable acceptance:** QC contact → GST+QST; duplicate warning while typing; merge keeps history.
- **Testing:** validators unit, merge rollback integration, duplicate detection fixtures (incl. accents), UI functional.
- **Risks:** merge missing a referencing model → FK registry + test that introspects all FKs to Contact.

### B-02 · Contact activity & statements
- **Branch:** `feature/B-02-contact-statements`
- **Objective:** per-contact timeline (documents, payments, emails, notes, changes); customer and supplier statements (outstanding / activity); supplier-statement reconciliation against bills.
- **Current (Xero):** no supplier-statement reconciliation. **Expected:** statement total = AR aging total for that contact on the same date; supplier statement uploaded (CSV/XLSX or manual lines) is matched to bills with differences listed.
- **Gap #s:** #23.
- **Business rules:** Phase 0 provides the timeline framework, statement engine and reconciliation engine against a `SubLedgerSource` interface; AR/AP documents arrive in Phase 1 (D/E) and register as sources — tests use fixture documents built through the interface; statements dated "as at" date; activity statements for a date range with opening balance; PDF on Letter with inch margins (A-10).
- **Edge cases:** contact with both roles (separate customer and supplier statements); credits/prepayments; foreign currency (statement in contact currency, R-02 later); zero-balance contacts excluded from bulk runs.
- **UI/UX notes:** contact page tab "Activity" (filterable timeline with icons and amounts), tab "Statements" (generate, preview, send, history); supplier reconciliation screen: two columns (their statement / our bills) with auto-match, unmatched highlighted, difference summary at top.
- **Dependencies:** B-01, A-06, A-07, C-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| B-02-T01 | Wireframes timeline, statement preview, supplier reconciliation | UX | — | Approved | Review |
| B-02-T02 | `ActivityEvent` model (contact, type, ref, amount, occurred_at, actor) + emitter API for modules | DB/BE | B-01 | Events ordered by time | Unit |
| B-02-T03 | `SubLedgerSource` interface (open items as at date, activity in range) + fixture implementation | BE | C-02 | Fixture source returns items | Unit |
| B-02-T04 | Statement engine (outstanding & activity types, opening balance, aging buckets) | BE | B-02-T03 | Total = sum of open items (= AR aging basis) | Unit + property |
| B-02-T05 | Statement PDF template (WeasyPrint, Letter, inch margins, EN/FR keys) | BE | A-10 | Snapshot matches fixture | Snapshot |
| B-02-T06 | Statement send via A-07 + history record | BE | A-07 | Sent statement stored in history and timeline | Integration |
| B-02-T07 | `SupplierStatement` + lines import (CSV/XLSX mapping) | DB/BE | A-06 | Imported lines count = file rows | Integration |
| B-02-T08 | Supplier reconciliation matcher (by invoice number, then amount+date ±3 d) + difference report | BE | B-02-T03, B-02-T07 | Fixture: 2 unmatched listed with amounts | Unit |
| B-02-T09 | APIs timeline, statements, reconciliation | API | B-02-T02..T08 | Contract tests; sweep | Integration |
| B-02-T10 | Activity tab UI with filters | FE | B-02-T09 | Filter by type works | Playwright |
| B-02-T11 | Statements tab UI (generate, preview, send) | FE | B-02-T09 | Preview equals PDF | Playwright |
| B-02-T12 | Supplier reconciliation UI (two-column, manual match, notes) | FE/UX | B-02-T09 | Manual match updates difference | Playwright |
| B-02-T13 | Data-validation test: statement total = AR aging total (activated with D in Phase 1; fixture now) | QA | B-02-T04 | Passes on fixture | Data validation |

- **Deliverable acceptance:** statement total = AR aging total for the contact on the same date.
- **Risks:** Phase 1 sources differ from interface → interface contract tests reused by D/E.

### B-03 · Import/export
- **Branch:** `feature/B-03-contact-import`
- **Objective:** CSV/XLSX import with column mapping, stable external ID matching (never by name), non-destructive updates (blank cells leave fields untouched), dry-run validation report, unlimited people; export of the same shape.
- **Current (Xero):** CSV only, headers must match, matches on name (renames create duplicates), blank Person columns delete people, max 5 people. **Expected:** re-importing the same file → 0 duplicates, 0 changes; a renamed contact updates in place.
- **Gap #s:** #15, #21.
- **Business rules:** match key priority: `external_id` → Numo9 contact number → (optional, opt-in) exact BN; never name; explicit clear token `__CLEAR__` to blank a field; people rows in a separate sheet/long format (contact_ref, person fields) unlimited; dry-run returns per-row action (create / update with changed fields / unchanged / error); apply runs as background job with per-row outcome (reuses V-03 job pattern); saved mappings per org; max 25 MB file (A-06).
- **Edge cases:** encoding (UTF-8, UTF-8-BOM, Windows-1252), date formats, duplicates within file, French column headers, Excel formulas (values only).
- **UI/UX notes:** 4-step wizard (Upload → Map columns with auto-suggest and sample values → Review dry-run with counts and filterable rows → Import); template download; mapping saved; errors downloadable as CSV with row numbers.
- **Dependencies:** B-01, A-06, A-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| B-03-T01 | Wireframes 4-step wizard | UX | — | Approved | Review |
| B-03-T02 | File parser (csv with charset detection via charset-normalizer, openpyxl read-only values) | BE | A-06 | 3 encodings parse identically | Unit |
| B-03-T03 | `ImportMapping` model (org, entity, column→field, saved name) + auto-suggest (fuzzy header match EN/FR) | DB/BE | — | "Courriel" maps to email | Unit |
| B-03-T04 | Row normaliser + validators (province, postal, email, currency, roles) | BE | B-01 | Invalid rows reported with reason | Unit |
| B-03-T05 | Matcher (external_id → number → opt-in BN) | BE | B-01 | Renamed contact matched by id | Unit |
| B-03-T06 | Diff engine (non-destructive; `__CLEAR__` handling) | BE | B-03-T05 | Blank cell → unchanged | Unit + property |
| B-03-T07 | Dry-run report (`ImportRun`, `ImportRunRow` with action & changes) | DB/BE | B-03-T06 | Dry-run writes 0 contacts | Integration |
| B-03-T08 | Apply job (per-row transaction, outcomes, audit) | BE | B-03-T07, A-08 | Re-import same file → 0 changes | Integration (gap-21) |
| B-03-T09 | People long-format import (unlimited) | BE | B-03-T08 | 12 people for one contact imported | Integration |
| B-03-T10 | Export CSV/XLSX in importable shape (round-trip) | BE | B-01 | Export → import = 0 changes | Integration |
| B-03-T11 | APIs upload, map, dry-run, apply, status, errors CSV | API | B-03-T02..T10 | Contract tests | Integration |
| B-03-T12 | Wizard UI steps 1–4 | FE/UX | B-03-T11 | Complete import of 500 rows in < 3 min usability | Playwright |
| B-03-T13 | Template download + help text (plain language) | FE/DOC | B-03-T11 | Template headers = mapping fields | Unit |
| B-03-T14 | Gap tests gap-15/21 | QA | B-03-T08 | Pass | Integration |

- **Deliverable acceptance:** re-import → 0 duplicates, 0 changes; renamed contact updates in place.
- **Risks:** destructive updates → diff engine property test (blank never clears).

---

### 6.6 Component C — General Ledger (foundation)

### C-01 · Chart of accounts
- **Branch:** `feature/C-01-chart-of-accounts`
- **Objective:** Canadian chart with types/sub-types, parent/child sub-accounts, codes unique per org, renumberable system accounts in the user's scheme, correct template typing, separate control accounts (GST/HST payable, ITC receivable, PST payable, QST payable, QST ITR, payroll liabilities by type), default purchase-tax code per expense account (home-province rate, not Exempt), default GIFI mapping, require-contact/tracking/attachment flags, archive instead of delete.
- **Current (Xero):** 1500 Inventory typed Current Asset (blocks inventory), intangibles typed Fixed Asset, one 820 Sales Tax control, mixed 3/4-digit codes, system accounts not renumberable, no sub-accounts, 0/139 GIFI mapped, every account Tax Exempt. **Expected:** template loads with 0 unmapped GIFI; system accounts cannot be archived; renumbering updates every reference; consistent 4-digit codes.
- **Gap #s:** #18, #29, #30, #44, #45, #46.
- **Business rules:** types: Asset (Current asset, Bank, Inventory, Prepayment, Fixed asset, Accumulated amortisation (contra), Non-current asset, Intangible), Liability (Current liability, Sales-tax control, Payroll liability, Non-current liability), Equity (Share capital, Retained earnings, Current year earnings, Dividends, Other equity), Revenue (Revenue, Other income), Expense (Cost of sales, Operating expense, Amortisation, Income tax, Other expense); `system_role` enum (AR, AP, GST_HST_PAYABLE, ITC_RECEIVABLE, PST_PAYABLE, QST_PAYABLE, QST_ITR, RETAINED_EARNINGS, CURRENT_YEAR_EARNINGS, ROUNDING, SUSPENSE_CONVERSION, UNPAID_EXPENSE_CLAIMS, WAGES_PAYABLE, CPP_PAYABLE, EI_PAYABLE, INCOME_TAX_WITHHELD, VACATION_PAYABLE, INVENTORY, FX_GAIN_LOSS…); codes referenced by FK (id), so renumbering is a code field change + audit; sub-account depth ≤ 4, child type = parent type family; posting only to leaf accounts; `default_tax_code` placeholder (filled with G-01 codes in Phase 1 — template stores home-province purchase code key); `gifi_code` validated against seeded GIFI list (CRA GIFI codes table, 4-digit); archive blocked for system accounts and accounts with balance ≠ 0.
- **Edge cases:** code collision on renumber; parent with posted transactions converted to parent (refused — must be leaf-free); deleting account with transactions (refused, archive); template for each province home (tax defaults differ).
- **UI/UX notes:** tree table (expand/collapse, indented children), type tabs, inline code edit with conflict check, account drawer (details, flags, GIFI search picker with descriptions, tax default, balance, recent transactions link), "How this account appears on reports" mini-diagram (original), bulk actions (archive, change tax default, set GIFI) with preview.
- **Dependencies:** A-01, A-04, A-10.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| C-01-T01 | Accountant review of template (Canadian small-business CoA, 4-digit, types, GIFI) — spreadsheet `coa_template_ca_v1.xlsx` | DOC | — | Signed off by project lead (+client accountant) | Review |
| C-01-T02 | `AccountType` / sub-type enums + `Account` model (code, name_i18n, type, subtype, parent, system_role, is_bank, gifi_code, require_contact, require_tracking, require_attachment, default_tax_key, status) | DB | A-01 | Code unique per org (DB) | Unit |
| C-01-T03 | Tree constraints (depth ≤ 4, same type family, post-to-leaf rule) | BE | C-01-T02 | Invalid parent rejected | Unit |
| C-01-T04 | GIFI master table seeded from CRA GIFI list (version-dated) | DB | — | Seed loads; lookup by code | Unit |
| C-01-T05 | Template loader service (per home province) creating accounts with GIFI and tax-default keys | BE | C-01-T01..T04 | Loaded template: 0 unmapped GIFI (gap-30) | Unit |
| C-01-T06 | System-role guard (cannot archive/delete; type immutable; one account per unique role) | BE | C-01-T02 | Archive system account → error naming role | Unit |
| C-01-T07 | Renumber service (code change, conflict check, audit, cache bust) | BE | C-01-T02, A-04 | All references (by FK) unchanged & reports show new code | Integration |
| C-01-T08 | Archive service (balance must be 0, not system) | BE | C-02 | Non-zero balance archive refused | Unit |
| C-01-T09 | API `/api/v1/orgs/{id}/accounts` CRUD, tree, renumber, archive, bulk; feature key; sweep | API | C-01-T05..T08 | Contract tests; sweep | Integration + security |
| C-01-T10 | Account picker component (shared, filtered by allowed types/context, grouped, searchable by code/name) | FE | A-10 | Sales context hides expense accounts (gap-07 groundwork) | Storybook + Vitest |
| C-01-T11 | CoA tree table UI with tabs, inline code edit, bulk actions | FE/UX | C-01-T09 | Renumber inline with conflict message | Playwright |
| C-01-T12 | Account drawer (flags, GIFI picker, tax default, balance) | FE/UX | C-01-T09 | GIFI search by number/description | Playwright |
| C-01-T13 | CoA import/export (CSV/XLSX, mapping, dry-run via B-03 framework) | BE/FE | B-03 | Round-trip 0 changes | Integration |
| C-01-T14 | Fixtures + gap tests gap-18/29/30/44/45/46 (Inventory typed Inventory; separate tax controls; GIFI 100 %) | QA | C-01-T05 | Tagged tests pass | Integration |
| C-01-T15 | Docs: CoA design + data dictionary entries | DOC | C-01-T02 | Merged | Review |

- **Deliverable acceptance:** 0 unmapped GIFI; system account cannot be archived; renumbering updates every reference.
- **Risks:** template accounting errors → accountant sign-off; renumber breaks references → FK by id, never code.

### C-02 · Journal posting engine
- **Branch:** `feature/C-02-posting-engine`
- **Objective:** the single double-entry engine: ≥2 lines, balanced to the cent, atomic, append-only, `reverse()` linked to original, states Draft → Awaiting approval → Posted → Reversed, book dimension (accounting / tax / both) per line, gap-free sequence numbers per org.
- **Current:** nothing. **Expected:** unbalanced rejected; 1,000 concurrent postings → gap-free sequence; TB of each book = 0; DB rejects UPDATE/DELETE of posted lines.
- **Business rules:** amounts `numeric(18,2)` via Python `Decimal` (ROUND_HALF_UP at 2 dp), debit/credit as separate non-negative columns, one side per line; `JournalEntry` (org, number, date, type, status, source_type/source_id, narration, book_scope, reversal_of, created_by, posted_by, posted_at); `JournalLine` (entry, account, debit, credit, book ∈ {accounting, tax, both}, contact nullable, tracking JSON, description, tax_code nullable); posting checks: balanced per book (for both: lines of book=both + book=accounting must balance; and both + tax must balance), leaf account, account active, lock date (A-05 module GL), period not closed (hook for C-06), entitlement; sequence via per-org `JournalSequence` row `UPDATE … RETURNING` inside the same transaction (gap-free); append-only enforced by Postgres trigger (raise on UPDATE/DELETE for posted rows) + Django `save()` guard; `reverse(date, reason)` creates mirror entry, marks original Reversed; posting table partitioned by org hash (S-06); service-only API (`post_journal(spec)`), no module writes lines directly (import-linter contract).
- **Edge cases:** rounding drift in multi-line splits (engine refuses; callers allocate pennies); posting to archived account; reversal of reversal (refused); concurrent reversal of same entry (row lock); date in locked period.
- **UI/UX notes:** Phase 0 exposes engine via a minimal internal "Journal viewer" (read-only entry detail: lines, books, source link, audit) and a developer test-posting page in dev only; full manual JE UI is C-04 (Phase 1). Error messages name exact reason ("Debits 1,000.00 ≠ credits 999.99 in the tax book (difference 0.01)").
- **Dependencies:** A-01, A-04, A-05, C-01, S-06.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| C-02-T01 | ADR-006 posting engine & book dimension (append-only, sequence, partitioning) | DOC | — | ADR merged | Review |
| C-02-T02 | `JournalEntry` + `JournalLine` models + numeric(18,2) + check constraints (debit≥0, credit≥0, not both) | DB | C-01 | Constraint violations raise | Unit |
| C-02-T03 | Partitioned line table migration (hash by org_id, 16 partitions) | DB | C-02-T02, S-06 | Inserts route to partitions | Integration |
| C-02-T04 | Append-only trigger on posted entries/lines + Django guard | DB | C-02-T02 | UPDATE on posted line → DB error | Integration |
| C-02-T05 | `JournalSequence` gap-free allocator | BE | C-02-T02 | Sequential numbers in-transaction | Unit |
| C-02-T06 | Validation service (≥2 lines, balance per book, leaf/active accounts, Decimal precision) | BE | C-02-T02 | Unbalanced → specific error | Unit + Hypothesis |
| C-02-T07 | Lock-date & period hook (A-05 GL lock; C-06 stub) | BE | A-05 | Pre-lock date refused naming lock | Unit |
| C-02-T08 | `post_journal()` atomic service (validate → sequence → insert → status Posted → audit) | BE | C-02-T05..T07 | Failure leaves no partial rows | Integration |
| C-02-T09 | State machine Draft → Awaiting approval → Posted → Reversed (django-fsm-like, explicit transitions) | BE | C-02-T08 | Illegal transition raises | Unit |
| C-02-T10 | `reverse()` service (mirror lines, link, row lock) | BE | C-02-T08 | Reversal of reversal refused; nets to 0 | Unit |
| C-02-T11 | Trial balance query per book (accounting = both+accounting; tax = both+tax) | BE | C-02-T02 | TB sums to 0 per book | Property test |
| C-02-T12 | Concurrency test: 1,000 concurrent postings across 20 workers → gap-free sequence, all balanced | QA | C-02-T08 | Numbers 1..1000 no gaps | Concurrency |
| C-02-T13 | Property test: random valid journal specs → TB both books = 0; random invalid → rejected | QA | C-02-T06, C-02-T11 | 10,000 examples pass | Hypothesis |
| C-02-T14 | import-linter contract: only `ledger.services` writes `JournalLine` | QA | C-02-T08 | Lint fails on direct write fixture | CI |
| C-02-T15 | Read API `GET /journals`, `/journals/{id}` (lines, books, source, audit) + feature key + sweep | API | C-02-T08 | Contract tests; sweep | Integration + security |
| C-02-T16 | Journal viewer UI (read-only detail, book badges, reversal link) | FE | C-02-T15 | Renders lines and books | Playwright |
| C-02-T17 | Performance: 100k-line fixture TB < 1 s | QA | C-02-T11 | Target met | Performance |

- **Deliverable acceptance:** unbalanced rejected; 1,000 concurrent postings → gap-free sequence; TB of each book = 0.
- **Testing:** Hypothesis, real-Postgres concurrency, trigger integration, import-linter.
- **Risks:** sequence contention → per-org row lock short transaction; float bugs → Decimal everywhere + lint ban on float in ledger package.

---

## 7. TEST — Phase 0 test plan (Rules 5–6)

### 7.1 Test matrix by category

| Category | Phase 0 scope | Tooling | Target / gate |
|---|---|---|---|
| Unit | Tenancy manager, RBAC resolver, approval limits, audit diff builder, lock-date checks, entitlement resolver, price windows, promo redemption, trial date maths, founding allocator, directory query builder, access resolver (groups), contact validators, duplicate detection, import diff engine, CoA tree rules, posting validation, sequence allocator, reversal | pytest, pytest-django, Hypothesis, factory_boy, freezegun, Vitest | ≥ 85 % line coverage on `tenancy`, `rbac`, `billing`, `entitlements`, `ledger`, `contacts` |
| Integration | Every endpoint one happy + one failure test; Stripe webhooks (stripe-mock + Stripe CLI); inbound email (A-06) via mailpit/SES stub; S3 via MinIO; Celery tasks eager + real worker smoke | pytest + DRF APIClient, Stripe CLI, MinIO, mailpit, Redis | 100 % endpoints covered |
| Functional (E2E) | Accountant sign-up → demo → trial org → group/search; owner subscribes; contact create/import; CoA renumber; journal posted and viewed | Playwright (Chromium, WebKit, Firefox), Storybook interaction tests | One scripted scenario per component (S, A, U, V, B, C) |
| Regression | Full suite on every PR; nightly on `main` with 2,000-org practice fixture | GitHub Actions | Zero known regressions |
| Data validation | TB per book = 0 on all fixtures; demo seed TB = 0; reset hash equality; import round-trip 0 changes; heatmap = audit counts; widget counts = drill-down counts | Reconciliation scripts (`manage.py verify_*`) | 100 % pass |
| Security | Tenant-isolation router sweep (A-01), practice-assignment revocation sweep (V-02/V-05), RBAC matrix (role × endpoint × method), entitlement-leak matrix (U-03), impersonation limits (U-06), webhook signature, 2FA enforcement, OWASP ZAP baseline, pip-audit, npm audit, gitleaks, Trivy image scan, semgrep | Custom sweeps, ZAP, pip-audit, npm audit, gitleaks, Trivy, semgrep | No high findings; sweeps 100 % |
| Concurrency | 1,000 concurrent postings (C-02), 1,500 founding allocations (U-08), 50 concurrent promo redemptions (U-02), trial convert vs expiry race (U-05), bulk job resume (V-03) | pytest + threads / pytest-xdist on real Postgres 16 service container | Exact counts, no gaps |
| Performance | Directory search p95 < 300 ms (2,000 orgs); practice dashboard < 1.5 s; demo creation < 10 s; entitlement call < 20 ms cached; TB 100k lines < 1 s | k6, Django-silk/pg_stat_statements | Targets met on staging-size data |
| Accessibility & UX | axe on every screen; keyboard-only flows (directory, contact form, CoA); Lighthouse a11y ≥ 95 on app shell; usability tasks (§3.6) | axe-core/Playwright, Lighthouse CI, moderated sessions (5 users) | 0 serious axe violations |
| Visual regression | Design-system components & all Phase 0 screens (light/dark, en-CA, pseudo-loc +30 %) | Storybook + Chromatic (or Playwright screenshots) | No unapproved diffs |
| Localisation | i18n lint (no hard-coded strings), missing-key report (fr-CA placeholders allowed until Phase 6), pseudo-localisation layout test | formatjs extract, custom CI job | 0 hard-coded strings |
| Gap closure | gap-01, 02, 03, 06, 12 (banners), 14, 15, 19, 20, 21, 22 (overview pattern component), 25 (limits engine), 29, 30, 31, 37, 38, 39, 40, 41, 43, 44, 45 (defaults groundwork), 46, 51, 52, 60 (a11y), 61 | Playwright + pytest tagged `gap-NN` | Every Phase 0 row observed |

### 7.2 Compliance & fixture sets created in Phase 0
- `fixtures/practice_2000/` — 1 practice, 25 staff, 2,000 orgs, groups/tags (generated by `seed_practice`).
- `fixtures/coa_ca_v1/` — template per home province with GIFI and tax-default keys; expected unmapped = 0.
- `fixtures/ledger_random/` — Hypothesis strategies for balanced/unbalanced journal specs across both books.
- `fixtures/contacts_import/` — UTF-8, UTF-8-BOM, Windows-1252, French headers, renamed contacts, blank cells, 12 people per contact.
- `fixtures/stripe_events/` — recorded webhook sequences incl. out-of-order and replay.
- `fixtures/demo_seed_v1.json` — Canadian demo dataset (signed off by client).

### 7.3 Exit demonstration script (observed on staging)

| # | Step | Expected result |
|---|---|---|
| 1 | Open staging over HTTPS; visit root URL and a legacy-style URL | Redirect to sign-in/home (gap-02); HSTS header present |
| 2 | Accountant signs up free (email + password), verifies email, enables TOTP | Unverified login refused before step; practice created; no billing screen anywhere for the accountant |
| 3 | Accountant clicks "Open demo" | Demo org ready < 10 s, Canadian data (Ontario company, provinces, BN format), watermark and demo bar visible; TB = 0 |
| 4 | Reset demo | Seed restored exactly (hash check shown in admin) |
| 5 | Accountant creates a trial organisation (QC address, Province picker, Postal code) | Org in `trialing`, header chip "Trial — 30 days left"; Tax Registrations page is single page |
| 6 | Second trial with same BN | Refused with clear message |
| 7 | Create groups "Toronto office → Retail clients", tag orgs; search directory by partial BN and by accented name; save a view | Results < 300 ms; saved view persists after re-login |
| 8 | Assign a staff member via group; then revoke | Staff gains access to all orgs in group; after revoke receives 404 on every record (sweep report shown) |
| 9 | Bulk edit 200 orgs (tags + staff) | One job, per-row outcomes, 0 rows without outcome; 200 audit entries |
| 10 | Owner subscribes (Stripe test card) to a package; replay webhook | Active subscription; no duplicate invoice; founding badge #n assigned; counter decremented |
| 11 | Downgrade package removing Payroll | Payroll screens show explicit locked panel naming product; read of history remains; no redirects |
| 12 | Simulate failed renewal (test clock) | Grace → reminders day 3/5/7 → read-only exactly at grace end; banner names reason |
| 13 | Create QC contact; type near-duplicate name | GST+QST hint; duplicate panel appears while typing; merge preserves history |
| 14 | Import contacts file, then re-import same file | Dry-run shows actions; re-import 0 duplicates, 0 changes; renamed contact updated in place |
| 15 | CoA: verify 0 unmapped GIFI; renumber a system account; try to archive it | Renumber reflected everywhere; archive refused naming the system role |
| 16 | Run concurrency harness: 1,000 concurrent postings | Gap-free sequence 1..1000; TB accounting = 0, TB tax = 0; UPDATE on posted line rejected by DB |
| 17 | Founding harness: 1,500 concurrent first payments (test DB) | Exactly 1,000 founding slots |
| 18 | Platform console: MRR/trials tiles, impersonate org user 15 min | Demo excluded from metrics; impersonation listed in org audit log with start/end |
| 19 | Global search: "lock date" | Opens Settings → Lock dates (gap-52) |
| 20 | Security reports | ZAP/pip-audit/npm audit/gitleaks/Trivy: no high findings |

### 7.4 Failure handling (Rule 5.3 / 6)
Stop dependent tasks on any failing test; identify exact failing condition; classify (code / data / configuration / wrong assumption); one focused correction; re-run affected tests then the regression suite; continue only when acceptance criteria are met. Never skip or mark a test passed without execution; if a sandbox (Stripe, email) is unavailable, the report states it. Debugging follows reproduce → expected vs actual → logs/data → hypothesis → one change → verify → regression; after 30 minutes without progress, re-examine requirements, architecture, data and assumptions.

---

## 8. IMPROVE — post-verification review (Rule 8)

### 8.1 Review checklist (per deliverable, after acceptance is observed)
- **Correctness:** every acceptance criterion from §6 observed and recorded with evidence (test name / screenshot).
- **Readability:** services < 50 lines per function where practical; domain names match the glossary (organisation, practice, cheque, Province, Postal code).
- **Maintainability:** no duplicated scoping, permission or entitlement logic outside `tenancy`, `rbac`, `entitlements`; import-linter contracts green.
- **Performance:** budgets in 8.2 met; `pg_stat_statements` top-10 reviewed; N+1 check with `django-zen-queries`/`nplusone` in tests.
- **Reliability:** every Celery task idempotent (key documented); retries with backoff; webhook handlers replay-safe.
- **Security:** sweeps pass; secrets only from manager; PII fields (BN, bank details) encrypted/masked where specified; impersonation limits verified.
- **Consistency:** every screen built from design-system components; empty/loading/error/gated/read-only states present; Canadian English lint clean.
- **UX polish:** keyboard path for primary tasks; focus management after modals; error messages name cause and fix; 0 promotional banners in working screens.
- Re-run relevant tests after any improvement; remove temporary artifacts (debug pages restricted to dev only, test keys, console logs).

### 8.2 Performance budgets (Phase 0)

| Item | Budget |
|---|---|
| Directory search (2,000 orgs) | p95 < 300 ms |
| Practice dashboard | < 1.5 s full render |
| Entitlement resolution (cached / cold) | < 20 ms / < 120 ms |
| Demo creation | < 10 s |
| Journal post (5 lines) | p95 < 80 ms |
| TB on 100k lines | < 1 s |
| App shell first load (LCP) | < 2.5 s on 4G profile |
| JS bundle (app shell, gzipped) | < 250 KB |

### 8.3 Phase-end architecture checkpoint
Module boundaries (`core`, `tenancy`, `rbac`, `audit`, `billing`, `entitlements`, `workspace`, `contacts`, `ledger`), query performance on the 2,000-org fixture, design-system coverage, accessibility audit, i18n key hygiene, entitlement matrix review with the client, ADR-001/005/006 up to date.

---

## 9. Git branch plan (Rule 7)

| # | Branch | Base | Deliverable | Merge order / parallel lane |
|---|---|---|---|---|
| 1 | `feature/S-01-repo-ci` | main | S-01 | 1 |
| 2 | `feature/S-02-hosting-ca` | main | S-02 | 2 (after S-01) |
| 3 | `feature/S-03-security-baseline` | main | S-03 | 3 |
| 4 | `feature/A-10-design-system` | main | A-10 | 3 (parallel lane FE) |
| 5 | `feature/A-01-tenancy` | main | A-01 | 4 |
| 6 | `feature/S-06-scale-baseline` | main | S-06 | 5 |
| 7 | `feature/A-02-auth-signup` | main | A-02 | 5 |
| 8 | `feature/A-03-rbac-limits` | main | A-03 | 6 |
| 9 | `feature/A-04-audit-log` | main | A-04 | 6 (parallel) |
| 10 | `feature/A-08-jobs` | main | A-08 | 6 (parallel) |
| 11 | `feature/A-05-org-settings-locks` | main | A-05 | 7 |
| 12 | `feature/A-06-files-inbox` | main | A-06 | 7 (parallel) |
| 13 | `feature/A-07-notifications-email` | main | A-07 | 7 (parallel) |
| 14 | `feature/U-01-product-catalogue` | main | U-01 | 8 |
| 15 | `feature/U-02-packages-pricing` | main | U-02 | 9 |
| 16 | `feature/U-03-entitlements` | main | U-03 | 10 |
| 17 | `feature/C-01-chart-of-accounts` | main | C-01 | 10 (parallel lane ledger) |
| 18 | `feature/C-02-posting-engine` | main | C-02 | 11 |
| 19 | `feature/B-01-contact-model` | main | B-01 | 11 (parallel) |
| 20 | `feature/U-04-stripe-billing` | main | U-04 | 11 (parallel) |
| 21 | `feature/U-05-free-trial` | main | U-05 | 12 |
| 22 | `feature/U-08-founding-offer` | main | U-08 | 12 (parallel) |
| 23 | `feature/B-02-contact-statements` | main | B-02 | 12 (parallel) |
| 24 | `feature/B-03-contact-import` | main | B-03 | 12 (parallel) |
| 25 | `feature/U-07-demo-org` | main | U-07 | 13 |
| 26 | `feature/A-09-global-search` | main | A-09 | 13 (parallel) |
| 27 | `feature/V-01-org-directory` | main | V-01 | 13 (parallel) |
| 28 | `feature/V-02-groups-tags` | main | V-02 | 14 |
| 29 | `feature/V-05-practice-staff` | main | V-05 | 15 |
| 30 | `feature/V-03-bulk-actions` | main | V-03 | 15 (parallel) |
| 31 | `feature/V-04-practice-dashboard` | main | V-04 | 16 |
| 32 | `feature/U-06-platform-console` | main | U-06 | 16 (parallel) |
| 33 | release tag `v0.1.0` (Phase 0) | main | Exit demo | 17 |

**Before starting each branch:** `git status` clean (never discard uncommitted work), pull `main`, confirm prerequisites merged, restate objective + acceptance criteria in the PR description, list atomic tasks as a PR checklist.
**Before declaring a branch complete:** all atomic tasks ticked with evidence; CI green (unit, integration, isolation sweep, RBAC matrix, entitlement-leak matrix, feature-key check, i18n lint, gitleaks, audits); no unrelated changes; no debug code; no secrets; docs/ADR/data dictionary updated; diff reviewed by a second engineer; merge to `main` only with project-lead authorisation; no production deploy in Phase 0.

---

## 10. Phase 0 risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Week-1 scope is large (33 deliverables) | High | High | Parallel lanes (infra, FE design system, ledger, SaaS); smallest working piece per card; stubs for later-phase providers (V-04, B-02) |
| 2 | Tenant / practice data leak | Low | Critical | `OrgOwnedModel` + scoped manager + lint + router sweep + revocation sweep (A-01, V-02, V-05) |
| 3 | Entitlement leak or over-gating core controls | Medium | High | Single engine; leak matrix; rule "never gate controls inside a product"; gap tests 06/14/41 |
| 4 | Stripe webhook double-processing / ordering | Medium | High | `StripeEvent` unique id; precedence rules; replay tests |
| 5 | Founding counter over-allocation | Low | Medium | Single atomic UPDATE; 1,500-concurrency test |
| 6 | Posting sequence gaps or contention | Medium | High | Per-org sequence row inside posting tx; 1,000-concurrency test; short transactions |
| 7 | CoA template accounting errors | Medium | High | Accountant sign-off; GIFI 100 % mapped check; typed system roles |
| 8 | Timezone/DST errors in trial and dunning | Medium | Medium | UTC storage, org TZ computation, DST fixtures, freezegun |
| 9 | Late client inputs (brand, domain, prices, Stripe, hosting, demo data sign-off) | Medium | Medium | Placeholders as data; schedule extension per Agreement 6.3; request on kickoff day |
| 10 | Directory/dashboard performance at 2,000 orgs | Medium | Medium | Denormalised summary, GIN/trigram indexes, k6 in CI nightly |
| 11 | Impersonation misuse | Low | High | Time-box, reason, consent option, blocked endpoints, org-visible audit |
| 12 | Design inconsistency creeping in (Xero's two generations) | Medium | Medium | One design system first (A-10), visual regression, lint for raw HTML controls |
| 13 | Import destroying data | Low | High | Non-destructive diff engine, dry-run mandatory, property test |
| 14 | Accessibility debt | Medium | Medium | axe gate in CI from day one; keyboard flows in E2E |

---

## 11. Phase 0 completion checklist (Rule 11) and reporting template (Rule 10)

### 11.1 Mandatory execution checklist (tick per deliverable in the PR, and once for the phase)

**UNDERSTAND**
- [ ] Investigated existing implementation (greenfield repo; earlier merged branches of this phase).
- [ ] Identified the user and desired outcome per deliverable.
- [ ] Defined inputs and outputs.
- [ ] Identified business rules (tenancy, RBAC, entitlements, billing, ledger integrity).
- [ ] Considered edge cases.
- [ ] Restated the objective in the PR.

**PLAN**
- [ ] Decomposed into atomic tasks (§6 tables).
- [ ] Identified dependencies and execution order (§5, §9).
- [ ] Defined acceptance criteria and testing procedures.

**BUILD**
- [ ] Implemented smallest functional piece first (model → service → API → UI).
- [ ] Followed architecture (services only write ledger; scoped managers; design system).
- [ ] Declared feature keys and i18n keys; registered endpoints in the tenant sweep.
- [ ] Avoided unrelated changes; preserved existing functionality.

**TEST**
- [ ] Verified behaviour; edge cases; failures investigated and resolved.
- [ ] Regression suite green; isolation, RBAC and entitlement sweeps green.
- [ ] Recorded unverified conditions (e.g., sandbox unavailable).

**IMPROVE**
- [ ] Code quality reviewed; temporary artifacts removed; readability improved where needed.
- [ ] Behaviour re-verified after improvements.

**COMPLETE**
- [ ] Final diff reviewed by a second engineer.
- [ ] Documentation updated (README, ADR-001/005/006, data dictionary, runbook sections, dev guides).
- [ ] Changes and test results reported.
- [ ] Acceptance criteria confirmed for all 33 deliverables.
- [ ] Exit demonstration (§7.3) observed on staging by the client's decision-maker.
- [ ] Final status reported: Complete / Partially complete / Blocked.

### 11.2 Reporting template

**Before implementation (per deliverable branch)**
1. Problem understanding — Objective · Existing behaviour · Expected behaviour.
2. Task breakdown — Components · Atomic tasks (IDs) · Dependencies.
3. Implementation plan — Execution order · Acceptance criteria · Testing strategy.

**After implementation (per deliverable branch)**
1. Changes made — Completed tasks (IDs) · Files/components modified · Important decisions (link ADRs).
2. Testing results — Tests executed · Passed · Failed · Not executed and why.
3. Remaining issues — Known limitations · Unresolved bugs · Risks/dependencies (e.g., awaiting client input).
4. Final status — Complete / Partially complete / Blocked.

**Phase 0 report to Profitex (end of week 1, with staging link)**
- Deliverables accepted (33) with evidence links; exit demonstration results per step (§7.3); security scan summary; performance results vs budgets (§8.2); open client inputs (brand assets, domain, package names/prices, founding wording, Stripe Canada account, hosting account, demo data sign-off); next-phase readiness (Phase 1 prerequisites A, U, B, C-01, C-02 merged).

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| S-01 | 17 | 25.5 |
| S-02 | 10 | 15 |
| S-03 | 12 | 18 |
| S-06 | 10 | 15 |
| A-01 | 16 | 24 |
| A-02 | 16 | 24 |
| A-03 | 16 | 24 |
| A-04 | 13 | 19.5 |
| A-05 | 15 | 22.5 |
| A-06 | 15 | 22.5 |
| A-07 | 12 | 18 |
| A-08 | 9 | 13.5 |
| A-09 | 11 | 16.5 |
| A-10 | 20 | 30 |
| U-01 | 15 | 22.5 |
| U-02 | 14 | 21 |
| U-03 | 15 | 22.5 |
| U-04 | 17 | 25.5 |
| U-05 | 13 | 19.5 |
| U-06 | 14 | 21 |
| U-07 | 14 | 21 |
| U-08 | 11 | 16.5 |
| V-01 | 15 | 22.5 |
| V-02 | 13 | 19.5 |
| V-03 | 12 | 18 |
| V-04 | 10 | 15 |
| V-05 | 10 | 15 |
| B-01 | 19 | 28.5 |
| B-02 | 13 | 19.5 |
| B-03 | 14 | 21 |
| C-01 | 15 | 22.5 |
| C-02 | 17 | 25.5 |
| **Total** | **443** | **664.5** |

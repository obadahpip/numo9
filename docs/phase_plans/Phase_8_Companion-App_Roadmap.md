# NUMO9 — Phase 8 Implementation Plan: Companion-App Roadmap

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | 8 — Companion-App Roadmap |
| **Weeks** | Week 12 (in parallel with the end of Phase 7) |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment) |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §1.6 #4 and #16, §3 Component W (W-01…W-03), F-03 note (`BankStatementSource`), §4 Gaps #48, #50, §5.2 Phase 8, §7 (out of scope), §11 Change control · Project_Phases.md (Phase 8) · Quotation GMA-PFX-2026-003 §4 "Open API & Companion-App Roadmap", §6 exclusions · Agreement GMA-PFX-2026-003-A 5.4(c), §11 · xero_teardown.md §0 (App launcher), §1 (App Store ads), §6.4, §6.16, §6.17, §10.B · AI Coding Agent — Mandatory Engineering Workflow |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE, applied to the phase, to every deliverable branch and to every atomic task |

---

## 0. How to use this file

- One branch per deliverable: `feature/W-02-companion-app-registry` (code) and `docs/W-03-commerce-discovery-annex` (document deliverable, still reviewed through a PR).
- Each atomic task (`W-0n-Tnn`) runs UNDERSTAND → PLAN → BUILD → TEST → IMPROVE.
- W-03 produces a change-controlled annex; **no Numo9 Commerce production code is written in this phase** (Agreement 5.4(c), Plan §11). Spikes/prototypes are allowed only in a throw-away branch and are not merged.
- Phase complete when the registry is live on staging and the annex is approved in writing by the client.

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase

| Area | State |
|---|---|
| W-01 public API (Phase 4) | OpenAPI 3 spec (`/api/public/v1/`), API keys and OAuth clients per organisation, scopes mapped to feature keys, webhooks (`invoice.posted`, `invoice.revised`, `payment.received`, `stock.moved`, `payrun.posted` …) with signatures and idempotent replay, rate limits, full-ledger export |
| U-01/U-03 entitlements (Phase 0) | Products → feature keys; entitlement engine with 402 contract; "future companion apps" reserved in the catalogue |
| F-03 replacement | `BankStatementSource` interface used by statement import (F-02) |
| Y (Phase 7) | Owner/employee mobile apps incl. receipt capture → E-05 ("Numo9 Receipts" delivered inside Y) |
| H, D, P | Items/stock, invoices, Stripe payments — the domains Numo9 Commerce will reuse |
| Platform console (U-06) | Package editor, feature flags, audited impersonation |
| Marketplace | None, by client decision 4 — no third-party app surface exists |

### 1.2 Problem definition — the seven questions

1. **Who uses this?** Platform Owner (registers Numo9-owned apps, sets them as products), Organisation Owner/Admin (installs/uninstalls apps for the organisation), accountants (see which apps an organisation uses), Numo9 companion apps themselves (as OAuth clients), GMA/Profitex product team (W-03 discovery).
2. **Desired outcome:** a registry where only Numo9-owned apps can be registered; installing an app for an organisation grants exactly its declared scopes and its entitlement as a product; uninstalling revokes everything; a client-approved annex defines Numo9 Commerce (requirements, data model, estimate, plan).
3. **Inputs:** app manifest (key, name, description EN/FR, publisher = Numo9, scopes, webhooks subscribed, product/feature keys, redirect URIs, icon), organisation install request with consent, client requirements interviews for Commerce.
4. **Outputs:** `CompanionApp`, `AppVersion`, `AppInstallation` records; OAuth grant scoped to the install; entitlement for the app product; audit entries; admin and organisation screens; W-03 annex document (Markdown → PDF) with data model diagrams, estimate and schedule.
5. **Business rules:** publisher must be the Numo9 platform entity — any other publisher is rejected (no third-party marketplace); scopes requested ⊆ scopes declared in the approved app version; install requires Owner/Admin permission and an active entitlement (or the app's own product subscription); scope changes in a new app version require re-consent; uninstall revokes tokens, webhooks and entitlement within one request and keeps historical data created by the app (ledger is append-only); the founding-1,000 rule "all products" includes companion apps marked `included_in_founding` (U-08); everything audited.
6. **What could go wrong:** scope creep (app gets more than declared); token survives uninstall; webhook deliveries continue after uninstall; entitlement leak (app usable without subscription); re-install duplicates; demo organisations installing apps that post real data; registry UI implying a public marketplace; Commerce scope inflating into a full build without annex approval.
7. **Smallest useful implementation:** registry model + Platform Owner registration of one internal app ("Numo9 Bank — statement source", stub) + organisation install/uninstall that grants/revokes its scopes, verified by a scope-sweep test.

### 1.3 Restated objective

- **Currently:** W-01 API and webhooks exist; there is no way to register a Numo9-owned app, install it per organisation or tie it to an entitlement; Numo9 Commerce has no defined scope.
- **Change:** deliver the companion-app registry (Numo9-owned only) and the Numo9 Commerce discovery annex.
- **Why:** client decision 4 replaces Xero's third-party marketplace with Numo9's own apps; a controlled registry keeps security and revenue inside Numo9 while letting the product grow (e-commerce first).
- **Done means:** installing an app grants exactly its scopes; uninstalling revokes them; no third-party marketplace surface exists (verified); registry live on staging; Commerce annex approved by the client before any build.

### 1.4 Assumptions & interpretations

1. "Registry" is an internal catalogue, visible to organisations as *Numo9 apps* inside Settings — not a public store.
2. Companion apps authenticate as OAuth 2.0 confidential clients (authorization code + PKCE for UI apps, client credentials bound to an installation for background jobs) on the W-01 server.
3. Initial registered apps: *Numo9 Bank* (planned, uses `BankStatementSource`), *Numo9 Receipts* (delivered within Y — registered as a first-party app record pointing to the mobile apps), *Numo9 Commerce* (registered in `planned` status, not installable).
4. App billing uses U-01/U-02: each app is a product with feature keys; price may be 0.
5. W-03 estimate is expressed in effort and calendar weeks; price is proposed in the annex for client approval under change control.

### 1.5 Client inputs required

| Input | Due | Used by |
|---|---|---|
| Commerce stakeholder interviews (2 × 60 min) | Week 12 day 1–2 | W-03-T02, T03 |
| Target merchant profile(s) and priority channels (own storefront, POS, marketplaces) | Week 12 day 2 | W-03-T04 |
| Decision on companion-app pricing model (included/add-on) | Week 12 day 3 | W-02-T05, W-03-T12 |
| Written annex approval | Within 5 business days of delivery | Phase exit |

---

## 2. BETTER THAN XERO — gap analysis for this phase

| Gap # | Teardown ref | What Xero does / fails to do | What Numo9 does instead | Observable proof |
|---|---|---|---|---|
| 48 | §6.12 | No generic full-ledger export or open API export; exports target specific AU/NZ products | W-01 full-ledger export + companion apps consume the same public, versioned API (no private back doors) | `gap-48`: Commerce annex data flows use only W-01 endpoints |
| 50 | §6.16 | Closed Xero-to-Xero network | Open, documented API/webhooks; Numo9's own apps prove the API; e-invoicing roadmap item noted in annex | `gap-50`: registry apps authenticate through public OAuth |
| — | §0, §1, §6.4, §6.17 | App launcher and dashboard push third-party apps/ads; "Connected apps" leaves the product to a separate domain | No advertising, no third-party marketplace; Numo9 apps managed in-product in Settings › Numo9 apps with explicit scopes and one-click uninstall | `gap-1-ads`: UI test asserts no external app listings exist |
| 41 / 6 | §6.3, §2.2 | Generic "upgrade" banners; features gated silently | App entitlement shown explicitly ("Included in your package" / "Available as add-on — CAD x/month"), never silent | `gap-41-apps`: gated app tile shows product and price |

**Beyond-Xero additions in this phase**
- Scope-transparent install consent screen (human-readable list of what the app can read/write), re-consent on scope change.
- Per-installation activity log (API calls, webhook deliveries) visible to the organisation and its accountant.
- Kill switch per app (Platform Owner) and per organisation (Owner).
- Accountant visibility: directory column "Numo9 apps" so practices see which organisations use Commerce/Bank.

**Xero strengths matched conceptually (original design)**
- Connected-apps list with revoke — Numo9 adds exact scope listing, activity log and in-product management.

**[EXTRA] refinements inside scope**
- App health status per installation (last successful call, failing webhooks) with notification to Owner.
- Sandbox installation on demo organisations (data watermarked, never posts to real books) for sales demos.
- Manifest linting in CI (scopes exist, feature keys exist, FR strings present).

---

## 3. UI/UX DESIGN PLAN

### 3.1 UX principles applied
1. **Trust through transparency** — every scope translated into plain language with read/write icons; nothing hidden behind "permissions".
2. **Reversible by default** — uninstall in two clicks with a clear statement of what stays (historical records) and what stops (sync, webhooks, access).
3. **No marketplace feel** — no ratings, no third-party publishers, no ads; a calm "Numo9 apps" catalogue of first-party extensions.
4. **Explicit gating** — tile states: *Installed*, *Available*, *Included in your package*, *Add-on*, *Coming soon* (planned apps, e.g. Commerce), never silent redirects.
5. **Accountant-first visibility** — install state visible in the directory and organisation summary.
6. Bilingual from day one (FR keys), WCAG 2.1 AA, responsive, keyboard navigable.

### 3.2 Information architecture / navigation added
- Organisation: Settings › **Numo9 apps** (catalogue, installed apps, activity).
- Platform console (U-06): **Companion apps** (registry, versions, scopes, kill switch, installs per organisation).
- Accountant directory (V-01): optional column and filter "Numo9 apps".
- Organisation audit log (A-04): app events filter.

### 3.3 Screen inventory

| Screen | Primary user | Purpose | Key components | States | Keyboard |
|---|---|---|---|---|---|
| Settings › Numo9 apps (catalogue) | Org Owner/Admin | Browse first-party apps | AppTile grid, StatusBadge, Filter chips | empty (no apps registered) / planned / gated / installed | arrows move between tiles, `Enter` opens |
| App detail | Org Owner/Admin, Accountant (read) | Description, scopes, pricing, install | ScopeList (read/write icons), PriceTag, Button | gated (add-on price, upgrade CTA) / installed (Uninstall, Activity) / coming soon | `I` install, `U` uninstall |
| Install consent dialog | Org Owner/Admin | Confirm scopes and billing | Modal, ScopeList, Checkbox consent, summary of billing change | error (entitlement missing → explicit message) | `Ctrl+Enter` confirm |
| Uninstall dialog | Org Owner/Admin | Confirm revocation effects | Modal, "what stops / what stays" lists | in-progress / done toast | — |
| Installation activity | Org Owner, Accountant | API calls, webhooks, errors | DataGrid, filters, health indicator | empty / failing (banner with fix) | — |
| Console › Companion apps list | Platform Owner | Registry management | DataGrid, status chips (draft/approved/planned/retired) | — | — |
| Console › App editor | Platform Owner | Manifest, versions, scopes, product link | Form, ScopePicker (from W-01 catalogue), JSON preview, lint results | validation errors inline | `Ctrl+S` |
| Console › Installations | Platform Owner | Installs per org, kill switch | DataGrid, Toggle (kill), audit link | — | — |
| Directory column "Numo9 apps" | Accountant | Which orgs use which apps | Column chooser, chips | — | — |

### 3.4 Key user flows
1. **Install Numo9 Bank (≤ 4 clicks, < 30 s):** Settings › Numo9 apps → tile *Numo9 Bank* → Install → review scopes (Read bank accounts; Create bank statement lines) and billing line → Confirm → toast "Numo9 Bank installed" + activity tab.
2. **Uninstall (2 clicks):** app detail → Uninstall → dialog shows "Stops: access, sync, webhooks. Stays: statement lines already imported." → Confirm → tokens revoked immediately.
3. **Scope change re-consent:** new app version adds scope → banner on app detail "Numo9 Bank needs one new permission" → Review → Approve (or keep old version until deadline).
4. **Platform Owner registers app:** Console › Companion apps → New → manifest form → scopes from W-01 catalogue → link to product → lint passes → Approve version → status *available*.
5. **Accountant checks usage:** Directory → column chooser → add "Numo9 apps" → filter "Commerce: installed".

### 3.5 Microcopy & error rules
- Scope strings: verb + object + limit ("Read your invoices and payments", "Create stock movements"). Write scopes marked with a pencil icon and the word *write*.
- Errors name cause + fix: "Numo9 Bank isn't included in your current package. Add it for CAD 0.00/month or contact your accountant." — FR: « Numo9 Banque n'est pas inclus dans votre forfait actuel. Ajoutez-le pour 0,00 $ par mois ou communiquez avec votre comptable. »
- Uninstall copy always lists what stays (append-only ledger).
- Planned apps: "Coming soon — Numo9 Commerce. Tell us what you need" (link to feedback form feeding W-03).

### 3.6 Accessibility & usability test plan

| Task | Success metric |
|---|---|
| Install an app and name two things it can do | 100 % success; scopes correctly recalled by ≥ 80 % |
| Uninstall and say what data remains | ≥ 90 % correct |
| Accountant finds organisations using an app | < 30 s |
| axe-core on all new screens (EN, FR) | 0 serious/critical |
| Keyboard-only install/uninstall | 100 % completable |

---

## 4. TOOLS & TECHNOLOGY FOR THIS PHASE

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| OAuth server | `django-oauth-toolkit` (from W-01) | App clients, authorization code + PKCE, client credentials per installation, token revocation (RFC 7009) | BSD |
| Scopes | W-01 scope catalogue + U-03 feature keys | Scope ⊆ declared check | Internal |
| Manifest schema | JSON Schema (`jsonschema` Python, `ajv` TS) | Validate app manifests | MIT |
| Webhooks | W-01 dispatcher (Celery), HMAC-SHA256 signatures | Per-installation subscriptions, revoke on uninstall | Internal |
| Entitlements | U-01/U-02/U-03 engine, Stripe Billing (add-on prices) | App as product | Stripe fees client-paid |
| API docs | `drf-spectacular`, Redoc | Scope documentation per endpoint | MIT/BSD |
| Frontend | Next.js design system (AppTile, ScopeList, Modal, DataGrid), React Query | Screens | Internal |
| Testing | pytest, factory_boy, Hypothesis (random scope sets), Playwright, Schemathesis (contract fuzzing on scoped tokens), axe-core | Verification | MIT |
| Security | OWASP ZAP (OAuth flows), semgrep rules (no scope bypass decorators), gitleaks | Abuse cases | — |
| Observability | Sentry, Prometheus counters per installation (calls, errors, webhook failures) | Health status | — |
| Discovery (W-03) | Figma/FigJam (journeys, storyboards), Miro alternative, dbdiagram.io / Mermaid ER diagrams, `mmdc` (Mermaid CLI) for annex images, MkDocs + `md-to-pdf`/WeasyPrint for annex PDF, spreadsheet estimator (XLSX) with three-point estimates, Lucidchart optional | Requirements, data model, estimate, plan | Client licence costs only if paid tools used |
| Research | Competitive scan of Canadian e-commerce needs (Shopify/WooCommerce/Square capabilities as functional reference only, no copying), CRA rules for online sales (GST/HST place of supply for e-commerce, digital economy measures) | Annex requirements | Public sources |
| Internal tools to build | `manage.py register_companion_app <manifest.json>`, manifest linter in CI, `scope_sweep` test generator (each scope × each endpoint), installation simulator for demo orgs, `revoke_installation` management command (incident use) | Phase productivity | — |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 objective
A Numo9-owned companion-app registry with exact scope grants per organisation install, and an approved Numo9 Commerce discovery annex.

### 5.2 Level 2 components

| Component | Deliverables | Purpose |
|---|---|---|
| W — Registry | W-02 | App records, versions, manifests, install/uninstall, scopes, entitlement, UI, audit |
| W — Discovery | W-03 | Commerce requirements, data model, estimate, plan, annex approval |

### 5.3 Dependency graph and execution order

```
W-01 API/OAuth + U-01/U-03 entitlements
   └─► W-02: models → manifest schema → registration (console) → install service → OAuth grant binding
             → webhook binding → uninstall/revoke → entitlement → org UI → accountant column → sweeps
W-03 (parallel): interviews → requirements → journeys → data model → integration map → NFRs → estimate → plan → annex → approval
```
Execution: W-02-T01…T08 first (smallest slice); W-03-T01…T06 in parallel; then W-02 UI and sweeps; W-03 estimate/plan/annex; exit.

---

## 6. PLAN — Deliverable cards with ATOMIC TASKS (Rule 3)

### W-02 · Companion-app registry (Numo9-owned only)

- **Branch:** `feature/W-02-companion-app-registry`
- **Objective:** register Numo9-owned apps, install them per organisation with exact scopes and entitlement, uninstall with full revocation.
- **Current behaviour:** OAuth clients exist only per organisation (W-01); no app concept, no install, no entitlement link.
- **Expected behaviour:** `CompanionApp` (publisher fixed to Numo9), versions with manifests, install per organisation grants exactly the version's scopes and webhook subscriptions and activates its product entitlement; uninstall revokes tokens, webhooks and entitlement in one transaction; planned apps: Numo9 Commerce, Numo9 Bank (`BankStatementSource`), Numo9 Receipts (within Y); no third-party marketplace surface.
- **Gap #s closed:** 48, 50, 41 (app gating), "no ads" (Gap #4 dashboard ads principle extended).
- **Business rules:** see §1.2 rule 5.
- **Edge cases:** install while subscription in grace/read-only (allowed read scopes only? → rule: install blocked, explicit message); concurrent double install (unique constraint); uninstall during webhook delivery (in-flight deliveries dropped by checking installation status at send); demo org install (sandbox flag, writes watermarked/blocked from real posting); version retirement with active installs (forced migration notice, 30-day window).
- **UI/UX notes:** see §3.
- **Dependencies:** W-01, U-01, U-02, U-03, U-06, A-03, A-04, F-02 (`BankStatementSource`), Y-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| W-02-T01 | ADR-006 "Companion apps": first-party only, OAuth model, scope binding, entitlement model, uninstall semantics | DOC | — | ADR approved | Review |
| W-02-T02 | Manifest JSON Schema (`key`, `name{en,fr}`, `description{en,fr}`, `publisher`, `scopes[]`, `webhooks[]`, `product_key`, `redirect_uris[]`, `icon`, `status`) + validator | BE | T01 | Valid sample passes; publisher ≠ `numo9` rejected | pytest schema cases |
| W-02-T03 | Models `CompanionApp`, `AppVersion` (manifest snapshot, approved_by, approved_at), migration; platform-level (not org-owned) with audit | DB | T02 | Migration applies; app key unique | pytest |
| W-02-T04 | Model `AppInstallation` (`OrgOwnedModel`: app_version, status installed/suspended/uninstalled, granted_scopes, consent_by, consent_at, oauth_application FK) + unique active install per org/app | DB | T03 | Second active install for same org/app violates constraint | pytest |
| W-02-T05 | Link app → U-01 product and feature keys (`product_key`), founding-inclusion flag | BE | T03, U-01 | Entitlement engine resolves app product for subscribed org | pytest |
| W-02-T06 | Registration service + `manage.py register_companion_app manifest.json` (draft → approved → available / planned / retired) | BE | T03 | Registering Numo9 Bank manifest creates approved version | pytest |
| W-02-T07 | Scope validator: requested scopes ⊆ W-01 catalogue; write scopes require matching feature keys | BE | T02, W-01 | Unknown scope rejected with field error | pytest |
| W-02-T08 | Install service: permission check (Owner/Admin), entitlement check, create OAuth application bound to installation with `granted_scopes`, audit event | BE | T04, T05, T07 | Installed app token can call only granted endpoints | pytest integration |
| W-02-T09 | Token scope enforcement middleware for installation tokens (endpoint scope map; 403 on outside scope, 402 when entitlement lapses) | BE/API | T08 | Scope sweep: every endpoint × every non-granted scope → 403 | Generated sweep test |
| W-02-T10 | Webhook binding: subscriptions created from manifest on install; deliveries check installation status at send | BE | T08, W-01 | Webhooks delivered while installed; zero after uninstall | pytest + Celery eager |
| W-02-T11 | Uninstall service: revoke tokens (RFC 7009), delete subscriptions, end entitlement add-on (Stripe proration if paid), status `uninstalled`, keep data, audit — single transaction + outbox for Stripe | BE | T08, T10 | After uninstall token → 401 within same request; webhooks 0; records remain | pytest |
| W-02-T12 | Re-install idempotency (new installation row, old kept for history) and re-consent on version scope change | BE | T11 | Re-install grants only new version scopes; history shows both | pytest |
| W-02-T13 | Version upgrade flow: new scopes → `pending_consent`; old version continues until accept or retirement deadline | BE | T12 | Added scope unusable before consent | pytest |
| W-02-T14 | Kill switches: platform-level per app/version, org-level suspend; suspended → tokens rejected, webhooks paused | BE | T08 | Suspend blocks calls within 1 request; resume restores | pytest |
| W-02-T15 | Demo organisation sandbox mode: installs on demo orgs flagged, writes allowed only to demo data, excluded from metrics (U-07 rules) | BE | T08, U-07 | Demo install never appears in platform metrics | pytest |
| W-02-T16 | API: `GET/POST /api/v1/apps/`, `GET /api/v1/apps/{key}`, `POST /api/v1/apps/{key}/install`, `POST /api/v1/apps/{key}/uninstall`, `GET /api/v1/apps/installations/{id}/activity` with OpenAPI docs | API | T08–T14 | Contract tests from spec pass | Schemathesis |
| W-02-T17 | Console API & permissions for Platform Owner (`/api/platform/v1/companion-apps/…`), Platform-only role | API | T06 | Org users get 404 on platform endpoints | Role matrix test |
| W-02-T18 | Wireframes + Figma for catalogue, detail, consent, uninstall, activity, console screens (EN/FR copy) | UX | T01 | Design reviewed by project lead | Design review |
| W-02-T19 | Org UI: Settings › Numo9 apps catalogue with tile states (installed/available/included/add-on/coming soon) | FE | T16, T18 | Planned Commerce tile shows "Coming soon", not installable | Playwright |
| W-02-T20 | Org UI: app detail + install consent dialog (ScopeList, billing summary) | FE | T19 | Install flow ≤ 4 clicks; consent stored with user and timestamp | Playwright |
| W-02-T21 | Org UI: uninstall dialog ("what stops / what stays") | FE | T20 | Uninstall in 2 clicks; toast; tile back to Available | Playwright |
| W-02-T22 | Org UI: installation activity (calls, webhook deliveries, errors) + health indicator and owner notification on repeated failure | FE/BE | T16 | Failing webhook shows red health and notification | Playwright + pytest |
| W-02-T23 | Console UI: registry list, app editor with manifest lint results, version approval, installations with kill switch | FE | T17, T18 | Platform Owner approves version from UI | Playwright |
| W-02-T24 | Accountant directory column/filter "Numo9 apps" (V-01) | FE/BE | T16 | Filter returns orgs with Commerce installed | Playwright |
| W-02-T25 | Seed registry: Numo9 Bank (planned/available stub using `BankStatementSource`), Numo9 Receipts (first-party, mobile Y), Numo9 Commerce (planned) | BE | T06 | Three records present on staging | Fixture check |
| W-02-T26 | Numo9 Bank reference stub: client-credentials job posting statement lines through `BankStatementSource` via public API only | BE | T09, F-02 | Stub imports 10 lines through API; duplicates 0 on rerun | Integration |
| W-02-T27 | "No third-party marketplace" guard: CI test asserting no publisher ≠ Numo9 can be registered and no external listing routes exist | QA | T06 | Test green; attempted third-party manifest fails | pytest + Playwright |
| W-02-T28 | i18n keys EN/FR for all app strings; manifest FR fields required by lint | FE/i18n | T19–T23 | i18n_report 0 missing in `apps/*` | CI |
| W-02-T29 | Security review: OAuth flows ZAP scan, PKCE enforced, redirect URI exact match, token lifetimes, semgrep rule against scope-bypass | QA | T09–T14 | No high findings | ZAP + semgrep |
| W-02-T30 | Property test: random install/uninstall/upgrade sequences → granted scopes always equal latest consented version's scopes; no live tokens after uninstall | QA | T11–T13 | 1,000 runs pass | Hypothesis |
| W-02-T31 | Documentation: "Building a Numo9 companion app" internal guide (manifest, scopes, webhooks, testing), platform-owner guide section | DOC | T23 | Pages in MkDocs | Review |

- **Deliverable acceptance:** installing an app grants exactly its scopes; uninstalling revokes them; no third-party marketplace surface exists; registry live on staging with three seeded apps.
- **Testing approach:** unit (schema, validators), integration (OAuth + scopes + webhooks + Stripe add-on), generated scope sweep, property test, functional E2E install/uninstall, security (ZAP, abuse cases), regression (W-01 contract tests), tenant isolation (installation tokens cannot see other orgs).
- **Risks & mitigations:** scope leak → generated sweep in CI; token not revoked → revocation in same transaction + test; Stripe add-on drift → outbox + reconciliation job; registry perceived as marketplace → copy and guard test.

---

### W-03 · Numo9 Commerce discovery annex

- **Branch:** `docs/W-03-commerce-discovery-annex`
- **Objective:** define Numo9 Commerce (e-commerce storefront posting sales and stock to the ledger) as a change-controlled annex — requirements, data model, estimate and plan — approved by the client before build.
- **Current behaviour:** Commerce exists only as a roadmap line (W-02 planned app).
- **Expected behaviour:** annex document `docs/annexes/ANNEX-W03-Numo9-Commerce.md` (+ PDF) covering scope, users, journeys, functional requirements, data model reusing H items, D orders → invoices, H stock, P payments, tax rules for online sales, integration through W-01 only, NFRs, estimate, schedule, risks, acceptance criteria, pricing proposal; written client approval.
- **Gap #s addressed:** 48, 50 (open API consumption), Teardown §10.B "open e-invoicing standards" noted as a roadmap requirement.
- **Business rules:** no production build until annex approved (Agreement 5.4(c), §11); annex uses Numo9's own engines (tax G-01/G-02, posting C-02, stock H-04, Stripe P-01) — no duplicated logic; Commerce sales must post through invoice/payment APIs so revisions, tax and AR stay consistent.
- **Edge cases:** scope creep in interviews (log as "later" backlog); undefined pricing (proposal with options); dependency on client marketing strategy (out of scope; noted).
- **UI/UX notes:** storefront and merchant-admin journeys storyboarded in FigJam; key screens low-fi only.
- **Dependencies:** W-01, W-02 (T01–T08 for integration model), H, D, P, G modules as reference.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| W-03-T01 | Discovery plan: objectives, interview guide, stakeholder list, annex outline, schedule (week 12) | DOC | — | Plan shared with client | Review |
| W-03-T02 | Stakeholder interview 1 (Profitex product owner): goals, target merchants, success metrics | DOC | T01 | Notes recorded and confirmed by client | Client confirmation |
| W-03-T03 | Stakeholder interview 2 (pilot merchant/accountant): order-to-cash pain points, channels, volumes | DOC | T01 | Notes recorded | Client confirmation |
| W-03-T04 | Merchant personas and channel priorities (storefront, in-person POS later, marketplaces later) | DOC/UX | T02, T03 | Personas page approved | Review |
| W-03-T05 | User journeys / storyboards (browse → cart → checkout → order → invoice posted → stock moved → payout reconciled → refund/return) in FigJam | UX | T04 | Journeys reviewed by client | Walkthrough |
| W-03-T06 | Functional requirements catalogue with MoSCoW priority (catalogue sync from H items, variants, pricing/price lists, cart, checkout, shipping, taxes, discounts/promo codes, orders, returns, customer accounts, email notifications EN/FR) | DOC | T05 | ≥ 90 % requirements prioritised and traced to journeys | Traceability table |
| W-03-T07 | Canadian tax & compliance requirements for online sales: place of supply by shipping address (G-02), GST/HST/PST/QST collection, zero-rated exports, CASL consent for marketing emails, PIPEDA/Law 25 privacy, French-language obligations for Quebec storefronts, PCI kept at Stripe | DOC | T06 | Section reviewed with client's tax lead | Review |
| W-03-T08 | Data model: entities (Storefront, ProductListing → H Item, Variant, Cart, Order, OrderLine, Fulfilment, Return, CustomerAccount → B Contact) with ERD (Mermaid) and mapping to existing models | DOC | T06 | ERD renders; every entity mapped or marked new | mmdc render |
| W-03-T09 | Integration map: order → D invoice (posted via W-01), payment → P-02/Stripe, fulfilment → H-04 stock movement, refund → D-06 credit note + P-05, webhooks used (`stock.moved`, `invoice.revised`), scopes required (manifest draft) | DOC | T08, W-02-T02 | Manifest draft validates against W-02 schema | Validator run |
| W-03-T10 | Non-functional requirements: performance (storefront LCP < 2.5 s), availability, scale (orders/day), security, accessibility WCAG 2.1 AA, bilingual EN/FR, SEO, hosting region | DOC | T06 | NFR table with measurable targets | Review |
| W-03-T11 | Architecture options (headless storefront on Next.js vs hosted template) with ADR draft and recommendation | DOC | T09, T10 | ADR-007 draft with trade-offs | Review |
| W-03-T12 | Work breakdown structure into components → atomic task estimate (three-point PERT) in XLSX | DOC | T08–T11 | Estimate sheet with totals and confidence range | Formula check |
| W-03-T13 | Delivery plan: phases, milestones, dependencies on Numo9 releases, team, test strategy (reuse §6 categories), acceptance criteria per milestone | DOC | T12 | Plan section complete | Review |
| W-03-T14 | Risks register and assumptions for Commerce (payments, tax, fraud/chargebacks, inventory sync, scope) | DOC | T13 | ≥ 10 risks with mitigation | Review |
| W-03-T15 | Commercial proposal options (price, payment milestones, warranty) per change-control clause §11 | DOC | T12, T13 | Options table presented | Review |
| W-03-T16 | Compile annex document (Markdown → PDF with diagrams) with original Numo9 wording; EN (FR summary optional) | DOC | T01–T15 | PDF generated; links and diagrams render | Build check |
| W-03-T17 | Annex walkthrough meeting with client; capture change requests | DOC | T16 | Minutes recorded | Client confirmation |
| W-03-T18 | Apply revisions; issue v1.1; obtain written approval (email sufficient) and record in `docs/annexes/approvals.md`; update W-02 Commerce app status to `approved_for_build` (not installable) | DOC/BE | T17 | Written approval on file; registry status updated | Record check |

- **Deliverable acceptance:** annex approved by the client before build.
- **Testing approach:** document review checklist (completeness, traceability journeys → requirements → data model → tasks → estimate), manifest draft validation, diagram build check.
- **Risks & mitigations:** client availability → interviews scheduled at week start; scope creep → MoSCoW + "later" backlog; estimate optimism → three-point estimates and contingency shown.

---

## 7. TEST — phase test plan

| Category | Scope | Tooling | Target |
|---|---|---|---|
| Unit | Manifest schema, scope validator, services | pytest | ≥ 85 % on `companion_apps` |
| Integration | OAuth install/uninstall, webhooks, Stripe add-on, entitlement | pytest, Stripe CLI, Celery eager | All happy + failure paths |
| Security | Generated scope sweep, tenant isolation for installation tokens, ZAP OAuth, PKCE, redirect URI | custom sweep, ZAP, semgrep | No high findings; sweep 100 % |
| Property | Random install/uninstall/upgrade sequences | Hypothesis | 1,000 runs green |
| Functional | Install → use → uninstall Numo9 Bank stub; Platform Owner registers/approves version; accountant filter | Playwright | 100 % |
| Regression | W-01 contract tests, U-03 entitlement leak tests | CI | 0 regressions |
| Localisation | App strings EN/FR, manifest FR fields | i18n gate | 0 missing |
| Gap closure | gap-48, gap-50, gap-41-apps, gap-1-ads | tagged tests | Green |
| Document QA (W-03) | Traceability matrix, diagram builds | checklist, mmdc | Complete |

**Exit demonstration script**
1. Platform console → Companion apps → show three registered apps (Bank available, Receipts first-party, Commerce planned).
2. Attempt to register a manifest with `publisher: "acme"` → rejected ("Only Numo9-owned apps can be registered").
3. Organisation Owner → Settings › Numo9 apps → install Numo9 Bank → consent screen shows 2 scopes → confirm.
4. Run Bank stub → 10 statement lines imported via public API; activity tab shows calls.
5. Use the installation token on `/api/public/v1/invoices/` → 403 (scope not granted).
6. Uninstall → token immediately 401; trigger `stock.moved` → no delivery; statement lines remain.
7. Show scope-sweep and property test reports green.
8. Show approved Numo9 Commerce annex PDF and written approval record; Commerce tile still "Coming soon".

**Failure handling:** stop dependent tasks, isolate failing scope/endpoint pair, single focused fix, rerun sweep and regression; never relax a scope rule to pass a test.

---

## 8. IMPROVE — post-verification checklist
- Review scope catalogue granularity (split over-broad scopes before first real app ships).
- Cache scope map lookups (target < 2 ms per request overhead).
- Remove stub-only code paths from production build (Bank stub behind flag).
- Confirm audit entries readable and filterable for app events.
- Re-run sweep + full regression after changes.
- **Performance budgets:** scope enforcement overhead < 2 ms p95; install/uninstall API < 500 ms p95; catalogue page < 1.5 s.

---

## 9. Git branch plan

| Branch | Base | Deliverable | Merge order |
|---|---|---|---|
| `feature/W-02-companion-app-registry` | `main` | W-02 | 1 |
| `docs/W-03-commerce-discovery-annex` | `main` | W-03 | 2 (parallel; final merge after approval) |
| `spike/W-03-storefront-prototype` (optional, never merged) | `main` | W-03 T11 support | — |

Pre-branch: clean `git status`, pull `main`, objective + acceptance in PR. Pre-complete: acceptance observed, CI green incl. scope sweep and isolation sweep, no unrelated changes, no secrets, docs updated, review, lead authorisation.

---

## 10. Phase risks register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Scope/permission leak through installation tokens | Low | Critical | Generated sweep + property test as CI gate |
| 2 | Week 12 overlaps mobile store release (Phase 7) | High | Medium | W-02 owned by backend/frontend engineers; mobile engineer not on critical path |
| 3 | Client delays annex approval | Medium | Low | Phase deemed accepted rules (Agreement 7.4); build stays blocked anyway |
| 4 | Commerce scope inflation | High | Medium | MoSCoW, change control, estimate ranges |
| 5 | Registry misread as third-party marketplace | Low | Medium | First-party guard test, copy review |
| 6 | Stripe add-on billing inconsistencies | Medium | Medium | Outbox + nightly reconciliation |

---

## 11. Phase completion checklist (Rule 11) & reporting template (Rule 10)

**UNDERSTAND** — [ ] W-01 API/scopes and U-03 entitlements inspected · [ ] users and outcomes identified · [ ] inputs/outputs defined · [ ] first-party and revocation rules identified · [ ] edge cases (grace, demo, concurrent install) considered · [ ] objective restated.
**PLAN** — [ ] atomic tasks for W-02 and W-03 · [ ] dependencies identified · [ ] order defined · [ ] acceptance per task · [ ] tests defined.
**BUILD** — [ ] smallest slice (register → install → revoke) first · [ ] W-01/U-03 reused, no duplicated auth logic · [ ] no Commerce production code · [ ] existing API behaviour preserved · [ ] feature keys and i18n keys declared.
**TEST** — [ ] scope sweep · [ ] property test · [ ] tenant isolation · [ ] regressions · [ ] unverified conditions recorded.
**IMPROVE** — [ ] stubs behind flags · [ ] performance overhead checked · [ ] readability reviewed · [ ] re-verified.
**COMPLETE** — [ ] diff reviewed · [ ] ADR-006/007 and guides updated · [ ] results reported · [ ] annex approval on file · [ ] final status reported.

**Reporting template**
- *Before implementation:* 1. Problem understanding. 2. Task breakdown. 3. Implementation plan (order, acceptance, tests).
- *After implementation:* 1. Changes made. 2. Testing results (executed / passed / failed / not executed and why). 3. Remaining issues. 4. Final status — Complete / Partially complete / Blocked.

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| W-02 | 31 | 46.5 |
| W-03 | 18 | 27 |
| **Total** | **49** | **73.5** |

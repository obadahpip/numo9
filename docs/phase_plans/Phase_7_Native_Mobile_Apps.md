# NUMO9 — PHASE 7 IMPLEMENTATION PLAN: Native Mobile Apps

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | 7 — Native Mobile Apps (iOS + Android) |
| **Weeks** | 10–12 (hypercare for mobile in week 13) |
| **Deliverables** | Y-01 Mobile foundation · Y-02 Organisation-owner app · Y-03 Employee app · Y-04 Store release & maintenance |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment) |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §1.4, §1.8 (assumption 9), §3 Component Y, §4, §5.1–5.4, §6 · Project_Phases.md (Phase 7) · Quotation GMA-PFX-2026-003 §4 (Native Mobile Apps, ★ loan status and SKU analytics) · Agreement GMA-PFX-2026-003-A §5.3, §06, §07, 9.1, §12 · xero_teardown.md · AI Coding Agent — Mandatory Engineering Workflow |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE — applied to the phase, to every deliverable (one Git branch each) and to every atomic task |

---

## 0. How to use this file

1. Each deliverable in §6 is one Git branch (`feature/Y-0n-<short-name>`) cut from `main`. Very large deliverables (Y-02, Y-03) may be split into sub-branches per screen group (`feature/Y-02-invoices`, `feature/Y-02-bills`…) — each sub-branch still maps to atomic task IDs in this file.
2. Every atomic task (`Y-0n-Tnn`) is worked through the full cycle on its own: restate → plan steps → build the smallest working piece → run it on a simulator/device → test (incl. invalid inputs and offline) → improve. A task is 1–2 hours of focused work.
3. Tasks are ordered; the `Depends` column must be satisfied before a task starts. Tasks with no shared dependency may run in parallel (two mobile engineers or mobile + backend).
4. Nothing is reported complete until its acceptance column has been **observed** on both iOS and Android (simulator for unit/feature work; physical device for camera, biometrics, push and release tasks).
5. The mobile apps are **clients of the existing W-01 public API** — the phase adds no business logic to the backend except the small mobile-support endpoints listed in Y-01 (device registration, push tokens, sync cursor, upload sessions). Any posting, tax, payroll or revision logic stays in the Django services built in Phases 0–4; the app never re-implements it.

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase

| Area | Built in | What the mobile apps reuse |
|---|---|---|
| Tenancy, `OrgOwnedModel`, cross-org 404, tenant sweep | A-01 (Phase 0) | Every mobile request is org-scoped by the same middleware; sweep extended to the mobile client |
| Auth: email/password, verification, reset, TOTP 2FA, session list, invitations | A-02 | Token issuance for mobile (OAuth2 PKCE / refresh tokens via W-01), session list shows mobile devices |
| RBAC, approval limits, permission catalogue | A-03 | Bill approval on mobile obeys the same `$5,000` limits; screens hide/disable by permission |
| Audit log | A-04 | Every mobile action is audited with `channel=mobile`, device id, app version |
| File storage, documents inbox, virus scan, 25 MB limit | A-06 | Receipt/photo uploads land in the org's documents inbox |
| Notifications centre, EN/FR templates | A-07 | Push becomes a new channel of the same notification service |
| Celery jobs | A-08 | Push fan-out, receipt OCR jobs |
| Global search | A-09 | Mobile search calls the same `/api/v1/search` endpoint |
| Design tokens (A-10) | Phase 0 | Colour, type, spacing, radius tokens exported as JSON → consumed by the mobile theme (one brand, two platforms) |
| Entitlement engine, 402 contract, feature matrix | U-03 | Mobile shows gated features explicitly ("Included in Payroll") — never hides or silently redirects |
| Subscription billing, trial, founding badge | U-04, U-05, U-08 | Subscription status screen (read-only; managing payment stays on web per store rules) |
| Invoices + revisions 101 → 101-1, pay links | D-03a, D-03b, P-02 | Mobile create/send/revise/share pay link; revision badge + history |
| Bills, approval routing, duplicates | E-02 | Approve/reject with limits |
| Receipt & bill capture with OCR confidence | E-05 | Camera capture → upload → per-field confidence review |
| Expense claims + mileage | E-04 | Employee expense claims |
| Never-locked bank accounts, spend/receive | F-01, F-07 | Spend/receive money with negative-balance warnings |
| Tax payments state machine | G-09 | Read-only status + "pay" deep link to web confirmation |
| Loans (FN-01…FN-05) [v2.1] | Phase 2 | Loan status cards (balance, next payment, YTD interest) |
| SKU analytics (H-09…H-13) [v2.1] | Phase 2 | Best-sellers, margins, reorder alerts (read-only + "create PO" handoff) |
| Payroll stubs, T4/T4A slips, leave, timesheets, self-service | M-03, M-06, N-05, N-08, J-02 | Employee app data |
| French catalogues | X-01, X-02 (Phase 6) | Mobile uses the same ICU catalogues; fr-CA from day one of the mobile build |
| Public API, OAuth scopes = feature keys, webhooks, rate limits | W-01 (Phase 4) | The only backend surface the apps use |
| Monorepo `mobile/` workspace, CI | S-01 | Pipeline exists but is empty — Y-01 fills it |

**Nothing mobile exists yet**: `mobile/` is an empty workspace placeholder. No Expo project, no store listings, no push credentials, no bundle identifiers.

### 1.2 Problem definition — the seven questions

1. **Who uses it?** (a) Organisation Owner / Organisation Admin — paying client, on the move, wants to see cash, send and fix invoices, approve bills, snap receipts, check taxes and loans. (b) Organisation users with limited roles (Sales clerk, Purchasing) — the same app with fewer actions. (c) Employee — pay stubs, slips, leave, expenses, timesheets. (d) System — push notifications, background sync, OCR jobs. Accountants keep the full workstation on web (Plan §1.8 assumption 9), but an accountant who is also an org user can sign in and switch orgs.
2. **Desired outcome:** two store-published apps (one binary per platform containing both experiences, or two binaries — decision ADR-005, see §1.4) that let owners and employees do their 80 % daily tasks in under a minute each, with data identical to web within one sync.
3. **Inputs:** credentials/biometrics, org selection, invoice fields and edits, bill approve/reject decisions with comment, spend/receive transactions, camera images and PDFs, leave requests, expense claims with photos and mileage, timesheet entries, push permission, language preference.
4. **Outputs:** API calls creating/updating records (with idempotency keys), uploaded documents, rendered dashboards, PDFs viewed/shared (stubs, slips, invoices), push notifications, local encrypted cache, crash/analytics telemetry (no PII), store builds.
5. **Business rules:** tenant isolation (cross-org → 404 also from mobile); RBAC + approval limits enforced server-side, mirrored in UI; entitlement gating explicit (402 → gated card); invoice edits on a posted invoice always create a revision (server decides suffix); employee sees only own records; SIN never shown, bank masked; offline queue may hold **captures and drafts only** — no offline posting of ledger-affecting actions (approve, post, pay) — these require connectivity and a fresh server state; tokens in secure hardware storage; session revocable from web; subscription purchase **not** sold inside the app (avoids in-app-purchase rules: "reader/business app" — manage on web); EN/FR per user; CRA six-year retention is server-side — the device cache is a cache, purged on logout.
6. **What could go wrong:** stale cache shows an old revision (101 instead of 101-1); offline duplicate submissions; approving a bill offline that was already approved; token theft from a lost phone; push leaking amounts on the lock screen; app-store rejection (login-only demo account missing, account-deletion requirement, privacy manifest, payments policy); Android back-button losing a draft; camera permission denied; huge photos exceeding 25 MB; French strings overflowing buttons; Dynamic Type at 200 % breaking layouts; time-zone differences in leave dates; mobile and web diverging behaviour; Expo SDK upgrade breaking builds; crash-free rate below 99 %.
7. **Smallest useful implementation:** Y-01 foundation (login + biometric + org switch + dashboard on both platforms, passing the tenant sweep) → owner invoices list/detail with revision badge → receipt capture → employee pay stubs. Everything else layers on.

### 1.3 Restated objective

- **Currently:** Numo9 is web-only; owners and employees must open a browser to approve, capture or view; the W-01 API exists but has no mobile client.
- **Change:** build a React Native (Expo) app family sharing the W-01 API and auth, with biometric unlock, secure token storage, push, offline capture queue; an owner experience (dashboard, invoices incl. revisions and pay links, bill approvals, bank spend/receive, receipt capture to E-05, tax-payment status, subscription status, loan status and SKU analytics [v2.1], notifications) and an employee experience (stubs, T4/T4A slips, leave, expense claims with camera, timesheets); publish both platforms under the client's developer accounts with EN/FR store copy and crash reporting.
- **Why:** owners act on cash and approvals daily; employees need self-service without a desk; Xero's mobile story is fragmented across separate apps (main app, Xero Me/Expenses, Hubdoc, Projects) — Numo9 gives one coherent app with consistent behaviour.
- **Done means:** login, org switch and dashboard on both platforms; tenant sweep executed through the mobile client; an invoice revised on web appears as the current revision on mobile within one sync; employee sees only own records; both apps approved and published; crash-free ≥ 99 % in hypercare.

### 1.4 Assumptions & interpretations

1. **One app, role-aware** (recommended, ADR-005): a single "Numo9" app per store whose home adapts to the user's role in the active org (Owner/Admin/Sales/Purchasing → owner experience; Employee → employee experience; a person who is both sees a role switcher). This halves review/maintenance cost and matches "both apps published" in the acceptance as "iOS app + Android app". If the client prefers two listings ("Numo9" and "Numo9 Team"), the same codebase builds two flavours via EAS build profiles (task Y-04-T03 covers both paths).
2. Expo SDK current stable at kickoff of Phase 7 (pinned in `mobile/package.json`), managed workflow with config plugins; EAS Build/Submit/Update.
3. Accountants are not the primary audience; they can log in but practice workspace (V-*) is web only — mobile shows "Open on web" deep link for practice-level actions.
4. Subscription purchase/upgrade is **not** offered in the app; the subscription screen is informational with a link to the web billing page (store policy compliant for B2B SaaS; verified in Y-04 review checklist).
5. Tax payments: mobile shows status and amounts owing; initiating a payment opens the web confirmation flow (in-app browser with SSO handoff) — keeps payment UI in one audited place. Status updates come by push.
6. Offline: read cache for last-synced data (dashboard, lists, stubs/slips PDFs downloaded by the user) + write queue for receipt captures, expense-claim drafts, leave drafts, timesheet entries and invoice **drafts**. Ledger-affecting confirmations (approve invoice, approve bill, spend money post, submit revision) are online-only with a clear "needs connection" state.
7. Push provider: Expo Push Service → APNs/FCM (credentials under client accounts). Lock-screen content is amount-free by default (setting to show amounts).
8. Minimum OS: iOS 16+, Android 9 (API 28)+ — covers > 95 % of Canadian devices; tablets supported in portrait/landscape with the phone layout scaled (no dedicated tablet UI in scope).
9. Demo account for App Review: a seeded demo organisation (U-07) with a reviewer login, refreshed before each submission.

**Open questions for the client (decision by start of week 10):** one listing vs two (ADR-005); app display names in EN/FR; support URL/email and privacy-policy URL; whether lock-screen amounts default on/off.

### 1.5 Client inputs required

| Input | Needed by | Source |
|---|---|---|
| Apple Developer Program account (organisation enrolment, D-U-N-S) with GMA added as Admin/App Manager | Start of week 10 (enrolment can take 1–2 weeks — request at Phase 5) | Agreement 9.1, Phase 7 client inputs |
| Google Play Console account with GMA as admin; merchant not required | Start of week 10 | Same |
| App names, short/long descriptions EN/FR approval, keywords | Week 11 | Client marketing |
| Privacy policy URL & support URL (from Q-01 site), data-safety answers confirmation | Week 11 | Client/legal |
| Brand assets for app icon/splash (yellow/black Numo9 logo, vector) | Week 10 | Brand pack (Phase 0) |
| French glossary reviewer for store copy and new mobile strings | Week 12 | X-02 reviewer |
| Test devices list (client UAT testers' devices) for TestFlight / internal track | Week 11 | UAT testers |

---

## 2. BETTER THAN XERO — gap analysis for this phase

The teardown inspected the Xero web app; its mobile experience is fragmented across the main app, Xero Me/Expenses, Hubdoc and Projects apps, with key actions plan-gated (teardown §7). Phase 7 carries the web gap closures onto mobile and adds mobile-specific improvements.

| Gap # | Teardown ref | What Xero does / fails to do | What Numo9 mobile does instead | Observable proof (test tag) |
|---|---|---|---|---|
| 1 | §0 | Two UI generations, inconsistent dates/grids/empty states | One mobile design system generated from the same A-10 tokens; one date format per locale; identical status names to web | `gap-01-mobile` snapshot suite: status chips and dates match web catalogue |
| 4 | §1 | No bank balance widget by default; "—k" on empty charts; ads on dashboard | Bank balances card is first on the dashboard; empty values render `$0.00`; no promotional content anywhere | `gap-04-mobile` Detox: empty org dashboard shows 0.00, no "—k", no ad component exists |
| 5 | §2.1 | "Online payments" card failed to load with no recovery | Every card has its own error state with retry and offline label; failures reported to Sentry with request id | `gap-05-mobile`: mocked 500 on one card → other cards render, retry works |
| 6 | §2.2 | Approval paywalled; no Overdue tab | Approve on mobile whenever the role allows; Overdue filter chip on invoices | `gap-06-mobile` |
| 14, 41 | §2.5, §6.3 | Silent redirects; generic upgrade banners; advisor can't see plan | 402 from API renders a gated card naming the product ("Included in Payroll — ask your owner or see plans on web"); subscription screen shows the package and products | `gap-14-mobile`, `gap-41-mobile` |
| 32 | §5.7 | Documents slow; no OCR confidence per field | Capture → on-device compression → background upload → per-field confidence chips (high/medium/low) and mandatory confirmation | `gap-32-mobile`: low-confidence field highlighted and cannot be skipped |
| 42 | §6.5 | No per-contact/user language | App follows user language (EN/FR) independent of device; invoices sent use contact language (server) | `gap-42-mobile` |
| 43 | §6.6–6.7 | NZ sample data, US/UK terms | Canadian demo data and terms (cheque, GST/HST, vacation pay, Province, Postal code) | lint `i18n-terms` on mobile catalogue |
| 51 | §7 | Expenses, projects, capture are separate paid add-ons/apps | Expense claims, receipt capture and timesheets are inside the one app, included with the products | `gap-51-mobile` |
| 52 | §8.1 | Search misses journals/accounts | Mobile global search uses A-09 (journals, accounts, contacts, invoices, bills, settings) | `gap-52-mobile` |
| 61 | §10.B | No clear plan/feature matrix | Feature matrix screen in Settings → "What's in my package" | `gap-61-mobile` |
| — (Client #5) | §2.3 / Plan §1.6 | Posted invoice can only be voided | Edit a sent invoice on mobile → server creates 101-1; badge "Revised" + history sheet; PDF shows revision stamp | Exit demo step 6 |
| — (Client #6) | §5.1 | Bank module locked behind feeds | Spend/receive from any bank/cash account with no feed; negative-balance warning before submit | `F-07` rule exercised from mobile |

**Beyond-Xero additions in this phase**

- Single app covering owner + employee experiences with role switcher (Xero splits across apps).
- Revision-aware invoices on mobile (101-1 badge, superseded versions viewable, pay link always follows current revision).
- Loan status cards [v2.1] — balance, next payment date/amount, principal vs interest split, YTD interest.
- SKU analytics [v2.1] — best sellers by quantity/revenue/margin, low-stock alerts, one-tap "Create purchase order draft" from an EOQ suggestion.
- Tax-payment status with due-date countdown and push before due date.
- T4/T4A slip viewer with offline download and share to a tax preparer.
- Mileage capture with CRA per-km rate preview.

**Xero strengths matched conceptually (original design, no copied UI/text)**

- Snap-a-receipt capture with extraction (Hubdoc/Xero Me) → Numo9 capture with confidence and duplicate detection.
- Quick invoice creation on the go → Numo9 invoice create with place-of-supply tax defaulting (G-02) shown live.
- Push for paid invoices → Numo9 push for payments, approvals, tax due dates, pay stubs available.

**[EXTRA] improvements within scope (refinements, not new modules)**

- [EXTRA] **"Needs you" inbox** on the owner home: a single prioritised list (bills awaiting your approval within your limit, invoices revised by your accountant, tax due in ≤ 7 days, receipts with low-confidence fields) — reduces navigation to one tap.
- [EXTRA] **Duplicate-receipt guard on device**: perceptual hash of the photo compared against the last 90 days of uploads before upload (server confirms with E-05 duplicate logic).
- [EXTRA] **Approve with reason templates** (quick replies "Approved — within budget", "Rejected — wrong supplier") stored per user.
- [EXTRA] **Privacy screen**: app switcher snapshot blurred; amounts hidden toggle ("Privacy mode") with a long-press to reveal.
- [EXTRA] **Accessible amounts**: screen readers read "one thousand seventeen dollars" with sign and currency, not "1 0 1 7".
- [EXTRA] **Revision diff sheet**: shows changed lines between 101 and 101-1 (old/new amount, tax) using the A-04 diff data.
- [EXTRA] **Offline banner with queue count** and per-item retry; nothing silently lost.
- [EXTRA] **Deep links** from emails/push (`numo9://org/{id}/invoices/{id}`, universal links on the Numo9 domain) with org switch confirmation when the link targets another org.
- [EXTRA] **Remote config kill-switch** per feature (U-06 feature flags) so a defective mobile feature can be disabled without a store release.

---

## 3. UI/UX DESIGN PLAN

### 3.1 UX principles applied

1. **Task-first home**: the first screen answers "how much cash do I have, what needs me, what's due" — no menus to dig through.
2. **Thumb-zone layout**: primary actions in the bottom 40 % of the screen (bottom tab bar, floating capture button, sticky bottom action bar on detail screens); destructive actions never in the primary thumb arc.
3. **Platform-native feel**: iOS — large titles, swipe-back, sheets with detents, SF Symbols-equivalent icon set; Android — Material 3 top app bar, predictive back, FAB, Material You dynamic colour disabled (brand yellow/black kept) but Material elevation/ripple used. Shared components with platform variants (`Platform.select`).
4. **Explicit gating, no silent redirects**: a feature outside the package renders a gated card naming the product; a permission-limited action shows the reason ("Your approval limit is $5,000.00").
5. **Online-only actions are honest**: approve/post/pay buttons show a "Needs connection" state offline instead of failing after a tap.
6. **Undo over confirm where safe**: reject/archive drafts → snackbar with Undo (5 s); ledger-affecting confirmations (approve bill, approve/send invoice, post spend money, submit revision) use a confirm sheet summarising amount, account and tax.
7. **Forgiving inputs**: amount keypad with automatic decimal; dates with "Today / Yesterday / pick" chips; contact search tolerant of accents and typos; camera auto-crop with manual adjust.
8. **Progressive disclosure**: invoice lines show item/qty/amount; tax code and account behind "More" (defaults from place-of-supply and item).
9. **Accessibility**: WCAG 2.1 AA contrast (yellow used as accent with black text, never yellow text on white), touch targets ≥ 44 pt iOS / 48 dp Android, Dynamic Type / font scale up to 200 % with reflow, VoiceOver/TalkBack labels on every control, reduce-motion respected, no information by colour alone (status chips carry text + icon).
10. **Localisation ready**: en-CA and fr-CA from the first screen; +30 % string-length tolerance; currency `$1,234.56` / `1 234,56 $`; dates `Nov 7, 2026` / `7 nov. 2026`; 24-hour time in FR.
11. **Privacy by default**: amounts hidden on lock-screen notifications; app switcher blur; biometric re-auth after 5 min in background (configurable 1/5/15 min).
12. **Speed budgets**: cold start ≤ 2.5 s on mid-range Android (Pixel 6a class), warm start ≤ 1 s, list scroll 60 fps, dashboard from cache ≤ 300 ms then refresh.
13. **Consistency with web**: identical status names, revision labels, error codes and money formatting from shared catalogues.

### 3.2 Information architecture / navigation

**Owner experience — bottom tabs (5):**
1. **Home** — Needs-you inbox, cash/bank balances, money in/out, tax due, loans, SKU highlights.
2. **Sales** — Invoices (All / Draft / Awaiting payment / Overdue / Paid / Revised), Quotes (read), Customers (lookup).
3. **Capture** (centre, raised action) — Receipt/bill photo, PDF import from Files/share sheet, spend money, receive money.
4. **Approvals** — Bills awaiting approval, expense claims awaiting approval (if role), timesheets (if role).
5. **More** — Banking (accounts, transactions), Taxes (status), Loans [v2.1], Inventory insights [v2.1], Documents, Notifications, Search, Subscription, Settings, Switch organisation, Help.

**Employee experience — bottom tabs (4):** Home (next pay date, latest stub, leave balance, pending items) · Pay (stubs, slips T4/T4A) · Requests (leave, expense claims) · Time (timesheets/timer) — Profile in header avatar.

**Global:** org switcher in the header (avatar + org name, sheet with search over the user's orgs); search icon in header; notifications bell with badge; deep-link router.

### 3.3 Screen inventory

| Screen | Primary user | Purpose | Key components | States | Shortcuts / gestures |
|---|---|---|---|---|---|
| Welcome / Sign in | All | Email + password, SSO handoff, "Try demo" | TextField, PasswordField, Button, Link | error (wrong credentials, unverified), locked, offline | Password autofill, passkey/keychain |
| 2FA code | All with TOTP | Enter TOTP | OTPInput (one-time-code autofill) | wrong code, rate-limited | SMS/one-time-code autofill |
| Biometric setup & unlock | All | Enable Face ID / Touch ID / fingerprint; unlock | BiometricPrompt, PIN fallback | not enrolled, lockout, disabled by policy | — |
| Org switcher sheet | Owner, accountant, multi-org employee | Choose org | SearchField, List with role chips, founding badge | one org (sheet hidden), many orgs (search), demo/trial labels | Swipe down to close |
| Owner Home | Owner | Overview + Needs-you | Card, BalanceRow, MiniChart, InboxList, Skeleton | empty org, loading skeleton, offline (cached time), per-card error, gated card | Pull to refresh |
| Needs-you inbox (full) | Owner | Prioritised actions | GroupedList, SwipeActions | empty ("You're all caught up"), offline | Swipe right approve (opens confirm), left snooze |
| Bank accounts | Owner | Balances per account incl. petty cash | List, AmountText, NegativeBadge | no bank account → set-up prompt (web link), negative balance warning | — |
| Bank account transactions | Owner | Ledger lines, reconciliation status | VirtualList, FilterChips | empty, offline cache | Pull to refresh, infinite scroll |
| Spend / Receive money form | Owner | Record without a feed | AmountKeypad, ContactPicker, AccountPicker (filtered), TaxCodePicker (effective-dated), AttachmentStrip | negative-balance warning (F-07), validation, online-only submit | Keypad, "Attach receipt" |
| Invoices list | Owner, Sales | Find & act | SegmentedFilters, SearchField, InvoiceRow with status + revision badge | empty with "Create invoice", offline cache, gated | Swipe: share pay link / send reminder |
| Invoice detail | Owner, Sales | View current revision, payments, history | Header with number "101-1", StatusChip, LinesList, Totals, PaymentList, Timeline, sticky ActionBar | superseded revision viewer, voided, paid, credit applied | Long-press number to copy |
| Invoice create / edit | Owner, Sales | Create draft or edit (revision) | ContactPicker, LineEditor sheet, TaxPreview, DueDateChips, ReasonField (edit) | draft offline-saved, revision warning in filed period (late-adjustment message), conflict (409) | Add line FAB |
| Revision history sheet | Owner | See 101 → 101-1 → 101-2 with diff | Timeline, DiffRow | single revision | — |
| Invoice PDF viewer / share | Owner | Preview and share | PDFView, ShareSheet | download progress, offline (cached) | Pinch zoom |
| Pay link share sheet | Owner | Copy/share link following current revision | QR, CopyButton, Share | Stripe not connected → web link | — |
| Bills approvals list | Owner, Purchasing | Approve/reject | List with amount, supplier, due, limit indicator | over-limit (disabled with reason), duplicate flag, empty | Swipe actions |
| Bill detail & approve sheet | Owner | Decide with evidence | Attachment viewer, LinesList, PO match status (E-01), ReasonTemplates | needs connection, already approved by someone else (409 → refresh) | — |
| Capture camera | Owner, Employee | Photograph receipt/bill | CameraView, EdgeDetectionOverlay, FlashToggle, MultiPage | permission denied (settings link), low light hint | Volume button shutter |
| Capture review (OCR) | Owner, Employee | Confirm extracted fields | ConfidenceField, SupplierPicker, AmountField, TaxSplit | processing, low-confidence fields highlighted, duplicate warning | — |
| Upload queue | All | See offline/pending uploads | QueueList, RetryButton | empty, failed with reason | Swipe to delete pending |
| Tax payments status | Owner | Amounts owing, due dates, status | Card per registration/period, Countdown, StatusChip | none owing, gated (no Tax product), paid with confirmation number | "Pay on web" |
| Loans [v2.1] | Owner | Loan balance & schedule | LoanCard, ProgressBar, ScheduleList | no loans, gated (Finance) | — |
| Inventory insights [v2.1] | Owner | Best-sellers, margins, low stock | RankList, Sparkline, Toggle (qty/revenue/margin), PeriodPicker | no items, gated (Inventory) | Tap item → detail; "Create PO draft" |
| Subscription | Owner | Package, products, renewal, trial days left, founding badge | Card, FeatureMatrix | trial, grace, read-only, founding | "Manage on web" |
| Feature matrix | All | What's included | Table/list | — | — |
| Notifications centre | All | History of alerts | List, unread dots | empty | Mark all read |
| Search | Owner | Global search | SearchField, grouped results | no results with suggestions, offline (disabled with message) | Recent searches |
| Settings | All | Language, biometric timeout, privacy mode, notifications per type, sign out, delete account request | List, Switch, Picker | — | — |
| Employee Home | Employee | Next pay, latest stub, leave balance, pending | Cards | no payroll yet, terminated (read-only) | Pull to refresh |
| Pay stubs list / detail | Employee | View earnings/deductions/YTD | List, StubBreakdown, PDF | none yet, offline downloaded | Share/download |
| Slips list (T4/T4A) | Employee | Year-end slips | List by year, PDF | not issued yet ("Available by Feb 28") | Share |
| Leave balances & request | Employee | Request leave | BalanceCards, DateRangePicker, TypePicker, Notes | insufficient balance warning, overlapping request, offline draft | — |
| Expense claim list / new | Employee | Claim with receipt or mileage | Camera, AmountKeypad, CategoryPicker, MileageCalculator | draft offline, rejected with reason | — |
| Timesheets / timer | Employee | Log time | WeekView, Timer, ProjectPicker, TaskPicker | running timer persisted across app kill, submitted (locked), approved | Start/stop from home card |
| Profile | Employee | Personal info view, masked SIN/bank | ReadOnlyFields | — | — |

### 3.4 Key user flows (targets)

1. **First login → dashboard** (target ≤ 60 s, 5 taps): open app → email → password (autofill) → 2FA code (autofill) → "Use Face ID next time?" → Home (if one org) / Org switcher (if many).
2. **Return unlock** (≤ 2 s): open → biometric → Home from cache → background refresh.
3. **Snap a receipt** (≤ 20 s, 3 taps): Capture tab → shutter (auto-crop) → "Use photo" → queued/uploaded → push "Receipt ready to review" → review fields (low-confidence highlighted) → Create bill/expense.
4. **Approve a bill** (≤ 15 s): push "Bill awaiting your approval $1,250.00" → deep link to bill → view attachment → Approve → confirm sheet (amount, supplier, account) → done; over-limit shows reason, no button.
5. **Revise an invoice** (≤ 60 s): Invoice 101 (Sent) → Edit → change qty → reason "Price correction" → confirm sheet: "This creates revision 101-1. Ledger and AR will be re-posted." → online submit → detail shows 101-1 with "Revised" badge; history sheet shows diff.
6. **Share pay link** (≤ 5 s): invoice row swipe → Share pay link → share sheet (link always resolves to current revision).
7. **Spend money from petty cash** (≤ 30 s): Capture → Spend money → amount → account Petty Cash → expense account (filtered) → tax auto → attach photo → submit → negative-balance warning if it goes below zero (reason required for advisers, blocked otherwise per F-07).
8. **Employee views pay stub** (≤ 10 s): push "Your pay stub for Nov 15 is ready" → Pay tab → stub detail → download PDF.
9. **Leave request** (≤ 30 s): Requests → Leave → type → dates → see "Uses 3 of 10 days" → submit (offline queued if needed).
10. **Expense with mileage** (≤ 45 s): Requests → New claim → Mileage → km 120 → rate shown → total → purpose → submit.

### 3.5 Microcopy & error-message rules

- Name the cause and the fix; never "Something went wrong" alone. Always include a short reference code for support (`Ref: 7F3A`).
- Use the user's terms: "organisation", "cheque", "GST/HST", "vacation pay", "pay stub", "T4 slip".
- Examples:
  - Over limit: "You can approve bills up to $5,000.00. This bill is $5,001.00 — ask an owner or admin to approve it."
  - Gated: "Loans are part of the Finance product. Your package doesn't include it yet. See packages on the web."
  - Offline action: "Approving needs a connection so everyone sees the same numbers. We'll keep this bill open for you."
  - Revision confirm: "Saving creates revision 101-1. The original stays viewable and is marked superseded."
  - Filed period: "This invoice is dated in a GST/HST period you already filed (Jul–Sep 2026). The tax difference will be adjusted in the next open period."
  - Conflict: "Someone changed this invoice a moment ago. We've loaded the latest version — please review your edit."
  - Camera denied: "Numo9 needs camera access to photograph receipts. Turn it on in Settings › Numo9 › Camera."
  - Negative cash: "This payment takes Petty Cash to −$994.17. Cash on hand can't be negative — record who funded it, or choose another account."
- French versions authored in the same ICU catalogue, reviewed by the client glossary reviewer.

### 3.6 Accessibility & usability test plan

| Usability task | Participants | Success metric |
|---|---|---|
| Sign in first time with 2FA and enable biometrics | 5 owners (UAT testers) | 5/5 complete, median ≤ 60 s |
| Snap and submit a receipt | 5 owners + 5 employees | ≥ 9/10 without help, median ≤ 20 s |
| Approve one bill and reject one with reason | 5 owners | 5/5, zero wrong-bill approvals |
| Find invoice 101 and see why it is 101-1 | 5 owners | 5/5 locate history sheet ≤ 3 taps |
| Request 3 days of leave | 5 employees | 5/5, no date errors |
| Find last T4 slip and share it | 5 employees | 5/5 ≤ 30 s |

Accessibility checks: VoiceOver (iOS) and TalkBack (Android) scripted walkthrough of every screen; font scale 200 % screenshots; contrast audit of tokens; reduce motion; switch control smoke test; `eslint-plugin-react-native-a11y` in CI; automated `accessibilityLabel` presence test on all touchables.

---

## 4. TOOLS & TECHNOLOGY FOR THIS PHASE

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| Framework | React Native via **Expo** (managed workflow, current stable SDK, pinned) | iOS + Android from one TypeScript codebase | Plan §5.1; config plugins instead of ejecting |
| Language | TypeScript (strict) | Type safety shared with web client types | `tsc --noEmit` in CI |
| Routing | **Expo Router** (file-based) + React Navigation under the hood | Tabs, stacks, modals, deep links, universal links | Typed routes |
| API client | Generated client from the W-01 **OpenAPI 3** spec (`openapi-typescript` + `openapi-fetch`, or `orval`) | One source of truth for request/response types | Regenerated in CI; contract drift fails build |
| Server state | **TanStack Query (React Query)** + `@tanstack/query-async-storage-persister` / `persistQueryClient` | Caching, background refresh, offline read cache | Persist to MMKV |
| Local storage | **react-native-mmkv** (encrypted instance) | Fast encrypted cache, offline queue | Encryption key in secure store |
| Secrets | **expo-secure-store** (Keychain / Android Keystore) | Refresh token, MMKV key, device id | `requireAuthentication` for refresh token where supported |
| Biometrics | **expo-local-authentication** | Face ID / Touch ID / fingerprint unlock | `NSFaceIDUsageDescription` EN/FR |
| Auth | **expo-auth-session** (OAuth2 Authorization Code + PKCE) / `expo-web-browser` | Login against W-01 OAuth; SSO handoff to web for payments | Refresh-token rotation |
| Client state | **Zustand** | Active org, role, UI preferences | Small, no boilerplate |
| Forms | **react-hook-form** + **zod** | Invoice, spend money, leave, expense forms | zod schemas generated/aligned with OpenAPI |
| Money & dates | `dinero.js` (or integer-cents utilities) + `Intl.NumberFormat`; `date-fns` + `date-fns-tz` | Never float money; locale formatting; org time zone | Server remains source of truth for totals |
| i18n | **i18next** + `react-i18next` + `i18next-icu` sharing X-01 ICU catalogues; `expo-localization` | en-CA / fr-CA | Missing-key gate in CI |
| UI kit | In-house `@numo9/mobile-ui` built on A-10 tokens; **react-native-reanimated**, **react-native-gesture-handler**, `@gorhom/bottom-sheet`, **@shopify/flash-list** | Components, sheets, swipe actions, fast lists | Tokens generated by **Style Dictionary** from the A-10 token JSON |
| Icons & fonts | `react-native-svg` + Numo9 icon set (SVG), `expo-font` | Brand icons, Inter / brand font | Original icons only |
| Charts | **victory-native** (Skia) or `react-native-gifted-charts` | Cash in/out, sparklines, SKU ranks | Accessible summaries for each chart |
| Camera & docs | **expo-camera**, **expo-image-manipulator**, `expo-image-picker`, **expo-document-picker**, `react-native-document-scanner-plugin` (edge detection) | Receipt capture, crop, compress, PDF import | Compress to ≤ 2 MB JPEG, max 25 MB file |
| Files & sharing | `expo-file-system`, `expo-sharing`, `expo-print`, `react-native-pdf` / `react-native-blob-util` | Download/view/share PDFs (invoices, stubs, slips) | PDFs from server (WeasyPrint) |
| Uploads | `expo-file-system` background upload task + resumable session endpoint | Offline-first capture upload | Idempotency key per capture |
| Network status | `@react-native-community/netinfo` | Offline banner, queue flush | — |
| Background tasks | `expo-background-fetch` + `expo-task-manager` | Queue flush, cache refresh | OS-scheduled, best effort |
| Push | **expo-notifications** + Expo Push Service → APNs / FCM; backend `exponent_server_sdk` (Python) | Payment received, approvals, tax due, stub ready | Credentials under client accounts |
| Deep links | Expo Router linking, iOS Associated Domains (`apple-app-site-association`), Android App Links (`assetlinks.json`) | Email/push links into the app | Files served by Q-04 domain |
| Clipboard / haptics | `expo-clipboard`, `expo-haptics` | Copy pay link, confirmation feedback | — |
| Secure UI | `expo-screen-capture` (prevent screenshots on SIN/bank screens), app-switcher blur (`AppState` + overlay) | Privacy | — |
| OTA updates | **EAS Update** (channels: dev, preview, production; runtime-version policy) | Hotfix JS without store review (policy-compliant) | Never changes native permissions |
| Builds | **EAS Build** (profiles: development, preview, production; per-flavour if ADR-005 = two apps) | Signed binaries | Credentials managed by EAS, owned by client accounts |
| Store submission | **EAS Submit**; **Fastlane** (`deliver`, `supply`, `snapshot`/`screengrab` for screenshots) | App Store Connect / Play Console upload, metadata EN/FR | Metadata in repo (`mobile/store/`) |
| Beta distribution | **TestFlight**, Google Play **internal testing** track, EAS internal distribution | UAT builds | From week 11 |
| Crash & performance | **Sentry React Native** (`@sentry/react-native` + EAS source maps upload), Firebase Crashlytics optional | Crash-free ≥ 99 %, release health | PII scrubbing rules |
| Product analytics | PostHog (self-hosted, Canadian region) or Sentry release health only | Funnels (capture → bill) without PII | Opt-in per privacy policy |
| Remote config | U-06 feature flags via `/api/v1/mobile/config` | Kill-switches, minimum supported version | Forced-update screen |
| Unit/component tests | **Jest** (`jest-expo`), **React Native Testing Library**, `@testing-library/jest-native` | Components, hooks, reducers, formatters | Plan §6.1 "Jest (mobile)" |
| API mocking | **MSW** (`msw/native`) | Deterministic tests, offline simulations, 402/409/500 | Shared handlers with web |
| E2E tests | **Detox** (Plan §6.1), **Maestro** (fast smoke flows on real devices/cloud) | Owner and employee flows, tenant sweep | Run on iOS simulator + Android emulator in CI |
| Device cloud | BrowserStack App Automate / AWS Device Farm | Real-device matrix (camera, biometrics stubs) | Paid by client if used |
| Visual regression | Storybook React Native + **Loki** / Chromatic for RN Web stories | Component snapshots EN/FR, 100 %/200 % font | — |
| Accessibility | `eslint-plugin-react-native-a11y`, Xcode Accessibility Inspector, Android Accessibility Scanner | Labels, contrast, target sizes | — |
| Performance | Flashlight (Android perf score), React Native Perf Monitor, `react-native-performance`, Hermes profiler | Cold start, FPS, memory | Budgets in §8 |
| Quality | ESLint (`eslint-config-expo`), Prettier, `tsc`, **Knip** (dead code), `depcheck`, Husky + lint-staged, commitlint | Code hygiene | Pre-commit |
| Security | `npm audit` / `pnpm audit`, **gitleaks**, **Semgrep** (RN rules), **MobSF** static scan of APK/IPA, OWASP MASVS checklist | Mobile security baseline | No high findings (S-03) |
| Dependency updates | Renovate (grouped Expo SDK upgrades) | Controlled upgrades | Warranty: store-compliance updates |
| Design | **Figma** (mobile frames, iOS 17/18 + Material 3 kits as reference only, Numo9 components), FigJam flows, Figma prototype for usability tests | Wireframes, hi-fi, handoff | Original design |
| Store assets | Figma screenshot templates, `fastlane frameit`, App Store / Play preview video (optional) | EN/FR listing screenshots (6.7", 6.5", 5.5", iPad optional; Android phone/7"/10") | — |
| Privacy compliance | iOS **Privacy Manifest** (`PrivacyInfo.xcprivacy` via config plugin), App Store **App Privacy** nutrition labels, Google Play **Data safety** form, account-deletion link | Store approval | Y-04 checklist |
| Backend (mobile support) | Django REST: `fcm/expo` push service module, `django-oauth-toolkit` (W-01), `drf-spectacular` | Device registration, push tokens, sync cursor, upload sessions | Small additions only |
| Dev productivity | Expo Dev Client, Expo Go (early spikes only), Flipper alternatives (React Native DevTools, Reactotron), `ngrok`/Expo tunnel to staging, Mailpit for invitation emails | Local dev against staging | — |
| CI | GitHub Actions: lint → typecheck → Jest → build dev client → Detox (macOS runner for iOS, Linux + emulator for Android) → EAS preview build on PR label | Gate per PR | macOS minutes cost owner: GMA within budget |
| Docs | MkDocs page `docs/mobile/` (architecture, release runbook, store checklist), **ADR-005** (one vs two apps), **ADR-006** (offline policy), **ADR-007** (OTA update policy) | Handover | T-04 documentation |
| Internal tools to BUILD | `mobile/scripts/seed-review-account` (creates/refreshes App Review demo org via U-07), `mobile/scripts/check-i18n` (missing keys + length +30 %), `mobile/scripts/gen-tokens` (Style Dictionary), `mobile/e2e/tenant-sweep.e2e.ts` (cross-org sweep through the app's API client), `make mobile-release` wrapper, Detox fixture loader `POST /api/v1/test/fixtures` (staging-only), push test console in U-06 ("send test push to device") | Repeatable QA and release | Staging-only endpoints disabled in production |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 objective

Native iOS and Android Numo9 apps for organisation owners and employees, sharing the W-01 API and auth, with biometric unlock, secure tokens, push and an offline capture queue, published in both stores under the client's accounts with EN/FR listings and crash reporting.

### 5.2 Level 2 components

| Component | Deliverables | Purpose |
|---|---|---|
| Mobile platform | Y-01 | Project, design system, auth, org switching, API client, cache, offline queue, push, deep links, i18n, telemetry, CI, mobile-support endpoints, tenant sweep |
| Owner experience | Y-02 | Home/Needs-you, banking, invoices incl. revisions and pay links, bill approvals, capture → E-05, tax-payment status, subscription status, loans [v2.1], SKU analytics [v2.1], notifications, search, settings |
| Employee experience | Y-03 | Employee home, pay stubs, T4/T4A slips, leave, expense claims with camera and mileage, timesheets/timer, profile |
| Release & maintenance | Y-04 | Store accounts and identifiers, signing, listings EN/FR, privacy declarations, review account, beta tracks, release pipeline, OTA policy, crash reporting dashboards, hypercare readiness |

### 5.3 Dependency graph and execution order

```
W-01 API + A-02 auth + Phases 1–4 features (done)
          │
          ▼
        Y-01 Mobile foundation ──────────────┬──────────────────────┐
          │                                  │                      │
          ▼                                  ▼                      ▼
        Y-02 Owner app                    Y-03 Employee app      Y-04 (store accounts, IDs,
          │   (screen groups in parallel)    │                     signing, listing drafts —
          └──────────────┬───────────────────┘                     starts day 1 in parallel)
                         ▼
                 Y-04 release (beta → review → publish)
                         ▼
                 Hypercare week 13 (T-05)
```

Execution order:

1. **Y-04-T01…T06** (accounts, bundle IDs, signing, push credentials) — start day 1, in parallel with Y-01 (external lead times).
2. **Y-01** foundation (T01→T34) — sequential core (project → tokens → API client → auth → org → cache → queue → push → telemetry → CI → sweep).
3. **Y-02** and **Y-03** in parallel once Y-01-T20 (authenticated shell + org switch) is merged: owner screen groups (Home → Banking → Invoices → Approvals → Capture → Taxes/Subscription → Loans/SKU → Notifications/Search/Settings) and employee groups (Home → Pay → Slips → Leave → Expenses → Time → Profile).
4. **Y-04** beta tracks from week 11 (TestFlight/internal) → UAT → store review submission week 12 → publish → hypercare week 13.

Week plan: **Week 10** — Y-01 complete, Y-02 Home/Banking/Invoices start, Y-03 Home/Pay start, Y-04 accounts/signing. **Week 11** — Y-02 approvals/capture/taxes/loans/SKU, Y-03 leave/expenses/time, first TestFlight/internal builds, UAT round 1. **Week 12** — polish, a11y, FR review, Detox full suite green, store submission, publish. **Week 13** — hypercare.

---

## 6. PLAN — Deliverable cards with ATOMIC TASKS (Rule 3)

### Y-01 · Mobile foundation

- **Branch:** `feature/Y-01-mobile-foundation` (sub-branches allowed: `feature/Y-01-auth`, `feature/Y-01-offline-queue`, `feature/Y-01-push`)
- **Objective:** a production-grade React Native (Expo) shell that authenticates against W-01, stores tokens securely, unlocks with biometrics, switches organisations, caches data, queues offline captures, receives push, opens deep links, speaks EN/FR and passes the tenant-isolation sweep through the mobile client.
- **Current behaviour:** `mobile/` workspace empty; no mobile auth flow; push channel absent in A-07; no device records.
- **Expected behaviour (better than Xero):** one app for every role; login → dashboard on both platforms; biometric unlock; org switch with explicit confirmation on cross-org deep links; all requests scoped and audited with `channel=mobile`; offline read cache + safe write queue; amount-free lock-screen push by default.
- **Gap #s closed:** 1, 5, 14, 41, 42, 43, 61 (foundations for mobile).
- **Business rules:** tokens never in plain AsyncStorage; refresh token rotation and revocation from web session list (A-02); biometric unlock only after one successful full login on that device; re-auth after configurable background timeout; logout and remote revocation purge cache + queue (after warning about unsent items); minimum app version enforced by remote config; every write carries `Idempotency-Key`; 402 → gated UI; 404 cross-org → "Not found in this organisation" (never shows data).
- **Edge cases:** clock skew vs TOTP; device without biometrics; biometric set changed (new fingerprint) → require password; token refresh race on parallel requests; app killed mid-upload; org removed while app in background (next request 404 → org list refresh); user belongs to 0 orgs (employee invited but not yet onboarded); demo org watermark; trial expired → read-only banner.
- **UI/UX notes:** splash → welcome; skeleton loaders; offline banner with queue count; org switcher sheet; gated card component; error boundary screen with "Try again" and ref code; forced-update screen.
- **Dependencies:** W-01, A-02, A-03, A-04, A-07, U-03, U-06, X-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| Y-01-T01 | Restate objective, confirm ADR-005 (one vs two apps), ADR-006 (offline policy: queue captures/drafts only), ADR-007 (OTA policy); record in `docs/adr/` | DOC | — | Three ADRs merged and approved by project lead | Review |
| Y-01-T02 | Initialise Expo project in `mobile/` (TypeScript strict, Expo Router, Hermes, pnpm workspace), app.config.ts with env-based bundle IDs (`ca.numo9.app`, `.dev`, `.preview`) | OPS | T01 | `pnpm --filter mobile start` runs on iOS sim + Android emulator showing placeholder screen | Manual run |
| Y-01-T03 | Tooling: ESLint (expo + a11y plugin), Prettier, tsc, Knip, Husky/lint-staged, commitlint; Jest (`jest-expo`) + RNTL configured with one sample test | OPS | T02 | `pnpm mobile:lint`, `mobile:typecheck`, `mobile:test` all pass in CI | CI |
| Y-01-T04 | Design tokens pipeline: Style Dictionary reads A-10 token JSON → generates `mobile/src/theme/tokens.ts` (colour, type scale, spacing, radius, elevation) incl. dark mode tokens | FE | T02 | Generated file committed; changing a web token regenerates mobile token in CI check | Unit snapshot |
| Y-01-T05 | Theme provider + typography components (`Text` variants mapping to Dynamic Type / font scale with max multiplier 2.0, reflow-safe) | FE | T04 | Text renders at 100/150/200 % without truncation in Storybook | Visual regression |
| Y-01-T06 | Core components batch 1: Button (primary/secondary/destructive, loading, disabled-with-reason), IconButton, Card, ListRow, StatusChip (text+icon), AmountText (locale, sign, accessible label) | FE | T05 | Storybook stories EN/FR; touch targets ≥ 44pt/48dp; a11y labels present | RNTL + Loki |
| Y-01-T07 | Core components batch 2: TextField, AmountKeypad field, DateChips + DatePicker, Picker sheet (searchable), Switch, SegmentedFilter, SearchField | FE | T06 | Inputs pass keyboard/IME tests; fr-CA decimal comma accepted | RNTL |
| Y-01-T08 | Feedback components: Skeleton, EmptyState, ErrorState (retry + ref code), OfflineBanner (queue count), Snackbar with Undo, ConfirmSheet (bottom sheet with summary), GatedCard (product name + web link) | FE | T06 | Each state shown in Storybook; GatedCard text from i18n | RNTL |
| Y-01-T09 | Storybook React Native setup + Loki visual snapshots in CI (iOS/Android, EN/FR, 100 %/200 %) | QA | T06 | CI fails on unintended visual diff | Visual regression |
| Y-01-T10 | i18n: i18next + ICU plugin loading shared X-01 catalogues (`packages/i18n/en-CA`, `fr-CA`), language follows user profile then device; `check-i18n` script (missing keys, +30 % length warnings) | FE | T02 | Switching language re-renders app; missing key fails CI | Unit + CI |
| Y-01-T11 | Formatting utils: money (integer cents → locale string), dates in org time zone, relative dates, percent; accessible spoken money string | FE | T10 | `1017.00` → "$1,017.00" / "1 017,00 $"; unit tests incl. negatives and zero ("$0.00", never "—") | Jest |
| Y-01-T12 | Generated API client from W-01 OpenAPI (`openapi-typescript` + fetch wrapper): base URL per env, auth header, `X-Organisation-Id`, `Idempotency-Key` on writes, `X-Client: numo9-mobile/<version>` | FE | T02 | Typed call to `/api/v1/me` compiles; CI regenerates and fails on drift | Jest + CI |
| Y-01-T13 | Error mapping layer: 400 field errors → form errors, 401 → refresh/logout, 402 → `GatedError(product)`, 403 → `PermissionError(reason)`, 404 → `NotFound`, 409 → `Conflict(latest)`, 429 → backoff, 5xx → retryable | FE | T12 | MSW tests for each status produce the right typed error | Jest + MSW |
| Y-01-T14 | Backend: mobile device model `MobileDevice` (user, org-agnostic, platform, model, app_version, push_token, last_seen, revoked_at) + endpoints `POST/DELETE /api/v1/mobile/devices` | BE/API | — | Device registers and appears in A-02 session list as "iPhone 15 · Numo9 1.0.0" | pytest |
| Y-01-T15 | Backend: `GET /api/v1/mobile/config` (min supported version, feature flags from U-06, support URLs) | BE/API | T14 | Returns flags per org; min version change reflected without deploy | pytest |
| Y-01-T16 | OAuth2 PKCE login with expo-auth-session against W-01 (`django-oauth-toolkit`), email/password native screen posting to token endpoint, unverified-user and locked-account errors | FE | T12, T13 | Login works on both platforms; unverified user sees "Verify your email" with resend | Detox |
| Y-01-T17 | TOTP 2FA screen with one-time-code autofill, rate-limit message | FE | T16 | Wrong code shows remaining attempts; correct code continues | Detox + MSW |
| Y-01-T18 | Secure token storage (expo-secure-store), refresh-token rotation with single-flight refresh lock, logout clears secure store | FE | T16 | 10 parallel requests with expired access token trigger exactly one refresh | Jest |
| Y-01-T19 | Biometric enrolment prompt + unlock (expo-local-authentication), PIN/password fallback, background timeout setting (1/5/15 min), invalidate on biometric set change | FE | T18 | Unlock in ≤ 2 s; timeout respected; new fingerprint forces password | Device test + Jest |
| Y-01-T20 | Authenticated shell: role-aware root layout (owner tabs / employee tabs / role switcher), header with org avatar, search, bell | FE | T19 | Owner sees 5 tabs, employee 4 tabs, dual-role user sees switcher | Detox |
| Y-01-T21 | Org switcher sheet: list user's orgs (`/api/v1/me/organisations`) with role, trial/demo/founding labels, search when > 7; persist last org; query cache keyed by org id (no cross-org cache reuse) | FE | T20 | Switching org clears visible data and loads the new org; cache keys include org id | Detox + Jest |
| Y-01-T22 | Query layer: TanStack Query with MMKV encrypted persister (key from secure store), stale times per resource, "last updated" timestamp, purge on logout/org removal | FE | T21 | Kill app offline → reopen shows cached Home with "Updated 10:42" | Detox (airplane mode) |
| Y-01-T23 | Offline write queue: MMKV-backed queue of typed jobs (capture upload, expense draft, leave draft, timesheet entry, invoice draft) with idempotency key, retry with exponential backoff, per-item status, flush on NetInfo reconnect and background fetch | FE | T22 | Create 3 captures offline → reconnect → 3 uploads, 0 duplicates server-side | Jest + Detox |
| Y-01-T24 | Upload queue screen (list, retry, delete pending with confirm) | FE | T23, T08 | Failed item shows reason and retries on tap | RNTL |
| Y-01-T25 | Online-only action guard hook `useOnlineAction()` → disables ledger-affecting buttons offline with explanation | FE | T22 | Approve button shows "Needs connection" in airplane mode | RNTL |
| Y-01-T26 | Backend: push channel in A-07 notification service — `PushChannel` sending via Expo Push API (`exponent_server_sdk`), receipts check job (A-08), invalid-token cleanup, per-user per-type preferences, lock-screen privacy (amount-free default) | BE | T14 | Test push from U-06 console reaches device; invalid token marked revoked | pytest + device |
| Y-01-T27 | Client push: permission prompt at a meaningful moment (after first approval or capture, not at launch), token registration, foreground handling, tap → deep link | FE | T26, T28 | Tap "Bill awaiting approval" opens bill detail | Device test |
| Y-01-T28 | Deep links & universal links: `numo9://` scheme + Associated Domains / App Links (files hosted by Q-04), router mapping, cross-org link → "Switch to Org X?" confirmation | FE/OPS | T21 | Email link opens the right record; cross-org link asks before switching | Detox |
| Y-01-T29 | Privacy: app-switcher blur overlay, Privacy mode toggle (mask amounts, long-press reveal), `expo-screen-capture` block on sensitive screens | FE | T20 | App switcher shows blurred view; masked amounts read "hidden" by VoiceOver | Device test |
| Y-01-T30 | Telemetry: Sentry RN (errors, performance, release health), EAS source-map upload, PII scrubbing (amounts, names, emails, SIN patterns), user id hashed | OPS | T02 | Test crash appears in Sentry with symbolicated stack and no PII | Manual + scrub unit test |
| Y-01-T31 | Remote config + forced update screen + feature kill-switch HOC `withFeature(flag)` | FE | T15 | Raising min version shows forced-update screen linking to store | Jest |
| Y-01-T32 | Global error boundary + gated/permission/not-found screens; 402 renders GatedCard with product from response | FE | T13, T08 | Requesting a gated endpoint shows "Included in Payroll" card, never redirects | Detox + MSW |
| Y-01-T33 | Audit attribution: backend middleware records `channel=mobile`, device id, app version on A-04 entries for requests with `X-Client` mobile | BE | T14 | Audit log shows "via Numo9 iOS 1.0.0" on a mobile edit | pytest |
| Y-01-T34 | Owner/employee dashboard minimal (Home placeholder with bank balances call) to satisfy foundation acceptance | FE | T22 | Login → org switch → dashboard shows balances on both platforms | Detox |
| Y-01-T35 | Detox setup (iOS sim + Android emulator), staging-only fixture loader endpoint `POST /api/v1/test/fixtures` (disabled in prod by setting + IP allowlist), MSW for unit layer | QA | T16 | `pnpm mobile:e2e` runs login scenario green on both | CI |
| Y-01-T36 | Mobile tenant-isolation sweep: e2e script using the app's API client with user from Org 1 requesting every Org 2 resource id the app uses (invoices, bills, stubs, slips, documents, loans, items) → all 404; removed practice member → 404 | QA/SEC | T35 | Sweep report 100 % 404, attached to PR | Detox/Jest sweep |
| Y-01-T37 | Entitlement leak test from mobile: org without Payroll hitting payroll endpoints → 402 and GatedCard; downgrade mid-session removes write buttons | QA/SEC | T32 | Leak test green | Jest + MSW + staging |
| Y-01-T38 | CI pipeline: GitHub Actions (lint, typecheck, Jest, i18n check, Detox iOS on macOS runner, Detox Android on Linux emulator, EAS preview build on label), cache config | OPS | T35 | PR shows all checks; failing Detox blocks merge | CI |
| Y-01-T39 | Security baseline: MASVS L1 checklist, Semgrep RN rules, gitleaks, `pnpm audit`, MobSF scan of preview APK, certificate pinning decision (pin to staging/prod CA via config plugin) | SEC | T38 | No high findings; checklist committed | Security scan |
| Y-01-T40 | Foundation docs: `docs/mobile/architecture.md` (layers, cache, queue, auth), developer setup guide | DOC | T38 | New engineer runs app in ≤ 30 min following guide | Peer review |

- **Deliverable acceptance:** login, org switch, dashboard on both platforms; tenant sweep through mobile client passes; biometric unlock works; push received; offline queue loses nothing (Project_Phases.md Y-01 + added).
- **Testing approach:** unit (formatters, refresh lock, queue), integration (MSW + staging API), functional (Detox login→dashboard), security (sweep, entitlement leak, MASVS, MobSF), regression (full Detox suite per PR).
- **Risks & mitigations:** Expo SDK native limitation → config plugins / dev client; refresh-token race → single-flight lock tested; push credential delays → Y-04-T05 day 1; MMKV key loss on restore to new device → treat as fresh login.

### Y-02 · Organisation-owner app

- **Branch:** `feature/Y-02-owner-app` (sub-branches: `feature/Y-02-home`, `-banking`, `-invoices`, `-approvals`, `-capture`, `-taxes-subscription`, `-loans-sku`, `-notifications-search-settings`)
- **Objective:** give the organisation owner (and limited org roles) a fast mobile workspace for cash, invoices incl. revisions and pay links, bill approvals, spend/receive money, receipt capture to E-05, tax-payment status, subscription status, loan status and SKU analytics [v2.1], notifications.
- **Current behaviour:** all of this is web-only.
- **Expected behaviour (better than Xero):** one app; Needs-you inbox; revision-aware invoices (edit a sent invoice → 101-1 with history and diff); approvals that show the user's limit; capture with per-field confidence; spend money from any never-locked account with negative-balance control; explicit gating; Canadian terms; amounts accessible.
- **Gap #s closed (mobile surface):** 4, 5, 6, 14, 32, 41, 51, 52, 61; client decisions #5 and #6.
- **Business rules:** server computes totals/tax/revision numbers — client shows previews only; revision of a filed-period invoice shows the late-adjustment message from the API; approval limits from A-03; approver ≠ creator; spend money obeys F-07 (warn/block); tax payment initiation is web-confirmed; subscription not purchasable in app; inventory/loan screens require Inventory/Finance product.
- **Edge cases:** invoice revised on web while open on mobile → 409 on save with reload; superseded revision opened from an old push → shows banner "Superseded by 101-2" with link; paid invoice edit → API rules (payments stay allocated, over-allocation becomes credit) displayed in confirm sheet; bill already approved by another user; multi-page receipt; PDF import from share sheet; foreign-currency invoice (R-02) display with currency code; zero bank accounts (set-up prompt on web); petty cash negative.
- **UI/UX notes:** see §3.3/§3.4; sticky bottom action bars; confirm sheets for ledger actions; revision badge `Revised · 101-1`; per-card error states on Home.
- **Dependencies:** Y-01; D-03a, D-03b, D-05, D-09, P-02, E-01, E-02, E-05, F-01, F-07, G-09, U-04, U-05, U-08, FN-01…FN-05, H-09…H-13, A-07, A-09.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| Y-02-T01 | Figma: owner wireframes for all §3.3 owner screens (iOS + Android variants), FigJam flows for §3.4 flows 1–7 | UX | — | Wireframes reviewed by project lead | Design review |
| Y-02-T02 | Figma: hi-fi owner screens EN + FR with 200 % font variants; prototype for usability test | UX | T01 | Prototype clickable; FR layouts hold | Usability pilot (2 users) |
| Y-02-T03 | Backend: `GET /api/v1/mobile/home` aggregate (bank balances, money in/out 6 months, owed/to pay, tax due, loans summary, SKU highlights, needs-you count) respecting entitlements per section | BE/API | Y-01 | Figures equal K-05 dashboard totals on fixture org | pytest tie-out |
| Y-02-T04 | Backend: `GET /api/v1/mobile/needs-you` prioritised list (bills within user's limit, revised invoices, tax due ≤ 7 days, low-confidence captures, expense claims to approve) | BE/API | T03 | List ordering deterministic; only items user may act on | pytest |
| Y-02-T05 | Home screen: cards (Bank balances first, Needs-you preview, Money in/out chart, Invoices owed / Bills to pay, Tax due countdown), each with skeleton/error/retry, pull-to-refresh, cached timestamp | FE | T03 | Empty org shows $0.00 values and no "—k"; one card failing doesn't break others | Detox + MSW (gap-04, gap-05) |
| Y-02-T06 | Money in/out chart with accessible summary text and tap-to-detail | FE | T05 | VoiceOver reads "October: in $12,400.00, out $9,100.00" | RNTL |
| Y-02-T07 | Needs-you full screen with grouped list and swipe actions (approve → confirm sheet; snooze 1 day) | FE | T04, T05 | Swipe approve opens confirm, never approves directly | Detox |
| Y-02-T08 | Bank accounts screen: all ledger bank/cash/credit-card/LOC accounts with balances, negative badge, "no bank account" set-up prompt linking to web | FE | Y-01 | Petty Cash −994.17 shows negative badge and explanation | Detox fixture |
| Y-02-T09 | Bank account transactions list (FlashList, filters: date range, money in/out, unreconciled), detail view | FE | T08 | 5,000 lines scroll at 60 fps on mid-range Android | Flashlight perf |
| Y-02-T10 | Spend / Receive money form: amount keypad, contact picker, bank account picker, account picker filtered to expense/revenue, tax code defaulted by G-02 and effective on date, attachment strip | FE | T08 | Sales/purchase codes filtered correctly; expired rates not offered | RNTL + MSW |
| Y-02-T11 | Spend money submit: online-only, confirm sheet, F-07 negative-balance handling (warning with reason for advisers / block message for others), idempotency | FE | T10 | Teardown scenario: −994.17 caught at entry; double tap creates one transaction | Detox (gap-27) |
| Y-02-T12 | Invoices list: segmented filters (All, Draft, Awaiting payment, Overdue, Paid, Revised), search, revision badge, amounts with currency code when foreign, infinite scroll, offline cache | FE | Y-01 | Tile counts match web list counts on fixture | Detox (gap-06) |
| Y-02-T13 | Invoice detail: current revision header ("Invoice 101-1"), status chip, contact, lines, tax breakdown, totals, payments, activity timeline, sticky action bar (Send, Share pay link, Edit, More) per permissions | FE | T12 | Revised invoice shows 101-1 and "Revised" badge | Detox |
| Y-02-T14 | Revision history sheet with diff rows (old/new qty, price, tax, total) from A-04 diffs; tap a superseded revision opens read-only view with "Superseded" banner | FE | T13 | 101 viewable and marked superseded | Detox |
| Y-02-T15 | Superseded-link handling: opening an old revision id (push/email) redirects visibly to current with banner "Updated to 101-2" | FE | T14 | Old link → current with banner, never stale data | Detox |
| Y-02-T16 | Invoice create: contact picker with create-new (name, email, province), line editor sheet (item search, qty, price, discount), tax preview from G-02 rules via `POST /api/v1/invoices/preview`, due date chips from terms, save draft (offline-capable via queue) | FE | T12, Y-01-T23 | Ontario customer → HST 13 % shown; offline draft syncs once online | Detox + MSW |
| Y-02-T17 | Invoice approve & send: confirm sheet (total, contact email, language), online-only, push/email result | FE | T16 | Approve posts balanced JE (server) and status becomes Awaiting payment | Detox staging |
| Y-02-T18 | Invoice edit → revision: edit form pre-filled from current revision, required reason, confirm sheet explaining revision and payment re-allocation, filed-period late-adjustment message, 409 conflict reload | FE | T13, T16 | Edit 1,130.00 → 1,017.00 shows 101-1, AR −113.00 on web, tax 1,017.00 | Detox staging (exit demo) |
| Y-02-T19 | Invoice PDF viewer (current revision PDF with stamp), download for offline, share | FE | T13 | PDF shows revision stamp; works offline after download | Device test |
| Y-02-T20 | Pay link: share sheet with copy/QR; link resolves to current revision (P-02); "Stripe not connected" state | FE | T13 | Sharing link from 101 after revision opens 101-1 payment page | Detox staging |
| Y-02-T21 | Send reminder action (D-07) with preview; hidden for paid/disputed | FE | T13 | Paid invoice has no reminder action | RNTL |
| Y-02-T22 | Quotes read-only list/detail with status (Draft/Sent/Accepted/Declined/Expired consistent with web) | FE | T12 | Expired status shown identically to web | RNTL (gap-05) |
| Y-02-T23 | Customer lookup: search, contact card (balance owing, overdue, statement PDF share) | FE | Y-01 | Balance equals AR aging for contact | Detox fixture |
| Y-02-T24 | Approvals list: bills awaiting approval with supplier, amount, due date, limit indicator, duplicate flag, PO match status | FE | Y-01 | Over-limit bills show disabled approve with reason | Detox |
| Y-02-T25 | Bill detail: attachment viewer (image/PDF zoom), lines, tax, PO/GRN match summary, history | FE | T24 | Attachment opens in ≤ 1.5 s on 4G | Device test |
| Y-02-T26 | Approve / reject sheet with reason templates, approver ≠ creator, $5,000 limit enforcement message, 409 already-decided handling | FE | T25 | $5,000-limit user cannot approve $5,001.00 bill; creator cannot approve own | Detox staging (A-03) |
| Y-02-T27 | Expense-claim approvals (for roles with permission) — list, detail with receipt, approve/reject | FE | T24 | Submitter cannot approve own claim | Detox |
| Y-02-T28 | Capture tab hub: Photo, Import PDF/image, Spend money, Receive money | FE | Y-01 | Hub reachable in 1 tap from any tab | RNTL |
| Y-02-T29 | Camera capture screen: expo-camera with edge detection overlay, auto-crop, flash, multi-page, volume-button shutter, permission-denied state | FE | T28 | Receipt captured and cropped; denied permission shows settings link | Device test |
| Y-02-T30 | Image processing: rotate/crop adjust, compress to ≤ 2 MB JPEG, perceptual hash, duplicate-on-device check (90 days) | FE | T29 | 12 MP photo → ≤ 2 MB; same receipt twice warns | Jest + device |
| Y-02-T31 | Share-sheet / Files import (iOS share extension via config plugin, Android intent filter) for PDFs and images | FE | T28 | Sharing a PDF from email into Numo9 queues upload to active org | Device test |
| Y-02-T32 | Backend: resumable upload session `POST /api/v1/documents/upload-sessions` → S3 presigned parts, finalise triggers virus scan + E-05 extraction job | BE/API | Y-01 | 20 MB PDF uploads on flaky network with resume; >25 MB rejected | pytest + integration |
| Y-02-T33 | Upload via offline queue with progress, push "Receipt ready to review" when extraction completes | FE | T30, T32, Y-01-T23 | Airplane-mode capture uploads after reconnect; push arrives | Detox + device |
| Y-02-T34 | Capture review screen: extracted supplier/date/total/tax with confidence chips, low-confidence fields must be confirmed, choose Create bill / Create expense / Attach to existing | FE | T33 | Low-confidence field blocks submit until touched (gap-32) | Detox |
| Y-02-T35 | Tax payments status screen: amounts owing by registration/period (GST/HST, QST, payroll, instalments), due-date countdown, status chips (initiated/submitted/confirmed/failed), confirmation number, "Pay on web" SSO handoff | FE | Y-01 | Paid period shows confirmation number; gated without Tax product | Detox staging |
| Y-02-T36 | Subscription screen: package, products, renewal date, trial days left, grace/read-only state, founding badge, "Manage on web" (no in-app purchase) | FE | Y-01 | Trial org shows days left; founding org shows badge | RNTL + MSW |
| Y-02-T37 | Feature matrix screen ("What's in my package") from U-01 export | FE | T36 | Matrix equals web matrix | RNTL (gap-61) |
| Y-02-T38 | Loans list [v2.1]: loan cards with balance, rate, next payment date/amount, progress bar, YTD interest; gated without Finance | FE | Y-01 | Balance equals FN-03 GL liability on fixture | Detox fixture |
| Y-02-T39 | Loan detail [v2.1]: amortisation schedule list (principal/interest split), past payments, total interest over term | FE | T38 | Schedule rows match web to the cent | Jest tie-out |
| Y-02-T40 | Inventory insights [v2.1]: best-selling SKUs by quantity / revenue / margin toggle, period picker, sparkline, margin % | FE | Y-01 | Ranking equals H-09 report for period | Detox fixture |
| Y-02-T41 | Low-stock & reorder suggestions [v2.1] list with EOQ quantity; "Create PO draft" → API creates draft PO, opens web/mobile confirmation | FE | T40 | Suggestion → PO draft in one action | Detox staging |
| Y-02-T42 | Notifications centre: list, unread, mark read, tap → deep link; notification preferences per type | FE | Y-01-T27 | Each push type opens the right screen | Detox |
| Y-02-T43 | Global search screen using A-09 (journals, accounts, contacts, invoices, bills, settings), grouped results, recents; offline disabled state | FE | Y-01 | Searching a journal narration returns the journal | Detox (gap-52) |
| Y-02-T44 | Settings: language, biometric timeout, privacy mode, notification types, lock-screen amounts toggle, sign out, sign out all devices, account-deletion request flow (store requirement) | FE | Y-01 | Account deletion request creates ticket + email; sign out purges cache | Detox |
| Y-02-T45 | Read-only / grace / demo states across owner screens (banner + disabled writes with reason, demo watermark) | FE | T36 | Read-only org cannot submit any write; banner explains | Detox |
| Y-02-T46 | Limited roles (Sales, Purchasing) tab/action visibility from permission catalogue | FE | Y-01 | Sales clerk sees Sales + Capture only; no approvals tab | Detox matrix |
| Y-02-T47 | i18n pass: all owner strings in catalogue, FR translations filled from glossary, +30 % layout check, FR money/date formats | FE | T05–T46 | 0 missing fr-CA keys for owner screens | CI check |
| Y-02-T48 | Accessibility pass: labels, roles, hints, focus order, 200 % font, contrast, reduce motion on every owner screen | QA | T47 | VoiceOver/TalkBack script passes; 0 a11y lint errors | Manual + lint |
| Y-02-T49 | Detox suite: owner flows (login → home → invoice create → approve → revise → share pay link → capture → review → approve bill → spend money → tax status → loans → SKU) on both platforms | QA | T05–T46 | Suite green on iOS + Android in CI | Detox |
| Y-02-T50 | Sync acceptance test: invoice created on mobile, revised on web via API, mobile shows 101-1 within one sync (pull-to-refresh or push-triggered invalidation) | QA | T18, T42 | Exit criterion observed and recorded | Detox staging |
| Y-02-T51 | Push-triggered cache invalidation: `invoice.revised`, `payment.received`, `bill.approved` push payloads invalidate matching queries | FE | Y-01-T27 | Revision appears without manual refresh when app foregrounds | Detox |
| Y-02-T52 | Performance pass: cold start, Home render from cache, list FPS, image memory on capture | QA | T49 | Budgets in §8 met | Flashlight + profiler |
| Y-02-T53 | Usability test round with 5 owners (UAT testers) on preview build; issues logged and fixed | UX | T49 | Success metrics in §3.6 met | Usability study |
| Y-02-T54 | Owner user guide (EN/FR) section in `docs/mobile/owner-guide.md` with screenshots | DOC | T53 | Guide reviewed | Review |

- **Deliverable acceptance:** an invoice revised on web appears on mobile within one sync (Project_Phases.md Y-02); plus: owner flows above green on both platforms; approval limits enforced; capture → bill with confidence review; tax/loan/SKU figures tie to web.
- **Testing approach:** unit (view models, formatters), integration (MSW + staging tie-outs), functional (Detox owner suite), security (role matrix, sweep), performance (Flashlight), usability (§3.6).
- **Risks & mitigations:** revision staleness → push invalidation + 409 handling; camera device fragmentation → device-cloud matrix; share extension rejection → follow Apple extension guidelines, fallback to in-app picker; aggregate endpoint slow → cache + per-section loading.

### Y-03 · Employee app

- **Branch:** `feature/Y-03-employee-app` (sub-branches: `-home`, `-pay`, `-slips`, `-leave`, `-expenses`, `-time`, `-profile`)
- **Objective:** self-service for employees: pay stubs, T4/T4A slips, leave requests, expense claims with camera and mileage, timesheets with timer.
- **Current behaviour:** M-06 self-service exists on web only.
- **Expected behaviour (better than Xero):** one app (no separate expenses app); offline drafts for leave, claims and time; slips downloadable for offline and shareable; masked sensitive data; employee sees only own records.
- **Gap #s closed:** 31 (Canadian terms: vacation pay, not annual leave), 42, 51.
- **Business rules:** employee scope = own `Employee` record only (M-06); SIN never displayed; bank last 3 digits only; leave accrual and balances from M-03/N-13 server rules; expense claims follow E-04 (CRA per-km rate configurable, submitter cannot approve own); timesheets follow J-02 (approved time immutable); slips visible only once issued; terminated employees keep read access to stubs/slips per policy.
- **Edge cases:** employee in several orgs (switcher); leave overlapping statutory holiday; partial days; leave request spanning year end (balance per year); timer running when app killed/phone restarted; offline expense with receipt then connection after claim period locked; T4 amended (T4 amended slip shown as latest with "Amended"); employee with no payroll yet.
- **UI/UX notes:** 4-tab layout; large clear numbers; next pay date card; leave balance cards; timer card on Home.
- **Dependencies:** Y-01; M-01, M-03, M-06, N-05, N-08, N-13, E-04, J-02.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| Y-03-T01 | Figma: employee wireframes for all employee screens (iOS/Android), flows 8–10 | UX | — | Reviewed by project lead | Design review |
| Y-03-T02 | Figma: hi-fi EN/FR + 200 % variants, prototype | UX | T01 | FR layouts hold | Usability pilot |
| Y-03-T03 | Backend: confirm/extend self-service endpoints under `/api/v1/me/employee/*` (stubs, slips, leave balances/requests, claims, timesheets) scoped to `request.user.employee` per org | BE/API | Y-01 | Endpoint returns only own records; other employee id → 404 | pytest sweep |
| Y-03-T04 | Employee Home: next pay date, latest stub summary (net pay, hidden by privacy mode), leave balances, pending requests, running timer card | FE | T03 | Values match web self-service | Detox fixture |
| Y-03-T05 | Pay stubs list grouped by year with net pay and pay date | FE | T03 | List equals N-05 stubs for employee | Detox |
| Y-03-T06 | Pay stub detail: earnings, taxable benefits, deductions (CPP, CPP2, EI or QPP/QPIP, federal/provincial tax), net, YTD columns, employer contributions info | FE | T05 | Figures equal register lines for employee | Jest tie-out |
| Y-03-T07 | Pay stub PDF download (offline), share, password-protected PDF option | FE | T06 | PDF available offline after download | Device test |
| Y-03-T08 | Slips list (T4, T4A [v2.1]) by tax year, "Amended" label, availability message before issue ("Available by Feb 28") | FE | T03 | Unissued year shows message, not empty error | RNTL |
| Y-03-T09 | Slip detail (box summary) + PDF view/download/share | FE | T08 | Box values equal N-08 slip | Jest tie-out |
| Y-03-T10 | Leave balances screen: by type (vacation, sick, personal, statutory holiday info), accrual explanation, year selector | FE | T03 | Balances equal M-03 accruals | Detox fixture |
| Y-03-T11 | Leave request form: type, date range with partial-day option, working-days calculation preview (excludes weekends and provincial statutory holidays), notes, attachment | FE | T10 | 3-day request shows "Uses 3 of 10 days" | RNTL + MSW |
| Y-03-T12 | Leave request validation: insufficient balance warning, overlapping request, past-dated rules; offline draft via queue | FE | T11, Y-01-T23 | Overlap blocked with message; offline draft submits once online | Detox |
| Y-03-T13 | Leave requests list with status (Pending/Approved/Rejected/Cancelled), cancel pending request with Undo | FE | T12 | Cancel shows Undo snackbar for 5 s | RNTL |
| Y-03-T14 | Expense claims list with status and reimbursement date | FE | T03 | Matches E-04 claims for employee | Detox |
| Y-03-T15 | New expense claim: camera capture (reuses Y-02 capture components), amount, date, category, tax (G-02 default), project (J-01) optional, notes | FE | T14, Y-02-T29 | Claim with photo saves as draft offline | Detox |
| Y-03-T16 | Mileage claim: km entry or from/to with distance, CRA per-km rate from org settings, total preview, purpose | FE | T14 | 120 km × configured rate shows correct total | Jest |
| Y-03-T17 | Multi-receipt claim (several lines in one claim) and submit online with confirm | FE | T15 | Submitted claim appears in owner approvals | Detox staging |
| Y-03-T18 | Rejected claim: reason displayed, edit and resubmit | FE | T17 | Resubmission creates new submission audit entry | Detox |
| Y-03-T19 | Timesheet week view: days, hours per project/task, totals, status (Draft/Submitted/Approved) | FE | T03 | Approved week locked (read-only) | RNTL |
| Y-03-T20 | Timer: start/stop with project/task, persisted across app kill/restart (start timestamp stored), Home card, optional ongoing notification (Android) / Live Activity not in scope | FE | T19 | Kill app with timer running → reopen shows correct elapsed time | Device test |
| Y-03-T21 | Time entry add/edit/delete with offline queue, submit week online | FE | T19, Y-01-T23 | Offline entries sync once, no duplicates | Detox |
| Y-03-T22 | Profile: name, position, department, manager, masked bank (•••123), SIN never shown, TD1 status, emergency contact view; screen-capture blocked | FE | T03 | SIN absent from UI and network logs | Detox + security test |
| Y-03-T23 | Employee notifications: stub ready, slip issued, leave decision, claim decision/reimbursed, timesheet reminder | FE/BE | Y-01-T26 | Each push opens the right screen | Device test |
| Y-03-T24 | Multi-org employee switching and dual-role (owner + employee) switcher integration | FE | Y-01-T20 | Dual-role user switches experiences without re-login | Detox |
| Y-03-T25 | Terminated employee state: read-only access to stubs/slips, no new requests | FE | T04 | Terminated fixture shows banner and disabled requests | Detox |
| Y-03-T26 | Employee isolation sweep through mobile: employee A requests employee B's stub/slip/leave/claim ids → 404 | QA/SEC | T03 | 100 % 404 | Detox/Jest sweep |
| Y-03-T27 | i18n pass employee screens (vacation pay / indemnité de vacances, T4 / T4 — état de la rémunération payée) incl. glossary terms | FE | T04–T25 | 0 missing fr-CA keys | CI |
| Y-03-T28 | Accessibility pass employee screens (VoiceOver/TalkBack, 200 % font, contrast) | QA | T27 | Script passes | Manual + lint |
| Y-03-T29 | Detox suite employee flows (login → home → stub → PDF → slip → leave request → expense with photo → mileage → timer → submit week) both platforms | QA | T04–T25 | Green in CI | Detox |
| Y-03-T30 | Performance pass (stub PDF open ≤ 1.5 s cached, home ≤ 300 ms from cache) | QA | T29 | Budgets met | Profiler |
| Y-03-T31 | Usability round with 5 employees | UX | T29 | §3.6 metrics met | Usability study |
| Y-03-T32 | Employee guide (EN/FR) `docs/mobile/employee-guide.md` | DOC | T31 | Reviewed | Review |

- **Deliverable acceptance:** employee sees only own records (Project_Phases.md Y-03); plus employee Detox suite green; offline drafts sync without duplicates; SIN never exposed.
- **Testing approach:** unit (working-days calc, mileage, timer persistence), integration (stub/slip tie-outs), functional (Detox), security (employee sweep, SIN leak scan of network logs), usability.
- **Risks & mitigations:** provincial holiday calendars → server-provided list, not client logic; timer drift → server time on submit; slip PDF size → cached download.

### Y-04 · Store release & maintenance

- **Branch:** `feature/Y-04-store-release` (release branches `release/mobile-vX.Y.Z`; tags `mobile-vX.Y.Z` per Plan §5.4)
- **Objective:** publish the app(s) on the Apple App Store and Google Play under the client's developer accounts with EN/FR store copy, crash reporting, a repeatable release pipeline and maintenance policy.
- **Current behaviour:** no store presence, no signing credentials, no release process.
- **Expected behaviour:** signed builds from CI; TestFlight/internal-track betas from week 11; store review passed first time where possible; both listings live; release health monitored; OTA hotfix policy; store-compliance updates under warranty.
- **Gap #s closed:** — (delivery); supports 42/43 via bilingual Canadian store copy.
- **Business rules:** accounts owned by the client (GMA as team member); no production submission without project lead authorisation (Plan §5.4); OTA updates may not change native permissions or purpose (store policy); privacy declarations must match actual data collection; account deletion available in-app; no in-app purchase of subscriptions.
- **Edge cases:** Apple D-U-N-S/enrolment delay; review rejection (guideline 2.1 incomplete info, 3.1.1 payments, 5.1.1 privacy/account deletion, 4.2 minimum functionality); Play pre-launch report crashes; target API level deadline; Expo SDK deprecations; expired push certificates/keys.
- **UI/UX notes:** store screenshots show real Canadian demo data, EN and FR sets; app icon tested at all sizes; splash on brand.
- **Dependencies:** Y-01 (builds), Y-02/Y-03 (content), Q-01 (privacy policy, support pages), U-07 (review demo org).

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| Y-04-T01 | Confirm client Apple Developer (organisation) and Google Play Console accounts; GMA invited with Admin/App Manager and Release Manager roles | OPS | — | Access verified in both consoles | Checklist |
| Y-04-T02 | Register bundle id / application id (`ca.numo9.app`; flavour ids if ADR-005 = two apps), App Store Connect app record, Play app entry, default language en-CA + fr-CA localisation | OPS | T01 | Records exist in both consoles | Checklist |
| Y-04-T03 | EAS project + build profiles (development, preview, production; per-flavour if two apps), runtime version policy, channels for EAS Update | OPS | T02, Y-01-T02 | `eas build --profile preview` produces installable iOS + Android builds | Manual install |
| Y-04-T04 | Signing credentials: iOS distribution certificate + provisioning via EAS credentials, Android upload keystore (backed up in client vault), Play App Signing enrolment | OPS/SEC | T03 | Signed production builds verify; keystore backup documented | Checklist |
| Y-04-T05 | Push credentials: APNs auth key (.p8) and FCM v1 service account uploaded to Expo; Associated Domains / App Links entitlements configured | OPS | T02 | Production push to TestFlight build received | Device test |
| Y-04-T06 | App icon (iOS all sizes, Android adaptive + monochrome), splash screen, notification icon from Numo9 brand assets | UX | T02 | Icon passes App Store Connect validation; adaptive icon correct on Pixel/Samsung | Visual check |
| Y-04-T07 | Privacy: iOS Privacy Manifest (`PrivacyInfo.xcprivacy` required-reason APIs), App Privacy nutrition labels, Google Play Data safety form; usage descriptions (camera, photos, Face ID, notifications) EN/FR | OPS/DOC | Y-01-T30 | Declarations match telemetry inventory; reviewed by project lead | Checklist |
| Y-04-T08 | Account deletion compliance: in-app request flow (Y-02-T44) + web URL for Play listing | OPS | Y-02-T44 | Deletion link reachable from listing and app | Checklist |
| Y-04-T09 | App Review demo account: `seed-review-account` script creating/refreshing a demo org (U-07) with owner + employee users, no 2FA for reviewer or documented code, review notes text | OPS | U-07 | Reviewer credentials work on preview build; script idempotent | Script test |
| Y-04-T10 | Store listing copy EN/FR: name, subtitle/short description, full description, keywords, promotional text, what's new; Canadian terms; glossary reviewer sign-off | DOC | T02 | Client approves copy in writing | Client review |
| Y-04-T11 | Screenshots: Fastlane snapshot / Maestro-driven capture on demo data for required device sizes, EN + FR sets, framed with captions | UX/QA | T09, Y-02-T49, Y-03-T29 | Screenshots meet size specs; uploaded via deliver/supply | Validation |
| Y-04-T12 | Store metadata as code in `mobile/store/` (Fastlane `deliver`/`supply` folders) and upload automation | OPS | T10, T11 | `make mobile-metadata` updates both consoles | Dry-run |
| Y-04-T13 | Content rating questionnaires (Play IARC, App Store age rating), category (Finance / Business), pricing free, availability (Canada first; other regions per client) | OPS | T02 | Ratings issued | Checklist |
| Y-04-T14 | Store-review pre-flight checklist (Apple guidelines 2.1, 2.3, 3.1.1/3.1.3 no in-app subscription sales, 4.2, 5.1.1 data/account deletion, 5.1.2; Play policies: permissions, data safety, target API, financial-services declaration) committed to `docs/mobile/store-checklist.md` | DOC/QA | T07–T13 | Every item ticked with evidence | Checklist |
| Y-04-T15 | Beta distribution: TestFlight internal + external group (UAT testers), Play internal testing track; build notes template | OPS | T03–T05 | UAT testers install week 11 build | Tester confirmation |
| Y-04-T16 | Release pipeline: GitHub Actions on tag `mobile-vX.Y.Z` → EAS build production → EAS submit to TestFlight + Play internal; manual promotion gate requiring project lead approval | OPS | T03, T12 | Tag produces store-ready builds without local machine | CI run |
| Y-04-T17 | Versioning policy: semantic version + auto build numbers, changelog generation, Sentry release + source maps per build | OPS | T16 | Sentry shows release with symbolicated crash from beta | Crash test |
| Y-04-T18 | OTA update policy implementation (ADR-007): EAS Update channel per release, staged rollout %, rollback command, no native changes via OTA | OPS | T16 | Hotfix published to 10 % then 100 %; rollback tested | Staging drill |
| Y-04-T19 | Play pre-launch report + Firebase Test Lab / device-cloud run on top 20 Canadian devices; fix blockers | QA | T15 | No crash/ANR in pre-launch report | Device matrix |
| Y-04-T20 | UAT round on beta builds with client testers; defects logged against Y-01…Y-03 task IDs; regression re-run | QA | T15 | UAT sign-off sheet for Y-components signed | UAT |
| Y-04-T21 | French QA of the entire app and store copy with the client glossary reviewer | QA | T20 | Reviewer sign-off; 0 missing keys | Review |
| Y-04-T22 | Submit to App Store review and Play production (staged rollout 20 % → 100 %) after authorisation | OPS | T14, T20, T21 | Both apps approved and published | Store status |
| Y-04-T23 | Rejection playbook: response templates per common guideline, fix-resubmit loop SLA (same day) | DOC | T14 | Playbook in docs | Review |
| Y-04-T24 | Release-health dashboards: Sentry crash-free sessions/users, ANR rate, app start time, adoption by version; alert when crash-free < 99 % | OPS | T17 | Alert fires on synthetic crash spike in staging | Alert test |
| Y-04-T25 | Store ratings & feedback: in-app review prompt (expo-store-review) after positive moments (3rd successful capture), support link | FE | T22 | Prompt appears at most once per 90 days | Jest |
| Y-04-T26 | Maintenance runbook: Expo SDK upgrade procedure, yearly target-API update, certificate/key expiry calendar, push key rotation, store policy watch — feeds warranty (Agreement §12.1) | DOC | T22 | Runbook in `docs/mobile/release-runbook.md` | Review |
| Y-04-T27 | Hypercare readiness: on-call rota for week 13, triage labels, priority definitions, hypercare log template | OPS | T22 | Hypercare log opened at release | Checklist |

- **Deliverable acceptance:** both apps approved and published under client accounts; crash-free ≥ 99 % in hypercare (Project_Phases.md Y-04); release pipeline reproducible from tag.
- **Testing approach:** release dry-runs, device matrix, store pre-flight checklist, crash-report verification, OTA rollback drill.
- **Risks & mitigations:** enrolment delays → request at Phase 5; rejection → pre-flight checklist + playbook + demo account; key loss → client vault backup; policy changes → warranty maintenance runbook.

---

## 7. TEST — phase test plan (Rules 5–6)

| Category | Scope in Phase 7 | Tooling | Target |
|---|---|---|---|
| Unit | Formatters, money/date utils, token refresh lock, offline queue reducer, working-days, mileage, timer persistence, error mapping | Jest (`jest-expo`), RNTL | ≥ 85 % on `mobile/src/core`, `queue`, `auth`, `format` |
| Component / visual | Every design-system component and screen state EN/FR, 100 %/200 % font, light/dark | Storybook RN + Loki | 0 unapproved diffs |
| Integration | API client vs staging W-01 contract; MSW scenarios (401/402/403/404/409/429/5xx); upload sessions; push receipts | MSW, staging API, pytest for backend additions | Each endpoint used by the app: one happy + one failure test |
| Functional (E2E) | Owner suite (Y-02-T49), employee suite (Y-03-T29), login/biometric/org switch (Y-01) on iOS + Android | Detox (CI), Maestro (device smoke) | 100 % scripted scenarios green |
| Regression | Full Jest + Detox on every PR; nightly device-cloud Maestro run on preview build | GitHub Actions, BrowserStack/Device Farm | Zero known regressions at submission |
| Data validation | Mobile figures vs web/report totals: Home vs K-05, invoice AR vs K-03, stubs vs N-05 register, slips vs N-08, loans vs FN-03, SKU vs H-09 | Tie-out tests on fixture org | 0.00 difference |
| Security | Tenant sweep through mobile client (Y-01-T36), employee sweep (Y-03-T26), entitlement leak (Y-01-T37), RBAC matrix incl. approval limits, MASVS L1, MobSF, secrets scan, PII scrubbing, SIN never in UI/logs, screenshot blocking | Custom sweeps, MobSF, Semgrep, gitleaks | No high findings |
| Performance | Cold start ≤ 2.5 s (mid Android), warm ≤ 1 s, Home from cache ≤ 300 ms, list 60 fps, capture to queued ≤ 3 s, memory < 300 MB during capture | Flashlight, Hermes profiler, Xcode Instruments | Budgets met |
| Offline | Airplane-mode scenarios: cached reads, queued captures/drafts, online-only guards, reconnect flush, app kill mid-upload | Detox with network toggling, device tests | 0 lost items, 0 duplicates |
| Localisation | Missing-key gate, +30 % length, FR money/dates, glossary review | `check-i18n`, Loki FR snapshots | 0 missing keys |
| Accessibility | VoiceOver/TalkBack scripts, a11y lint, contrast, 200 % font | Manual + lint + Accessibility Inspector/Scanner | All screens pass |
| Usability | §3.6 tasks | Moderated sessions | Metrics met |
| Gap closure | `gap-01/04/05/06/14/32/41/42/43/51/52/61-mobile` tagged checks | Detox + Jest | All observed |
| Release | Store pre-flight checklist, pre-launch report, beta UAT, OTA rollback drill | Fastlane, EAS, Play Console | Approved first submission target |

**Exit demonstration script (Phase 7)**

1. Install the production build from TestFlight (iOS) and Play internal track (Android) on two physical devices. → App launches to Welcome in ≤ 2.5 s.
2. Sign in as the fixture owner with 2FA; enable biometrics. → Home loads; bank balances first; no "—k", no ads.
3. Switch organisation from the header to a second org. → Data changes; first org data not visible.
4. Run the mobile tenant sweep report (CI artefact) for the build. → 100 % 404 for cross-org ids.
5. Create invoice on mobile for an Ontario customer: 1 line, total CAD 1,130.00 (HST 13 % shown); approve and send. → Status Awaiting payment.
6. On web, edit the invoice to CAD 1,017.00 with reason. → Web shows 101-1.
7. On mobile, pull to refresh (or receive `invoice.revised` push). → Invoice shows **101-1**, "Revised" badge; history sheet shows 101 superseded and diff −113.00; PDF has revision stamp; pay link opens 101-1 payment page.
8. Capture a receipt in airplane mode; re-enable network. → Upload completes once; push "Receipt ready to review"; low-confidence field must be confirmed; bill created.
9. As a $5,000-limit user, open a $5,001.00 bill. → Approve disabled with reason; owner approves successfully.
10. Spend money from Petty Cash driving it negative. → Warning/block per F-07 shown before posting.
11. Open Taxes, Loans [v2.1] and Inventory insights [v2.1]. → Figures equal web reports; gated card shown on an org without Finance.
12. Sign in as employee; open latest pay stub and T4; request 3 days' leave; submit mileage claim with photo; run timer, kill app, reopen. → Only own records; balances updated; timer correct.
13. Employee sweep artefact. → Other employees' records 404.
14. Switch device language to French. → All screens French, `1 017,00 $` formatting.
15. Show both store listings live (EN/FR) and Sentry release-health dashboard. → Both apps published; crash-free tracking active (≥ 99 % target through hypercare).

**Failure handling:** a failing test stops dependent tasks; identify the exact condition; classify code/data/config/assumption; one focused fix; re-run affected tests then the regression suite; never skip or disable a test to pass; if a device-only test cannot run (e.g., device cloud unavailable), record what prevented verification in the task report. Structured debugging and the 30-minute principle apply (Rule 6).

---

## 8. IMPROVE — post-verification review checklist (Rule 8)

- **Correctness:** every acceptance row observed on both platforms; tie-outs 0.00; revision display correct for 101, 101-1, 101-2.
- **Readability/maintainability:** feature folders (`app/(owner)`, `app/(employee)`, `src/features/*`), no business rules duplicated from backend, typed API only, no `any`.
- **Performance budgets:** cold start ≤ 2.5 s mid-range Android / ≤ 1.5 s iPhone 13; JS bundle ≤ 8 MB; Home from cache ≤ 300 ms; lists 60 fps (Flashlight score ≥ 85); capture-to-queued ≤ 3 s; app size ≤ 60 MB download.
- **Reliability:** offline queue durability after kill/reboot; retry/backoff; push receipts cleanup; graceful 5xx.
- **Security:** MASVS L1 items re-checked; tokens only in secure store; MMKV encrypted; PII scrub verified in Sentry; screenshot blocking on sensitive screens; certificate pinning decision documented.
- **Consistency:** status names, revision labels, money/date formats identical to web; design tokens in sync; Canadian terms lint clean.
- **Accessibility:** re-run VoiceOver/TalkBack scripts after fixes; 200 % font sweep.
- **Cleanup:** remove dev-only screens, MSW in production build, test fixture endpoint disabled in production, console logs stripped (babel plugin).
- **Docs:** architecture, guides, runbook, store checklist, ADR-005/006/007 updated with final decisions.

---

## 9. Git branch plan (Rule 7)

| Branch | Base | Deliverable / tasks | Merge order |
|---|---|---|---|
| `feature/Y-04-store-setup` | `main` | Y-04-T01…T08 (accounts, IDs, signing, push creds, icons, privacy) | 1 (parallel with Y-01) |
| `feature/Y-01-mobile-foundation` (+ `-auth`, `-offline-queue`, `-push`) | `main` | Y-01-T01…T40 | 2 |
| `feature/Y-02-home` | `main` after Y-01 | Y-02-T01…T07 | 3 |
| `feature/Y-02-banking` | `main` | Y-02-T08…T11 | 4 |
| `feature/Y-02-invoices` | `main` | Y-02-T12…T23 | 5 |
| `feature/Y-02-approvals` | `main` | Y-02-T24…T27 | 6 |
| `feature/Y-02-capture` | `main` | Y-02-T28…T34 | 7 |
| `feature/Y-02-taxes-subscription` | `main` | Y-02-T35…T37 | 8 |
| `feature/Y-02-loans-sku` | `main` | Y-02-T38…T41 | 9 |
| `feature/Y-02-notifications-search-settings` | `main` | Y-02-T42…T54 | 10 |
| `feature/Y-03-home-pay-slips` | `main` after Y-01 | Y-03-T01…T09 | 3 (parallel) |
| `feature/Y-03-leave` | `main` | Y-03-T10…T13 | 4 (parallel) |
| `feature/Y-03-expenses` | `main` after `Y-02-capture` | Y-03-T14…T18 | 8 |
| `feature/Y-03-time-profile` | `main` | Y-03-T19…T32 | 9 (parallel) |
| `feature/Y-04-store-release` | `main` | Y-04-T09…T27 | 11 |
| `release/mobile-v1.0.0` | `main` | Release stabilisation; tag `mobile-v1.0.0` | 12 |

**Before each branch:** `git status` clean; pull `main`; restate objective + acceptance in the PR description; list atomic task IDs covered; confirm dependencies merged.
**Before declaring a branch complete:** all its tasks' acceptance observed on iOS + Android; CI green (lint, typecheck, Jest, i18n gate, Detox, sweeps); no unrelated changes; no debug code or MSW in production bundle; no secrets (gitleaks); docs updated; final diff reviewed by a second engineer; no merge, store submission or OTA production publish without project lead authorisation.

---

## 10. Phase risks register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Apple/Google account enrolment delay (D-U-N-S, verification) | Medium | High | Request at Phase 5; Y-04-T01 day 1; build/test on dev profiles meanwhile |
| 2 | App Store rejection (payments 3.1.1, account deletion 5.1.1, incomplete demo 2.1) | Medium | High | No in-app subscription sales; in-app deletion; seeded review account; pre-flight checklist; rejection playbook |
| 3 | Mobile shows stale revision / divergent data from web | Medium | High | Server is source of truth; push-triggered invalidation; 409 handling; tie-out tests; Y-02-T50 |
| 4 | Offline duplicates or lost captures | Medium | High | Idempotency keys, durable MMKV queue, reconnect flush tests, app-kill tests |
| 5 | Tenant/employee data leak via cache | Low | Critical | Cache keyed by org + user; purge on logout/org removal; sweeps through mobile client |
| 6 | Lost phone → token theft | Low | High | Secure store + biometric unlock + remote revocation from web session list |
| 7 | Device fragmentation (camera, biometrics, Android OEM background limits) | Medium | Medium | Device-cloud matrix, pre-launch report, graceful fallbacks |
| 8 | Expo SDK / native module incompatibility | Low | Medium | Pinned SDK, config plugins, dev client, Renovate grouped upgrades |
| 9 | French string overflow / Dynamic Type breakage | Medium | Medium | +30 % checks, 200 % snapshots, glossary review |
| 10 | Schedule squeeze (3 weeks for 3 builds + release) | High | High | Y-01 core first; parallel owner/employee tracks; strict scope (no accountant workstation on mobile); OTA for minor post-release fixes |
| 11 | Crash-free below 99 % in hypercare | Medium | Medium | Sentry release health alerts, staged rollout, OTA hotfix, rollback |
| 12 | Push credential/key expiry | Low | Medium | Expiry calendar in runbook; warranty maintenance |
| 13 | Privacy declaration mismatch | Low | High | Telemetry inventory reviewed in Y-04-T07; PII scrubbing tests |

---

## 11. Phase completion checklist (Rule 11) + reporting template (Rule 10)

**UNDERSTAND** — [ ] Reviewed W-01 spec and every backend feature consumed · [ ] Identified owner/employee/limited-role users and outcomes · [ ] Defined inputs/outputs per screen · [ ] Business rules (RBAC, limits, entitlements, revisions, online-only actions) listed · [ ] Edge cases incl. offline/kill/conflict considered · [ ] Objective restated in each PR.
**PLAN** — [ ] Atomic tasks in §6 confirmed · [ ] Dependencies and parallel tracks set · [ ] Acceptance per task defined · [ ] Test procedures per category defined · [ ] ADR-005/006/007 approved.
**BUILD** — [ ] Smallest piece first (foundation → owner/employee screens) · [ ] Only W-01 API used; no duplicated business logic · [ ] Design-system components only · [ ] EN/FR keys on every string · [ ] Feature flags/kill-switches wired.
**TEST** — [ ] Jest, Detox (iOS + Android), sweeps, leak tests, tie-outs, offline, a11y, performance, usability all executed · [ ] Failures investigated and fixed · [ ] Regression suite green · [ ] Unverified conditions recorded.
**IMPROVE** — [ ] §8 checklist completed · [ ] Dev artefacts removed · [ ] Behaviour re-verified after improvements.
**COMPLETE** — [ ] Final diffs reviewed · [ ] Docs/guides/runbook updated · [ ] Exit demonstration (§7) observed on staging/production builds · [ ] Both apps approved and published · [ ] Hypercare log opened (week 13) · [ ] Status reported.

**Reporting template — before implementation (per task / per branch):**
1. Problem understanding — objective; existing behaviour; expected behaviour.
2. Task breakdown — components; atomic task IDs; dependencies.
3. Implementation plan — execution order; acceptance criteria; testing strategy.

**Reporting template — after implementation:**
1. Changes made — completed task IDs; files/components modified (`mobile/...`, backend mobile-support modules); key decisions.
2. Testing results — tests executed (Jest/Detox/sweeps/tie-outs/device); passed; failed; not executed and why (e.g., device cloud unavailable).
3. Remaining issues — known limitations; unresolved bugs; risks/dependencies (e.g., store review pending).
4. Final status — Complete / Partially complete / Blocked.

Sprint report to Profitex every two weeks with staging demo and, from week 11, TestFlight / internal-track build links (Agreement §5.5).

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| Y-01 | 40 | 60 |
| Y-02 | 54 | 81 |
| Y-03 | 32 | 48 |
| Y-04 | 27 | 40.5 |
| **Total** | **153** | **229.5** |

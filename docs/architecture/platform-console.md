# Platform console (U-06)

One console for Numo9 staff: practices and organisations, subscription states, metrics, packages,
feature flags and audited sign-in as a user. Separate shell at **`/console`** with its own accent
colour, so staff never confuse it with an organisation.

## Information architecture (U-06-T01)

| Area | Path | What | Permission |
|---|---|---|---|
| Metrics (home) | `/console` | KPI tiles (MRR, active, trials, conversion, churn, founding x/1,000) with drill-down, trends | `platform.console.view` |
| Practices | `/console/practices` | practices with staff and client counts | `platform.console.view` |
| Organisations | `/console/organisations` | filters (status, package, province, created), paged; detail with subscription timeline, users, practices, audit link | `platform.console.view` |
| Packages & prices | `/console/packages` | the U-02 editor (packages, prices, promo codes, products) | `platform.catalogue.manage` |
| Trial | `/console/trial` | trial package and length (`TrialConfig`, U-05-T01) | `platform.catalogue.manage` |
| Feature flags | `/console/flags` | per organisation, practice, % rollout, everyone | `platform.flags.manage` |
| Sign in as a user | from an organisation's detail | reason, 15 min–2 h, red bar, end | `platform.impersonate` |
| Jobs | `/console/jobs` | background jobs (A-08-T08) | `platform.jobs.view` |

Founding counter and demo manager panels arrive with U-07/U-08 (U-06-T13).

Wireframes: [design/wireframes.md §27–29](../design/wireframes.md) (and §7 for the metrics home).

## Shell and route guard (U-06-T02)

Every `/console/*` page renders inside `ConsoleFrame` (`frontend/src/console/shell`). It first asks
**`GET /api/v1/platform/me`** (`numo9.platform.api`):

| Who | API | Screen |
|---|---|---|
| no platform role (organisation users, accountants, practice admins) | `404` | the **404 page** — nothing of the console renders, nothing leaks |
| platform role without two-factor authentication | `403 auth.two_factor_required` | "Turn on two-factor authentication" with a link to Security settings |
| platform staff with 2FA | the user and their platform permissions | the console's navigation on its own dark-blue accent bar (never an organisation's colours), with only the areas their permissions open, the current one marked |

The guard is a convenience: every console endpoint still checks its own `platform.*` permission
(security tests, U-06-T14). `backend/tests/test_platform_guard.py`,
`frontend/src/console/shell/ConsoleFrame.test.tsx`; the Playwright console suites answer the
guard with a platform owner (`e2e/auth-helpers.ts` `mockPlatformMe`).

## Practices and organisations APIs (U-06-T03)

`numo9.platform.directory`, both with `platform.console.view`:

| Endpoint | Filters (repeatable values = any of them) | Row |
|---|---|---|
| `GET /api/v1/platform/organisations` | `status`, `package` (code, or `none`), `province`, `created_from` / `created_to` (inclusive dates), `q` (name, accents ignored) | id, name, status, `is_demo`, current package and subscription status, province, created |
| `GET /api/v1/platform/practices` | `q`, `created_from` / `created_to` | id, name, staff count, active clients count, created |

Newest first; `page` (1-based) and `page_size` (1–200, default 50); the answer carries `count`,
`page`, `page_size`, `pages`. A value it can't use is `400 platform.bad_filter` with `field`.
`backend/tests/test_platform_lists.py`.

## Organisation detail (U-06-T04)

`GET /api/v1/platform/organisations/<id>` (`platform.console.view`, 404 for an unknown id) and the
console pages `/console/organisations` (filters from U-06-T03, paged table, demo marked) and
`/console/organisations/<id>`:

- status, province, time zone, created; the current subscription (status, package, interval,
  period end, founding);
- **subscription history**, oldest first: trial started (trial registry), subscription created and
  every status change (the subscription's audit events, A-04), trial converted;
- users (role, last sign-in), practices serving it (role, staff assigned, switched off), and the
  organisation's 20 latest audit events.

Dates in the organisation's time zone. Tests: `backend/tests/test_platform_organisation_detail.py`,
`frontend/src/console/organisations/OrganisationDetailScreen.test.tsx`.

## Metrics service and daily snapshot (U-06-T05)

`numo9.platform.metrics` computes the console's figures; **demo organisations are never counted**
(organisation status `demo` or a `demo` subscription).

| Metric | Definition |
|---|---|
| MRR | Σ over `active` + `past_due` subscriptions of the price in force today for their package and interval, a month's worth (annual ÷ 12, half-up to the cent), CAD cents |
| Active | organisations with an `active` or `past_due` subscription |
| Trials | organisations whose subscription is `trialing` |
| Conversion (30 days) | trials converted in the window ÷ trials that ended in it (converted, or read-only `trial_ended` with the period ending in the window); `null` when none ended |
| Churn (30 days) | subscriptions cancelled in the window ÷ (active now + cancelled in the window); `null` when nothing was active |

`metrics.drill_down("active" | "mrr" | "trials")` returns the organisations a tile counts, so a
tile and its list never disagree. `PlatformMetricDaily` (platform model, one row per date,
`update_or_create`) is written nightly by `numo9.platform.snapshot_metrics` (beat 05:51 UTC);
trend charts read it instead of recomputing history.

## KPI tiles, trend charts and drill-down (U-06-T06)

`/console` (the console's home, "Metrics") shows five tiles — MRR, active organisations, trials,
conversion and churn (30 days, with "1 of 2 trials that ended" / "1 of 10 cancelled" under the
rate; a dash when there is nothing to divide by) — and a Recharts line chart of the selected tile
over 30, 90 or 365 days, whose figures also open as a table (exact values, screen readers).

| Endpoint | Answers |
|---|---|
| `GET /api/v1/platform/metrics?days=7–366` | `current` (computed live) and `history`: the `PlatformMetricDaily` rows of the period, then today's live point — the chart's last point equals the tiles |
| `GET /api/v1/platform/metrics/{active,mrr,trials}/organisations` | the organisations the tile counts, in the organisations list's page shape |

The tile and its list come from the same query (`metrics.drill_down`), so **the tile's count is
always the list's `count`**. Both need `platform.console.view`.

## Package editor in the console (U-06-T07)

The U-02 screens are reused unchanged inside the console frame: **Packages and prices**
(`platform.catalogue.manage`) holds `/console/packages` (list, `new`, `<code>` — the editor, price
timeline and Stripe sync of U-02-T09/T10), `/console/products` (U-01-T11) and
`/console/promo-codes` (U-02-T11), with a "Catalogue" sub-navigation between them
(`console/shell/CatalogueNav.tsx`). An organisation's detail links its current package to the
editor for staff who may manage the catalogue.

## Impersonation sessions (U-06-T08)

`ImpersonationSession` (platform model) — one row per session: `actor` (platform staff),
`target_user`, `organisation` (the **one** organisation the session is scoped to, even when the
user belongs to many), `reason` (required, ≤ 500 characters), `started_at`, `expires_at`
(default 30 minutes, at most 2 hours — a database check), `ended_at` and `end_reason`
(`ended` / `expired` / `revoked`). The database also refuses self-impersonation and a second open
session for the same staff member.

`numo9.platform.impersonation.start()` applies the rules before creating the row (the user acted
as must be a member of that organisation and hold no platform role); `current()` returns the open
session and closes it as `expired` once its time is up.

## Impersonation auth: time box and blocked endpoints (U-06-T09)

| Endpoint | Who | Does |
|---|---|---|
| `POST /api/v1/platform/impersonation` `{organisation, user, reason, minutes}` | `platform.impersonate` (2FA) | starts the session (U-06-T08 rules) and stores its id in the browser session |
| `GET /api/v1/platform/impersonation/current` | signed in | `{session, ended}` — the open session, or the one that just expired |
| `POST /api/v1/platform/impersonation/end` | signed in | ends it (`ended`); the next request is the staff member again |

`numo9.platform.middleware.ImpersonationMiddleware` (after the 2FA policy, before the audit and
tenant context) turns each request of that browser into the user's: `request.user` becomes the
user acted as, `request.audit_impersonator` the staff member. It **ends** the session when its
time is up (`expired`; that request answers `403 impersonation.expired` and changes nothing), when
the staff member loses `platform.impersonate` (`revoked`) and on sign-out (`ended`).

While impersonating, `BLOCKED` endpoints answer `403 impersonation.blocked`: billing portal,
checkout, change (and its preview) and cancel; SIN/bank reveal; allauth password, email,
authenticators (2FA), phone, providers, password reset, re-authentication and sessions; practice
workspaces (`/api/v1/practice/…`) and creating organisations or practices; the Django admin; the
console itself except `impersonation/current` and `impersonation/end`. Every other request is
scoped to the session's organisation: another organisation answers 404.

## Impersonation in the organisation's audit log (U-06-T10)

The organisation's own audit log (its owner sees it in Settings → Audit log) records:

| Action | When | `meta` |
|---|---|---|
| `platform.impersonation.started` — "Numo9 support signed in as this user" | the session starts | `acting_as`, `impersonator`, `impersonation_session`, `reason`, `expires_at` |
| every write of the session (any action) | during it | `acting_as`, `impersonator`, `impersonation_session` |
| `platform.impersonation.ended` — "Numo9 support session ended" | ended, expired, revoked or signed out | the same, plus `end_reason`, `ended_at` |

All of them have `actor_kind = impersonation`, `actor_user` = the user acted as and `impersonator` =
the staff member (the label reads "Dana Lee (dana@…) — signed in by Sam Support (…)").

## Impersonation UI (U-06-T11)

- **Start** — on an organisation's detail page each user has "Sign in as …" (staff with
  `platform.impersonate`). The modal (`StartImpersonationDialog`) explains what is recorded and
  what stays locked, asks for the reason (required, 500 characters) and the time limit (15 min,
  30 min — default, 1 h, 2 h), then opens the organisation's home as that user.
- **Red bar** — `ImpersonationBar` is mounted in the app shell's banner slot, so it shows on
  **every page** (organisation pages, the console, pages outside an organisation) while
  `GET …/impersonation/current` returns a session: "You're signed in as Dana Lee in Maple Leaf
  Supply", a `mm:ss` countdown (role `timer`) and "End session" (back to the organisation in the
  console). At zero it asks the API again — which ends the session — and says it ended.

# Entitlement engine (U-03)

| | |
|---|---|
| **Deliverable** | U-03 · Entitlement engine, Phase 0 (component U — SaaS, packages and billing) |
| **Branch** | `feature/U-03-entitlements` |
| **Decision** | [ADR-0004 — Entitlement resolution and caching](../adr/0004-entitlement-resolution-and-caching.md) |
| **Code** | `backend/numo9/entitlements/` (models, engine, cache, drf, api, presenter, source); `frontend/src/entitlements/` (store, read-only notice); `frontend/src/catalogue/Gated.tsx` (locked panel); `packages/ui/src/shell/AppShell.tsx` (locked navigation items, banner slot) |
| **Depends on** | U-01 (products, feature keys, `RequiresFeature`, `<Gated>`), U-02 (packages), A-01 (tenancy), A-03 (permissions), A-04 (audit) |
| **Used by** | Every gated endpoint and screen; U-04 billing (extends `Subscription`, flips statuses), U-05 trial, U-06 platform console (override UI, U-03-T14), U-07 demo, U-08 founding offer |
| **Gaps** | gap-06 (approval never paywalled), gap-14 (no silent redirect), gap-41 (explicit prompt, no generic banners), gap-61 (plan/feature matrix) |

What Xero does (xero_teardown §2.2, §2.5, §6.3): approval of invoices is behind a plan, a credit
note silently redirects to another screen, upgrade banners are generic and the advisor can't see
the client's plan. Numo9 resolves organisation → subscription → package → products → feature keys
in **one cached call** and gates **explicitly**: the API answers 402 naming the product and the
packages that include it, the screen shows a locked panel at its own URL.

## Models

| Model | Task | What |
|---|---|---|
| `Subscription` | T02 | The organisation's package and status: `trialing`, `active`, `past_due` (full access until `grace_until`), `read_only`, `cancelled` (read + export), `demo`; `current_period_end`, `founding` (U-08: every product), `override` JSON (`products`: extra product codes; `limits`: over the package's, U-06), `status_changed_at` and `status_reason` (`trial_ended`, `payment_failed`, `cancelled`, `platform`). **At most one not cancelled per organisation** — partial unique index `entitlements_one_current_subscription`; cancelled ones stay as history. Past-due needs `grace_until` (DB check); a draft package can't be subscribed to. Saving mirrors the status on `Organisation.status` (trialing → trial, past_due → grace…). Billing fields arrive with U-04-T02 |
| `EntitlementOverride` | T03 | The Platform Owner grants one product until `expires_at` with a `reason` (required; the grant is in the organisation's audit log). Expired or removed → ignored |
| `OrgProductHistory` | T05 | Every product the organisation was ever entitled to (first and last seen): read retention |

All three are organisation records (`OrgOwnedModel`); `Subscription` and `EntitlementOverride`
are audited (`AuditedModel`).

## Resolution (T04, T05)

`numo9.entitlements.engine.resolve_entitlements(org, now)` →
`Entitlements(mode, reason, products, read_products, features, since, package, status, founding,
valid_until)`:

| State | Mode | Reason | Features |
|---|---|---|---|
| `trialing`, `active`, `demo` | `full` | the status | every key of the entitled products |
| `past_due`, before `grace_until` | `full` | `past_due` | 〃 |
| `past_due`, after `grace_until` (even before the status job flips it) | `read_only` | `payment_failed` | read keys only |
| `read_only` | `read_only` | its `status_reason` (else `read_only`) | read keys only |
| `cancelled` | `read_only` | `cancelled` | read keys only |
| no subscription (self sign-up) | `full` | `no_subscription` | the trial package |
| no subscription, organisation `demo` / `read_only` / `cancelled` | as the status | the status | — |
| no organisation | `none` | `no_organisation` | nothing |

Entitled products: the subscription's package — a trial or demo without one uses
`NUMO9_TRIAL_PACKAGE` / `NUMO9_DEMO_PACKAGE` (package codes; empty or unknown = every active
product) — plus every active product when `founding`, plus `override["products"]`, plus each
unexpired `EntitlementOverride`, plus the free sets (Practice, Client portal: in every package).
Planned products are never entitled (not shipped); a retired product in a package stays.

**Read retention** — products entitled in `full` mode are written to `OrgProductHistory`. A product
in the history that is no longer entitled keeps its `*.read` keys (`read_products`): after a
downgrade from a package with Payroll, `payroll.*.read` is allowed and `payroll.*.write` is not.

**Never gated** — `CORE` (sign-in, tenancy, users and roles, approval limits, audit, jobs,
settings) is allowed in every mode. Inside a product nothing is sold separately: every
`accounting.*.approve` key belongs to Accounting (gap-06). Practice users acting inside an
organisation get the organisation's answer — the engine never looks at the user.

## Cache (T06)

`numo9.entitlements.cache.entitlements_for(org)` reads Django's default cache (Redis in staging and
production) at `ent:{org public id}:{org version}.{global version}` and resolves on a miss.

| Change | Bump |
|---|---|
| `Subscription`, `EntitlementOverride` saved or deleted; `Organisation` saved | the organisation's version |
| `Package`, `PackageProduct`, `Product`, `FeatureKey` saved or deleted | the global version |

The next call builds a new key, so a change is visible on the next request — no TTL wait. Bumps run
at once and again on commit. An entry's timeout stops at `valid_until` (grace end, override
expiry), so the answer never outlives the moment it changes by itself; old entries expire after an
hour. A cached call runs no query. The cache holds feature keys and product codes only — no
personal data.

## API (T07, T08, T09)

**402 — not in the package** (`RequiresFeature`, `settings.NUMO9_ENTITLEMENT_RESOLVER =
"numo9.entitlements.engine.Engine"`):

```json
{"code": "entitlement.feature_not_in_package",
 "detail": "This isn't in your organisation's package: it's part of Payroll. …",
 "feature": "payroll.pay_runs.write", "product": "payroll", "product_name": "Payroll",
 "packages": [{"code": "complete", "name": "Complete"}]}
```

`packages` lists the packages offered that include the product (the plan's
`feature_not_in_package`, a dotted key like every error code). Order of checks: foreign
organisation 404 → missing permission 403 → read-only 402 → not in the package 402.

**402 — read-only organisation** (`numo9.entitlements.drf.ReadOnlyGuard`, the plan's "read-only
mode middleware"; a DRF permission so it runs after the access checks and an outsider never learns
the billing state): every unsafe method (POST, PUT, PATCH, DELETE) answers

```json
{"code": "entitlement.organisation_read_only", "detail": "This organisation is read-only: …",
 "reason": "payment_failed", "since": "2026-11-20T05:00:00+00:00"}
```

except methods marked `@allowed_when_read_only` (or views with `allowed_when_read_only = True`):
billing (U-04 — paying makes the organisation writable again) and exports. Reading is never
refused.

**Bootstrap** — `GET /api/v1/o/<org>/entitlements` (the plan's `/orgs/{id}/entitlements`; Numo9's
organisation URLs are `/o/<org>/…`): anyone who can open the organisation (`can_access`, 404
otherwise), `CORE`, readable while read-only. Body: `organisation`, `mode`, `reason`, `since`,
`package`, `package_name`, `status`, `founding`, `products`, `read_products`, `features`, `version`,
`product_names` (every product, the request's language), `packages_by_product`, `time_zone` and
`viewer.can_change_package` (the organisation's owner). Cached answers take < 20 ms p95
(`tests/test_entitlements_api.py`).

Packages see subscriptions through `NUMO9_SUBSCRIPTION_SOURCE = "numo9.entitlements.source.Subscriptions"`
(U-02 interface): subscriber count, the subscriptions a price change affects (every one on the
package that hasn't ended until U-04-T02 adds the interval and the grandfathered flag) and an
organisation's package.

## Web app (T10, T11, T12)

| Piece | What |
|---|---|
| Entitlement store | `frontend/src/entitlements/store.tsx` — `EntitlementsProvider` (React Query, key `["entitlements", org]`, fresh 60 s, refetch on focus; one retry on a network failure only), mounted by the app shell for every organisation page; feeds `FeatureProvider`, so every `useFeature` / `<Gated>` decides from the package. `loading` until the first answer; if the call fails, decisions are `allowed` (the API still refuses with 402). `useRefreshEntitlements()` after a 402 |
| Locked panel | `GatedPanel` (`frontend/src/catalogue/Gated.tsx`): icon, "Payroll isn't in this organisation's package", "It's part of the Payroll product, included in Complete." Buttons per role: the **owner** — *See what's in each package* (Settings → Package and features) and *Change the package* (Settings → Subscription); **everyone else** (staff, accountants — they can't buy) — *See what's in each package* and *Ask the owner*, which says only the owner can change the package. `decisionFromError(body)` builds the same panel from a 402 in a form |
| Navigation | `primaryNav(fm, org, path, decide)` — an item whose module's feature is gated keeps its place and its link, with a lock glyph, the tooltip "<Product> isn't in this organisation's package" (also as screen-reader text, and written out in the phone/tablet drawer) |
| Gated routes | The app shell wraps a module whose registry `feature` isn't `CORE` in `<Gated>`: visiting a gated URL renders the locked panel as the page heading, the URL unchanged — no redirect (gap-14) |
| Read-only notice | `ReadOnlyNotice` in the shell's `banner` slot (under the top bar, outside the work area): "This organisation has been read-only since 20 Nov 2026: the payment failed and the grace period ended. You can still see and export everything." + *Reactivate the subscription* for the owner, "Ask the organisation's owner to reactivate it." for everyone else. Reasons: `payment_failed`, `trial_ended`, `cancelled`, `platform`; the date in the organisation's time zone. Nothing in any other mode — an account-state notice, never a promotion (gap-12 holds) |

## Tests

| Task | Tests |
|---|---|
| T02, T03 | `backend/tests/test_entitlements_models.py` |
| T04, T05 | `backend/tests/test_entitlements_engine.py` (every status, table-driven; downgrade keeps Payroll read) |
| T06 | `backend/tests/test_entitlements_cache.py` (every invalidating save; Redis with `NUMO9_TEST_REDIS_URL`) |
| T07–T09 | `backend/tests/test_entitlements_api.py`, `backend/tests/test_requires_feature.py` |
| T10 | `frontend/src/entitlements/store.test.tsx`, `frontend/src/catalogue/Gated.test.tsx`, Storybook *Entitlements/Gated* (locked panel — owner / staff) |
| T11 | `frontend/e2e/entitlements-gating.spec.ts` (`@gap-14`), `frontend/src/routing/navigation.test.ts`, `packages/ui/src/shell/AppShell.test.tsx`, `frontend/src/app/o/[org]/[...module]/page.test.tsx` |
| T12 | `frontend/e2e/read-only-banner.spec.ts`, `frontend/src/entitlements/ReadOnlyNotice.test.tsx`, Storybook *Shell/AppShell — Locked module + read-only notice* |
| T13 | `backend/tests/test_entitlements_leaks.py` — every feature key × every status, engine and API |
| T15 | `backend/tests/test_entitlements_gaps.py` (`gap-06`, `gap-14`, `gap-41`), `frontend/e2e/gap-06-14-41.spec.ts` |

U-03-T14 (platform-owner override UI) waits for the platform console organisations screens (U-06).

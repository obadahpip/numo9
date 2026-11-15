# ADR-0004: Entitlement resolution and caching — one engine, versioned cache keys, read retention

| | |
|---|---|
| **Status** | accepted — 2026-11-15 (takes effect when the U-03 pull request is merged) |
| **Date** | 2026-11-15 |
| **Deciders** | Obadah Abu Odeh — project lead and decision-maker (approval = merging the PR) |
| **Deliverable / task** | U-03-T01 (the phase plan calls it "ADR-005"; repository numbering is sequential) |

## Context and problem statement

Every API method and screen declares a feature key (U-01: `<product>.<area>.<action>` or `CORE`).
U-03 must answer "may this organisation use this key now?" on every request, from organisation →
subscription → package → products → features, plus founding offers (U-08), platform overrides,
trials (U-05), demo organisations (U-07) and read-only states after a failed payment or a
cancellation (U-04). A wrong answer is a top project risk (plan §risk 3: entitlement leaks — a
lapsed organisation keeping paid features, or a paying one losing them), and Xero's behaviour is
what we must not copy: paywalled approval (gap-06), a credit note that silently redirects
(gap-14), generic upgrade banners (gap-41).

## Decision drivers

1. **One answer everywhere** — API, screens and jobs ask the same engine (no second copy of rules).
2. **Correct after every change** — a subscription, package or override change is visible on the
   next request; no waiting for a TTL (U-03-T06 acceptance).
3. **Fast** — the bootstrap call answers in < 20 ms p95 when cached (U-03-T09).
4. **History is never lost** — a downgrade removes writes at once but keeps reading what was
   created while entitled (`*.read` keys survive, plan U-03 business rule).
5. **Explicit gating** — the answer carries the product and the packages that include it, so the
   UI and the 402 body can name them (never a redirect).

## Considered options

**A. Where the rules live**
1. One pure function `resolve_entitlements(org, now)` returning products, features, mode and
   reason; `RequiresFeature`, the read-only guard and the bootstrap API only read its result. — **chosen**
2. Checks spread over each module (`if org.package == …`).

**B. Caching**
1. Django cache (Redis in staging/prod) with **versioned keys**: `ent:{org}:{org_version}.{global_version}`;
   saves bump a counter instead of deleting keys. — **chosen**
2. Delete-on-write (`cache.delete(key)`) — races: a reader can re-fill the old answer after the delete.
3. Per-process memoisation with a TTL — stale for up to the TTL; violates driver 2.
4. No cache — a handful of queries per request; fails driver 3 once modules multiply.

**C. Read retention**
1. `OrgProductHistory` row per (organisation, product) ever entitled, written when the engine
   first sees the product entitled; read keys of every product in it stay granted. — **chosen**
2. Derive history from subscription history — subscriptions change in place (U-04), and an
   override or founding grant has no subscription row.

**D. Read-only enforcement**
1. A DRF permission after `RequiresPermission` (404 → 403 → 402 order, like `RequiresFeature`),
   refusing unsafe methods in `read_only` mode unless the view is marked
   `allowed_when_read_only` (billing, exports). — **chosen**
2. A Django middleware before the views — it runs before access checks, so an outsider could
   learn an organisation's billing state from a 402 instead of a 404.

## Decision outcome

**Chosen options:** A1, B1, C1, D1.

- **Resolution** (`numo9.entitlements.engine`): the organisation's *current* subscription (at
  most one not cancelled — partial unique index; else its latest cancelled one) decides the mode:

  | Subscription | Mode | Products |
  |---|---|---|
  | `trialing`, `active`, `past_due` before `grace_until` | `full` | the package's products |
  | `demo` | `full` | the package's products |
  | `past_due` after `grace_until`, `read_only` | `read_only` | read keys only |
  | `cancelled` | `read_only` (read + export) | read keys only |
  | none (sign-up before choosing a package) | `full` (trial) | the trial package (`NUMO9_TRIAL_PACKAGE`), else every active product |
  | no organisation | `none` | nothing |

  A trialing or demo subscription without a package resolves like "none" (the configured trial or
  demo package, else every active product). Founding organisations (U-08) get every **active**
  product, including products that ship later; an unexpired `EntitlementOverride` adds its product.
  Free sets (Practice, Client portal) are in every package. Products in `OrgProductHistory` but not
  entitled now keep their read keys. `CORE` is never gated; approval inside a product is never a
  separate key (gap-06). Clock skew: grace end and override expiry are compared with `now`, and a
  cached answer expires at the next such moment.
- **Cache**: Django's default cache (Redis in staging/prod, `numo9` prefix). Saving or deleting a
  `Subscription` or `EntitlementOverride` increments the organisation's version; saving a
  `Package`, `PackageProduct`, `Product` or `FeatureKey` increments the global version. Old keys
  are never read again and expire (1 hour). The cache holds no personal data.
- **Interface**: `settings.NUMO9_ENTITLEMENT_RESOLVER` → `numo9.entitlements.engine.Engine`
  (U-01-T05 stub replaced, no view changes); `NUMO9_SUBSCRIPTION_SOURCE` → the real subscription
  counts for U-02.

### Consequences

- Good: one place to test exhaustively (table-driven over every status, leak matrix over every
  key × status); changes are immediate; the bootstrap call is a cache read.
- Good: practice users acting in an organisation inherit the organisation's answer — the engine
  never looks at the user.
- Bad: the version counters live in the cache; if Redis is flushed, versions restart at 1 and old
  entries are gone too, so no stale answer can be read. Mitigation: none needed.
- Bad: a package change bumps every organisation's cache. Package edits are rare (platform owner).
- Bad: history rows are written during a read. Mitigation: insert-if-missing (`ignore_conflicts`).

### Confirmation

`tests/test_entitlements_engine.py` (every status), `test_entitlements_cache.py` (no TTL wait,
Redis when `NUMO9_TEST_REDIS_URL` is set), `test_entitlements_api.py` (402 bodies, read-only
guard, bootstrap), `test_entitlements_leaks.py` (feature key × status matrix),
`test_entitlements_gaps.py` (gap-06/14/41) and the Playwright suites for the locked panel, the
navigation locks and the read-only banner.

# Packages, prices and promo codes (U-02)

Packages are what organisations subscribe to. They are **client data** entered by the Platform
Owner in the console — names, product mixes and prices are never code. Code lives in
`backend/numo9/packages/`; the console screens in `frontend/src/packages/`.

## Model

| Model | What it holds | Rules |
|---|---|---|
| `Package` | `code` (stable, unique, never changes), `name_i18n` / `description_i18n` (`{"en-CA", "fr-CA"}`; English required), `status` (`draft` → `active` → `retired`), `is_founding_eligible`, `limits` (`{"max_org_users": n \| null}`), `sort`, `stripe_product_id` | A package with no product can't be activated; practice users never count against limits |
| `PackageProduct` | The products in a package | Only active, billable products (main, active companion apps). Free sets (Practice, Client portal) are part of **every** package and never chosen. An active package keeps at least one product |
| `PackagePrice` | One price version: `interval` (`month`/`year`), `amount_cents`, `currency` (`CAD` only), `tax_behaviour` (`exclusive` — GST/HST on top, Phase 1 tax engine), `effective_from`, `effective_to` (exclusive; null = open), `stripe_price_id` | Versions of a package and interval **never overlap** — PostgreSQL exclusion constraint `packages_price_no_overlap` (btree_gist over `daterange(from, to, '[)')`). A version is never edited; only its end date and (once) its Stripe id are set later |
| `PromoCode` | `code` (upper-case, case-insensitive), percent (1–100) or fixed amount (cents), duration `once` / `repeating` (+ months) / `forever`, `max_redemptions`, `redemptions_count`, `expires_at`, package restriction (none = all) | The database refuses a counter above the maximum |
| `PromoRedemption` | An organisation used a code (organisation record, `OrgOwnedModel`) | Once per code and organisation |

Packages, prices and promo codes are platform records (tenancy allow-list); every change goes to
the **platform** audit log.

## Which price applies

`price_for(package, interval, on_date)` (`prices.py`) returns the version in force on the day
(`effective_from <= day < effective_to`) or raises `PriceNotFound`. A subscription renews at
`price_for(package, interval, renewal_date)` unless it is grandfathered (U-04), so a price dated
in the future changes nothing until a renewal on or after its start.

Scheduling a price (`services.schedule_price`) adds a version that starts today or later (drafts
may start in the past — never sold) and after every existing version of that interval; the
version in force on that day gets `effective_to = start`. A version that hasn't started can be
deleted; the previous one is then open again.

## Lifecycle

| From | To | Rule |
|---|---|---|
| draft | active | Needs a product; offered at sign-up and on the pricing page |
| active | retired | Hidden from sign-up; **subscribers keep it**. The only offered package can't be retired |
| retired | active | Offered again |

Delete: only a draft nobody subscribes to (409 otherwise — retire instead). Subscriptions arrive
with U-03/U-04: packages ask the **subscription source** (`subscriptions.py`,
`NUMO9_SUBSCRIPTION_SOURCE`) for the subscriber count, the subscriptions a price change affects
(not grandfathered, same package and interval) and an organisation's package. Until U-03 the
source is `NoSubscriptions`.

The catalogue's feature matrix and the in-app "Package and features" page read the offered
packages through `NUMO9_PACKAGE_SOURCE = numo9.packages.source.OfferedPackages` (U-01 interface).

## Promo codes

`promos.redeem(code, organisation, package)` — what checkout (U-04) calls — locks the code's row
(`SELECT … FOR UPDATE`), refuses unknown (404), expired, used-up, wrong-package or already-used
codes (409), increments the counter and records the redemption, in one transaction: 50
simultaneous redemptions of a code limited to 10 give exactly 10.

## API

| Route | Who | What |
|---|---|---|
| `GET/POST /api/v1/platform/packages` | `platform.catalogue.manage` | List / create a draft |
| `GET/PATCH/DELETE /api/v1/platform/packages/<code>` | 〃 | Read / edit texts, products, limits, founding flag / delete a draft |
| `POST …/<code>/activate`, `…/retire` | 〃 | Status changes |
| `POST …/<code>/prices` | 〃 | Schedule a price version |
| `GET …/<code>/prices/impact?interval=&effective_from=` | 〃 | Subscriptions a price starting that day affects at their next renewal |
| `DELETE …/<code>/prices/<id>` | 〃 | Delete a version that hasn't started |
| `GET/POST /api/v1/platform/packages/promo-codes`, `GET/PATCH …/<code>`, `POST …/<code>/expire` | 〃 | Promo codes |
| `GET /api/v1/public/pricing` | Anyone | Offered packages, products (+ free sets), limits, founding flag, price in force per interval and the next scheduled change; cached 60 s per language (website Q-01) |

Validation errors come back in field form (`{"field": ["message"]}`); everyone but the platform
owner gets 403.

## Stripe

Every price version gets its own Stripe Price, created once and **never modified** (Stripe prices
are immutable): `stripe_sync.sync_stripe_prices` (platform job, `io` queue) creates the missing
Stripe Product per sold package (`numo9_pkg_<code>`) and Price per version (CAD, recurring
monthly/yearly, `tax_behavior=exclusive`), with idempotency keys from the rows' public ids. It is
started after a price is scheduled on a sold package or a package is activated. A stub until U-04:
without `STRIPE_SECRET_KEY` nothing is started and the job does nothing. Tests run against
stripe-mock (`NUMO9_TEST_STRIPE_MOCK_URL`; CI service `stripe/stripe-mock`).

## Console screens

- `/console/packages` — list; `/console/packages/new`, `/console/packages/<code>` — editor with
  product cards, limits, founding switch, a live preview of the public pricing card, and the price
  timeline (versions per interval, today marker, schedule dialog with the impact count).
- `/console/promo-codes` — list with usage bars (redemptions ÷ maximum), create dialog, expire.

Wireframes: [Phase 0 wireframes §8–10](../design/wireframes.md#8-package-editor-u-02-t01).

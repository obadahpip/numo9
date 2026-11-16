# Subscription billing (U-04)

| | |
|---|---|
| **Deliverable** | U-04 · Subscription billing (Stripe), Phase 0 (component U — SaaS core) |
| **Branch** | `feature/U-04-stripe-billing` |
| **Code** | `backend/numo9/billing/`; billing fields on `entitlements.Subscription`; billing page `frontend/src/billing/` |
| **Depends on** | U-02 (packages, prices, Stripe price sync), U-03 (subscriptions, entitlements), A-07 (emails), A-08 (jobs), S-03 (secrets) |
| **Gaps** | gap-13 (subscription object: proration, renewals, dunning), gap-41 |

Organisations pay for their package by card or by pre-authorised debit (PAD, Stripe ACSS Debit).
Accountants are never billed: the Stripe customer is the **organisation** — never a user, never a
practice. Stripe holds the card and the PAD mandate (PCI and PAD scope stay at Stripe); Numo9
keeps the subscription's state, a mirror of the platform invoices and the events it received.

## Stripe account and configuration (U-04-T01)

One Stripe **Canada** account for the platform, in test mode until the client's live keys:

| Setting (Stripe dashboard) | Value |
|---|---|
| Country / currency | Canada / CAD |
| Billing | Enabled (subscriptions, invoices, customer emails off — Numo9 sends its own) |
| Payment methods | Card, **ACSS Debit** (Canadian PAD; mandate collected by Checkout) |
| Stripe Tax | Off — platform GST/HST is a tax rate per province of the organisation (data) |
| Products and prices | Created by the price sync (U-02-T12): one Price per package price version, never changed |
| Webhook endpoint | `https://<host>/webhooks/stripe/`, events: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.finalized`, `invoice.paid`, `invoice.payment_failed` |

Keys live in the encrypted secrets file of each environment (SOPS + age,
[secrets runbook](../security/secrets-runbook.md)) — test keys on staging, live keys on
production — and reach the containers as environment variables (`infra/secrets/env.template`):

| Variable | What | Empty |
|---|---|---|
| `STRIPE_SECRET_KEY` | Secret key `sk_test_…` / `sk_live_…` (server only) | Stripe off: price sync skipped, checkout answers 503 |
| `STRIPE_PUBLISHABLE_KEY` | Publishable key `pk_…` (given to the browser for Stripe.js) | Billing page shows "billing unavailable" |
| `STRIPE_WEBHOOK_SECRET` | Signing secret `whsec_…` of the webhook endpoint | Every webhook is refused (400) |
| `STRIPE_API_BASE` | Another API base (stripe-mock in CI) | Stripe's own API |

No key is ever in the repository: gitleaks (`.gitleaks.toml`) has rules for Stripe secret and
restricted keys (`sk_`/`rk_` test and live) and webhook secrets (`whsec_`) on top of its defaults,
run on every commit (pre-commit) and on the full history (security workflow). Developers use
their own Stripe test account and `stripe listen --forward-to localhost:8000/webhooks/stripe/`
(Stripe CLI), which prints a local `whsec_` for `.env`.

## Subscription billing fields (U-04-T02)

Migration `entitlements.0004_subscription_billing` adds to `Subscription` (every new column has a
database default, so rows written by older code stay valid):

| Field | Type | Rules / meaning |
|---|---|---|
| `stripe_customer_id` | varchar(64), `""` | The organisation's Stripe customer (`cus_…`), one per organisation (U-04-T04); indexed |
| `stripe_subscription_id` | varchar(64), `""` | The Stripe subscription (`sub_…`); unique when set (`entitlements_stripe_subscription_unique`) |
| `interval` | `month` · `year`, default `month` | Billing interval (`entitlements_subscription_interval_valid`) |
| `cancel_at_period_end` | boolean, `false` | The owner cancelled: access continues until `current_period_end` |
| `payment_method_type` | `card` · `acss_debit` · `""` | How the organisation pays; the card or the PAD mandate stays at Stripe (`entitlements_subscription_method_valid`) |

## Stripe events (U-04-T03)

`billing.StripeEvent` — every webhook event, stored once (platform data: an event arrives before
its organisation is known; `organisation` is filled when resolved):

| Field | Meaning |
|---|---|
| `event_id` | Stripe's `evt_…`, **unique** — idempotency key |
| `type` | `invoice.paid`, `customer.subscription.updated`… |
| `payload` | The event exactly as received |
| `stripe_created` | Stripe's `created` time (ordering of out-of-order events, U-04-T15) |
| `livemode` | Live or test event |
| `processed_at`, `attempts`, `error` | Processing outcome (U-04-T06) |

`numo9.billing.events.record_event(event) → (row, created)`: `INSERT … ON CONFLICT (event_id) DO
NOTHING` — a re-delivered or replayed event stores nothing and returns the stored row (whatever
the replay's payload says), so it is never processed twice. A payload without an `evt_` id, a
type or a created time is refused (`MalformedEvent`).

## Stripe gateway and customers (U-04-T04)

`numo9.billing.gateway.get_gateway()` — every Stripe call billing makes goes through one
interface (`BillingGateway`): `settings.NUMO9_BILLING_GATEWAY` (a class path: the tests' fake),
else the Stripe client when `STRIPE_SECRET_KEY` is set (`STRIPE_API_BASE` → stripe-mock in CI),
else `BillingUnavailable` (503 `billing.unavailable`). Calls that create something carry an
idempotency key built from Numo9 ids.

`numo9.billing.customers.ensure_customer(organisation) → "cus_…"` — **one customer per
organisation** (never per user or practice: accountants are never billed):

- the id is stored on the organisation's current subscription (`stripe_customer_id`); a second
  call returns it and creates nothing;
- otherwise the customer is created with the organisation's name, its owner's email and metadata
  `numo9_org` = the organisation's public id (webhooks find the organisation by it), with the
  idempotency key `numo9-customer-<org public id>` — a retried request gets the same customer;
- it runs under a row lock on the subscription (two first calls at once create one customer);
- an organisation without a subscription is refused (409 `billing.no_subscription`).

`organisation_of_customer("cus_…")` finds the organisation from a customer id.

## Checkout (U-04-T05)

`POST /api/v1/o/<org>/billing/checkout` `{package, interval, methods?}` → 201 `{url, session_id,
package, interval, amount_cents}` — the owner is sent to Stripe Checkout:

1. the package must be for sale (active) with a price for the interval in force today already
   created at Stripe by the price sync — else 400 `billing.package_unknown` / 409
   `billing.price_not_ready`;
2. an organisation already paying through Stripe changes its package instead (409
   `billing.already_subscribed`, U-04-T10);
3. the organisation's Stripe customer (U-04-T04);
4. a Checkout session in subscription mode: card and pre-authorised debit by default (`methods`
   narrows: `card`, `acss_debit`; PAD with a business mandate, automatic verification), metadata
   `numo9_org`, `numo9_package`, `numo9_interval` (on the session and the subscription), return
   to the billing page `…/settings/subscription?checkout=success` / `?checkout=cancelled`.
   Idempotency key: `numo9-checkout-<org>-<Idempotency-Key header or a new id>`.

The subscription is recorded from Stripe's webhooks (U-04-T07), never from the redirect.

**Owner only.** Permissions `organisation.billing.view` / `organisation.billing.manage` are
`owner_only` (risk high / critical): the owner role has them; admins and practice admins (who get
every other organisation permission), accountants and other staff don't — 403; another
organisation is a 404. Billing is part of every organisation (`CORE`, never gated). Billing off →
503 `billing.unavailable`.

## Webhook endpoint (U-04-T06)

`POST /webhooks/stripe/` (no session, no CSRF: Stripe authenticates with the signature):

1. **Signature** — `Stripe-Signature` checked against the raw body with `STRIPE_WEBHOOK_SECRET`
   (Stripe's 5-minute tolerance stops old captured requests). Not configured, missing or wrong →
   **400** (`not_configured`, `no_signature`, `bad_signature`), nothing stored. A body that isn't
   a Stripe event → 400 `bad_event`.
2. **Persistence** — `record_event` (U-04-T03).
3. **Dispatch** — a new event is queued for the Celery task `numo9.billing.process_stripe_event`
   (queue `high`) when the transaction commits; the endpoint answers **200**
   `{"received": true, "duplicate": false}` at once. A replayed or re-delivered event answers 200
   `"duplicate": true` and queues nothing.

`numo9.billing.processing.process_event(pk)` (the task): locks the event row; an event already
processed is skipped; the handler registered for its type (`register_handler(*types)`: U-04-T07
subscriptions, U-04-T08 invoices) runs in the event's transaction; a type without handler is
recorded as processed ("ignored"). On success `processed_at` is set; on an error the handler's
changes roll back, `attempts` and `error` (scrubbed) are recorded and the task retries with the
jobs backoff (8 retries). The path is exempt from the tenant sweep (`TENANT_SWEEP_EXEMPT`).

Local development: `stripe listen --forward-to localhost:8000/webhooks/stripe/` (Stripe CLI)
prints the `whsec_` to put in `.env`; `stripe trigger invoice.paid` sends a test event.

## Subscription state from Stripe (U-04-T07)

Handlers (`numo9/billing/subscriptions.py`) of `checkout.session.completed` and
`customer.subscription.created` / `.updated` / `.deleted`. Stripe's subscription is the source of
truth for billing; Numo9 keeps what its entitlements need.

| Stripe status | Numo9 status | Notes |
|---|---|---|
| `active`, `trialing` | `active` | Grace and reason cleared (Stripe trials aren't used: the trial is Numo9's) |
| `past_due` | `past_due` | `grace_until` = failure + 7 days (kept if already set), reason `payment_failed` — dunning, U-04-T09 |
| `unpaid`, `paused` | `read_only` | Read and export only, reason `payment_failed` |
| `canceled` (and every `.deleted` event) | `cancelled` | Reason `cancelled` |
| `incomplete`, `incomplete_expired` | unchanged | First payment not settled — a PAD debit takes 3–5 business days; access continues |

Each subscription event also records the Stripe ids, the **package** (from the price —
`PackagePrice.stripe_price_id` — else the metadata `numo9_package`), the interval, the period end
(`items[0].current_period_end`), `cancel_at_period_end` and the payment method when the
subscription has one. `checkout.session.completed` (subscription mode) links the Stripe ids,
the package and interval of the metadata, and activates a trialing (or ended) subscription — paid
by card, or a PAD debit still processing.

The local subscription is found by `stripe_subscription_id`, else by the customer, else by the
organisation in the metadata (`numo9_org` / `client_reference_id`): the checkout event may arrive
before or after the subscription events, and before the owner's browser returns. An event no
organisation matches fails and is retried. Every change is a `Subscription.save()` — audited, the
organisation's status follows, the entitlement cache is bumped — and the event records its
organisation.

## Platform invoices and receipts (U-04-T08)

`billing.PlatformInvoice` (organisation record, audited) — Numo9's invoice to the organisation,
a mirror of the Stripe invoice: `stripe_invoice_id` (unique), Stripe's `number`, `status`
(`draft`, `open`, `paid`, `uncollectible`, `void`), `currency`, amounts in cents (`subtotal`,
`tax` = total − total excluding tax, `total`, `amount_paid`, `amount_due`), `period_start/end`,
`issued_at` (finalized), `paid_at`, `attempt_count`, `next_attempt_at`, `hosted_url`, `pdf_url`,
the Stripe subscription, `receipt_sent_at` and `stripe_event_created` (the last event applied).

Handlers of `invoice.finalized`, `invoice.paid`, `invoice.payment_failed` upsert the row for the
organisation of the invoice's customer (or subscription) — the local rows are exactly Stripe's
invoices; an event older than the last one applied changes nothing.

- `invoice.paid` — the owner gets a **receipt** once per invoice (notification `billing.receipt`,
  category *Billing and subscription*: in the app and by email): "Receipt: $55.37 paid for Maple
  Bakery Inc."; a past-due or read-only subscription comes back to active (the dunning stops).
- `invoice.payment_failed` — the subscription goes past due with the 7-day grace (if the
  subscription event hasn't already) and the dunning starts (U-04-T09).

## Dunning (U-04-T09)

A renewal that fails puts the subscription **past due** with `grace_until` = failure + 7 days
(full access meanwhile). Then:

| Day | Step |
|---|---|
| 0 | Reminder at once (`invoice.payment_failed` handler, `start_dunning`) |
| 3, 5 | Reminders (Stripe retries the card or debit in between) |
| 7 | The grace ends: **read-only** (reason `payment_failed`) and the owners are told |

A step is the `dunning` system email (A-07-T11; each owner in their language: amount, failure
date, grace end, link to the billing page) plus an in-app notification (`billing.payment_failed`;
day 7 `billing.read_only` — both mandatory).

`numo9.billing.dunning.run_dunning(now)` — platform job `numo9.billing.run_dunning`, beat every
15 minutes — takes for each past-due subscription the **latest** step due and not taken (a job that
missed runs never sends a burst of old reminders). Each step is recorded once —
`billing.DunningReminder`, unique per subscription, grace period and day — so a second run or a
re-delivered failure event sends nothing twice. Read-only is exact at `grace_until`: the
entitlement engine already answers read-only for a past-due subscription after its grace end
(U-03), and the job records the status within 15 minutes. `invoice.paid` makes the subscription
active and stops the dunning; a later failure starts a new cycle (new grace period).

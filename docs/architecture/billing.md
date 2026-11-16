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

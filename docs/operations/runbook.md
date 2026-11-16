# Operations runbook

Incidents the on-call engineer handles, by area: what you see, what to check, what to do. Keep
each section short and executable. Secrets (keys, rotation) are in the
[secrets runbook](../security/secrets-runbook.md).

## Stripe billing incidents (U-04-T17)

Design: [Subscription billing](../architecture/billing.md). Tools: the Stripe dashboard
(Developers → Webhooks / Events / Logs), the platform console's job dashboard (A-08), and on the
server `docker compose exec backend python manage.py billing_events` (list unprocessed events;
`--retry` queues them again; `--event evt_…` processes one now — always idempotent).

### 1. Webhooks fail at Stripe (endpoint shows 4xx/5xx)

- **See:** Stripe dashboard → Webhooks → endpoint: failed deliveries; logs `billing.webhook.refused`
  with a reason.
- **`bad_signature` / `not_configured`:** `STRIPE_WEBHOOK_SECRET` doesn't match the endpoint's
  signing secret (after a roll, or a new endpoint). Copy the endpoint's secret into the secrets
  file (`secrets.sh set <env> STRIPE_WEBHOOK_SECRET`), deploy. Then resend the failed events from
  the dashboard (Events → Resend) — duplicates are ignored, nothing runs twice.
- **5xx / timeouts:** the app or database is down — fix that first. Stripe retries for up to 3
  days with backoff; once the endpoint answers, deliveries resume by themselves.

### 2. Events stored but not processed

- **See:** `billing_events` lists events with `attempts` and an `error`; the billing page or the
  organisation's status didn't change after a payment.
- **Celery `high` queue not consuming:** check the worker (`docker compose ps`, worker logs);
  restart it. Then `billing_events --retry`.
- **`UnknownSubscription`:** the event's customer matches no organisation — a customer created
  by hand in the dashboard, or an organisation deleted. Find the organisation (customer metadata
  `numo9_org`), set its subscription's `stripe_customer_id` (Django admin), then
  `billing_events --event evt_…`.
- **Any other error:** read it, fix the cause (data or code), then retry. Never mark an event
  processed by hand.

### 3. Paid, but the organisation is still read-only / past due

1. Stripe dashboard → Customer → the invoice is **paid**? If not, it isn't an incident (PAD
   debits take 3–5 business days; the organisation keeps access while `processing`).
2. `billing_events` — the `invoice.paid` event is there and processed? If unprocessed → section 2.
   If missing → resend it from the dashboard.
3. Processed but the state didn't move: an older event can't overwrite a newer one (U-04-T15) —
   compare the events' `created` times. Resend the subscription's latest
   `customer.subscription.updated` event; the entitlement cache is bumped on every event.

### 4. Dunning reminders not sent / read-only too early or late

- The beat job `numo9.billing.run_dunning` runs every 15 minutes (job dashboard). Not running →
  check `beat` and the worker.
- Each step is recorded once (`billing.DunningReminder`); emails are in the email log
  (`kind` `dunning.day0` … `dunning.day7`). An email that failed to send is retried by the email
  task; see the notifications runbook in [Notifications and email](../architecture/notifications.md).
- Read-only is exact at `grace_until` even if the job is late (the entitlement engine reads the
  grace end). To give an organisation more time, Numo9 staff extend `grace_until` on its
  subscription (Django admin, audited) — never edit the status by hand.

### 5. Checkout or the billing page answers 503 "Billing isn't available"

`STRIPE_SECRET_KEY` is empty or wrong (also look for Stripe API errors in the logs), or Stripe is
down (status.stripe.com). Fix the key (secrets runbook) or wait; nothing is lost — no session was
created.

### 6. Refunds, disputes, invoices voided at Stripe

Done in the Stripe dashboard only. The `invoice.*` events update the Numo9 invoice mirror; a
dispute doesn't change access. A refund doesn't cancel the subscription — cancel it from the
organisation's billing page (or the dashboard: the `customer.subscription.deleted` event makes it
*cancelled*).

### 7. A subscription was deleted in the Stripe dashboard by mistake

The organisation is now *cancelled* (read and export only). Stripe can't undo a deletion: the
owner subscribes again from the billing page (Checkout), which links the new subscription to the
same customer and organisation. Data is never deleted by billing.

### 8. Downgrade didn't happen at the period end

The beat job `numo9.billing.apply_changes` moves scheduled downgrades in the period's last hour.
Check the job dashboard; a `billing.ScheduledChange` with `applied_at` empty past its
`effective_at` → run the job again from the console (idempotent). If the renewal already went
out at the old price, refund the difference in the dashboard and apply the change now.

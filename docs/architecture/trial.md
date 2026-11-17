# Free trial (U-05)

Every new organisation starts a free trial of a configurable package; reminders go out 7, 3 and 1
days before it ends and when it ends; converting keeps every record; one trial per Business
Number and per owner email.

## Trial settings (U-05-T01)

`entitlements.TrialConfig` — **one row** (`pk = 1`, database check
`entitlements_trial_config_single`): the package the trial gives (`package`, empty = the
`NUMO9_TRIAL_PACKAGE` setting, else every product — the entitlements engine's rule) and its length
(`days`, 1–90, default 30). `TrialConfig.current()` reads it (creating the default once). A draft
package is refused. The Platform Owner edits it in the console (U-06). Platform data (allow-listed
in `tenancy.checks.PLATFORM_MODELS`). `backend/tests/test_trial_config.py`.

## Trial registry (U-05-T02)

`entitlements.TrialRegistry` — one row per trial started: the organisation, when, and the
**normalised** Business Number (nine digits) and owner email it was started with. Partial unique
indexes `entitlements_trial_one_per_bn` and `entitlements_trial_one_per_email` (only non-empty
values) make the database refuse a second trial with the same BN or email, even when two sign-ups
race; check constraints refuse values that aren't normalised (9 digits; lower-case email). Empty
values never collide (no BN yet, no owner yet). Platform data, never shown to tenants.
`backend/tests/test_trial_registry.py`.

## Normalisers (U-05-T03)

`numo9.entitlements.trials`:

| Function | In | Out |
|---|---|---|
| `normalise_bn` | `123 456 782`, `123-456-782`, `123456782RT0001`, `123456782 rt 0001` | `123456782` — the nine digits, program account suffix (RT, RP, RC, RZ…) dropped; `""` when not nine digits with a valid check digit |
| `normalise_email` | `  Dana+numo9@Refined.CA ` | `dana@refined.ca` — trimmed, lower-case, plus-addressing stripped; `""` when not an address |

`backend/tests/test_trial_normalisers.py` (table tests).

## Starting a trial (U-05-T04)

`trials.start_trial(organisation)` — a `trialing` `Subscription` of the configured package
(`TrialConfig`), ending at **23:59:59 organisation-local time on the last day** (the start day is
day 1; `trial_end(start, days, time_zone)`), stored in UTC. Computed on the local calendar, so a
DST change during the trial (spring forward in March, fall back in November) never moves the end
off local 23:59:59. Saving the subscription mirrors `trial` on `Organisation.status`. An
organisation that already has a current subscription keeps it. `trial_days_left(subscription)`
counts whole days on the organisation's calendar (0 on the last day).
`backend/tests/test_trial_start.py` — DST fixtures in Toronto (fall back, spring forward), Regina
(no DST), St. John's (half-hour zone).

## Every new organisation starts a trial (U-05-T05)

`start_trial` is called where organisations are created, in the same transaction:

- the owner's sign-up, organisation path (`accounts.forms.SignupForm.signup`);
- `POST /api/v1/organisations` — a signed-in user creating their own organisation, **or an
  accountant creating one for a client** (the owner is invited later).

The accountant sign-up path creates a practice — practices are free, no trial.
`backend/tests/test_trial_hooks.py`.

## One trial per BN and per owner email (U-05-T06)

`start_trial` records the trial in the registry with the organisation's BN (from any BN or program
registration, normalised) and the owner's email (normalised; the sign-up passes it). A BN or email
that already had a trial raises `TrialAlreadyUsed` (a `ValidationError`, code
`trial_already_used`, `field` = `bn` or `email`) and **nothing is created**; two concurrent trials
with the same value are settled by the registry's unique indexes.

| Where | Answer |
|---|---|
| Sign-up, organisation path | form error on `email`, code `trial_already_used` (allauth 400) — checked before anything is created |
| `POST /api/v1/organisations` | `409 entitlements.trial_already_used` with `field`; the Platform Owner (`platform.console.view`) also gets `existing_organisation`, the **masked** name of the organisation that used it (`Ma*** Le*** Su*** Lt***`); nobody else does |
| A BN entered after the trial started (`TaxRegistration` save) | checked then (`pre_save`): another organisation's trial with that BN → `ValidationError` `trial_already_used` (the settings API answers 400); otherwise stored on the trial |

`backend/tests/test_trial_duplicates.py`.

## Reminders (U-05-T07)

The platform job `numo9.entitlements.trial_reminders` (beat **hourly** at :13 — organisations'
days start at different UTC hours) emails each owner the `trial_reminder` system message (A-07,
owner's language: organisation, days left, local end date, link to the subscription page):

| Milestone | When |
|---|---|
| 7, 3, 1 | the trial has 7 / 3 / 1 days left or fewer, on the organisation's calendar (the latest one reached: a job that missed runs never sends a burst of old reminders) |
| 0 | the trial ended (read-only, reason `trial_ended`) |

`entitlements.TrialReminder` (unique per subscription and milestone) makes it idempotent: exactly
one email per milestone per owner, however often or late the job runs. A converted trial (active)
gets nothing more. `backend/tests/test_trial_reminders.py` — the job run every hour through a whole
30-day Toronto trial across the DST change sends 7, 3, 1, 0 once each.

## Expiry (U-05-T08)

The platform job `numo9.entitlements.expire_trials` (beat every 5 minutes) ends every trial whose
end (local 23:59:59 on the last day) has passed: **read-only**, reason `trial_ended` — books
readable, export allowed, nothing deleted — and tells the owners at once (milestone 0).
`expire_trial` locks the subscription row (`SELECT … FOR UPDATE`) and re-reads it: a conversion
that committed first — even at 23:59 local — leaves it `active`, and the job skips it; a conversion
holding the lock makes the job wait, then skip. Meanwhile the entitlement engine already treats a
`trialing` subscription past its end as read-only (`trial_ended`), and an entitlement answer for a
trial is cached only until the trial's end.
`backend/tests/test_trial_expiry.py` — not before 23:59:59 local, after it read-only with data
intact and one day-0 email; converted at the last minute → skipped; a real two-connection race.

## Conversion (U-05-T09)

The first successful payment (`invoice.paid`, or a paid Checkout) moves the subscription to
`active` through the billing state table (`billing.subscriptions.apply_status`). When it was a
trial — running, or ended unpaid (read-only, `trial_ended`) — that is a **conversion**
(`trials.trial_converted`): only the subscription's status changes, **no business record is
touched**; the registry records `converted_at` once (a re-delivered event changes nothing), the
audit log gets `entitlements.trial.converted`, and the registered conversion checks run —
`register_conversion_check(check)`, where the founding-1,000 offer (U-08) adds its eligibility
check (trial organisations count toward the founding counter only from their first payment).
`backend/tests/test_trial_conversion.py` — row counts of every organisation-owned table identical
before and after; ended trials convert too.

## Trial chip and package comparison (U-05-T10)

The entitlements bootstrap (`GET /api/v1/o/<org>/entitlements`) answers `trial_ends_at` and
`trial_days_left` (whole days on the organisation's calendar, 0 = the last day) while the reason
is `trialing`, `null` otherwise. The header shows **`TrialChip`** (`frontend/src/entitlements`) to
every role (gap-41: the plan state is visible to all): "Trial — 12 days left" / "Trial — last
day" — neutral above 7 days, amber at 7 or fewer, red at 1 or 0; the words always carry the days
(never colour alone; token pairs from the A-10 contrast-checked palette). It opens a drawer:
when the trial ends, the package being tried, the packages compared (what each includes, the
trial's marked) from `GET /api/v1/o/<org>/package-features`, and *Choose a package* (subscription
page) for whoever may change it — "The organisation's owner chooses the package" for everyone else.
Tests: `frontend/src/entitlements/TrialChip.test.tsx` (thresholds, drawer, axe),
`backend/tests/test_trial_bootstrap.py`.

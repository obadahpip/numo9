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

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

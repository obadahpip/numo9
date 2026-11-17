# Bulk edit and bulk actions (V-03)

A practice selects many organisations in the directory and applies one action to all of them —
move to a group, add or remove tags, assign or unassign staff, change a *safe* setting, send a
message, export the list — previewed first, then run as **one background job with one outcome
per organisation** (never a silent partial failure).

## Models (V-03-T02)

| Model | Holds |
|---|---|
| `BulkJob` | practice, who started it, `action` (`group`, `tags`, `staff`, `settings`, `message`, `export`), `params`, `selection` (`{"ids": [...]}` or `{"query": {...}}` — the directory's search and filters), `status` (`preview` → `queued` → `running` → `completed` / `cancelled`), `total`, the A-08 `job_run`, the result file, timestamps and the cancel request |
| `BulkJobRow` | one per selected organisation (unique per job), `position`, `outcome` (`pending`, `succeeded`, `skipped`, `failed`, `cancelled`), `reason` code and `message`, `before` / `after` values, `processed_at` (set exactly when the outcome is final — a database check) |

Both are practice data (allow-listed in `tenancy/checks.py`), read only through the practice's
bulk API.

## Safe settings (V-03-T03)

`numo9.bulk.safe_settings.SAFE_SETTINGS` is the whitelist, in code; `clean_settings()` refuses any
other key (`400 bulk.unsafe_setting`) and validates each value (`400 bulk.bad_value`):

| Key | Value | Rule |
|---|---|---|
| `sales_terms` | `{type, days}` | A-05 terms type; 0–365 days, or day 1–31 for "of the month" types |
| `purchase_terms` | `{type, days}` | the same |
| `time_format` | `{value}` | `12h` / `24h` |
| `fiscal_year_end` | `{month, day}` | a real day of the month; organisations with posted (or reversed) journals are skipped: `fye_has_posted` |

Legal name, Business Number, currency, time zone, addresses and everything else stay one
organisation at a time.

## Preview (V-03-T04)

`numo9.bulk.preview.preview(user, practice, action, params, selection)` computes every change
**without writing** (no organisation data, no audit event, no bulk row — the test counts the SQL
writes: zero; an organisation without settings is previewed from defaults, not created):

- the **selection** is `{"ids": [...]}` (ticked rows, order kept) or `{"query": {...}}` — *select
  all matching* re-runs the directory's own `DirectoryQuery` on the server (search and filters),
  never a list of ids from the browser; at most 5,000 organisations;
- each organisation gets one line: `change` (before → after), `no_change`, or `skipped` with a
  reason — `no_access` (not in the user's directory: kept in the selection, never dropped),
  `no_permission` (the action's organisation permission, e.g. `organisation.settings.manage`),
  `not_served`, `fye_has_posted`, `no_recipients`;
- the answer has the total, the counts and the first 50 lines.

The actions (`numo9.bulk.actions`) each declare the practice permission checked once
(`practice.groups.manage` for group and tags, `practice.clients.assign` for staff,
`practice.directory.view` otherwise) and the organisation permission checked per row.

## Executor (V-03-T05)

`numo9.bulk.service`:

| Step | What happens |
|---|---|
| `create_job` | the action's practice permission, `clean` of the parameters, the preview; the `BulkJob` is stored as `preview` |
| `confirm` | the selection is resolved again, **one pending row per organisation** is created and the platform job `numo9.bulk.run` is started once (keyed by the bulk job; a second confirm answers `409 bulk.not_preview`) |
| `cancel` | sets `cancel_requested_at`; the executor stops before the next organisation — finished rows stay, the rest become `cancelled` (a job still in preview is cancelled at once) |
| `execute` | for each pending row, in order, **one transaction**: lock the row, skip it if an earlier attempt finished it, check again the directory access and permissions of the person who started the job, apply, write the outcome |

Because the change and the outcome commit together, a worker killed between rows or in the middle
of one leaves finished rows finished and the interrupted one untouched; the redelivered or retried
job (A-08) takes the pending rows — every organisation is changed exactly once. An exception in
one organisation rolls back only that organisation (`failed: error`, "Nothing was changed"); a
change already in place is `skipped: no_change`. The job ends `completed` (or `cancelled`) with
no pending row.

## Actions (V-03-T06)

| Action | Parameters | Practice permission | Per organisation | Before → after |
|---|---|---|---|---|
| `group` | `group`, `mode` `add` / `move` (leave the practice's other groups) / `remove` | `practice.groups.manage` | V-02 `add_organisation` / `remove_organisation` | group names |
| `tags` | `add`, `remove` (tag ids) | `practice.groups.manage` | V-02 `tag_organisation` / `untag_organisation` | tag names |
| `staff` | `member` (user id of a practice member), `mode` `assign` / `unassign` | `practice.clients.assign` | the organisation's practice assignment (direct access, A-01) | assigned staff names |
| `settings` | `settings` — safe settings only (T03) | `practice.directory.view` | `organisation.settings.manage` there; validated and saved (audited, A-05) | the setting values |
| `message` | `subject` (≤ 150), `body` (≤ 5,000) | `practice.directory.view` | notification `practice.message` (in-app + email, A-07) to the organisation's owners and admins; none → `skipped: no_recipients` | number of recipients |
| `export` | `format` `csv` / `xlsx` | `practice.directory.view` | the organisation's line (name, BN, status, groups, tags, staff) | the line |

`numo9.bulk.exports`: `export_file(job)` builds the export action's CSV (UTF-8 with BOM) or XLSX
from the succeeded rows; `results_csv(job)` lists every selected organisation with its outcome,
reason, message and before/after.

## API (V-03-T07)

| Method and path | Who | Answer |
|---|---|---|
| `POST /api/v1/practice/bulk` `{practice?, action, params, selection}` | directory view + the action's practice permission | `201 {job, preview}` — nothing changed yet |
| `GET /api/v1/practice/bulk/<id>` | the practice's members (directory view) | status, `total`, `done`, `percent`, `counts` per outcome, `export_ready` |
| `POST …/confirm` | the person who created it | `202` the job, queued (one row per organisation); `409 bulk.not_preview` if already applied or cancelled |
| `POST …/cancel` | the person who created it | the job, `cancel_requested` |
| `GET …/rows?outcome=&page=` | members | 100 a page, each with outcome, reason, message, before/after |
| `GET …/results.csv` | members | every organisation with its outcome |
| `GET …/export` | members | the export action's CSV/XLSX once completed (404 before) |

Status is **polled** (the progress drawer asks every second while the job runs); no server-sent
events are needed for a job of a few hundred organisations. Another practice's job is 404.

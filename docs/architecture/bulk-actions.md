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

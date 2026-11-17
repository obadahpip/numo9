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

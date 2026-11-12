# Audit log and history (A-04)

Every change to a business record is written to one append-only table, `audit_event`, with who
made it, from where, and the old and new value of every field that changed. The organisation's
audit log viewer, the record history drawer on detail pages and the CSV/XLSX/PDF exports all read
that table (gap-37: Xero keeps 7 days by default, shows no diffs and attributes system changes to
nobody; gap-44: system changes must be attributed).

## The table (A-04-T01)

`numo9.audit.models.AuditEvent`, table `audit_event`:

| Column | What it holds |
|---|---|
| `created_at`, `id` | Primary key. `id` comes from the sequence `audit_event_id_seq`; `created_at` is set by the audit service and is part of the hashed payload |
| `public_id` | Random UUID used in URLs (indexed, not unique — see *Partitioning*) |
| `organisation_id` | The organisation; empty for platform events (sign-ins) and practice events |
| `practice_id` | The practice, for practice events (practice staff invitations, practice roles) |
| `actor_kind` | `user`, `system` (a background job, a management command) or `impersonation` |
| `actor_user_id`, `impersonator_id` | The person; for `impersonation`, the platform staff member signed in as them (both required) |
| `actor_label` | The name shown in the log, as it was then: `Name (email)` or `System: <job name>` |
| `action` | `<app>.<model>.created` / `updated` / `deleted` / `restored`, or a named event (`auth.login.failed`) |
| `object_type`, `object_id`, `object_label` | The record: model label, public id, display name as it was then |
| `changes` | `{field: [old, new]}` for every field that changed; masked fields never in clear |
| `meta` | Extra facts (a failed sign-in's reason, a batch summary's counts) |
| `ip`, `user_agent`, `request_id` | Where the change came from |
| `batch_id` | The bulk operation the change belongs to |
| `prev_hash`, `hash` | The organisation's hash chain |

### Partitioning

The table is created partition-ready for S-06-T03, which turns it into a parent partitioned by
month on `created_at`:

- the primary key is `(created_at, id)` — PostgreSQL requires the partition key in every unique
  constraint (Django `CompositePrimaryKey`);
- no other unique constraint exists; `public_id` is a plain index;
- no foreign key points at the table;
- every index is a plain b-tree that is created on each partition.

### Reading it

`AuditEvent.objects` is the organisation-scoped manager of every business record (A-01-T04): it
only returns the active organisation's events. `AuditEvent.platform_events` reads every event,
including platform and practice events; it is used by the platform audit endpoint and the chain
verifier only.

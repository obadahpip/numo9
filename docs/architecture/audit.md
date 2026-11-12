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

## Append-only (A-04-T02)

Migration `audit.0002_append_only`:

1. **Privileges** — `UPDATE`, `DELETE` and `TRUNCATE` on `audit_event` are revoked from `PUBLIC`
   and from the role that runs the migrations (the table owner: the application role in staging
   and production). The application can only `INSERT` and `SELECT`.
2. **Trigger** `audit_event_append_only` (`BEFORE UPDATE OR DELETE`, for each row) raises
   `insufficient_privilege` with *audit_event is append-only*. It also stops roles that ignore
   privileges (superusers) or were granted too much by mistake, and it carries over to every
   partition when S-06-T03 partitions the table.

The model refuses too: `AuditEvent.save()` on a stored event and `delete()` raise
`AuditImmutable` before any SQL is sent. Bulk `QuerySet.update()` / `delete()` reach the database
and are refused there (`tests/test_audit_append_only.py`).

`TRUNCATE` is a table operation, not a row change: only a superuser can still empty the table (the
test runner does between transactional tests). Retention (≥ 6 years, CRA) is handled by dropping
whole monthly partitions once they are past retention (S-06), never by deleting rows.

## Writing events (A-04-T03)

### `record()`

`numo9.audit.service.record(action, *, obj=None, organisation=…, practice=None, changes=None,
meta=None, actor=None)` writes one event **in the caller's transaction** — if the change rolls back,
its event does too.

- `obj` fills the record's type (model label), id (public id) and label (`audit_label()` or
  `str()`); its organisation is the event's organisation unless one is given; otherwise the
  active organisation (`current_org()`).
- `changes` is `{field: [old, new]}`. Values are stored the way people read them: decimals as
  exact strings (`"1234.50"`), dates and times in ISO 8601, UUIDs as text, related records as
  `{"id": <public id>, "label": <name>}`. Text longer than 10,000 characters is cut and marked
  `{"truncated": true, "text": …, "length": n}`.
- `actor` is the user who made the change; A-04-T04 fills it from the request or job.

### `AuditedModel`

Business models inherit `numo9.audit.mixins.AuditedModel` **before** `OrgOwnedModel`:

```python
class Contact(AuditedModel, OrgOwnedModel):
    audit_masked = frozenset({"bank_account"})
    audit_exclude = frozenset({"search_vector"})
```

The row's audited fields are snapshotted when it is loaded (*pre*); `save()` runs the save and
the audit write in one transaction and compares with the saved values (*post*):

| What happened | Action | `changes` |
|---|---|---|
| New row | `<app>.<model>.created` | every non-empty field as `[null, value]` |
| Fields changed | `…updated` | `[old, new]` of each changed field (no change → no event) |
| `soft_delete()` | `…deleted` | — |
| `restore()` | `…restored` | — |
| `delete()` (rare) | `…deleted` | last values as `[value, null]` |

`save(update_fields=…)` compares the saved fields only. A row built with an existing primary key
(never loaded) is read from the database first. Bookkeeping fields (`id`, `public_id`,
`organisation`, `created_at`, `updated_at`, `created_by`, `deleted_at`) are never diffed. Bulk
`QuerySet.update()` and `bulk_create()` bypass `save()`: code that changes many rows records them
itself inside an audit batch (A-04-T06).

### Masked fields

SIN and bank details are never stored in a diff (Phase 0 business rule). A field is masked when it
is an `EncryptedField`, is listed in the model's `audit_masked`, or its name is one of
`numo9.audit.service.MASKED_NAMES` (sin, social_insurance_number, bank_account, institution_number,
transit_number, account_number, password, …) or contains *password*, *secret* or *token*. Its old
and new value are stored as `{"masked": true}`: the log shows that the field changed, never its
value. `record()` masks such names in hand-written `changes` too.

### Role and limit changes

The `rbac_changed` signal of A-03-T15 (role, assignment, approval-limit and access-request
changes) is stored by `numo9.audit.receivers.store_rbac_change`: the organisation's event, or a
practice event for practice roles, with the A-03 diff.

## Sign-in, 2FA and invitation events (A-02-T14)

`numo9.audit.auth_events` connects Django's and allauth's signals; the invitation service
(`numo9.tenancy.invitations`) calls `invitation_event()` at each step.

| Action | When | Log |
|---|---|---|
| `auth.login.succeeded` | signed in (after 2FA when used) | platform |
| `auth.login.failed` | wrong email or password; `meta.email` = the address typed, known or not | platform |
| `auth.login.locked` | refused because the address is locked (S-03-T07) | platform |
| `auth.logout` | signed out | platform |
| `auth.2fa.failed` | wrong 2FA or recovery code | platform |
| `auth.2fa.enabled` / `auth.2fa.disabled` | authenticator app added / removed | platform |
| `auth.recovery_codes.created` / `regenerated` / `removed` | recovery codes | platform |
| `tenancy.invitation.created` / `resent` / `revoked` / `accepted` | invitation flows (A-02-T09) | the organisation, or the practice for practice staff |

Sign-in and 2FA events are about a person, not an organisation: they have no organisation and are
read by platform staff in the platform audit log (A-04-T07). Their record is the user (`accounts.User`,
public id, email); a failed sign-in for an address without an account has no record id and the
typed address as its label. Passwords, codes and invitation tokens are never recorded. allauth
sends its 2FA signals after the change commits, so those events are written just after it.

## Who, from where: the audit context (A-04-T04)

`record()` never needs the actor, IP or device passed in: it asks
`numo9.audit.context.current_actor()`, which looks, in order, at

1. an explicit `audit_context(...)` block (scripts, impersonation flows, tests);
2. **a background job** (`numo9.jobs.runtime.current_job()`) — `actor_kind = system`,
   `actor_label = "System: <job name>"` (the task's `label`, gap-44), and in `meta.job` the run's
   id and task and, when a person started it, `started_by` (id and name);
3. **the request** (`AuditContextMiddleware`) — the signed-in user, read when the event is written
   (a sign-in during the request counts). When `request.audit_impersonator` is set (U-06), the
   event is `impersonation`: `actor_user` is the person signed in as, `impersonator` the platform
   staff member, and the label names both;
4. **a Celery task** that is not a job — `System: <task name>`;
5. otherwise — `System` (`System: manage.py <command>` for management commands).

An explicit `actor=` passed to `record()` wins over 2–5 for the person; IP, device and request id
still come from the context.

### Request id, IP and device

`AuditContextMiddleware` (after `AuthenticationMiddleware`, before the tenant middleware):

- **request id** — a well-formed `X-Request-ID` from the client or proxy (8–64 of
  `A–Z a–z 0–9 . _ -`) is kept, anything else replaced by a new random id; returned in the
  `X-Request-ID` response header and bound to every log line of the request (structlog
  `request_id`), so an audit event, its log lines and a support ticket can be matched;
- **IP** — `REMOTE_ADDR`, or with `NUMO9_TRUSTED_PROXY_COUNT = n` the *n*-th address from the right
  of `X-Forwarded-For` (Caddy in staging/prod: `1`). Addresses further left are written by the
  client and never trusted;
- **device** — the `User-Agent` (first 512 characters).

## Hash chain and `audit_verify` (A-04-T05)

Every organisation's events form one chain in `id` order; platform and practice events (no
organisation) form the platform chain. `numo9.audit.chain`:

```
prev_hash = hash of the chain's previous event   (GENESIS = 64 × "0" for the first)
hash      = SHA-256( prev_hash + "\n" + canonical JSON of the event )
```

The canonical JSON (`payload()`, version 1) holds every field the log shows — id, public id, time
(UTC, microseconds), organisation, practice, actor kind, user and impersonator (public ids),
label, action, record type/id/label, changes, meta, IP (canonical form), device, request id, batch
id — with sorted keys, compact separators and UTF-8, so a stored row always hashes to the same
value.

**Writing.** `record()` seals the event inside the caller's transaction: it takes a
transaction-scoped advisory lock on the chain (`pg_advisory_xact_lock(0x41554454, organisation
pk | 0)`), draws the next `id` from `audit_event_id_seq`, reads the chain's last hash and computes
the new one. Concurrent writers of one organisation take turns until each transaction ends, so the
chain follows commit order; other organisations are never blocked. A long transaction that writes
audit events holds its organisation's chain until it commits — keep such transactions short.

**Checking.** `python manage.py audit_verify [--organisation <public id>] [--quiet]` walks every
chain, prints `OK`/`BROKEN`, the number of events and the head hash, and reports each problem:

- `hash` — the event's content no longer matches its hash (the row was changed);
- `link` — its `prev_hash` is not the previous event's hash (an earlier event was removed, or an
  event was inserted).

It exits with code 1 when any chain is broken. Removing the newest events of a chain leaves no
broken link; compare the head (event count and hash) with an earlier run — the scheduled run and
its kept output arrive with monitoring (S-04).

## Bulk operations: audit batches (A-04-T06)

```python
from numo9.audit.batch import audit_batch

with audit_batch("Recode transactions", meta={"rule": str(rule.public_id)}) as batch:
    for line in lines:
        line.account = new_account
        line.save()          # each event carries batch.id
```

Every event written in the block — through `record()` or `AuditedModel` — gets the batch's id
(`batch_id`). When the block ends, one **summary event** is written with the same id:

| Field | Value |
|---|---|
| `action` | `audit.batch` |
| record | `audit.Batch`, the batch id, the label |
| `meta` | the caller's `meta` + `events` (count), `actions` (`{action: count}`), `types` (record types), `status` (`completed` / `failed`) |

So a 500-row operation is one batch: 500 row events and one summary (V-03 bulk edit and C-07
recode are its first users). Inside one transaction a failing block rolls back its events and
summary together; a block whose rows committed one by one (a step-committing job) still writes the
summary, with `status: "failed"`. Nested blocks join the outer batch. The viewer shows a batch as
its summary line with the rows behind it (`?batch=<id>`, A-04-T07).

## API (A-04-T07)

Organisation log — `audit.log.view` (Owner, Admin, Accountant delegate, practice Admin,
Accountant, Reviewer, Read-only staff; not Sales, Purchasing, Payroll, HR or Employee):

| Route (`/api/v1/o/<org>/audit/…`) | What |
|---|---|
| `GET events` | The global viewer's list, newest first, cursor pages |
| `GET events/<id>` | One event with full values (long text whole) and its hashes |
| `GET records/<type>/<id>` | One record's history over **every date** (the record history drawer); 404 when the record has no history in the organisation |
| `GET filters` | Filter choices: the people and record types that appear in the log (loose index scans — fast on millions of rows), and the verbs |

Platform log — `GET /api/v1/platform/audit/events`, `platform.audit.view` (Platform owner,
Platform support): every event, including sign-ins, 2FA and practice events, with the same
filters plus `organisation=<public id>`.

### The query object

`numo9.audit.query.AuditQuery.from_params(params, organisation)` reads the filters; `apply()`
returns the newest-first queryset that the list, the exports (A-04-T08) and every other consumer
page through — one query object, so an export holds exactly the screen's rows.

| Parameter | Meaning |
|---|---|
| `from`, `to` | Dates `YYYY-MM-DD` in the organisation's time zone, both included. **Default: the last 90 days** (today and the 89 days before). One bound alone keeps the other's default |
| `user` | User public ids, or `system` (several: repeat or comma-separate) |
| `type` | Record types (model labels) |
| `action` | Full actions (`role.created`) or verbs (`created`, `updated`, `deleted`, `restored`) |
| `object_type` + `object_id` | One record |
| `batch` | One bulk operation |
| `q` | Text in the record's name, the person's name or the action |
| `cursor`, `limit` | Page token from the previous page's `next`; 1–200 rows (default 50) |

**Cursor pagination** is a keyset on `(created_at, id)` descending (index
`audit_org_time_idx`): page 1,000 is as fast as page 1 and new events never shift a page. No
total count is computed (counting millions of rows on every page is what makes logs slow).

### Response

```json
{
  "results": [{
    "id": "…", "at": "2026-11-12T15:00:00-05:00",
    "action": "testapp.auditedinvoice.updated", "action_label": "Edited", "verb": "updated",
    "actor": {"kind": "user", "label": "Avery Owner (avery@refined.ca)", "user": {…}, "impersonator": null},
    "record": {"type": "…", "type_label": "Invoice", "id": "…", "label": "Invoice 101"},
    "changes": [{"field": "amount", "label": "Amount", "old": "100.00", "new": "120.50", "masked": false}],
    "meta": {}, "ip": "203.0.113.9", "device": "…", "request_id": "…",
    "batch_id": null, "is_batch_summary": false
  }],
  "next": "<cursor or null>",
  "range": {"from": "2026-08-15", "to": "2026-11-12", "default": true, "time_zone": "America/Toronto"},
  "viewer": {"locale": "en-ca", "time_format": "12h", "time_zone": "America/Toronto"}
}
```

Labels (`action_label`, `type_label`, field `label`) are translated (`numo9.audit.presenter`):
named actions have their own words ("Signed in", "Invitation sent", "Role edited"), others the
verb; record types and fields use the model's verbose names. In the list, text over 200
characters comes back cut (`{"truncated": true, "text": …, "length": n}`); the event's detail has
it whole. `viewer` carries the person's display preferences for the screen (A-04-T12).

## Exports: CSV, XLSX, PDF (A-04-T08)

`GET /api/v1/o/<org>/audit/export/<csv|xlsx|pdf>` with the viewer's filters — `audit.log.export`
(the same roles as `audit.log.view`). `numo9.audit.exports` builds the **same `AuditQuery`** as the
list and writes every row it returns, newest first, in keyset chunks: the file holds exactly the
rows the screen pages through (`tests/test_audit_export.py` compares them by event id). Events
written after the export started — including the export's own event — are not in it.

| Column | Content |
|---|---|
| Date and time | Organisation time zone, the person's language and 12/24-hour preference: `26 Oct 2026, 4:33 p.m.` / `26 Oct 2026, 16:33` / `26 oct. 2026, 16 h 33` — never "16:33PM" (`numo9.documents.formatting.format_datetime`, the same output as `formatDateTime` in `@numo9/ui`). In XLSX a real date-time cell |
| User | The actor label (`System: <job>` for jobs) |
| Action, Record type, Record | Translated labels and the record's name |
| Changes | `Amount: 100.00 → 120.50; Notes: (empty) → Net 30`; masked fields `Hidden` |
| IP address, Request ID | Where it came from |
| Event ID | The event's public id |

- **CSV** streams any number of rows, UTF-8 with a byte-order mark (Excel shows accents).
- **XLSX** (openpyxl, write-only) up to 1,000,000 rows; bold header.
- **PDF** (WeasyPrint, `audit/export.html` on the document baseline, Letter) up to 2,000 rows —
  beyond that `413 audit.export_too_large` asks to narrow the filters or choose CSV.
- Text that a spreadsheet would run as a formula (`=`, `+`, `-`, `@`, tab) is written with a
  leading `'` (CSV/formula injection).
- File name `audit-log_<organisation>_<from>_<to>.<ext>`; `Cache-Control: no-store`.
- Every export writes an `audit.log.exported` event (format and filters in `meta`).

Exports run in the request. Very large ones move to a background job with a result link (A-08)
when real volumes call for it.

## The audit log viewer (A-04-T09)

Settings → Audit log, `/o/<org>/settings/audit-log` (`frontend/src/audit/AuditLogScreen.tsx`):

- **Dates** — presets Today, Last 7 / 30 / 90 days, This month, This quarter, This fiscal year,
  Custom dates (From / To date pickers). **Last 90 days is the default** and is the API's own
  default, so the first request sends no dates. Ranges are calendar dates in the organisation's
  time zone and end today (`src/audit/presets.ts`; the fiscal year end defaults to 31 December
  until organisation settings (A-05) provide it).
- **Filters** — User (Everyone, System, or a person who appears in the log), Record types
  (several, ticked in a list), Action (created / edited / deleted / restored), Search (record,
  person or action). Filters apply on **Show**; **Reset filters** returns to the default.
  URL parameters (`?batch=`, `?object_type=&object_id=`, `?from=`…) open the screen filtered — the
  record history drawer and the bulk-operation summary link here.
- **List** — the `@numo9/ui` DataGrid (column chooser, density, search within the loaded rows):
  Date and time (the person's 12/24-hour preference, A-04-T12), User, Action, Record type,
  Record, Changes (how many fields and which). **Show older events** loads the next cursor page;
  the line under the grid says how many are shown and when every event of the range is.
- **Event drawer** — a row opens the event: when, who (with the platform staff member for
  impersonation, the background job and who started it for system changes), record type, IP,
  device, request id, event id and the **DiffViewer**; a bulk operation's summary offers to show
  its changes (`?batch=`).
- **DiffViewer** (`src/audit/DiffViewer.tsx`) — each field with *Before* and *After* in words, a −
  / + mark and red / green backgrounds: never colour alone. Masked fields read *Changed — the
  value is hidden for privacy*; empty values *(empty)*; cut values say their length.
- **Export** menu — CSV, Excel (XLSX), PDF links to `/api/v1/o/<org>/audit/export/<format>` with
  the screen's applied filters (`filterParams()` builds both query strings), so a file holds the
  rows listed.
- **Refused** — without `audit.log.view` the screen shows the "Why can't I?" panel (A-03-T14).

Tests: `frontend/e2e/audit-log.spec.ts` (filters reach the API and the export links, custom
dates, the drawer and DiffViewer, pages, refusal, 360 px, axe), `src/audit/presets.test.ts`.

## Record history drawer (A-04-T10)

`frontend/src/audit/RecordHistory.tsx` — the **History** button a detail page puts next to its
heading, and the drawer it opens:

```tsx
<RecordHistory org={org} type="contacts.Contact" id={contact.id} label={contact.name} />
```

The drawer reads `GET …/audit/records/<type>/<id>` (every date, newest first) and shows each
change: action, date and time (the viewer's 12/24-hour preference), who, and the DiffViewer.
**Show older changes** pages back; **Open in the audit log** opens the global viewer filtered to
the record. A record without history says so (the API's 404); a refusal shows the API's sentence.

Mounted today on the role editor for custom roles (system roles belong to no organisation). The
contact (B-01) and account (C-01) detail pages mount the same component when they are built —
`type` is the model label, `id` the public id.

Tests: `frontend/e2e/record-history.spec.ts`.

## View a record as of a date (A-04-T11) [EXTRA]

`GET /api/v1/o/<org>/audit/records/<type>/<id>/as-of?at=<YYYY-MM-DD | ISO date-time>` (default: now)
(`audit.log.view`) rebuilds the record from its history (`numo9.audit.asof.reconstruct`): the
events up to that moment are replayed oldest first, each `changes` entry setting its field to the
*new* value; `…deleted` marks the record deleted, `…restored` undoes it. A date means the end of
that day in the organisation's time zone.

| Field | Meaning |
|---|---|
| `state` | `[{field, label, value, masked}]` — the fields as they were |
| `exists` | Created by then and not deleted |
| `deleted` | Deleted at that moment (`state` = its last values) |
| `complete` | The history starts at the record's creation, so every field is known (records created before their model was audited show only the fields changed since) |
| `events_applied`, `last_event` | How many events were replayed, and the last one |

Masked fields stay hidden: the log never held their values. 404 when the record has no history in
the organisation.

**UI** — the record history drawer has a *View as of* date and **Show**: the record's name at the
end of that day and its fields, or *didn't exist yet* / *was deleted* / *history starts after it
was created*.

Tests: `backend/tests/test_audit_as_of.py` (the rebuilt state equals snapshots taken at the time,
before creation, delete/restore, end of day in the organisation's zone, isolation),
`frontend/e2e/record-history.spec.ts`.

## Times: the viewer's 12/24-hour preference (A-04-T12)

Every audit timestamp on screen goes through `frontend/src/audit/time.tsx` — `auditDateTime()` and
the `<AuditTime>` element — which call `formatDateTime` of `@numo9/ui` (A-10-T08) with

- the viewer's `time_format` (`12h` / `24h`, the A-02-T01 user preference) and the organisation's
  time zone, both sent by the API in `viewer` with every list and history page;
- the viewer's language.

| | 12 h | 24 h |
|---|---|---|
| en-CA | `5 Jan 2026, 4:33 p.m.` | `5 Jan 2026, 16:33` |
| fr-CA | `5 janv. 2026, 4 h 33 p.m.` | `5 janv. 2026, 16 h 33` |

The hour cycle and the day period always come from one formatter, so a 24-hour clock with
"PM" — Xero's "16:33PM" (gap-44) — cannot appear. The exports use the backend twin
(`numo9.documents.formatting.format_datetime`), which writes the same text.

Tests: `frontend/src/audit/time.test.tsx` — inline snapshots of every language × preference, the
organisation's time zone, the per-language default, a sweep over a whole day that never finds a
24-hour time with a.m./p.m., and snapshots of the `<time>` element and the DiffViewer text;
`backend/tests/test_audit_export.py::test_times_follow_the_persons_preference`.

## Tests (A-04-T13)

| What | Where |
|---|---|
| Export rows = screen rows (CSV, XLSX by event id; PDF by record) for several filters, every row beyond one page | `backend/tests/test_audit_export.py` |
| Append-only: raw `UPDATE`/`DELETE`, ORM bulk update/delete, the owner's privileges, an ordinary role, a role granted everything | `backend/tests/test_audit_append_only.py` |
| Masking end to end: SIN, bank account and a model-masked field are absent from the table, the list, the detail, the history, view-as-of, CSV, XLSX, PDF and the platform log | `backend/tests/test_audit_masking.py` |
| Performance: 1,000,000 events of one organisation (+ 200,000 of another); first page (default 90 days), a page after 2,000 rows, two-year range, user filter, record history and filter choices each under 1 s (about 20 ms on the CI database); the plan uses `audit_org_time_idx`, no sequential scan | `backend/tests/test_audit_performance.py` |
| Hash chain tamper detection, concurrency | `backend/tests/test_audit_chain.py` |

The performance test inserts its rows with `generate_series` (about 30 s in CI).

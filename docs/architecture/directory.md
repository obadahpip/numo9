# Organisation directory (V-01)

The accountant's home: every organisation the practice serves, searchable, filterable, sortable,
with saved views. UX: [Organisation directory — UX research brief](../design/directory-ux-brief.md).
Code: `backend/numo9/workspace/` (API, search, summary) and `frontend/src/directory/` (screen).

```mermaid
flowchart LR
  subgraph Sources
    O[Organisation] --- S[OrganisationSettings]
    R[TaxRegistration BN] --- M[Owner membership]
    Sub[Subscription / overrides] --- A[PracticeAssignment]
    P[Later-phase providers: GST/HST cycle, overdue, unfiled] --- T[V-02 tags]
  end
  Sources -- "signals → on commit" --> Refresh[summary.refresh_organisation]
  Nightly[nightly job rebuild_directory] --> Refresh
  Refresh --> D[(OrgDirectorySummary\npractice × organisation)]
  D --> Q[search.DirectoryQuery\nscope ∩ access resolver]
  Q --> API["GET /api/v1/practice/orgs"]
  API --> UI["/p/:practice/directory"]
  V[(SavedView)] --- VAPI["/api/v1/practice/views"]
  VAPI --> UI
```

## 1. The summary row (V-01-T02)

`OrgDirectorySummary` is a **derived read model**: one row per practice × organisation the practice
actively serves, with everything the directory searches, filters, sorts and counts. Nothing edits it
by hand.

| Column | Source |
|---|---|
| `name`, `legal_name`, `industry`, `province`, `fye_month`, `fye_day` | Organisation settings (A-05): display name (else the organisation's name), legal name, industry, physical province (else mailing), fiscal year end |
| `bn` | Registered BN (A-05 tax registrations), nine digits |
| `owner_name`, `owner_email` | The organisation's (earliest) owner membership |
| `package`, `status`, `trial_ends_at`, `payroll_enabled` | Entitlement engine (U-03): package code; organisation status mapped to *trial / paid / demo / read-only / archived* (active and grace → paid, cancelled → archived); a trialing subscription's period end; Payroll entitled |
| `gst_cycle`, `overdue_count`, `unfiled_count` | **Providers** registered by later phases (`summary.register_summary_provider`); empty / 0 until then |
| `tags` | The practice's tags (V-02 registers `summary.register_tags_provider` and calls `summary.tags_changed`) |
| `search_vector` | PostgreSQL `tsvector` (`simple` + `unaccent`): name, legal name, BN (weight A); owner name and email, tags (B); industry, province code and its English and French names (C) |

Indexes: GIN on `search_vector`, trigram (`gin_trgm_ops`) on `bn`, B-tree on (practice, name),
(practice, status) and organisation. The GIN/trigram indexes and the `unaccent`/`pg_trgm` extensions
are created on PostgreSQL only, so a throw-away SQLite database still migrates.

It is not an `OrgOwnedModel` (it is read across organisations, per practice): it is allow-listed in
`numo9.tenancy.checks.PLATFORM_MODELS`, and **every read goes through `search.directory_scope`**.

## 2. Keeping it current (V-01-T03)

- **Signals** (`workspace/signals.py`) on organisations, practice assignments, organisation settings,
  tax registrations, subscriptions, entitlement overrides, owner memberships and the owner's name or
  email schedule `summary.schedule_refresh(org)`: the organisation's rows are rebuilt **after the
  transaction commits**, once per organisation per transaction however many records changed. A
  change is visible as soon as its transaction commits (acceptance: < 5 s). A failing refresh is
  logged and never fails the user's save.
- **Nightly** `numo9.workspace.rebuild_directory` (beat 08:41 UTC) rebuilds every row and removes
  orphans, repairing any drift (a missed signal, a provider's late data). `manage.py
  rebuild_directory` does the same on demand (after an import or restore).
- An assignment switched off deletes its row; switched back on, the row returns.

## 3. Search, filters, facets (V-01-T04)

`search.directory_scope(user, practice)`: the practice's rows whose assignment is active, for a
practice-wide role (practice admin) all of them, otherwise only those where the user is assigned
staff (groups join with V-02) — **intersected with the access resolver** (A-01-T05), so an
organisation the user cannot open is never listed, matched or counted.

| Feature | Rule |
|---|---|
| Search `q` | Every word must match the start of a word (`maple sup`), accents and case ignored (`erable` → *Érable*); name, legal name, BN, owner, tags, industry, province (`quebec` → QC). A query of digits, spaces and dashes also matches the BN anywhere in its digits (`123 456` → `123456789`, trigram index). Results ranked (name/BN first) unless a sort is chosen |
| Filters | `package`, `status`, `province`, `fye` (month), `gst_cycle`, `payroll` / `overdue` / `unfiled` (`yes`/`no`), `tag`. Several values of one filter = any of them; several filters = all of them |
| Archived | Cancelled organisations are hidden unless `archived=include` or the status filter names `archived` |
| Facets | For each filter, each value's count **with every other filter applied**: choosing a value in a filter that had none selected narrows the list to exactly that count. Every status is always listed (zero counts dimmed); a chosen value stays listed even at 0 |
| Sort | Any column key, `-` for descending; empty text values sort last either way; ties by name |

Facets and counts are computed from **one slim read** of the searched rows (a practice's directory is
at most a few thousand small tuples), evaluated in Python with the same rules as the SQL filters;
the page itself is one ordered, sliced query. Three queries per request.

## 4. API (V-01-T05, T08)

`GET /api/v1/practice/orgs` — parameters and answer in the OpenAPI schema (`practice_orgs_list`):
`practice` (query or `X-Numo9-Practice`; may be omitted when the user has one practice), `q`, the
filters (repeatable), `archived`, `sort`, `page`, `page_size` (1–2,000), `columns`, `facets=0`.
The answer: `practice`, `count` (matching), `total` (in the directory), `page`, `page_size`, `pages`,
`columns`, `results` (`id` = organisation public id, `name`, plus the requested columns' fields,
including `package_name` and `trial_days_left`), `facets` (`value`, `label` in the request's
language, `count`).

| Situation | Answer |
|---|---|
| Not signed in | 401/403 |
| Unknown practice, not a member, no practice at all | 404 (the same answer) |
| Several practices and none named | 400 `workspace.practice_required` |
| Member without `practice.directory.view` | 403 `permission.denied` (every practice system role has it) |
| A refused parameter | 400 `workspace.bad_filter` / `bad_sort` / `bad_column` / `bad_page` with `field` |

Saved views — `GET/POST /api/v1/practice/views`, `PATCH/DELETE /api/v1/practice/views/<id>`: the
user's own named states (search and filters, shown columns in order, sort, density, opens by
default) per practice. Names unique per user and practice (case ignored), at most 50, one default.
Nobody else — not even the practice admin — lists, changes or deletes them (404). They live on the
server, so they follow the user after logout/login and on another device.

Neither endpoint is organisation-scoped (no `/o/<org>/` in the URL): both are on the tenant-sweep
exempt list (`^api/v1/practice/`), and `tests/test_workspace_isolation.py` (marker
`tenant_isolation`, run by the CI tenant-sweep job) sweeps random practice/staff/assignment graphs:
each user sees exactly their organisations, and searching the others' names or BNs finds nothing.

## 5. Performance (V-01-T06, T07)

- `manage.py seed_practice --orgs 2000 [--password …]` — a practice with 2,000 Canadian clients
  (valid BNs, provinces, fiscal year ends, owners, packages, statuses, staff with a share each);
  directory ready in about 40 s (acceptance < 2 min; `tests/test_workspace_seed.py` times it).
- `tools/perf/k6/directory-search.js` (`make perf-directory`) — 30 accountants with 0.5–2 s think
  time: first page with facets, word/accent/BN searches, filters, sorts, the full 2,000-row list and
  the go-to-organisation search; threshold p95 < 300 ms and no failures.

| Run (2,000 organisations, 2 vCPU, k6 on the same machine) | Directory p95 | Failures |
|---|---|---|
| 30 VUs, 0.5–2 s think time (acceptance scenario) | 164 ms | 0 |
| 1 VU, requests back to back (service time) | 92 ms | 0 |

Before the slim-read facets the same scenario measured p95 > 500 ms (12 queries per request).
`THINK=0` with many VUs is a saturation test of the machine, not of the directory. Rerun the
acceptance scenario on the staging server (ADR-0002) after each change to the directory queries.

## 6. The screen (V-01-T09…T15)

`/p/:practice/directory` (`frontend/src/directory/`), built from `@numo9/ui` only:

| Part | Behaviour |
|---|---|
| Grid (T09) | The shared `DataGrid` in **server mode** (`manual`): the server searches, filters and sorts; the grid virtualises up to 2,000 rows (only a screenful in the DOM), sticky header, status chips (*Trial 12 d*, Paid, Demo, Read-only, Archived), the organisation name links to its Home, an "Open in new tab" row action |
| Search (T10) | The grid's search box (`/` focuses it) asks the server **150 ms after the last key**; matches are highlighted with `<mark>` (`HighlightedText`: word starts, accents ignored; BN digits across spaces) |
| Filters (T11) | "Filters" (`F`) opens the panel: one `fieldset` per filter, each option with the server's facet count (zero options dimmed), "Show archived organisations"; active filters are removable chips |
| Columns and views (T12) | The shared `ColumnChooser` now also **reorders** (drag handle, or `Alt+↑/↓`, announced); the left rail lists the user's saved views (server-stored), "All organisations", "Save current view", and per view: Update with changes, Rename, Set as default, Delete (confirmed). The default view opens first |
| Keyboard (T13) | `/` search, `↓` from search into the rows, `↑/↓ PgUp/PgDn Home/End` move, `Enter` opens, `Ctrl/⌘+Enter` (or Ctrl/⌘+click) opens in a new tab, `F` filters. `Ctrl/⌘+K` anywhere opens **Go to organisation** (top bar slot, `GoToOrganisationSlot`): the same search, `↑/↓`, `Enter`, `Ctrl/⌘+Enter`, `Esc` |
| States (T14) | First run ("Create organisation" → creates a trial organisation for the practice via `POST /api/v1/organisations`; "Open demo" appears once U-07 provides the demo), no results ("Clear search and filters"), loading skeleton, error with Try again |
| i18n and a11y (T15) | Every string in `frontend/messages/*.json` (fr-CA placeholders until Phase 6); `role="grid"`, `aria-rowcount`, `aria-sort`, live result count, labelled regions; axe 0 serious/critical at 1280 and 360 px and in French |

Tests: `src/directory/*.test.tsx` and `packages/ui/src/data-grid/DataGridServer.test.tsx` (Vitest),
`e2e/directory.spec.ts` (Playwright: 2,000-row scroll ≈ 60 fps, BN typing, facet = result count,
saved view after logout/login, keyboard-only flow, axe; `@visual` snapshots of the five states).

## 7. Extension points for later deliverables

| Deliverable | Hook |
|---|---|
| V-02 groups and tags | `register_tags_provider`, `tags_changed(practice, orgs)`; group-based access in `directory_scope` (with the access resolver) |
| V-03 bulk actions | "Select all matching" sends the same query parameters (`api.parse_directory_params`) to the server |
| V-04 dashboards | Widgets return directory filter parameters for drill-down |
| G (GST/HST), D/E (invoices), K (filings) | `register_summary_provider` returning `gst_cycle`, `overdue_count`, `unfiled_count`, then `schedule_refresh(org)` on their own changes |

## Groups (V-02-T02)

`workspace.OrgGroup` — a practice's tree of groups of client organisations ("Toronto office →
Retail clients"), stored as a **materialised path** (`django-treebeard` `MP_Node`: `path`,
`depth`, `numchild`): a subtree or the ancestors are one indexed query, and a cycle can't be
represented. `workspace.OrgGroupMembership` files an organisation in a group (unique per group;
an organisation can be in several groups). Both are practice data (allow-listed in
`numo9.tenancy.checks`), never an organisation's records.

`numo9.workspace.groups` — `create_group(practice, name, parent=None)`, `rename_group`,
`move_group(group, parent | None)` (with its sub-groups), `add_organisation` /
`remove_organisation`, `groups_of(practice)` (tree order). Refusals are `GroupError` with a code:

| Code | Rule |
|---|---|
| `workspace.group.too_deep` | Depth 1–5: a sixth level, or a move that would put the moved subtree's deepest group at level 6. The database checks it too (`workspace_group_max_depth`) |
| `workspace.group.into_itself` | Not inside itself or one of its sub-groups |
| `workspace.group.other_practice` | Parent from the same practice only |
| `workspace.group.name_taken` | Unique among siblings, case and accents ignored (the same name under another parent is fine) |
| `workspace.group.name_required` / `name_long` | 1–80 characters |
| `workspace.group.not_served` | Only organisations the practice actively serves |

When a practice stops serving an organisation (assignment switched off or deleted) its
memberships in that practice's groups are removed; other practices' groups keep theirs.

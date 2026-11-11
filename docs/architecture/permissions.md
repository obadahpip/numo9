# Roles and permissions (A-03)

| | |
|---|---|
| **Deliverable** | A-03 · Roles & permissions (RBAC + approval limits), Phase 0 |
| **Code** | `backend/numo9/rbac/`, each app's `permissions.py` |

## Permission catalogue (A-03-T01)

Every permission Numo9 checks is declared in code, in the `permissions.py` of the app that owns
it, and registered in `numo9.rbac.catalogue.catalogue` when the apps load
(`RbacConfig.ready` imports every installed app's `permissions` module).

| Field | Meaning |
|---|---|
| `key` | stable dotted id, `<area>.<thing>.<action>` (2–4 lower-case parts), e.g. `organisation.members.invite`; stored in role permissions, so never renamed once released |
| `label` | gettext message — the translation key; shown in the role editor (EN/FR) |
| `module` | product area for grouping (`MODULES`, navigation order): home, sales, purchases, banking, accounting, tax, payroll, hr, inventory, reports, contacts, documents, settings, users, practice, platform |
| `risk` | `low` · `medium` · `high` · `critical` — what misuse could do (risk badges, care when granting) |
| `scope` | where it is checked: `organisation` (in one organisation — organisation roles, and the roles of a practice serving it), `practice` (in one practice), `platform` (Numo9 staff) |
| `owner_only` | not given by broad roles such as Admin (e.g. `organisation.close`) |

The registry refuses a malformed key, an unknown module and a key declared twice. Actions
`view` and `export` are read-only (what read-only roles get). Apps add their permissions as they
are built (contacts with B-01, chart of accounts with C-01, …).

```python
# numo9/<app>/permissions.py
from django.utils.translation import gettext_lazy as _
from numo9.rbac.catalogue import Permission, Risk, register

CONTACT_VIEW = register(Permission("contacts.contact.view", _("View contacts"), "contacts", Risk.LOW))
```

`manage.py permcat_export [--format json|csv|markdown] [--locale fr-ca] [--output FILE]` exports
the whole catalogue (key, label, module, risk, scope, owner-only).

Tests: `backend/tests/test_permission_catalogue.py`.

## Models (A-03-T02)

| Model | What | Rules (database constraints unless noted) |
|---|---|---|
| `Role` | a named set of permissions at one **scope**: `platform`, `practice` or `organisation` | **System roles** (`is_system`, seeded by Numo9, A-03-T03) have a `key`, belong to no tenant and are not editable; `(scope, key)` unique. **Custom roles** have no key and belong to one organisation (organisation scope) or one practice (practice scope); there are no custom platform roles; names unique per tenant, ignoring case |
| `RolePermission` | one catalogue key granted by a role | unique per role; the key must exist in the catalogue and fit the role's scope — organisation roles grant organisation permissions, practice roles practice **and** organisation permissions (in the organisations their practice serves), platform roles platform permissions (validated on save) |
| `RoleAssignment` | a role given to a user in an organisation, a practice, or — platform roles — everywhere | never both an organisation and a practice; unique per role, user and tenant; the tenant must match the role's scope and a custom role is used only in its own organisation/practice (validated on save) |
| `ApprovalLimit` | highest amount (CAD) a **user or a role** (exactly one) may approve for a document type — `journal`, `bill`, `purchase_order`, `pay_run` — in one organisation | an `OrgOwnedModel` (scoped, soft-deleted); `numeric(18,2)`, never negative; one live limit per user (or role) and document type |

The role that comes with a membership (`OrganisationMember.role`, `PracticeMember.role`) is the
system role with that key; it is not copied into `RoleAssignment`. `Role`, `RolePermission` and
`RoleAssignment` are on the platform-model allow-list (they hold no organisation business data);
`ApprovalLimit` is an organisation record.

Tests: `backend/tests/test_rbac_models.py`.

## System roles (A-03-T03)

15 system roles, defined in `numo9/rbac/system_roles.py` and seeded by migration
`rbac.0002_seed_system_roles`. Their keys are the membership roles of A-01, so
`OrganisationMember.role = "sales"` means the system role *Sales*. Names are stored in English
and shown translated by key.

Permission sets are **rules over the catalogue**, not fixed lists: when a later app declares
permissions (contacts, invoices, pay runs…) each system role receives the ones its rule selects.
The sync runs after every `migrate` (`post_migrate`) and from `manage.py sync_system_roles`; it
keeps each system role's set exactly equal to its rule (system roles are not editable — create a
custom role for anything else).

| Scope | Role (key) | Default permissions |
|---|---|---|
| platform | Platform owner (`platform_owner`) | every platform permission |
| platform | Platform support (`platform_support`) | console, jobs (view), audited sign-in as a user |
| practice | Practice admin (`practice_admin`) | every practice permission; every organisation permission except owner-only |
| practice | Accountant (`accountant`) | practice: view, staff list, create clients; organisations: everything except critical, users read-only |
| practice | Reviewer (`reviewer`) | practice: view, staff list; organisations: read-only plus approve / review actions |
| practice | Payroll specialist (`payroll_specialist`) | practice: view; organisations: payroll and HR (not critical), read-only reports / documents / contacts |
| practice | Read-only staff (`read_only`) | read-only practice and organisation permissions |
| organisation | Owner (`owner`) | every organisation permission |
| organisation | Admin (`admin`) | every organisation permission except owner-only (`organisation.close`) |
| organisation | Accountant delegate (`accountant_delegate`) | everything except critical, users read-only |
| organisation | Sales (`sales`) | sales and contacts (not critical); read-only reports and documents |
| organisation | Purchasing (`purchasing`) | purchases and contacts (not critical); read-only inventory, reports, documents |
| organisation | Payroll (`payroll`) | payroll (not critical); read-only reports and documents |
| organisation | HR (`hr`) | HR (not critical); read-only documents |
| organisation | Employee (`employee`) | the organisation's details (self-service comes with Phase 3) |

Every practice and organisation role includes `organisation.profile.view`. "Critical" and
"read-only" come from the catalogue (`risk`, actions `view`/`export`). Today the functional roles
(Sales … Employee) hold only `organisation.profile.view`: their modules declare permissions as
they are built, and the sync grants them.

Tests: `backend/tests/test_system_roles.py`.

## Resolver (A-03-T04)

`numo9.rbac.resolver.has_perm(user, organisation, key)` — whether the user may do an
organisation permission in an organisation. The user's set there is the **union** of:

1. as a **member**: the system role of `OrganisationMember.role` + organisation roles assigned in
   that organisation (custom roles);
2. through each **practice** actively assigned to the organisation that gives the user access
   (A-01-T05: practice-wide role, or assigned staff): the system role of `PracticeMember.role` +
   practice roles assigned in that practice.

No access → no permissions, whatever roles the user holds; inactive and anonymous users have none;
Django `is_staff`/`is_superuser` grant nothing. `has_practice_perm(user, practice, key)` and
`has_platform_perm(user, key)` answer for practice and platform permissions; asking a resolver
for another scope's key, or an unknown key, raises (programming error). Entitlements (U-03) will
intersect the set.

**Cache: one request.** `PermissionCacheMiddleware` opens a cache per request, so several checks
in one view query once; nothing is cached across requests — a removed role, membership or
assignment applies on the next request. Outside a request (jobs, scripts) every call reads the
database.

Tests: `backend/tests/test_permission_resolver.py` (truth table over member roles and practice
access, union, custom organisation and practice roles, no-access, practice and platform
permissions, cache scope).

## Declaring permissions on API views (A-03-T05)

Every method of every Numo9 API view declares the permission it needs, and
`numo9.rbac.drf.RequiresPermission` — the DRF default permission class — enforces it.

```python
class ContactList(APIView):
    permission_classes = [IsOrgMemberOrAssigned, RequiresPermission]

    @requires_permission("contacts.contact.view")
    def get(self, request, org): ...

class CsrfTokenView(APIView):
    required_permission = PUBLIC                     # every method; or {"GET": PUBLIC, "POST": AUTHENTICATED}
```

| Declaration | Allowed |
|---|---|
| `PUBLIC` | anyone, signed in or not (CSRF token, invitation preview) |
| `AUTHENTICATED` | any signed-in user — the view or its service checks the objects (own memberships, create a practice, invitation services) |
| organisation key | the active organisation must be accessible (else **404**, as for an unknown one), then `has_perm`; missing → **403** `permission.denied` naming the action ("You don't have permission to change organisation settings…") |
| practice key | the acting practice (else 404), then `has_practice_perm` |
| platform key | `has_platform_perm` |

`HEAD` follows `GET`; `OPTIONS` follows `GET` or needs a signed-in user. An undeclared method is
refused at runtime (403, logged on `numo9.rbac`). A method the view does not implement gets
DRF's `405` (A-03-T09: answering `403` there, before the organisation check, would let a caller
tell a foreign organisation's URL from its own).

**System check** (runs with every `manage.py` command, the test suite and CI's `check --deploy`):

| Id | Fails when |
|---|---|
| `rbac.E001` | a method of a DRF view in `ROOT_URLCONF` has no declaration |
| `rbac.E002` | a declaration names a key that is not in the catalogue |
| `rbac.E003` | the view's `permission_classes` don't include `RequiresPermission` |
| `rbac.E004` | a third-party DRF view is not on `settings.RBAC_EXEMPT_VIEWS` (path → reason; today only the OpenAPI schema view) |
| `rbac.E005` | a view that is not a DRF view is mounted under `/api/` (it would skip `RequiresPermission`), unless on `RBAC_EXEMPT_VIEWS` (A-03-T06) |

Today's endpoints declare `PUBLIC` (CSRF token, invitation preview) or `AUTHENTICATED` (own
organisations, create a practice or an organisation, invitation create/resend/revoke/accept —
their services check the targets); organisation-scoped endpoints arrive with their modules and
declare catalogue keys. django-allauth's authentication API (non-DRF) and the Django admin are
outside the check. Public views also list `AllowAny`, which only marks the OpenAPI operation as
open to signed-out callers.

Tests: `backend/tests/test_requires_permission.py`.

## CI gate: undeclared permission fails (A-03-T06)

The backend CI job runs, after the migration check:

1. **`python manage.py permission_check`** — one line per endpoint method with what it requires
   (catalogue key, `@public`, `@authenticated`), then every `rbac.E001`–`E005` problem with its
   hint; exit code 1 on any problem, so the job is red;
2. **the canary** — the same command on `tests.testapp.rbac_urls_ci_canary` (the project URLs plus
   one fixture view without a declaration) **must fail**; if it passes, the gate itself is broken
   and the step fails.

```text
$ python manage.py permission_check --urlconf tests.testapp.rbac_urls_ci_canary --quiet
FAIL rbac.E001: /api/v1/ci-canary/: GET on tests.testapp.rbac_api.CanaryUndeclared declares no required permission.
     hint: Decorate the method with @requires_permission('<catalogue key>') …
permission_check: 10 endpoint methods, 1 problem(s)
```

The same check also runs as a Django system check on every `manage.py` command and in the test
suite. Run `python manage.py permission_check` locally before opening a PR that adds endpoints.

Tests: `backend/tests/test_permission_ci_check.py` (project passes, canary fails — through
`call_command` and as a real process exit code —, non-DRF view under `/api/`, CI workflow wiring).

## Approval limits (A-03-T07)

`numo9.rbac.approvals.assert_can_approve(user, doc_type, amount, *, organisation=None, exclude=())`
— raises `ApprovalLimitExceeded` unless the amount (a `Decimal` in CAD, the base currency) is
within the user's **effective limit** for the document type (`journal`, `bill`,
`purchase_order`, `pay_run`) in the organisation; returns that limit otherwise.

| Rule | |
|---|---|
| Limits that apply | the user's own `ApprovalLimit` + the limits of every role they hold in the organisation: membership system role, assigned organisation roles, system practice roles through a serving practice (`resolver.organisation_roles`) |
| Effective limit | the **lowest** of those — a role limit tightens a user's own limit, never widens it (Phase 0 plan: `min(user limit, role limit)`) |
| No limit | no approval (`approval.no_limit`) — owners included; limits are explicit |
| No access | no limit, whatever rows exist (A-01-T05) |
| Currency | compared in CAD; callers convert foreign amounts first. Floats are refused (`TypeError`), negative / NaN / infinite amounts too (`ValueError`) |
| Freshness | read from the database on every call — a limit or role changed mid-action applies at commit |
| Organisation | the active one (`org_context`); pass `organisation=` outside a request; never another organisation than the active one |

The refusal is a `403` API error, `approval.limit_exceeded` ("This bill is for $5,001.00, above
your approval limit of $5,000.00. Ask Avery Owner, Zoe Admin to approve it.") or
`approval.no_limit`, with the **next eligible approvers** — people with access whose effective
limit covers the amount, by name; the refused user and `exclude` (the document's creator, for
segregation of duties) are left out — named in the message (first 3) and listed in the body:

```json
{"detail": "…", "code": "approval.limit_exceeded", "doc_type": "bill", "amount": "5001.00",
 "limit": "5000.00", "approvers": [{"id": "<user public id>", "name": "Avery Owner", "limit": "100000.00"}]}
```

`effective_limit()`, `can_approve()` and `eligible_approvers()` answer the same questions without
raising. The service checks amounts only; each module checks its approve permission itself.
Users now carry a random `public_id` (accounts migration `0002`) used for them in APIs.

Tests: `backend/tests/test_approval_limits.py` (gap-25: a $5,000 limit blocks a $5,001 bill).

## Segregation of duties (A-03-T08)

`numo9.rbac.duties.assert_not_creator(user, obj, *, fields=("created_by",), record=None)` —
where a workflow requires it ("approver ≠ creator": bills, purchase orders, pay runs, tax
filings), the person who created a record may not approve it. Callers decide where the rule
applies.

- The creator is `obj.created_by_id` (every `OrgOwnedModel` has it) — no query; `fields=` checks
  several people fields (e.g. `("created_by", "submitted_by")`).
- No creator (system-created: imports, seeders, jobs) → anyone may approve.
- Refusal: `SelfApprovalRefused`, a `403` API error `approval.self_approval` — "You created this
  bill, so someone else has to approve it." (`record=` names the document; default: the model's
  verbose name); the body adds `field`.
- A field the object does not have raises `TypeError` (programming error).
- `is_creator()` / `creators()` answer without raising; pass `creators(obj)` as `exclude=` to
  `assert_can_approve` so the creator is never suggested as the next approver.

Tests: `backend/tests/test_segregation_of_duties.py`.

## API: roles, assignments, approval limits, catalogue (A-03-T09)

All under `/api/v1/`; organisation routes are `o/<org>/…` (organisation public id; not
accessible → `404`). Documented in the OpenAPI schema (`/api/schema/`).

| Route | Method | Permission | What |
|---|---|---|---|
| `permissions/catalogue` | GET | signed in | every permission (key, label, module, risk + label, scope, owner-only, read-only) and the modules in order, in the request's language |
| `o/<org>/roles` | GET | `roles.role.view` | system organisation roles, the organisation's custom roles, then the system practice roles (not assignable here; limits may name them) — each with permissions, `editable`, `assignable`, `holders` |
| `o/<org>/roles` | POST | `roles.role.manage` | create a custom role: `name`, `description`, `permissions`, `copy_from` (any role's id) |
| `o/<org>/roles/<role>` | GET · PATCH · DELETE | view · manage | PATCH `name` / `description` / `permissions` (the complete new set); system roles → `409 roles.system_role`; DELETE refused while anyone holds it (`409 roles.in_use`), removes its approval limits |
| `o/<org>/members` | GET | `organisation.members.view` | people with access: members (main role + custom roles) and staff of serving practices (practice + practice role + custom roles) |
| `o/<org>/members/<user>/roles` | POST | `roles.assignment.manage` | `{role}`: a system organisation role **replaces** a member's main role; a custom role is **added** (201; 200 if already held) |
| `o/<org>/members/<user>/roles/<role>` | DELETE | `roles.assignment.manage` | take a custom role away; the main role can only be replaced (`409 roles.main_role`) |
| `o/<org>/my-permissions` | GET | `organisation.profile.view` (every role) | the signed-in user's permissions here — screens show only the actions that work (A-03-T11) |
| `o/<org>/invitations` | GET | `organisation.members.view` | pending user/owner invitations (sending them: `POST /api/v1/invitations`, A-02-T09) |
| `o/<org>/approval-limits` | GET · POST | `roles.limit.view` · `roles.limit.manage` | live limits; create `{doc_type, max_amount, user | role}` (one per person/role and type: `409 limits.duplicate`) |
| `o/<org>/approval-limits/<limit>` | GET · PATCH · DELETE | view · manage | PATCH `{max_amount}`; DELETE is a soft delete (kept for retention) |
| `o/<org>/approval-limits/check?doc_type&amount&user` | GET | `roles.limit.view` | would that person be allowed to approve the amount? — `assert_can_approve` itself: `{allowed, limit, code, detail, approvers}` (A-03-T13) |

Rules (`numo9/rbac/services.py`), whoever calls them:

- **No escalation** — you can only put into a role, or give someone a role with, permissions you
  hold yourself here (`403 roles.grant_exceeds_own`, body `permissions`: the missing keys). An
  admin can't create a role with `organisation.close` or make someone an owner; editing keeps
  permissions already in a role but can't add ones you lack.
- **Custom roles** grant organisation permissions only (`400 roles.permission_scope`), names are
  unique per organisation ignoring case (`409 roles.name_taken`); another organisation's role is
  unknown (`404` / `400`).
- **Main role** — each member has exactly one (their membership role); the last active owner
  keeps it (`409 roles.last_owner`). People who work here through a practice have no main role
  (`400 roles.not_a_member`) and can get custom roles; practice roles are given by the practice
  (`400 roles.not_assignable`).
- People are referred to by `User.public_id`, never the database id.

Tests: `backend/tests/test_rbac_api.py`; the tenant sweep covers every new organisation route.

## Permission matrix test (A-03-T10)

`backend/tests/test_rbac_matrix.py` checks **every role × every endpoint × every method**, all
generated:

- endpoints — every method of every Numo9 API view in `ROOT_URLCONF` with its declaration (the
  same walk as `permission_check`, A-03-T06);
- roles — the 15 system roles (organisation roles as members, practice roles as assigned staff
  of a serving practice, platform roles as platform assignments), a custom organisation role
  holding exactly the endpoint's permission, and a signed-out visitor;
- expected — from the catalogue rules: allowed exactly when the role's permission set contains
  the key (`PUBLIC`: everyone; `AUTHENTICATED`: every signed-in user).

A refusal must be `403 permission.denied` (`401`/`403` signed out; platform staff get `404` for
organisation endpoints — they are not in the organisation); an allowed call must get past the
check and never fail with a server error. Today: 24 endpoint methods × 17 subjects = 408 cases,
plus guards that the matrix covers every endpoint and every system role, that each organisation
key splits the roles, and that no practice-scope endpoint appears without extending the matrix.
New endpoints and permissions join the matrix by themselves; a mutation that grants one key to
everyone fails 30 cases.

## Users and roles screen (A-03-T11)

`/o/<org>/settings/users-roles` (`frontend/src/settings/users-roles/`), tab **Users**:

- loads `my-permissions` first: without `organisation.members.view` (and `roles.role.view`) the
  screen is the permission refusal panel; an organisation the user can't access looks unknown
  (404 panel);
- the people table — name and email, **role chips** (main role "Purchasing (main role)", the
  practice role of practice staff, custom roles with a × to take them away), access ("Member" or
  "Through Profitex (Accountant)");
- **Give a role** (needs `roles.assignment.manage`): a dialog with the main roles (members only;
  replaces the current one) and the custom roles not yet held; practice roles are never offered;
  a refusal shows the API's own sentence (e.g. `roles.grant_exceeds_own`, `roles.last_owner`);
- **Invite a user** — email + main role through the A-02 invitation API
  (`POST /api/v1/invitations`, kind `organisation_user`); pending invitations are listed below
  the table with role, inviter and expiry;
- a person who may only look sees no buttons; success is a toast naming the person and role.

Tests: `frontend/e2e/users-roles.spec.ts` (Playwright, 360 and 1280 px, axe): give a custom
role and take it away, a main role replaces the main one, refusal reason, invite, read-only,
not accessible.

## Role editor (A-03-T12)

Settings → Users and roles → **Roles** lists the organisation roles (system roles first, then
custom ones) with a *System role* / *Custom role* badge, how many people hold each one and how
many permissions it has; **New role** and **Copy <role>** open the editor at
`/o/<org>/settings/users-roles/roles/new[?copy=<role>]`; `/roles/<id>` opens a role.

The editor (`frontend/src/settings/users-roles/RoleEditor.tsx`):

- **name**, optional description, **Copy from role** (replaces the ticked set with that role's
  permissions, then adjust);
- the **permission matrix by module** (catalogue order and module names from
  `GET /permissions/catalogue`), one fieldset per module with **Everything in <module>**, each
  permission with its label, key, **risk badge** (low neutral · medium info · high warning ·
  critical danger, the word always shown) and *Owners only by default*; only organisation
  permissions are listed — what a custom organisation role can give;
- **search** across label, key, module and risk;
- "N of M permissions selected"; **Save role** (POST / PATCH with the complete set) returns to
  the Roles tab with a status line; **Delete role** only when nobody holds it (otherwise the
  editor says how many people do);
- permissions the editor doesn't hold are disabled ("You don't have this permission, so you
  can't give it") — the API refuses them too (no escalation);
- system roles open read-only with **Copy into a custom role**.

Tests: `frontend/e2e/role-editor.spec.ts` with the real catalogue and roles list
(`frontend/e2e/fixtures/`, generated from the API): creating a role by copy + search + tick +
save takes well under a minute (asserted < 60 s), module grouping and risk badges, select-all,
no-escalation, read-only system role, edit + delete at 360 / 1280 px, axe.

## Approval-limit editor (A-03-T13)

Settings → Users and roles → **Approval limits** (`LimitsPanel.tsx`):

- one table per document type (manual journals, bills, purchase orders, pay runs): each limit's
  person — or "Everyone with <role>" — and amount in CAD (`formatMoney`); an empty type says
  "No limits yet, so nobody can approve bills.";
- **Add a limit** (needs `roles.limit.manage`): document type, a person or a role (organisation
  roles and the system practice roles), amount with the currency input (forgiving: `5,000`,
  `$5 000,00`); **Change** / **Remove** per row; the API's refusals (duplicate, validation) are
  shown in place;
- **Verify an amount** — document type, person, amount → the server's `assert_can_approve`
  answer, word for word ("This bill is for $5,001.00, above your approval limit of $5,000.00.
  Ask Avery Owner to approve it." / "Sam Patel can approve this: their limit is $5,000.00.").
  The explanation above the tables says the lowest limit applies and no limit means no approval.

Saved and enforced: `backend/tests/test_rbac_api.py::test_limit_saved_through_the_api_is_enforced_by_the_check`
saves limits through the API and checks them through the same service the documents use;
`frontend/e2e/approval-limits.spec.ts` covers the screen (save, check, role limit, change,
remove, validation, view-only; 360 / 1280 px, axe).

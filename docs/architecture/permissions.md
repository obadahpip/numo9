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
refused at runtime (403, logged on `numo9.rbac`).

**System check** (runs with every `manage.py` command, the test suite and CI's `check --deploy`):

| Id | Fails when |
|---|---|
| `rbac.E001` | a method of a DRF view in `ROOT_URLCONF` has no declaration |
| `rbac.E002` | a declaration names a key that is not in the catalogue |
| `rbac.E003` | the view's `permission_classes` don't include `RequiresPermission` |
| `rbac.E004` | a third-party DRF view is not on `settings.RBAC_EXEMPT_VIEWS` (path → reason; today only the OpenAPI schema view) |

Today's endpoints declare `PUBLIC` (CSRF token, invitation preview) or `AUTHENTICATED` (own
organisations, create a practice or an organisation, invitation create/resend/revoke/accept —
their services check the targets); organisation-scoped endpoints arrive with their modules and
declare catalogue keys. django-allauth's authentication API (non-DRF) and the Django admin are
outside the check. Public views also list `AllowAny`, which only marks the OpenAPI operation as
open to signed-out callers.

Tests: `backend/tests/test_requires_permission.py`.

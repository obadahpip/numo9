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

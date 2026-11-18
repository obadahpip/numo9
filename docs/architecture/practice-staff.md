# Practice staff management (V-05)

Who works for a practice, on which organisations, whether they still sign in, and what they
did — app `numo9.staff`.

## Staff list (V-05-T02)

`GET /api/v1/practice/staff?practice=…` (members of the practice with `practice.directory.view`;
another practice → 404) answers the practice's `dormant_days` and one line per member and per
**pending** staff invitation:

| Field | Meaning |
|---|---|
| `id`, `name`, `email` | the user (an invitation's id and email when pending) |
| `role`, `role_label` | practice role |
| `organisation_count` | organisations they can open in the practice's directory (direct, through groups, or every client for practice-wide roles); 0 when suspended |
| `last_login`, `joined_at` | last sign-in; when they joined |
| `status` | `active`; `dormant` — no sign-in for `Practice.dormant_days` (default 60) days or more, counted from joining when they never signed in (day 60 dormant, day 59 not); `suspended` (`PracticeMember.suspended_at`); `pending` (invitation not accepted, not expired — `invitation_expires_at`) |

## Assignments (V-05-T04)

| Method and path (`?practice=…`) | Who | Does |
|---|---|---|
| `GET /api/v1/practice/staff/<user>/assignments` | directory view | `{organisations: [direct], groups: [{name, role, depth}]}` |
| `PUT` / `DELETE …/staff/<user>/organisations/<org>` | `practice.clients.assign` | the member on the organisation's practice assignment (direct access); an organisation the practice doesn't serve → 404 |
| `PUT` / `DELETE …/staff/<user>/groups/<group>` `{role}` | `practice.groups.manage` | V-02 group assignment with its role (`accountant`, `reviewer`, `payroll_specialist`, `read_only`) |

Access changes on the **next request**: direct assignments bump the V-02 access cache on
`m2m_changed` of `assigned_staff`, group assignments already do. Direct changes write
`staff.organisation_assigned` / `staff.organisation_unassigned` in the organisation's audit log.
The editor (`src/staff/AssignmentEditor.tsx`, page `/p/:practice/staff/:member`) adds an
organisation by search, a group with a role, and removes either at once.

## Suspend, reinstate, remove (V-05-T05)

`numo9.staff.members` and `POST …/staff/<user>/suspend`, `POST …/reinstate`,
`DELETE …/staff/<user>` (`practice.staff.manage`):

- **suspend** sets `PracticeMember.suspended_at`: history and assignments stay, but every access
  path ignores a suspended member — A-01 `accessible_organisations` (practice-wide roles and
  direct assignments), the RBAC resolver (organisation roles through the practice, practice
  permissions), V-02 group access, the directory scope and the practice API (`resolve_practice`:
  404). Effective on the next request (the access cache is bumped);
- **reinstate** lifts it (`409 staff.not_suspended` when there is nothing to lift);
- **remove** deletes the membership with its direct and group assignments: every organisation
  reached through the practice answers 404 at once; the audit event lists the organisations;
- **last-admin guard**: the practice's last active practice admin can't be suspended or removed
  (`409 staff.last_admin`).

Audited in the practice's log: `staff.member_suspended`, `staff.member_reinstated`,
`staff.member_removed`.

## Dormant staff: daily job and widget (V-05-T06)

- **Rule** — dormant from day `Practice.dormant_days` (default 60) without a sign-in (never signed
  in: from joining); tested with a frozen clock (freezegun): day 59 → nothing, day 60 → alert.
- **Job** `numo9.staff.dormant_alerts` (Celery beat, daily 12:23 UTC): for every non-suspended
  dormant member, once per period of inactivity (`DormantAlert`, unique per member and
  `inactive_since`), an email to each **active** practice admin of the practice (in their
  language) with a link to the member's page; signing in again restarts the count.
- **Widget** — `GET /api/v1/practice/staff/dormant` (`practice.staff.manage`) answers the dormant
  members with their days; `DormantStaffWidget` on the practice home (`/p/:practice/directory`)
  lists them with one-click *Suspend access* (V-05-T05) and renders nothing for anyone else.

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

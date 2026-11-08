# Branch Policy

## Protected branch: `main`

`main` is protected on GitHub. The following rules are enforced (administrators included):

| Rule | Setting |
|---|---|
| Pull request required before merging | Yes — direct pushes to `main` are rejected |
| Required approving reviews | 1 |
| Dismiss stale approvals on new commits | Yes |
| Required status checks | Yes — branch must be up to date with `main`; CI check names are added in S-01-T08 |
| Linear history | Required (squash or rebase merge only; no merge commits) |
| Force pushes | Blocked |
| Branch deletion | Blocked |
| Conversation resolution before merge | Required |

## Branch naming rule

Every branch is cut from `main` and named:

```
<type>/<ID>-<short-name>
```

| Part | Allowed values |
|---|---|
| `<type>` | `feature`, `fix`, `improvement`, `refactor`, `chore`, `docs`, `hotfix` |
| `<ID>` | Deliverable ID from the phase plans, e.g. `S-01`, `A-02`, `U-04`. Bug fixes may use the issue number, e.g. `GH-123` |
| `<short-name>` | lowercase kebab-case, `a-z`, `0-9`, `-` only, max 40 characters |

Regex: `^(feature|fix|improvement|refactor|chore|docs|hotfix)/([A-Z]-[0-9]{2}|GH-[0-9]+)-[a-z0-9]+(-[a-z0-9]+)*$`

Examples:

- `feature/S-01-repo-ci-envs`
- `feature/A-02-auth-signup`
- `fix/GH-42-trial-reminder-timezone`

Rules:

1. One deliverable per branch (each deliverable card in `docs/phase_plans` is one branch).
2. Each atomic task within the deliverable is one or more commits prefixed with its task ID, e.g. `S-01-T02: ...`.
3. Release tags: `vX.Y.Z` (web/backend deploy), `mobile-vX.Y.Z` (reserved for mobile).

## Exceptions: automated dependency updates (S-01-T16)

Dependabot (`.github/dependabot.yml`) opens its own pull requests every Sunday 07:00 Amman time:

- Branches `dependabot/<ecosystem>/<dependency>` and commits prefixed `chore(deps):` are exempt from
  the naming rule and the task-ID commit prefix above.
- Everything else still applies: required status checks green, one approving review (Dependabot is
  the author, so the project lead can approve), rebase merge.
- Minor and patch updates arrive grouped, one PR per ecosystem (npm, pip, GitHub Actions, Docker,
  Compose); each major update arrives on its own and is reviewed against the phase plans before it
  is merged. Majors pinned by the plan (Next.js 15, React 19, Django 5.2 LTS, Python 3.12, Node 22,
  PostgreSQL 16, Redis 7) are ignored in the config.

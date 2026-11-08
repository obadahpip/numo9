# Contributing to Numo9

Every change follows the engineering workflow in `docs/AI CODING AGENT — MANDATORY ENGINEE.txt`:
**UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE**, applied to every deliverable and,
separately, to every atomic task. Nothing is reported complete until its acceptance criterion has
been observed.

## Local setup

| Need | Command |
|---|---|
| Dev stack (Postgres 16, Redis 7, MinIO, Mailpit, ClamAV, backend, frontend) | `make up` |
| JavaScript workspace (frontend, mobile) | `pnpm install` at the repository root |
| Backend virtualenv | `python -m venv backend/.venv` then `pip install -r backend/requirements/dev.txt` |
| Git hooks (ruff, mypy, eslint, prettier, gitleaks, fixers) | `pre-commit install` |
| Documentation site | `make docs` (build) · `make docs-serve` (preview on port 8001) |

## Work items

- One issue per atomic task, created with the **Atomic task** issue form (task ID, objective,
  current/expected behavior, dependencies, steps, acceptance criteria, testing, risks).
- Tasks come from the deliverable cards in `docs/phase_plans/` and are done in the order of their
  `Depends` column. A task larger than one to two hours is split before coding.
- `status.txt` at the repository root tracks every atomic task: ✅ only once acceptance was observed.

## Branches

Full policy: `docs/branching.md`.

- Cut every branch from `main`: `<type>/<ID>-<short-name>`, e.g. `feature/S-01-repo-ci-envs`.
  Types: `feature`, `fix`, `improvement`, `refactor`, `chore`, `docs`, `hotfix`.
- One deliverable per branch. `main` is protected: pull request, one approving review, all required
  checks green, branch up to date, linear history (rebase merge), no force pushes.
- Release tags `vX.Y.Z` deploy to staging; production needs the project lead's approval.

## Commits

```text
S-01-T17: MkDocs site skeleton, ADR template and CONTRIBUTING

- what changed and why, one bullet per logical change
- decisions a reviewer needs (alternatives rejected, trade-offs)

Verified: how the acceptance criterion was observed.

Co-Authored-By: Name <email>
```

- **Subject:** `<TASK-ID>: <imperative summary>`, at most 72 characters, no trailing full stop.
  Every commit belongs to exactly one atomic task; a task may have several commits.
- **Body:** wrapped at 72 characters; explains *why*, not only *what*; ends with how the change
  was verified.
- **Status updates:** a separate commit `<TASK-ID>: mark complete in status.txt`.
- **Trailers:** `Co-Authored-By:` for pair or AI-assisted work.
- **Not allowed:** merge commits, commits mixing tasks, secrets or personal data,
  "WIP"/"fix" subjects on `main`.
- **Exception:** Dependabot commits use `chore(deps): …` (see `docs/branching.md`).

## Pull requests

1. Push the branch and open a PR against `main`. The template asks for the Rule 10 report (problem
   understanding, task breakdown, plan, changes, testing results, remaining issues, final status)
   and the Rule 11 checklist. Fill every section; write "n/a" with a reason instead of deleting.
2. CI must be green: backend, frontend (including the `gap-02` crawl), i18n, tenant sweep, gap tests,
   docs, and the security jobs (pip-audit, npm audit, gitleaks, semgrep, Trivy).
3. One approving review, then **Rebase and merge**.
4. Never disable or skip a failing test to get a green build. A flaky test gets a `quarantine`
   label and an issue, never a silent skip.

## Code rules (summary)

- Every user-visible string is an i18n message with en-CA and fr-CA keys; Canadian spelling.
- Every new endpoint declares a feature key (U-01) and is covered by the tenant-isolation sweep (A-01).
- Every new screen uses the design system (A-10).
- No secrets in the repository; configuration comes from environment variables.

## Architecture decisions

Significant or hard-to-reverse decisions are recorded as ADRs in `docs/adr/` using the template
`docs/adr/template.md`.

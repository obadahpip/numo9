# Tag deploys (S-01-T12)

`git tag v0.0.1 && git push origin v0.0.1` runs `.github/workflows/deploy-staging.yml`:

1. **images** — builds the `runtime` targets of `backend/Dockerfile` and `frontend/Dockerfile` and
   pushes them to GHCR as `ghcr.io/<owner>/numo9-backend:<tag>` / `numo9-frontend:<tag>` (plus a
   `sha-<commit>` tag), with provenance and SBOM attestations.
2. **deploy** (GitHub Environment `staging`) — copies `infra/deploy/deploy.sh` to the host and runs
   it over SSH: pull → migrate (new tag) → switch services → health gate → record the tag.
   If the health gate fails, the services switch back to the previous tag and health is re-checked.
   If migrations fail, nothing is switched.

Migrations are not reversed on rollback, so every migration must be backward compatible with the
previous release (expand/contract). `django-migration-linter` enforces this in CI.

## Host contract (implemented by S-02-T06)

| Item | Requirement |
|---|---|
| App directory | `STAGING_APP_DIR`, owned by the deploy user; contains `docker-compose.staging.yml` |
| Images | Compose references `ghcr.io/<owner>/numo9-backend:${NUMO9_TAG}` and `…/numo9-frontend:${NUMO9_TAG}` |
| Migrations | Service `backend` can run `python manage.py migrate --noinput` via `docker compose run --rm backend …` |
| Health | `STAGING_HEALTH_URL` returns HTTP 200 with `ok` in the body (backend `/healthz` through Caddy) |
| Tools | Docker Engine + Compose v2, `curl`, `timeout` (coreutils), `bash` |
| State | `deploy.sh` keeps `.deploy/current_tag`, `.deploy/previous_tag`, `.deploy/history.log` in the app directory |

## GitHub Environment `staging` configuration

| Kind | Name | Value |
|---|---|---|
| Variable | `STAGING_SSH_HOST` | Host name or IP of the staging VM |
| Variable | `STAGING_SSH_USER` | Named deploy user (S-02-T10 access policy) |
| Variable | `STAGING_APP_DIR` | e.g. `/srv/numo9` |
| Variable | `STAGING_HEALTH_URL` | e.g. `https://staging.<domain>/healthz` |
| Variable | `STAGING_PUBLIC_URL` | Shown on the deployment in GitHub |
| Secret | `STAGING_SSH_PRIVATE_KEY` | Private key of the deploy user (ed25519) |
| Secret | `STAGING_SSH_KNOWN_HOSTS` | `ssh-keyscan -t ed25519 <host>` output, verified out of band |

A missing value fails the deploy job with a list of what is missing.

## Exit codes of `deploy.sh`

| Code | Meaning |
|---|---|
| 0 | Deployed and healthy |
| 1 | Failed and safe: rolled back to the previous tag, or aborted before switching (pull/migration failure) |
| 2 | Usage/configuration error (bad tag, missing `HEALTH_URL`, compose file missing, deploy already running) |
| 3 | Failed **and** the rollback is unhealthy, or there was no previous tag — needs a human |

## Local test

```bash
make images                              # builds numo9-backend:local
bash infra/deploy/tests/test_deploy.sh   # good deploy, upgrade, unhealthy → rollback, failed migration, bad tag
bash infra/deploy/tests/test_resolve_release.sh          # production tag rules (no Docker)
python3 infra/deploy/tests/test_deploy_prod_workflow.py  # approval-gate invariants of deploy-prod.yml
```

# Production deploys (S-01-T13)

`.github/workflows/deploy-prod.yml` promotes a release that is already live on staging. It never
rebuilds: production pulls the same `numo9-backend:<tag>` / `numo9-frontend:<tag>` images.

| Trigger | When | Result |
|---|---|---|
| `workflow_run` | "Deploy staging" finished **successfully** for a stable tag `vX.Y.Z` | A production run is queued and waits for approval |
| `workflow_run` | staging failed/cancelled, or a pre-release tag (`v1.2.0-rc.1`) | No production job (resolve only, `deploy=false`) |
| `workflow_dispatch` | Actions → Deploy production → Run workflow, `tag` = `vX.Y.Z` | Waits for approval, then deploys (re-deploy / roll forward / roll back to an older tag) |
| `workflow_dispatch` + `dry_run` | same, with "Dry run" ticked | Waits for approval, runs every check, **does not connect to production** |

Both triggers only work once the workflow file is on `main` (GitHub runs them from the default
branch).

Sequence:

1. **resolve** (no environment, no production secrets) — `resolve-release.sh` picks the tag and
   rejects anything that is not `vX.Y.Z`; the tag must be on `main`; its latest staging deployment
   must be `success`; both images must exist in GHCR.
2. **deploy** (GitHub Environment `production`) — **waits for the project lead's approval**. Only
   after approval are the `PRODUCTION_*` secrets released to the job. It then runs the same
   `deploy.sh` as staging (pull → migrate → switch → health gate → rollback on failure), with
   `COMPOSE_FILE=docker-compose.prod.yml` by default.

Only one production deploy runs at a time; later runs queue (never cancelled midway).

## GitHub Environment `production` protection

Created by `bash infra/deploy/configure-production-environment.sh [lead-login]` (repo admin, `gh`
authenticated). Re-runnable.

| Rule | Value |
|---|---|
| Required reviewers | project lead only (`obadahpip`) |
| Administrators bypass | not allowed |
| Self-review | allowed (the lead may approve a run they started) |
| Deployment branches | `main` only |

Required reviewers on a **private** repository need a paid GitHub plan (Pro/Team/Enterprise).

## GitHub Environment `production` configuration (set when S-02 provisions the host)

| Kind | Name | Value |
|---|---|---|
| Variable | `PRODUCTION_SSH_HOST` | Host name or IP of the production VM (Canadian region, ADR-001) |
| Variable | `PRODUCTION_SSH_USER` | Named deploy user (S-02-T10 access policy) |
| Variable | `PRODUCTION_SSH_PORT` | Optional, default `22` |
| Variable | `PRODUCTION_APP_DIR` | e.g. `/srv/numo9` |
| Variable | `PRODUCTION_HEALTH_URL` | e.g. `https://app.<domain>/healthz` |
| Variable | `PRODUCTION_COMPOSE_FILE` | Optional, default `docker-compose.prod.yml` |
| Variable | `PRODUCTION_PUBLIC_URL` | Shown on the deployment in GitHub |
| Secret | `PRODUCTION_SSH_PRIVATE_KEY` | Private key of the production deploy user (ed25519) |
| Secret | `PRODUCTION_SSH_KNOWN_HOSTS` | `ssh-keyscan -t ed25519 <host>` output, verified out of band |

A real deploy with a missing value fails with the list of what is missing; a dry run only warns.

## Dry run (acceptance of S-01-T13)

1. `bash infra/deploy/configure-production-environment.sh`
2. With the workflow on `main` and a tag already deployed to staging:
   `gh workflow run deploy-prod.yml -f tag=v0.0.1 -f dry_run=true`
3. The run shows **deploy to production — Waiting** with "Review deployments"; only the project
   lead can approve. After approval the job ends at "Dry run — stop before touching production".

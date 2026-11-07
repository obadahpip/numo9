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
```

#!/usr/bin/env bash
# Numo9 tag deploy with health gate and automatic rollback (S-01-T12).
# Runs ON the target host (staging/prod), inside APP_DIR. Invoked by .github/workflows/deploy-*.yml.
#
#   deploy.sh <tag>            e.g. deploy.sh v0.0.1
#
# Sequence: validate tag -> lock -> pull images -> run migrations (new tag) -> switch services to new
# tag -> health gate -> record tag.  If the health gate fails the services are switched back to the
# previously deployed tag and health is re-checked.  If migrations fail, nothing is switched.
#
# Migrations are NOT reversed on rollback: they must be backward compatible with the previous
# release (expand/contract), which django-migration-linter enforces in CI.
#
# Exit codes: 0 deployed and healthy; 1 deploy failed (rolled back, or aborted before switching);
#             2 usage/configuration error; 3 deploy failed AND rollback unhealthy (page someone).
#
# Environment:
#   HEALTH_URL       required  URL that must return HTTP 200 with "ok" in the body
#   APP_DIR          default: directory of this script
#   COMPOSE_FILE     default: docker-compose.staging.yml (relative to APP_DIR)
#   MIGRATE_SERVICE  default: backend
#   MIGRATE_CMD      default: python manage.py migrate --noinput
#   MIGRATE_TIMEOUT  default: 900 (seconds)
#   HEALTH_RETRIES   default: 30
#   HEALTH_INTERVAL  default: 5 (seconds)
#   PULL             default: 1 (set 0 to use local images; tests only)
#   SOPS_ENV_FILE    default: secrets.sops.env — decrypted to .env when present (S-03-T03)
#   SOPS_AGE_KEY_FILE default: /etc/numo9/age/host.key (this host's age private key)
set -euo pipefail

log() { printf '%s deploy: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }
die() { log "ERROR: $2"; exit "$1"; }

TAG="${1:-}"
[[ "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]] \
  || die 2 "usage: deploy.sh <tag>  (tag must look like v1.2.3 or v1.2.3-rc.1; got '${TAG}')"
[[ -n "${HEALTH_URL:-}" ]] || die 2 "HEALTH_URL is required"

APP_DIR="${APP_DIR:-$(cd "$(dirname "$0")" && pwd)}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.staging.yml}"
MIGRATE_SERVICE="${MIGRATE_SERVICE:-backend}"
MIGRATE_CMD="${MIGRATE_CMD:-python manage.py migrate --noinput}"
MIGRATE_TIMEOUT="${MIGRATE_TIMEOUT:-900}"
HEALTH_RETRIES="${HEALTH_RETRIES:-30}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-5}"
PULL="${PULL:-1}"

cd "$APP_DIR" || die 2 "APP_DIR not found: $APP_DIR"
[[ -f "$COMPOSE_FILE" ]] || die 2 "compose file not found: $APP_DIR/$COMPOSE_FILE"

STATE_DIR="$APP_DIR/.deploy"
mkdir -p "$STATE_DIR"
LOCK_DIR="$STATE_DIR/lock"
# mkdir is atomic: only one deploy at a time on this host.
mkdir "$LOCK_DIR" 2>/dev/null || die 2 "another deploy is running (remove $LOCK_DIR if stale)"
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

PREVIOUS_TAG="$(cat "$STATE_DIR/current_tag" 2>/dev/null || true)"

# Secrets (S-03-T03): when the workflow uploaded the SOPS-encrypted environment file, decrypt it
# to .env (mode 600, read by Compose) with this host's own age key. Never logged, never committed.
SOPS_ENV_FILE="${SOPS_ENV_FILE:-secrets.sops.env}"
if [[ -f "$SOPS_ENV_FILE" ]]; then
  export SOPS_AGE_KEY_FILE="${SOPS_AGE_KEY_FILE:-/etc/numo9/age/host.key}"
  command -v sops >/dev/null 2>&1 || die 2 "$SOPS_ENV_FILE present but sops is not installed"
  secrets_tmp="$(mktemp "$APP_DIR/.env.XXXXXX")"
  chmod 600 "$secrets_tmp"
  if ! sops decrypt --input-type dotenv --output-type dotenv "$SOPS_ENV_FILE" >"$secrets_tmp"; then
    rm -f "$secrets_tmp"
    die 1 "could not decrypt $SOPS_ENV_FILE with $SOPS_AGE_KEY_FILE; nothing changed"
  fi
  mv "$secrets_tmp" .env
  log "secrets: $SOPS_ENV_FILE decrypted to .env"
fi

compose() { NUMO9_TAG="$1" docker compose -f "$COMPOSE_FILE" "${@:2}"; }

healthy() {
  local attempt body
  for ((attempt = 1; attempt <= HEALTH_RETRIES; attempt++)); do
    if body="$(curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null)" && [[ "$body" == *ok* ]]; then
      log "health OK after ${attempt} attempt(s): $body"
      return 0
    fi
    sleep "$HEALTH_INTERVAL"
  done
  log "health FAILED after ${HEALTH_RETRIES} attempts: $HEALTH_URL"
  return 1
}

log "deploying $TAG (previous: ${PREVIOUS_TAG:-none}) from $APP_DIR/$COMPOSE_FILE"

if [[ "$PULL" == "1" ]]; then
  log "pulling images for $TAG"
  compose "$TAG" pull --quiet || die 1 "image pull failed for $TAG; nothing changed"
fi

log "running migrations with $TAG: $MIGRATE_CMD"
# shellcheck disable=SC2086  # MIGRATE_CMD is intentionally word-split into argv
if ! timeout "$MIGRATE_TIMEOUT" env NUMO9_TAG="$TAG" \
  docker compose -f "$COMPOSE_FILE" run --rm "$MIGRATE_SERVICE" $MIGRATE_CMD; then
  die 1 "migrations failed or timed out (${MIGRATE_TIMEOUT}s) for $TAG; services NOT switched (still ${PREVIOUS_TAG:-none})"
fi

log "switching services to $TAG"
compose "$TAG" up -d --remove-orphans

if healthy; then
  [[ -n "$PREVIOUS_TAG" ]] && echo "$PREVIOUS_TAG" >"$STATE_DIR/previous_tag"
  echo "$TAG" >"$STATE_DIR/current_tag"
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $TAG ok" >>"$STATE_DIR/history.log"
  log "deployed $TAG"
  exit 0
fi

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $TAG failed-health" >>"$STATE_DIR/history.log"
if [[ -z "$PREVIOUS_TAG" ]]; then
  die 3 "$TAG is unhealthy and there is no previous tag to roll back to"
fi

log "rolling back to $PREVIOUS_TAG"
compose "$PREVIOUS_TAG" up -d --remove-orphans
if healthy; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $PREVIOUS_TAG rollback-ok" >>"$STATE_DIR/history.log"
  die 1 "$TAG failed the health gate; rolled back to $PREVIOUS_TAG (healthy)"
fi
die 3 "$TAG failed the health gate and rollback to $PREVIOUS_TAG is ALSO unhealthy"

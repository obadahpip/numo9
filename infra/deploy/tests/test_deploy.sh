#!/usr/bin/env bash
# Local integration test for infra/deploy/deploy.sh (S-01-T12). Requires Docker.
#
#   make images                       # builds numo9-backend:local (runtime target)
#   bash infra/deploy/tests/test_deploy.sh
#
# Scenarios (images derived from numo9-backend:local):
#   v0.0.1  good                 -> deployed (no previous tag)
#   v0.0.2  good                 -> deployed, previous = v0.0.1
#   v0.0.3  starts but unhealthy -> health gate fails -> rolled back to v0.0.2 (exit 1)
#   v0.0.4  migrations fail      -> aborted before switching, v0.0.2 keeps serving (exit 1)
#   latest  invalid tag          -> usage error (exit 2)
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEPLOY="$HERE/../deploy.sh"
SOURCE_IMAGE="${SOURCE_IMAGE:-numo9-backend:local}"
REPO="numo9-deploytest-backend"
PORT="${DEPLOYTEST_PORT:-18080}"
WORK="$(mktemp -d)"
export DEPLOYTEST_PORT="$PORT"

failures=0
pass() { printf 'PASS  %s\n' "$*"; }
fail() { printf 'FAIL  %s\n' "$*"; failures=$((failures + 1)); }

cleanup() {
  (cd "$WORK" && NUMO9_TAG=v0.0.1 docker compose -f docker-compose.staging.yml down -v --remove-orphans >/dev/null 2>&1)
  docker rmi -f "$REPO:v0.0.1" "$REPO:v0.0.2" "$REPO:v0.0.3" "$REPO:v0.0.4" >/dev/null 2>&1
  rm -rf "$WORK"
}
trap cleanup EXIT

docker image inspect "$SOURCE_IMAGE" >/dev/null 2>&1 || { echo "missing $SOURCE_IMAGE — run 'make images' first"; exit 2; }

# Fixture images.
docker tag "$SOURCE_IMAGE" "$REPO:v0.0.1"
docker tag "$SOURCE_IMAGE" "$REPO:v0.0.2"
printf 'FROM %s\nCMD ["sleep", "infinity"]\n' "$SOURCE_IMAGE" | docker build -q -t "$REPO:v0.0.3" - >/dev/null
# v0.0.4: `manage.py migrate` exits non-zero (the web server itself would still start).
printf 'FROM %s\nRUN printf "import sys\\nsys.exit(\\"fixture: migration failure\\")\\n" > /app/manage.py\n' \
  "$SOURCE_IMAGE" | docker build -q -t "$REPO:v0.0.4" - >/dev/null

# Fake host app directory, shaped like the staging contract.
cp "$HERE/docker-compose.deploy-test.yml" "$WORK/docker-compose.staging.yml"

export APP_DIR="$WORK" PULL=0 HEALTH_URL="http://127.0.0.1:$PORT/healthz" HEALTH_RETRIES=15 HEALTH_INTERVAL=2

run_deploy() { bash "$DEPLOY" "$1" >"$WORK/last.log" 2>&1; echo $?; }
current_tag() { cat "$WORK/.deploy/current_tag" 2>/dev/null; }
running_image() {
  docker inspect -f '{{.Config.Image}}' "$(cd "$WORK" && NUMO9_TAG=x docker compose -f docker-compose.staging.yml ps -q backend)" 2>/dev/null
}
health_body() { curl -fsS --max-time 5 "$HEALTH_URL" 2>/dev/null; }

# 1) first deploy
rc=$(run_deploy v0.0.1)
if [[ "$rc" == 0 && "$(current_tag)" == v0.0.1 && "$(health_body)" == *ok* ]]; then
  pass "v0.0.1 deployed (exit 0, current_tag=v0.0.1, /healthz ok)"
else fail "v0.0.1: rc=$rc current=$(current_tag)"; cat "$WORK/last.log"; fi

# 2) upgrade
rc=$(run_deploy v0.0.2)
if [[ "$rc" == 0 && "$(current_tag)" == v0.0.2 && "$(cat "$WORK/.deploy/previous_tag")" == v0.0.1 \
      && "$(running_image)" == "$REPO:v0.0.2" ]]; then
  pass "v0.0.2 deployed (exit 0, previous_tag=v0.0.1, running $REPO:v0.0.2)"
else fail "v0.0.2: rc=$rc current=$(current_tag) image=$(running_image)"; cat "$WORK/last.log"; fi

# 3) unhealthy release -> rollback
rc=$(run_deploy v0.0.3)
if [[ "$rc" == 1 && "$(current_tag)" == v0.0.2 && "$(running_image)" == "$REPO:v0.0.2" \
      && "$(health_body)" == *ok* ]] && grep -q "rolled back to v0.0.2" "$WORK/last.log"; then
  pass "v0.0.3 unhealthy -> rolled back to v0.0.2 (exit 1, running $REPO:v0.0.2, /healthz ok)"
else fail "v0.0.3: rc=$rc current=$(current_tag) image=$(running_image)"; cat "$WORK/last.log"; fi

# 4) failing migrations -> no switch
rc=$(run_deploy v0.0.4)
if [[ "$rc" == 1 && "$(current_tag)" == v0.0.2 && "$(running_image)" == "$REPO:v0.0.2" \
      && "$(health_body)" == *ok* ]] && grep -q "services NOT switched" "$WORK/last.log"; then
  pass "v0.0.4 migrations fail -> aborted, v0.0.2 still serving (exit 1)"
else fail "v0.0.4: rc=$rc current=$(current_tag) image=$(running_image)"; cat "$WORK/last.log"; fi

# 5) invalid tag
rc=$(run_deploy latest)
if [[ "$rc" == 2 ]]; then pass "invalid tag 'latest' rejected (exit 2)"; else fail "invalid tag: rc=$rc"; fi

echo "--- deploy history ---"; cat "$WORK/.deploy/history.log" 2>/dev/null
if ((failures)); then echo "test_deploy: $failures failure(s)"; exit 1; fi
echo "test_deploy: all scenarios passed"

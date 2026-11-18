#!/usr/bin/env bash
# S-06-T09 — run the three k6 baselines and store their summaries under docs/perf/baselines/<date>/.
#
#   BASE_URL=http://127.0.0.1:8000 PASSWORD="$FIXTURE_PASSWORD" tools/perf/k6/run-baselines.sh
#
# Needs a scratch/staging stack with the fixture practice (make_fixture_practice --orgs 2000
# --lines 200 --password …) and NUMO9_PERF_ENDPOINTS=1 for the posting baseline. DURATION and VUS
# are passed through to every script. Exit status: non-zero when a threshold failed.
set -euo pipefail
cd "$(dirname "$0")/../../.."
OUT="docs/perf/baselines/${RUN_DATE:-$(date +%F)}"
mkdir -p "$OUT"
status=0
for script in directory-search contacts-list post-journal; do
  echo "== $script"
  k6 run --quiet -e BASE_URL="${BASE_URL:-http://127.0.0.1:8000}" -e EMAIL="${EMAIL:-fixture-admin@example.com}" \
    -e PASSWORD="${PASSWORD:?set PASSWORD}" -e DURATION="${DURATION:-60s}" ${VUS:+-e VUS="$VUS"} \
    --summary-export "$OUT/$script.json" "tools/perf/k6/$script.js" || status=1
done
echo "Summaries in $OUT"
exit $status

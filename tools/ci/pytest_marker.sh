#!/usr/bin/env bash
# Run the backend tests carrying one pytest marker (S-01-T11).
# "No tests collected" (pytest exit code 5) counts as a pass, so a job passes while its suite
# is still empty. Every other non-zero exit code fails the job.
#
#   tools/ci/pytest_marker.sh <marker> [extra pytest args...]
set -uo pipefail

marker="${1:?usage: pytest_marker.sh <marker> [pytest args...]}"
shift

cd "$(dirname "$0")/../../backend" || exit 2

"${PYTHON:-python}" -m pytest -m "$marker" "$@"
status=$?

if [ "$status" -eq 5 ]; then
  echo "pytest_marker: no tests marked '$marker' yet — passing (placeholder until the suite is wired)."
  exit 0
fi
exit "$status"

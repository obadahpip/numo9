#!/usr/bin/env bash
# Create/update the GitHub Environment "production" used by .github/workflows/deploy-prod.yml
# (S-01-T13). Run once by a repository admin; safe to re-run.
#
#   bash infra/deploy/configure-production-environment.sh [<lead-github-login>]
#
# Protection rules written:
#   - required reviewer: the project lead only (default: obadahpip); no other user or team;
#   - administrators cannot bypass the approval;
#   - self-review allowed (the lead may approve a run they started);
#   - deployments only from workflows running on branch main (workflow_run / workflow_dispatch
#     always run on the default branch), so a workflow edited on a feature branch cannot deploy.
#
# Host variables and secrets (PRODUCTION_*) are set separately when S-02 provisions the
# production host; see infra/deploy/README.md.
#
# Requires: gh (authenticated as a repo admin). Required reviewers on a private repository need a
# paid GitHub plan (Pro/Team/Enterprise); public repositories work on any plan.
set -euo pipefail
export MSYS_NO_PATHCONV=1

LEAD="${1:-obadahpip}"
REPO="${REPO:-obadahpip/numo9}"
ENV_NAME="production"
GH="${GH:-gh}"
command -v "$GH" >/dev/null 2>&1 || GH="/c/Program Files/GitHub CLI/gh.exe"

LEAD_ID="$("$GH" api "users/$LEAD" --jq .id)"
[[ "$LEAD_ID" =~ ^[0-9]+$ ]] || { echo "could not resolve GitHub user id for '$LEAD'"; exit 2; }

"$GH" api -X PUT "repos/$REPO/environments/$ENV_NAME" --silent --input - <<JSON
{
  "wait_timer": 0,
  "prevent_self_review": false,
  "can_admins_bypass": false,
  "reviewers": [{ "type": "User", "id": $LEAD_ID }],
  "deployment_branch_policy": { "protected_branches": false, "custom_branch_policies": true }
}
JSON

policies="$("$GH" api "repos/$REPO/environments/$ENV_NAME/deployment-branch-policies" \
  --jq '.branch_policies[] | "\(.type // "branch"):\(.name)"')"
if ! grep -qx 'branch:main' <<<"$policies"; then
  "$GH" api -X POST "repos/$REPO/environments/$ENV_NAME/deployment-branch-policies" \
    -f name=main -f type=branch --silent
fi

echo "environment '$ENV_NAME' on $REPO:"
"$GH" api "repos/$REPO/environments/$ENV_NAME" --jq '{
  reviewers: [.protection_rules[] | select(.type == "required_reviewers") | .reviewers[] | .reviewer.login],
  prevent_self_review: ([.protection_rules[] | select(.type == "required_reviewers") | .prevent_self_review][0]),
  can_admins_bypass,
  deployment_branch_policy
}'
"$GH" api "repos/$REPO/environments/$ENV_NAME/deployment-branch-policies" \
  --jq '[.branch_policies[] | "\(.type // "branch"):\(.name)"]'

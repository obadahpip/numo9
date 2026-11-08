#!/usr/bin/env bash
# Decide which release tag .github/workflows/deploy-prod.yml promotes to production (S-01-T13).
# Runs on the GitHub runner; writes tag / dry_run / deploy / reason to $GITHUB_OUTPUT (or stdout).
#
# Environment (set by the workflow):
#   EVENT           workflow_run | workflow_dispatch
#   INPUT_TAG       workflow_dispatch input "tag"
#   INPUT_DRY_RUN   workflow_dispatch input "dry_run" ("true"/"false")
#   RUN_TAG         workflow_run.head_branch (the tag that triggered "Deploy staging")
#   RUN_EVENT       workflow_run.event       (must be "push")
#   RUN_CONCLUSION  workflow_run.conclusion  (must be "success")
#
# Rules: production only receives stable tags vX.Y.Z (pre-release tags are staging-only), and only
# after the staging deploy of that tag succeeded.  A manual dispatch with a bad tag is an error
# (exit 2); an automatic run that must not promote ends quietly with deploy=false (exit 0).
set -euo pipefail

STABLE='^v[0-9]+\.[0-9]+\.[0-9]+$'
OUT="${GITHUB_OUTPUT:-/dev/stdout}"

emit() { # tag dry_run deploy reason
  {
    printf 'tag=%s\n' "$1"
    printf 'dry_run=%s\n' "$2"
    printf 'deploy=%s\n' "$3"
    printf 'reason=%s\n' "$4"
  } >>"$OUT"
  printf 'resolve-release: tag=%s dry_run=%s deploy=%s (%s)\n' "$1" "$2" "$3" "$4" >&2
}

case "${EVENT:-}" in
  workflow_dispatch)
    TAG="${INPUT_TAG:-}"
    if [[ ! "$TAG" =~ $STABLE ]]; then
      echo "::error::production accepts stable release tags only (vX.Y.Z); got '${TAG}'" >&2
      exit 2
    fi
    DRY_RUN=false
    [[ "${INPUT_DRY_RUN:-false}" == "true" ]] && DRY_RUN=true
    emit "$TAG" "$DRY_RUN" true "manual dispatch"
    ;;
  workflow_run)
    TAG="${RUN_TAG:-}"
    if [[ "${RUN_CONCLUSION:-}" != "success" ]]; then
      emit "$TAG" false false "staging deploy did not succeed (${RUN_CONCLUSION:-unknown})"
    elif [[ "${RUN_EVENT:-}" != "push" ]]; then
      emit "$TAG" false false "staging run was not triggered by a tag push (${RUN_EVENT:-unknown})"
    elif [[ "$TAG" =~ $STABLE ]]; then
      emit "$TAG" false true "staging deploy of $TAG succeeded"
    else
      emit "$TAG" false false "'$TAG' is not a stable vX.Y.Z tag; pre-release tags stay on staging"
    fi
    ;;
  *)
    echo "::error::unsupported event '${EVENT:-}'" >&2
    exit 2
    ;;
esac

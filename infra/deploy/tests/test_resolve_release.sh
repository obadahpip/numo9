#!/usr/bin/env bash
# Unit test for infra/deploy/resolve-release.sh (S-01-T13). No Docker or network needed.
#
#   bash infra/deploy/tests/test_resolve_release.sh
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$HERE/../resolve-release.sh"
failures=0

# run <expected exit> <expected "tag|dry_run|deploy" or "-"> <description> -- VAR=value...
run() {
  local want_rc="$1" want="$2" desc="$3"
  shift 4
  local out rc got
  out="$(mktemp)"
  env -i PATH="$PATH" GITHUB_OUTPUT="$out" "$@" bash "$SCRIPT" 2>/dev/null
  rc=$?
  got="$(awk -F= '/^tag=/{t=$2} /^dry_run=/{d=$2} /^deploy=/{p=$2} END{printf "%s|%s|%s", t, d, p}' "$out")"
  rm -f "$out"
  if [[ "$rc" == "$want_rc" && ("$want" == "-" || "$got" == "$want") ]]; then
    printf 'PASS  %s\n' "$desc"
  else
    printf 'FAIL  %s (exit %s, want %s; got "%s", want "%s")\n' "$desc" "$rc" "$want_rc" "$got" "$want"
    failures=$((failures + 1))
  fi
}

# Automatic promotion after "Deploy staging"
run 0 "v1.2.3|false|true"  "staging success on v1.2.3 -> promote (waits for approval)" -- \
  EVENT=workflow_run RUN_TAG=v1.2.3 RUN_EVENT=push RUN_CONCLUSION=success
run 0 "v1.2.3|false|false" "staging failure -> no production run" -- \
  EVENT=workflow_run RUN_TAG=v1.2.3 RUN_EVENT=push RUN_CONCLUSION=failure
run 0 "v1.2.3|false|false" "staging cancelled -> no production run" -- \
  EVENT=workflow_run RUN_TAG=v1.2.3 RUN_EVENT=push RUN_CONCLUSION=cancelled
run 0 "v1.3.0-rc.1|false|false" "pre-release tag stays on staging" -- \
  EVENT=workflow_run RUN_TAG=v1.3.0-rc.1 RUN_EVENT=push RUN_CONCLUSION=success
run 0 "main|false|false" "staging run not from a tag push" -- \
  EVENT=workflow_run RUN_TAG=main RUN_EVENT=workflow_dispatch RUN_CONCLUSION=success
run 0 "mobile-v1.0.0|false|false" "mobile tag is never promoted" -- \
  EVENT=workflow_run RUN_TAG=mobile-v1.0.0 RUN_EVENT=push RUN_CONCLUSION=success

# Manual dispatch
run 0 "v0.0.1|true|true"   "dispatch dry run v0.0.1" -- \
  EVENT=workflow_dispatch INPUT_TAG=v0.0.1 INPUT_DRY_RUN=true
run 0 "v0.0.1|false|true"  "dispatch real deploy v0.0.1" -- \
  EVENT=workflow_dispatch INPUT_TAG=v0.0.1 INPUT_DRY_RUN=false
run 0 "v0.0.1|false|true"  "dispatch without dry_run input defaults to false" -- \
  EVENT=workflow_dispatch INPUT_TAG=v0.0.1
run 2 "-" "dispatch pre-release tag rejected" -- \
  EVENT=workflow_dispatch INPUT_TAG=v0.0.1-rc.1 INPUT_DRY_RUN=true
run 2 "-" "dispatch 'latest' rejected" -- \
  EVENT=workflow_dispatch INPUT_TAG=latest
run 2 "-" "dispatch empty tag rejected" -- \
  EVENT=workflow_dispatch INPUT_TAG=
run 2 "-" "dispatch injection attempt rejected" -- \
  EVENT=workflow_dispatch 'INPUT_TAG=v1.0.0;rm -rf /'
run 2 "-" "dispatch tag with trailing newline rejected" -- \
  EVENT=workflow_dispatch "INPUT_TAG=v1.0.0
x"
run 2 "-" "unsupported event rejected" -- \
  EVENT=push RUN_TAG=v1.0.0

if ((failures)); then
  printf '\n%d test(s) failed\n' "$failures"
  exit 1
fi
printf '\nall resolve-release tests passed\n'

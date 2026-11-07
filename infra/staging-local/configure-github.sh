#!/usr/bin/env bash
# Write the GitHub Environment "staging" settings for the temporary local staging host.
#
#   bash infra/staging-local/configure-github.sh <tunnel-host> [cloudflared|tcp <port>]
#
#   cloudflared (default): <tunnel-host> = <name>.trycloudflare.com
#   tcp <port>           : <tunnel-host> = ngrok host, <port> = ngrok port
#
# The known_hosts entry is built from the host key read directly from the local container, so the
# key GitHub trusts is verified locally (not taken from the network).
set -euo pipefail
export MSYS_NO_PATHCONV=1

HOST="${1:?usage: configure-github.sh <tunnel-host> [cloudflared|tcp <port>]}"
MODE="${2:-cloudflared}"
PORT="${3:-}"
KEY="${KEY_DIR:-$HOME/.numo9-staging-local}/deploy_ed25519"
GH="${GH:-gh}"
command -v "$GH" >/dev/null 2>&1 || GH="/c/Program Files/GitHub CLI/gh.exe"
REPO="${REPO:-obadahpip/numo9}"

[[ -f "$KEY" ]] || { echo "deploy key not found: $KEY (run up.sh first)"; exit 2; }
HOST_KEY="$(docker exec numo9-staging-host cat /etc/ssh/ssh_host_ed25519_key.pub | awk '{print $1" "$2}')"

"$GH" api -X PUT "repos/$REPO/environments/staging" --silent
set_var() { "$GH" variable set "$1" --repo "$REPO" --env staging --body "$2"; }
set_var STAGING_SSH_HOST "$HOST"
set_var STAGING_SSH_USER deploy
set_var STAGING_APP_DIR /srv/numo9
set_var STAGING_HEALTH_URL "http://127.0.0.1:8000/healthz"
if [[ "$MODE" == "cloudflared" ]]; then
  set_var STAGING_SSH_PROXY cloudflared
  "$GH" variable delete STAGING_SSH_PORT --repo "$REPO" --env staging 2>/dev/null || true
else
  [[ -n "$PORT" ]] || { echo "tcp mode needs a port"; exit 2; }
  set_var STAGING_SSH_PORT "$PORT"
  "$GH" variable delete STAGING_SSH_PROXY --repo "$REPO" --env staging 2>/dev/null || true
fi
"$GH" secret set STAGING_SSH_PRIVATE_KEY --repo "$REPO" --env staging <"$KEY"
printf '%s %s\n' "$HOST" "$HOST_KEY" | "$GH" secret set STAGING_SSH_KNOWN_HOSTS --repo "$REPO" --env staging

echo "staging environment configured for $HOST ($MODE)"
"$GH" variable list --repo "$REPO" --env staging
"$GH" secret list --repo "$REPO" --env staging

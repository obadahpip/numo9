#!/usr/bin/env bash
# End-to-end test of infra/secrets/secrets.sh with throw-away age keys (S-03-T03):
# keygen → recipients → edit (create) → set → check → decrypt as the "host" → add/remove a
# recipient (updatekeys, rotate) → a removed key can no longer decrypt → plaintext is caught.
#   bash infra/secrets/tests/test_secrets.sh        (needs sops, age, python3)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
pass() { printf 'ok   %s\n' "$*"; }

# A scratch copy of the layout the script expects (repo root with infra/secrets and tools/ci).
mkdir -p "$WORK/repo/infra/secrets/recipients" "$WORK/repo/tools/ci"
cp "$REPO/infra/secrets/secrets.sh" "$REPO/infra/secrets/env.template" "$WORK/repo/infra/secrets/"
cp "$REPO/tools/ci/check_secrets.py" "$WORK/repo/tools/ci/"
S="$WORK/repo/infra/secrets/secrets.sh"
FILE="$WORK/repo/infra/secrets/staging.sops.env"

lead_pub="$("$S" keygen "$WORK/keys/lead.key")"
host_pub="$("$S" keygen "$WORK/keys/host.key")"
[[ "$lead_pub" == age1* && "$host_pub" == age1* ]] || fail "keygen did not print age public keys"
[[ "$(stat -c %a "$WORK/keys/lead.key")" == 600 ]] || fail "private key is not mode 600"
"$S" keygen "$WORK/keys/lead.key" 2>/dev/null && fail "keygen overwrote an existing key"
pass "keygen: key pair, mode 600, never overwrites"

printf '%s  # lead\n%s  # staging host\n' "$lead_pub" "$host_pub" >"$WORK/repo/infra/secrets/recipients/staging.txt"
"$S" recipients >/dev/null
grep -q "$lead_pub,$host_pub" "$WORK/repo/.sops.yaml" || fail ".sops.yaml lacks the recipients"
pass "recipients: .sops.yaml generated"

export SOPS_AGE_KEY_FILE="$WORK/keys/lead.key"
EDITOR=true "$S" edit staging
grep -q '^DJANGO_SECRET_KEY=' "$FILE" || fail "edit did not create the file from the template"
printf 'super-secret-value-123\n' | "$S" set staging DJANGO_SECRET_KEY
printf 'pg"pass\\word x\n' | "$S" set staging POSTGRES_PASSWORD
grep -q 'super-secret-value-123' "$FILE" && fail "plain text value in the encrypted file"
python3 "$WORK/repo/tools/ci/check_secrets.py" "$WORK/repo" >/dev/null || fail "check rejects a correct file"
pass "edit + set: values encrypted at rest, check OK"

export SOPS_AGE_KEY_FILE="$WORK/keys/host.key"
mkdir -p "$WORK/app"
"$S" decrypt staging "$WORK/app/.env"
grep -qx 'DJANGO_SECRET_KEY=super-secret-value-123' "$WORK/app/.env" || fail "host could not decrypt"
grep -qxF 'POSTGRES_PASSWORD=pg"pass\word x' "$WORK/app/.env" || fail "value with quote/backslash/space not preserved"
# gitleaks sees nothing in the encrypted file.
if command -v gitleaks >/dev/null; then
  gitleaks dir "$WORK/repo/infra/secrets/staging.sops.env" --no-banner --redact >/dev/null 2>&1 \
    || fail "gitleaks flags the encrypted file"
fi
[[ "$(stat -c %a "$WORK/app/.env")" == 600 ]] || fail "decrypted file is not mode 600"
pass "decrypt on host: values intact, mode 600"

# deploy.sh decrypts an uploaded secrets.sops.env to .env before switching (docker/curl stubbed).
mkdir -p "$WORK/bin" "$WORK/host"
printf '#!/bin/sh\nexit 0\n' >"$WORK/bin/docker"
printf '#!/bin/sh\necho ok\n' >"$WORK/bin/curl"
chmod +x "$WORK/bin/docker" "$WORK/bin/curl"
touch "$WORK/host/docker-compose.staging.yml"
cp "$FILE" "$WORK/host/secrets.sops.env"
PATH="$WORK/bin:$PATH" APP_DIR="$WORK/host" HEALTH_URL=http://stub/healthz HEALTH_INTERVAL=0 \
  SOPS_AGE_KEY_FILE="$WORK/keys/host.key" bash "$REPO/infra/deploy/deploy.sh" v1.2.3 2>/dev/null \
  || fail "deploy.sh failed with a decryptable secrets file"
grep -qx 'DJANGO_SECRET_KEY=super-secret-value-123' "$WORK/host/.env" || fail "deploy.sh did not write .env"
[[ "$(stat -c %a "$WORK/host/.env")" == 600 ]] || fail "deploy.sh .env is not mode 600"
other_pub="$("$S" keygen "$WORK/keys/other.key")"
[[ -n "$other_pub" ]] || fail "keygen"
printf 'KEEP=1\n' >"$WORK/host/.env"
if PATH="$WORK/bin:$PATH" APP_DIR="$WORK/host" HEALTH_URL=http://stub/healthz \
  SOPS_AGE_KEY_FILE="$WORK/keys/other.key" bash "$REPO/infra/deploy/deploy.sh" v1.2.4 2>/dev/null; then
  fail "deploy.sh continued without being able to decrypt"
fi
grep -qx 'KEEP=1' "$WORK/host/.env" || fail "failed decrypt replaced .env"
ls "$WORK/host"/.env.* >/dev/null 2>&1 && fail "failed decrypt left a temp file"
pass "deploy.sh: decrypts to .env (600); wrong host key stops the deploy and keeps .env"

# Remove the lead (person leaves): updatekeys + rotate; the old key must no longer work.
printf '%s  # staging host\n' "$host_pub" >"$WORK/repo/infra/secrets/recipients/staging.txt"
"$S" recipients >/dev/null
"$S" updatekeys staging >/dev/null 2>&1
"$S" rotate staging >/dev/null 2>&1
export SOPS_AGE_KEY_FILE="$WORK/keys/lead.key"
if "$S" decrypt staging "$WORK/app/lead.env" 2>/dev/null; then fail "removed recipient can still decrypt"; fi
export SOPS_AGE_KEY_FILE="$WORK/keys/host.key"
"$S" decrypt staging "$WORK/app/.env"
grep -qx 'DJANGO_SECRET_KEY=super-secret-value-123' "$WORK/app/.env" || fail "rotation lost a value"
pass "remove recipient: updatekeys + rotate; old key refused, values kept"

# The check catches plain text and committed private keys.
printf 'EXTRA_TOKEN=plain-text\n' >>"$FILE"
python3 "$WORK/repo/tools/ci/check_secrets.py" "$WORK/repo" >/dev/null && fail "plain text value not caught"
cp "$WORK/keys/host.key" "$WORK/repo/infra/secrets/host.txt"
out="$(python3 "$WORK/repo/tools/ci/check_secrets.py" "$WORK/repo" || true)"
[[ "$out" == *"EXTRA_TOKEN is not encrypted"* && "$out" == *"age private key"* ]] || fail "check output: $out"
pass "check: plain text value and private key detected"

echo "all secrets tests passed"

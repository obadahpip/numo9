#!/usr/bin/env bash
# Start the TEMPORARY local staging host (S-01-T12) and install the staging compose file.
# The real staging VM (S-02) replaces this; see infra/staging-local/README.md.
#
#   bash infra/staging-local/up.sh
#
# Creates (once) a dedicated deploy key in $KEY_DIR, builds and runs the host container with SSH
# on 127.0.0.1:${SSH_PORT}, copies infra/staging/docker-compose.staging.yml to /srv/numo9 and
# verifies an SSH login as `deploy` that can run Docker.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
KEY_DIR="${KEY_DIR:-$HOME/.numo9-staging-local}"
SSH_PORT="${SSH_PORT:-2222}"
NAME="numo9-staging-host"

# Git Bash on Windows rewrites "/srv/..." arguments into Windows paths; keep container paths
# literal and convert local source paths explicitly.
export MSYS_NO_PATHCONV=1
local_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -w "$1"; else echo "$1"; fi; }

mkdir -p "$KEY_DIR"
chmod 700 "$KEY_DIR" 2>/dev/null || true
if [[ ! -f "$KEY_DIR/deploy_ed25519" ]]; then
  ssh-keygen -q -t ed25519 -N "" -C "numo9-staging-deploy" -f "$KEY_DIR/deploy_ed25519"
fi

docker build -q -t "$NAME:local" "$(local_path "$ROOT/infra/staging-local")" >/dev/null

if ! docker container inspect "$NAME" >/dev/null 2>&1; then
  docker run -d --name "$NAME" --privileged --restart unless-stopped \
    -p "127.0.0.1:${SSH_PORT}:22" \
    -v numo9-staging-docker:/var/lib/docker \
    -v numo9-staging-srv:/srv/numo9 \
    -v numo9-staging-sshkeys:/etc/ssh/keys \
    -e AUTHORIZED_KEY="$(cat "$KEY_DIR/deploy_ed25519.pub")" \
    "$NAME:local" >/dev/null
fi

docker cp "$(local_path "$ROOT/infra/staging/docker-compose.staging.yml")" "$NAME:/srv/numo9/docker-compose.staging.yml"
docker exec "$NAME" chown deploy:docker /srv/numo9/docker-compose.staging.yml

# Wait for sshd and dockerd.
for _ in $(seq 1 60); do
  if docker exec "$NAME" sh -c 'docker info >/dev/null 2>&1 && pgrep sshd >/dev/null'; then break; fi
  sleep 1
done

# The host key we trust (compare with ssh-keyscan through the tunnel before storing it).
docker exec "$NAME" ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub | awk '{print "host key fingerprint: " $2}'

ssh -i "$KEY_DIR/deploy_ed25519" -p "$SSH_PORT" -o IdentitiesOnly=yes \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
  deploy@127.0.0.1 'echo "ssh ok as $(whoami)"; docker version --format "docker engine {{.Server.Version}}"; ls -l /srv/numo9'

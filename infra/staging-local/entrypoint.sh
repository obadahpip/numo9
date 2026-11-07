#!/usr/bin/env bash
# Entrypoint of the temporary local staging host: sshd + dockerd.
set -euo pipefail

: "${AUTHORIZED_KEY:?AUTHORIZED_KEY (deploy public key) is required}"

# Host key persists in /etc/ssh/keys (volume) so known_hosts stays valid across restarts.
mkdir -p /etc/ssh/keys
[[ -f /etc/ssh/keys/ssh_host_ed25519_key ]] \
  || ssh-keygen -q -t ed25519 -N "" -f /etc/ssh/keys/ssh_host_ed25519_key
ln -sf /etc/ssh/keys/ssh_host_ed25519_key /etc/ssh/ssh_host_ed25519_key
ln -sf /etc/ssh/keys/ssh_host_ed25519_key.pub /etc/ssh/ssh_host_ed25519_key.pub

printf '%s\n' "$AUTHORIZED_KEY" > /home/deploy/.ssh/authorized_keys
chown deploy:docker /home/deploy/.ssh/authorized_keys /srv/numo9
chmod 600 /home/deploy/.ssh/authorized_keys

# Secrets for the staging stack live only on the host (.env, mode 600).
if [[ ! -f /srv/numo9/.env ]]; then
  umask 077
  {
    echo "DJANGO_SECRET_KEY=$(head -c 48 /dev/urandom | base64 | tr -d '\n/+=')"
    echo "POSTGRES_PASSWORD=$(head -c 24 /dev/urandom | base64 | tr -d '\n/+=')"
  } > /srv/numo9/.env
  chown deploy:docker /srv/numo9/.env
fi

/usr/sbin/sshd -e
exec dockerd-entrypoint.sh dockerd --group docker

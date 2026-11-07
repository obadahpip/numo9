# Temporary local staging host (S-01-T12)

A stand-in for the real staging VM until S-02 provisions it (ADR-001, Canadian region).
It is a Docker-in-Docker container with `sshd` that behaves like a small Linux VM:

- user `deploy` (non-root, in the `docker` group), **public-key login only**; root and password
  login are refused;
- its own Docker engine (isolated from the developer's local Docker), app directory `/srv/numo9`
  with `docker-compose.staging.yml` and a generated `.env` (mode 600, never leaves the host);
- data persists in volumes `numo9-staging-docker`, `numo9-staging-srv`, `numo9-staging-sshkeys`.

**It is not production-grade staging**: it exists only while this PC, the container and the
tunnel are running, and the tunnel exposes the SSH port to the internet while it is open.

## Start

```bash
bash infra/staging-local/up.sh          # builds/starts the host on 127.0.0.1:2222, prints host key
```

The dedicated deploy key is created once in `~/.numo9-staging-local/` (outside the repository).

## Expose SSH to GitHub Actions (pick one, run it yourself)

| Tunnel | Command | GitHub `staging` variables |
|---|---|---|
| Cloudflare quick tunnel (free, no card) | `cloudflared tunnel --no-autoupdate --url ssh://127.0.0.1:2222` → prints `https://<name>.trycloudflare.com` | `STAGING_SSH_HOST=<name>.trycloudflare.com`, `STAGING_SSH_PROXY=cloudflared`, `STAGING_SSH_PORT` unset |
| ngrok TCP (needs a card on the ngrok account) | `ngrok tcp 127.0.0.1:2222` → prints `tcp://<host>:<port>` | `STAGING_SSH_HOST=<host>`, `STAGING_SSH_PORT=<port>`, `STAGING_SSH_PROXY` unset |

Both give a new address on every start, so the variables (and `STAGING_SSH_KNOWN_HOSTS`, keyed by
`STAGING_SSH_HOST`) are updated each time.

Other `staging` settings: `STAGING_SSH_USER=deploy`, `STAGING_APP_DIR=/srv/numo9`,
`STAGING_HEALTH_URL=http://127.0.0.1:8000/healthz` (checked on the host), secret
`STAGING_SSH_PRIVATE_KEY` = `~/.numo9-staging-local/deploy_ed25519`, secret
`STAGING_SSH_KNOWN_HOSTS` = `<STAGING_SSH_HOST> <contents of the host's ssh_host_ed25519_key.pub>`.

## Stop / remove

```bash
docker stop numo9-staging-host                       # stop (state kept)
docker rm -f numo9-staging-host                      # remove container (volumes kept)
docker volume rm numo9-staging-docker numo9-staging-srv numo9-staging-sshkeys   # wipe everything
```

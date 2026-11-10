# Secrets management and rotation runbook

S-03-T03 · ADR-0002 (Hetzner has no KMS: SOPS + age, keys held by named people).

**Rule: no secret is ever committed in plain text.** gitleaks scans every commit (security
workflow, full history, `.gitleaks.toml`) and the pre-commit hook; `tools/ci/check_secrets.py`
fails the build if an encrypted file holds a plain value or a key / `.env` file is committed.

## How secrets are stored

| Where | What | Who can read it |
|---|---|---|
| `infra/secrets/staging.sops.env`, `infra/secrets/prod.sops.env` (in Git, **encrypted**) | Runtime secrets of the environment: `DJANGO_SECRET_KEY` (+ `_FALLBACKS`), `POSTGRES_PASSWORD`, field-encryption key ring (S-03-T04), later Stripe, email provider, Sentry DSN | The age recipients in `infra/secrets/recipients/<env>.txt` |
| Each host: `/etc/numo9/age/host.key` (root/deploy user, mode 400) | The host's own age private key — generated on the host, never copied | The host |
| Each person: `~/.config/sops/age/keys.txt` (mode 600) | That person's age private key | That person |
| GitHub Environments `staging` / `production` (secrets) | CI/CD credentials only: SSH deploy key, known hosts | Workflows of that environment (production needs approval, S-01-T13) |
| Host: `APP_DIR/.env` (mode 600) | Decrypted runtime values, written by `deploy.sh` at each deploy, read by Compose | The deploy user |

Runtime flow: the deploy workflow uploads `infra/secrets/<env>.sops.env` as `secrets.sops.env`;
`infra/deploy/deploy.sh` decrypts it with the host key to `.env` (mode 600) **before** pulling
and migrating; if decryption fails the deploy stops and the previous `.env` stays.

`infra/secrets/env.template` lists the variable names (no values).

## Tools

```bash
infra/secrets/secrets.sh keygen ~/.config/sops/age/keys.txt   # your key pair; prints the public key
infra/secrets/secrets.sh recipients                           # .sops.yaml from recipients/*.txt
infra/secrets/secrets.sh edit staging                         # edit in $EDITOR (decrypted in memory only)
printf '%s' "$VALUE" | infra/secrets/secrets.sh set staging NAME   # one value from stdin
infra/secrets/secrets.sh updatekeys staging                   # after recipients change
infra/secrets/secrets.sh rotate staging                       # new data key (after removing someone)
infra/secrets/secrets.sh check                                # same check as CI
```

Requires `sops` ≥ 3.9 (CI pins v3.11.0 by SHA-256) and `age`.

## First-time set-up (per environment)

1. Project lead: `secrets.sh keygen ~/.config/sops/age/keys.txt`; add the printed `age1…` key with
   a `# name` comment to `infra/secrets/recipients/staging.txt` and `prod.txt`.
2. On the host (as root): `install -d -m 700 -o deploy /etc/numo9/age`, then as the deploy user
   `age-keygen -o /etc/numo9/age/host.key && chmod 400 /etc/numo9/age/host.key`; add its public key
   (`age-keygen -y /etc/numo9/age/host.key`) to that environment's recipients file only.
3. `secrets.sh recipients`, then `secrets.sh edit <env>` and fill every variable of the template.
   Generate values with `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
4. `secrets.sh check`, commit the recipients files, `.sops.yaml` and `<env>.sops.env`.
5. Install `sops` and `age` on the host. The next tag deploy writes `.env` from the encrypted file.

## Rotating a secret

Always: change the value with `secrets.sh set` or `edit`, open a pull request (the diff shows only
which variable changed), merge, deploy the next tag. Record the rotation in the audit log of the
change (PR description: what, why, who).

| Secret | Steps | Downtime |
|---|---|---|
| `DJANGO_SECRET_KEY` | 1. Move the current value to `DJANGO_SECRET_KEY_FALLBACKS`. 2. Set a new `DJANGO_SECRET_KEY`. 3. Deploy. 4. After the session lifetime (14 days) and password-reset link expiry, empty `DJANGO_SECRET_KEY_FALLBACKS` and deploy again. | None — old sessions and signed links still verify through the fallback |
| `POSTGRES_PASSWORD` | 1. `ALTER ROLE numo9 PASSWORD '<new>'` on the database (psql as admin). 2. Set the new value. 3. Deploy (containers restart with the new `.env`). | Seconds (connection restart) |
| Field-encryption key (S-03-T04) | 1. Add a new key id to `NUMO9_FIELD_ENCRYPTION_KEYS` and make it `NUMO9_FIELD_ENCRYPTION_ACTIVE_KEY`. 2. Deploy. 3. `python manage.py rotate_field_encryption` re-encrypts every value. 4. Remove the old key after the command reports 0 values on it. | None |
| Stripe / email / Sentry keys | 1. Create the new key in the provider console. 2. Set it. 3. Deploy. 4. Revoke the old key in the console. | None |
| SSH deploy key (GitHub Environment) | 1. `ssh-keygen -t ed25519` for the deploy user, add the public key on the host. 2. Replace `*_SSH_PRIVATE_KEY` in the GitHub Environment. 3. Run a deploy. 4. Remove the old public key from `authorized_keys`. | None |
| A host's age key (host rebuilt or compromised) | Generate a new host key (set-up step 2), replace the public key in the recipients file, `secrets.sh recipients && secrets.sh updatekeys <env> && secrets.sh rotate <env>`, then rotate **every value** in the file (the old key could read them). | Per value, as above |

Schedule: `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD` and provider keys every 12 months; field-
encryption key every 24 months; immediately on suspected exposure or when someone with access
leaves.

## Someone with access leaves

1. Remove their line from `infra/secrets/recipients/<env>.txt` (every environment).
2. `secrets.sh recipients && secrets.sh updatekeys <env> && secrets.sh rotate <env>`.
3. Rotate every value they could read (table above) — removing a recipient only protects
   **future** values.
4. Remove their SSH access (S-02-T10) and GitHub Environment reviewer rights.

## A secret was committed in plain text

1. Treat it as exposed: rotate it at once (table above); revoke provider keys.
2. Remove it from the branch; history rewrites do not un-leak a pushed secret, rotation does.
3. Record an incident (Phase H incident report template) and add a gitleaks rule if the pattern
   was not caught.

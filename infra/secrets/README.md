# infra/secrets

SOPS + age encrypted environment files (S-03-T03). Nothing in this directory is plain text
except the variable names in `env.template` and the **public** keys in `recipients/`.

| File | Purpose |
|---|---|
| `staging.sops.env`, `prod.sops.env` | Encrypted runtime secrets (created with `secrets.sh edit <env>`) |
| `recipients/<env>.txt` | age public keys allowed to decrypt that environment |
| `env.template` | Variable names every environment needs |
| `secrets.sh` | keygen, recipients, edit, set, updatekeys, rotate, decrypt, check |
| `tests/test_secrets.sh` | End-to-end test with throw-away keys |

Runbook: `docs/security/secrets-runbook.md`.

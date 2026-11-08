# Infrastructure as code — OpenTofu on Hetzner Cloud (S-02)

Location rules come from [ADR-0002](../../docs/adr/0002-hetzner-helsinki-hosting.md) (supersedes
ADR-0001): every workload runs in **Hetzner `hel1` (Helsinki)**; **`fsn1` (Falkenstein)** holds the
off-site backup copy only. CI fails if any file under `infra/` names another Hetzner location,
another network zone, or any AWS region (`tools/ci/check_infra_locations.py`).

The reference tool is **OpenTofu ≥ 1.10** (the plan allows "Terraform (or OpenTofu)"); the code is
plain HCL and also works with Terraform ≥ 1.10. Provider: `hetznercloud/hcloud` ~> 1.70.

The server is bought **at deployment** (ADR-0002). Until then the deploy target stays the temporary
local host in `infra/staging-local/`, and this code is verified by the offline tests below.

## Layout

```text
infra/terraform/
  modules/
    network/      private network 10.20.0.0/16 + servers subnet 10.20.1.0/24 (eu-central)
    app_server/   Ubuntu 24.04 server in hel1, Primary IPv4 (survives rebuilds), Cloud Firewall,
                  bootstrap SSH key, private IP on the network
  environments/
    staging/      S-02-T02: network + app server + firewall (production reuses the modules with
                  protection = true)
```

## Firewall (Hetzner Cloud Firewall, inbound)

| Port | Source | Why |
|---|---|---|
| 80/tcp | any (IPv4 + IPv6) | Caddy: HTTP → HTTPS redirect, ACME HTTP-01 |
| 443/tcp | any (IPv4 + IPv6) | Caddy: TLS (S-02-T08) |
| 22/tcp | `ssh_allowed_cidrs` only | Bastion / named admin IPs; each entry must be IPv4 `/24` or narrower — `0.0.0.0/0` is refused by validation |
| ICMP | any | Path MTU discovery, diagnostics |
| anything else | — | dropped |

PostgreSQL (S-02-T04) listens on the private network only. Host-level hardening (ufw, fail2ban,
named accounts, root login off, auditd) is S-02-T05.

## First run (at deployment)

Prerequisites: OpenTofu; a Hetzner Cloud project; an API token (read/write) for that project; an
Object Storage bucket `numo9-tfstate` in `hel1` (private) with S3 credentials.

```bash
cd infra/terraform/environments/staging
cp backend.hcl.example backend.hcl            # bucket / endpoint
cp terraform.tfvars.example terraform.tfvars  # bastion CIDRs, bootstrap public key
export TF_VAR_hcloud_token=<hetzner api token>
export AWS_ACCESS_KEY_ID=<object storage access key> AWS_SECRET_ACCESS_KEY=<secret>
tofu init -backend-config=backend.hcl
tofu plan -out staging.tfplan
tofu apply staging.tfplan
tofu plan                                     # reproducibility: must report "No changes."
```

`backend.hcl`, `*.tfvars`, `*.tfplan` and state files are git-ignored. Outputs:
`server_public_ipv4` (→ GitHub `STAGING_SSH_HOST`, DNS A records in S-02-T07),
`server_public_ipv6` (AAAA), `server_private_ip` and `network_id` (→ PostgreSQL in S-02-T04).

On Windows PowerShell use `$env:TF_VAR_hcloud_token = "<token>"` instead of `export`.

## Tests (no Hetzner account needed)

Each module and environment has `tests/*.tftest.hcl` that run against a **mocked** `hcloud`
provider (plan only): firewall ports and sources, Helsinki location, private network layout,
primary IP kept on server deletion, protection flags, and rejection of `0.0.0.0/0` / wide SSH
ranges / other locations / ARM server types.

```bash
for d in modules/* environments/*; do
  tofu -chdir="$d" init -backend=false || exit 1
  tofu -chdir="$d" validate || exit 1
  if [ -d "$d/tests" ]; then tofu -chdir="$d" test || exit 1; fi
done
tofu fmt -recursive -check .
python ../../tools/ci/check_infra_locations.py ../../infra
```

The same runs in CI (`ci.yml` → job `infra`). Mocked tests prove the configuration, not the live
project: `tofu apply` + an empty second `tofu plan` at deployment is still required for S-02-T02.

## Provider lock file

`environments/staging/.terraform.lock.hcl` is committed with the `linux_amd64` hash of
`hetznercloud/hcloud 1.70.0`. Before running from Windows or macOS, add those platforms once:

```bash
tofu -chdir=environments/staging providers lock \
  -platform=linux_amd64 -platform=windows_amd64 -platform=darwin_arm64
```

## Note for S-02-T06 / S-02-T10

`deploy-staging.yml` connects over SSH from GitHub-hosted runners, whose IPs are not in
`ssh_allowed_cidrs`. Hetzner has no Session Manager equivalent, so when the server exists the deploy
job will either go through the bastion (`ProxyJump`) or add the runner's IP to the Cloud Firewall
for the duration of the job via the Hetzner API — decided in S-02-T06 and recorded in the access
policy (S-02-T10).

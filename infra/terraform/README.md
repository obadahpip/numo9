# Infrastructure as code — OpenTofu (S-02)

Region and residency rules come from [ADR-0001](../../docs/adr/0001-hosting-and-data-residency.md):
workloads run in **AWS `ca-central-1`** only; `ca-west-1` holds backup copies only. CI fails if any
file under `infra/` names another AWS region (`tools/ci/check_infra_regions.py`).

The reference tool is **OpenTofu ≥ 1.10** (the phase plan allows "Terraform (or OpenTofu)"); the
code is plain HCL and also works with Terraform ≥ 1.10.

## Layout

```text
infra/terraform/
  modules/
    network/        VPC, 2 public + 2 private subnets (2 AZs), IGW, route tables, locked default SG
    app_host/       EC2 host (Ubuntu 24.04), security group, instance role (SSM), Elastic IP
  environments/
    bootstrap/      one-time: S3 bucket for remote state (local state)
    staging/        S-02-T02: network + staging host + firewall
```

## Firewall (security group of the app host)

| Port | Source | Why |
|---|---|---|
| 80/tcp | `0.0.0.0/0` | Caddy: HTTP → HTTPS redirect, ACME HTTP-01 |
| 443/tcp | `0.0.0.0/0` | Caddy: TLS (S-02-T08) |
| 22/tcp | `ssh_allowed_cidrs` only | Bastion / named admin IPs; each entry must be IPv4 `/24` or narrower — `0.0.0.0/0` is refused by validation |
| anything else | — | refused |

Private subnets have no internet route (RDS goes there in S-02-T04). The VPC default security group
has every rule removed. Host hardening (fail2ban, named accounts, auditd) is S-02-T05.

## First run (needs the Client's AWS account — ADR-0001)

Prerequisites: OpenTofu, AWS credentials for an IAM Identity Center user with MFA
(`aws sso login --profile numo9`), `AWS_PROFILE=numo9`.

```bash
# 1. State bucket (once per account)
cd infra/terraform/environments/bootstrap
tofu init
tofu apply -var 'allowed_account_ids=["<account-id>"]'     # note output state_bucket

# 2. Staging
cd ../staging
cp backend.hcl.example backend.hcl            # set bucket = <state_bucket>
cp terraform.tfvars.example terraform.tfvars  # account id, bastion CIDRs, bootstrap public key
tofu init -backend-config=backend.hcl
tofu plan -out staging.tfplan
tofu apply staging.tfplan
tofu plan                                     # reproducibility: must report "No changes."
```

`backend.hcl`, `*.tfvars`, `*.tfplan` and state files are git-ignored. Outputs: `host_public_ip`
(→ GitHub `STAGING_SSH_HOST`, DNS A records in S-02-T07), subnet IDs and the host security group
(→ RDS in S-02-T04).

## Tests (no AWS account needed)

Every module and environment has `tests/*.tftest.hcl` that run against a **mocked** AWS provider
(plan only): firewall ports and sources, subnet layout, private route table, IMDSv2, encrypted root
volume, and rejection of `0.0.0.0/0` / wide SSH ranges / non-Canadian regions.

```bash
for d in modules/* environments/*; do
  tofu -chdir="$d" init -backend=false || exit 1
  tofu -chdir="$d" validate || exit 1
  if [ -d "$d/tests" ]; then tofu -chdir="$d" test || exit 1; fi
done
tofu fmt -recursive -check .
python ../../tools/ci/check_infra_regions.py ../../infra
```

The same runs in CI (`ci.yml` → job `infra`). Mocked tests prove the configuration, not the live
account: `tofu apply` + an empty second `tofu plan` in the real account is still required.

## Provider lock file

`environments/*/.terraform.lock.hcl` is committed; it currently pins `hashicorp/aws 6.70.0` with
the `linux_amd64` hash. Before running from Windows or macOS, add those platforms once:

```bash
tofu -chdir=environments/staging providers lock \
  -platform=linux_amd64 -platform=windows_amd64 -platform=darwin_arm64
```

## Known gap carried to S-02-T06 / S-02-T10

`deploy-staging.yml` connects over SSH from GitHub-hosted runners, whose IPs are not in
`ssh_allowed_cidrs`. The host role already allows AWS Systems Manager Session Manager, so the
deploy job will reach port 22 through an SSM tunnel (GitHub OIDC → IAM role) instead of opening 22
— wired when the host is live (S-02-T06) and documented in the access policy (S-02-T10).

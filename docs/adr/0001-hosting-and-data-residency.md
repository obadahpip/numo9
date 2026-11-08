# ADR-0001: Host Numo9 on AWS Canada (Central) with Canada (West) for backups

| | |
|---|---|
| **Status** | superseded by [ADR-0002](0002-hetzner-helsinki-hosting.md) on 2026-11-08 (was accepted 2026-11-08) |
| **Date** | 2026-11-08 |
| **Deciders** | Obadah Abu Odeh — project lead and decision-maker (sign-off, Agreement §6.4) |
| **Deliverable / task** | S-02-T01 (S-02 · Hosting and data residency) |

## Context and problem statement

Numo9 stores the books, tax data and payroll of Canadian organisations, including Social Insurance
Numbers and bank details. The Project Plan (§1.7, "Hosting") requires a Canadian region, the Phase 0
plan (S-02 card) requires that "all personal and financial data [are] stored in Canada", and the
Agreement (§6.4) says the hosting region is decided jointly at kickoff and recorded in an ADR.
Every S-02 task after this one (Terraform network and VMs, buckets, PostgreSQL with PITR, DNS, Caddy,
residency register) and S-03-T03/T04 (secret store, KMS-held encryption key) depends on the provider
chosen here, so it is decided first.

Today staging is a temporary Docker host on a GMA workstation reached through a tunnel
(`infra/staging-local/`, S-01-T12). It is outside Canada and is not production-grade.

## Decision drivers

1. **Residency (PIPEDA, Agreement §14, Plan §1.7):** every copy of personal and financial data —
   database, files, quarantine, **and every backup and replica** — stays in Canada.
2. **Off-site copy inside Canada:** encrypted backups are kept for the CRA six-year period (S-05),
   and an off-site copy must not leave the country, so the provider needs **two Canadian
   locations**.
3. **Managed PostgreSQL 16 with point-in-time recovery** (S-02-T04, S-06), with a recovery window
   long enough to notice a bad posting before it is lost (target ≥ 14 days).
4. **S3-compatible object storage in Canada** with versioning, lifecycle rules and encryption at
   rest (S-02-T03, A-06).
5. **Key management:** an envelope master key held in a KMS, not in a file on the server (S-03-T04
   field-level encryption of SIN and bank details), plus a secret store (S-03-T03).
6. **Infrastructure as code:** a maintained Terraform/OpenTofu provider for network, VMs, buckets,
   database and IAM (S-02-T02…T04), so the stack can be rebuilt in the Client's own account.
7. **Fits the agreed operating pattern:** Linux VMs running Docker Compose behind Caddy, deployed by
   tag over SSH (Plan §5.1 "Infra", `infra/deploy/`). No re-platforming onto Kubernetes.
8. **Cost owned by the Client** (Agreement §8.6: hosting, storage, backups, monitoring and domain are
   contracted and paid by the Client directly), so the monthly bill must stay small at launch and
   grow with paying organisations.
9. **Operable by a small team from Jordan** under Agreement §10.3 and §14.3: named accounts, MFA,
   least privilege, audited access.

## Considered options

1. **AWS — Canada (Central) `ca-central-1`, Montréal, primary; Canada (West) `ca-west-1`, Calgary,
   backup copies.** EC2 + Docker Compose, RDS for PostgreSQL 16, S3, KMS, Secrets Manager.
2. **DigitalOcean — `TOR1`, Toronto.** Droplets + Docker Compose, Managed PostgreSQL, Spaces.
3. **OVHcloud — Beauharnois (`BHS`) and Toronto (`ca-east-tor`).** Public Cloud instances, Public
   Cloud Databases for PostgreSQL, Object Storage.
4. **Hetzner Cloud** (GMA's current provider for its own projects). Rejected at screening: Hetzner
   has no Canadian location (Germany, Finland, USA and Singapore only), so driver 1 cannot be met.
5. **Self-hosted PostgreSQL on VMs** at any of the above, instead of a managed database. Kept as a
   fallback only: PITR (WAL archiving, base backups, restore drills) would then be ours to build and
   operate, which the timeline (90 days) does not allow.

## Decision outcome

**Chosen option:** option 1, **AWS `ca-central-1` (primary) with `ca-west-1` (backup copies only)**,
because it is the only candidate that meets drivers 1–5 together: two Canadian regions, managed
PostgreSQL PITR up to 35 days, S3 with versioning/lifecycle/default encryption, and a native KMS for
the field-encryption master key — while still running the Docker Compose + Caddy pattern on plain VMs
(driver 7). The cost premium over options 2 and 3 is small at Numo9's launch size (see "Cost"),
and is accepted in exchange for in-country backups and a managed KMS.

### What runs where

| Item | Location | Notes |
|---|---|---|
| Production VM(s): Caddy, Django API, Celery worker + beat, Next.js, Redis, ClamAV | `ca-central-1`, EC2 in a private VPC subnet behind Caddy on 80/443 | Docker Compose, deployed by `infra/deploy/deploy.sh` |
| Staging VM | `ca-central-1`, same account, separate VPC/subnets and IAM | Same Compose stack; synthetic and anonymised data only |
| PostgreSQL 16 | `ca-central-1`, RDS (staging: Single-AZ; production: Multi-AZ) | Encrypted with KMS; automated backups with PITR window 14 days on staging, **35 days on production** |
| Buckets `files`, `quarantine`, `backups` | `ca-central-1`, S3 | Block public access, versioning, SSE-KMS, lifecycle (S-02-T03) |
| Off-site backup copies | `ca-west-1`, S3 bucket + RDS snapshot copies | Six-year encrypted retention (S-05); no other region is ever used |
| Master encryption key, secrets | `ca-central-1` KMS + Secrets Manager (replica key in `ca-west-1` for restores) | S-03-T03, S-03-T04 |
| Container images | GHCR (source code and images only — no personal data) | Unchanged from S-01-T12 |
| DNS | Numo9 domain at the Client's registrar or Route 53 | Records for `app.`, `api.`, `staging.`, `console.`, `in.` (S-02-T07). **No TLS-terminating proxy outside Canada** in front of app hosts: Caddy on the VM terminates TLS |

Rules that follow from the decision (they bind every later task):

1. Terraform and application configuration may only reference `ca-central-1` and `ca-west-1`. Any
   other region in `infra/` is a review blocker (enforced by a CI check in S-02-T02).
2. Services that would carry personal data out of Canada (third-party processors) are allowed only
   when they are listed in the data-residency register (S-02-T09) with what they receive. Logs and
   error reports are scrubbed of SIN, bank, card and token data before they leave the server
   (S-03-T06).
3. Real client data is never loaded into the temporary local staging host
   (`infra/staging-local/`); it carries synthetic data only and is retired when Canadian staging is
   live (S-02-T06/T08).

### Cost owner and indicative cost

- **Owner:** the Client contracts the AWS account and pays it directly (Agreement §8.6, 9.1(d)).
  GMA is given access through named IAM Identity Center users with MFA (driver 9, S-02-T10).
- **If the Client's account is not ready on day 1** (Phase 0 plan §1.4.2): GMA provisions staging
  in a GMA-held AWS account in the **same region**, with synthetic data only, and re-applies the same
  Terraform in the Client's account before any real data arrives (Phase 5 migration at the latest).
  Nothing is migrated between accounts except code and configuration.
- **Indicative monthly cost at launch** (USD list prices, on-demand, to be confirmed with the AWS
  Pricing Calculator and attached to the sign-off):

| Environment | Main items | Indicative range |
|---|---|---|
| Staging | 1 small EC2 VM, RDS `db.t4g.small` Single-AZ (instance about USD 26/month in `ca-central-1`) + storage, S3 | about USD 60–90 |
| Production (launch) | 1–2 EC2 VMs, RDS Multi-AZ small instance + storage + backups, S3 + `ca-west-1` copies, KMS, Secrets Manager, data transfer | about USD 180–300 |

Savings plans / reserved instances are reviewed after three months of real usage.

### Consequences

- Good: every copy of client data, including off-site backups, stays in Canada (drivers 1, 2).
- Good: PITR is managed and long (driver 3); the restore drill in S-05 restores from a managed
  backup, not a hand-built WAL archive.
- Good: KMS gives S-03-T04 a real envelope master key with rotation and audit (CloudTrail).
- Good: the deploy pipeline from S-01-T12 is unchanged — staging is just another SSH host.
- Bad: higher monthly cost and more moving parts than DigitalOcean or OVHcloud. Mitigation: small
  instance classes at launch, Single-AZ staging, budgets and cost alerts in Terraform, and a review
  after three months.
- Bad: provider lock-in for RDS, KMS and IAM. Mitigation: application code talks only to PostgreSQL,
  S3 and a small secrets/KMS interface; buckets and database are standard protocols; Terraform keeps
  the rest reproducible.
- Bad: more IAM surface to secure. Mitigation: IAM Identity Center with MFA, no long-lived access
  keys on servers (instance roles), CloudTrail on (S-02-T10, S-03).

### Confirmation

- **Sign-off:** recorded below (2026-11-08); status `accepted`; ADR index updated.
- **CI fitness check (S-02-T02):** a check fails the build if any file under `infra/` names a region
  other than `ca-central-1` or `ca-west-1`.
- **Inspection (S-02-T03, T04):** `aws s3api get-bucket-location` returns `ca-central-1` for the
  three buckets and `ca-west-1` for the backup copy; RDS shows the configured PITR window and
  encryption; recorded in the PR of each task.
- **Register (S-02-T09):** the data-residency register lists every data class with the location
  defined here.

## Pros and cons of the options

### Option 1 — AWS `ca-central-1` + `ca-west-1`

- Good, because two Canadian regions allow in-country off-site backups and disaster recovery.
- Good, because RDS for PostgreSQL keeps automated backups with PITR for up to 35 days.
- Good, because S3, KMS, Secrets Manager and CloudTrail are native and covered by one Terraform
  provider.
- Bad, because it costs more and needs more configuration than the alternatives.

### Option 2 — DigitalOcean `TOR1`

- Good, because it is the cheapest and simplest: Droplets, Managed PostgreSQL 16 and Spaces are all
  available in Toronto, with a mature Terraform provider.
- Bad, because `TOR1` is DigitalOcean's only Canadian datacenter, so an off-site backup copy would
  have to leave Canada or go to a second provider (driver 2).
- Bad, because managed PostgreSQL PITR is limited to the last 7 days (driver 3).
- Bad, because from 30 November 2026 new Standard Edition clusters can no longer add standby nodes,
  so high availability needs a different edition with fewer features.
- Bad, because there is no managed KMS; the field-encryption master key would live in a secret file
  (driver 5).

### Option 3 — OVHcloud Beauharnois + Toronto

- Good, because it is inexpensive and has two Canadian locations with S3-compatible Object Storage
  (`bhs`, `ca-east-tor`, both single-AZ).
- Good, because managed PostgreSQL 16 is offered with PITR within the plan's retention period
  (2 / 14 / 30 days by plan).
- Bad, because managed database backups are replicated off-site by default and for a service in
  `BHS` the default off-site location is Strasbourg (France); it must be overridden on every
  service, and a mistake silently exports data (driver 1).
- Bad, because key management and IAM are less complete than AWS for an envelope-key design
  (driver 5), and object storage is single-AZ in both Canadian regions.

### Option 4 — Hetzner Cloud

- Good, because it is GMA's current, lowest-cost platform.
- Bad, because it has no Canadian location — fails driver 1. Not evaluated further.

### Option 5 — Self-hosted PostgreSQL

- Good, because it is portable and cheap in money.
- Bad, because PITR, replication, backup encryption and restore drills become GMA's to build and
  operate inside a 90-day project (driver 3); kept as a fallback only.

## Client sign-off

| | |
|---|---|
| **Decision** | Option 1 — AWS `ca-central-1` primary, `ca-west-1` backup copies |
| **Decision-maker** | Obadah Abu Odeh, project lead |
| **Approved on** | 2026-11-08 |
| **Reference** | Decision recorded on PR #17 (https://github.com/obadahpip/numo9/pull/17), 2026-11-08 |
| **AWS account owner and billing contact** | The Client (Agreement §8.6, 9.1(d)); account ID recorded in S-02-T02 when created |

## More information

- Phase 0 plan, S-02 card: `docs/phase_plans/Phase_0_Foundation_and_SaaS_Core.md` §6.1.
- Project Plan §1.7 (Canadian context — hosting, privacy, records) and §5.1 (technology stack).
- Agreement GMA-PFX-2026-003-A: §6.4 kickoff decisions, §8.6 costs paid by the Client, §9.1(d)
  hosting account access, §10.3 security, §14 confidentiality and data protection.
- Provider facts checked on 2026-11-08: Hetzner Cloud locations; DigitalOcean regional availability
  and PostgreSQL limits/pricing; OVHcloud Object Storage endpoints, PostgreSQL capabilities and
  automated-backup locations; AWS RDS backup and recovery guidance. Re-check prices before sign-off.
- Follow-up tasks: S-02-T02 (Terraform + region CI check), S-02-T03 (buckets), S-02-T04 (RDS + PITR,
  PgBouncer), S-02-T09 (residency register), S-03-T03/T04 (Secrets Manager, KMS).
- Revisit: after three months of production usage (cost), or if the Client's privacy counsel
  requires changes to the residency rules.

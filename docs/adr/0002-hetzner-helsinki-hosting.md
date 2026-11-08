# ADR-0002: Host Numo9 on Hetzner Cloud in Helsinki (supersedes ADR-0001)

| | |
|---|---|
| **Status** | accepted — 2026-11-08 · supersedes [ADR-0001](0001-hosting-and-data-residency.md) |
| **Date** | 2026-11-08 |
| **Deciders** | Obadah Abu Odeh — project lead and decision-maker |
| **Deliverable / task** | S-02-T01 (revision), applied in S-02-T02 onward |

## Context and problem statement

ADR-0001 chose AWS in Canada. The decision-maker has replaced it with Hetzner Cloud, which GMA
already operates (Docker Compose + Caddy on `gma-infra-01`, Helsinki). Hetzner has **no Canadian
location** (Falkenstein and Nuremberg in Germany, Helsinki in Finland, Ashburn and Hillsboro in the
USA, Singapore), so Numo9 data will be stored **outside Canada**. The Agreement (§6.4) recommends,
but does not require, Canadian residency; the Project Plan (§1.7) and the Phase 0 S-02 card state
"Canadian region". This ADR records the new decision and what changes because of it.

The production server is bought **at deployment**, not now. Until then the temporary local staging
host (`infra/staging-local/`, S-01-T12) remains the deploy target, with synthetic data only.

## Decision drivers

1. Decision-maker's choice of provider (cost, and the platform GMA already runs).
2. Monthly cost the Client pays (Agreement §8.6) kept low at launch.
3. The agreed operating pattern: Linux VMs with Docker Compose behind Caddy, deployed by tag over
   SSH (Plan §5.1, `infra/deploy/`).
4. PIPEDA accountability for personal information processed outside Canada (Agreement §14.2–14.3).
5. Reproducible infrastructure as code (S-02-T02…T04).

## Considered options

1. **Hetzner Cloud, Helsinki (`hel1`), off-site backup copy in Falkenstein (`fsn1`).** — chosen
2. Hetzner Cloud, Nuremberg/Falkenstein (Germany). Equivalent; Helsinki chosen to match GMA's
   existing location.
3. Hetzner Cloud, Ashburn (USA). Closest to Canadian users, but Hetzner Object Storage is offered in
   `fsn1`, `nbg1` and `hel1` only, so backups would leave the continent anyway; US CLOUD Act exposure.
4. AWS `ca-central-1` + `ca-west-1` (ADR-0001). Superseded.

## Decision outcome

**Chosen option:** option 1 — **Hetzner Cloud `hel1` (Helsinki, Finland)** for every workload and
primary data store, with **`fsn1` (Falkenstein, Germany)** used only for the off-site backup copy.
Both locations are in the EU and covered by GDPR.

### What runs where

| Item | Location | How |
|---|---|---|
| App server: Caddy, Django API, Celery worker + beat, Next.js, Redis, ClamAV | `hel1` cloud server | Docker Compose (S-02-T06); public IPv4 is a Hetzner Primary IP so DNS survives rebuilds |
| PostgreSQL 16 | `hel1`, same private network, on an encrypted Hetzner Volume | **Self-hosted** (Hetzner has no managed PostgreSQL). Point-in-time recovery by continuous WAL archiving + base backups (WAL-G or pgBackRest) to Object Storage — S-02-T04 |
| Buckets `files`, `quarantine`, `backups` | `hel1` Object Storage (S3-compatible) | Versioning, lifecycle (noncurrent-version expiry), object lock for backups, SSE-C where supported — S-02-T03 |
| Off-site backup copy | `fsn1` Object Storage | Encrypted copies of DB backups and the `backups` bucket; CRA six-year retention (S-05) |
| Field-encryption master key, secrets | SOPS + age encrypted files in the repo, decrypted only on the server at deploy | Hetzner has no KMS; S-03-T03/T04 use a key file loaded from SOPS, never committed in plain text |
| Firewall | Hetzner Cloud Firewall (+ host ufw in S-02-T05) | 80/443 public, 22 bastion/admin IPs only — S-02-T02 |
| Container images, source | GHCR / GitHub (no personal data) | Unchanged |

Rules that bind every later task (they replace the rules in ADR-0001):

1. `infra/` may reference only the Hetzner locations `hel1` (workloads) and `fsn1` (backup copy),
   and no AWS region. A CI check fails the build otherwise (`tools/ci/check_infra_locations.py`).
2. Every place personal data is stored or sent is listed in the data-residency register
   (S-02-T09), now including the fact that primary storage is in Finland and backups in Germany.
3. Real client data is never loaded into the temporary local staging host.

### Cost owner and indicative cost

- **Owner:** the Client pays the Hetzner account (Agreement §8.6) once production is bought at
  deployment; GMA may hold it in a GMA project until handover (Agreement §13).
- **Indicative monthly cost** (Hetzner EU list prices since 15 June 2026, excl. VAT; confirm in the
  console on the day of purchase — the cost-optimised CX line was not orderable in Sept–Oct 2026):

| Item | Indicative |
|---|---|
| Server CPX32 (4 vCPU, 8 GB, 160 GB) | about €35.50 |
| Primary IPv4 | €0.50 |
| Volume for PostgreSQL (50 GB) | about €2.90 |
| Object Storage (base, includes a storage/egress quota) | about €6.50 + usage |
| **Total at launch** | **about €46/month** |

### Consequences

- Good: lowest cost of all options; one provider GMA already knows; nothing changes in the deploy
  pipeline (the server is just another SSH host).
- Bad: **personal and financial data, including SINs and bank details, is stored outside Canada.**
  Mitigation: the Client is informed in writing and reflects it in its privacy notice (Agreement
  §14.3); field-level encryption of SIN/bank details (S-03-T04) stays mandatory; the residency
  register (S-02-T09) states the locations; the Phase 0 plan and Project Plan wording "Canadian
  region" is to be read as "per ADR-0002".
- Bad: PostgreSQL backups, PITR, upgrades and restore drills become GMA's responsibility.
  Mitigation: WAL-G/pgBackRest with automated restore test in S-02-T04 and the S-05 restore drill.
- Bad: no managed KMS. Mitigation: SOPS + age with keys held by named people, rotation runbook
  (S-03-T03), key id stored with every ciphertext (S-03-T04).
- Bad: no live staging server until deployment, so S-02 acceptance criteria that need a running host
  (apply, buckets, PITR, hardening scan, TLS, DNS, SSH logging) are observed at deployment; code and
  offline tests are delivered before.

### Confirmation

- CI: `check_infra_locations.py` passes; OpenTofu tests pass with a mocked `hcloud` provider.
- At deployment: `tofu apply` then `tofu plan` reports no changes; the server, volume and buckets
  show `hel1` (backup copy `fsn1`) in the Hetzner console/API; recorded in the PRs of S-02-T02…T04.

## More information

- Supersedes [ADR-0001](0001-hosting-and-data-residency.md) (AWS Canada).
- Provider facts checked 2026-11-08: Hetzner Cloud locations; Object Storage locations
  (`fsn1`, `nbg1`, `hel1`) and supported S3 actions (versioning, noncurrent-version expiry, object
  lock, SSE-C); 2026 price list. Re-check before purchase.
- Client acknowledgement of non-Canadian storage (recommended before real data is loaded):
  _date / reference_.

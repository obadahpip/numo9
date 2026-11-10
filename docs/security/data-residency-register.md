# Data-residency register

| | |
|---|---|
| **Task** | S-02-T09 (S-02 · Hosting and data residency) |
| **Decision it implements** | [ADR-0002](../adr/0002-hetzner-helsinki-hosting.md) — Hetzner Cloud `hel1` (Helsinki, Finland) for workloads, `fsn1` (Falkenstein, Germany) for the off-site backup copy only |
| **Owner** | Project lead (Obadah Abu Odeh). The Client is the organisation in control of the personal information (Agreement §14.2) |
| **Last reviewed** | 2026-11-09 |
| **Next review** | at every change of provider, region or sub-processor, and before real Client data is loaded (Phase 5 migration) |

This register lists **where every class of data lives** and **every third party (sub-processor)
that stores or receives it**. It is the record that ADR-0002 rule 2 requires and the source the
Client uses for its privacy notice (Agreement §14.3).

!!! warning "Data is stored outside Canada"
    Under ADR-0002 all personal and financial data — including Social Insurance Numbers and bank
    details — is stored in **Finland** (primary) and **Germany** (backup copy), both in the EU and
    covered by GDPR. The Client must reflect this in the privacy notices it gives its users
    (Agreement §14.3) **before real data is loaded**. The wording "Canadian region" in the Project
    Plan (§1.7) and the Phase 0 S-02 card is read as "per ADR-0002".

## Rules

1. **No undeclared location.** Personal or financial data may be stored in, or sent to, only the
   locations and sub-processors listed below. Adding a provider, changing a region or enabling an
   optional integration (OCR, SMS/WhatsApp, tax-payment provider, push) first updates this register
   in the same pull request.
2. **Infrastructure locations are enforced in CI.** `infra/` may name only Hetzner `hel1` and
   `fsn1` (`tools/ci/check_infra_locations.py`, ADR-0002 rule 1).
3. **Scrub before it leaves the server.** Logs, error reports and crash reports are scrubbed of
   SIN, bank, card, token and password data before they are sent anywhere (S-03-T06, M-01-T07).
4. **Field-level encryption.** SIN and bank details are encrypted at field level (S-03-T04), masked
   on screen and never written to logs (Agreement §14.2) — wherever the database or its backups
   live.
5. **Card data never touches Numo9.** Card and PAD details are collected by Stripe Elements /
   Checkout; Numo9 stores Stripe identifiers only (PCI scope stays with Stripe).
6. **Synthetic data only outside production.** Development machines, CI and the temporary local
   staging host (`infra/staging-local/`) carry synthetic or anonymised data only (ADR-0002 rule 3).
7. **Access from outside Canada** by GMA personnel (Jordan) is remote access, not storage: named
   accounts, SSH keys only, session logging and least privilege (Agreement §10.2, §14.3; S-02-T05,
   S-02-T10). No production data is copied to personnel devices.
8. **Retention.** Accounting records and backups are kept for the CRA six-year period (S-05);
   records are soft-deleted only.

## Locations

| Code | Place | Provider | Used for |
|---|---|---|---|
| `hel1` | Helsinki, Finland (EU) | Hetzner Online GmbH — Hetzner Cloud | All workloads and primary data stores |
| `fsn1` | Falkenstein, Germany (EU) | Hetzner Online GmbH — Object Storage | Off-site encrypted backup copy only |
| GitHub | United States | GitHub, Inc. (GitHub repository, Actions, GHCR) | Source code, CI, container images, SOPS-encrypted secret files — **no personal data** |
| Local | GMA workstation, Amman, Jordan | GMA (temporary local staging host, dev stacks) | Synthetic data only, until production is bought at deployment |

## Register of data classes

"Encrypted" means: at rest on an encrypted Hetzner Volume or Object Storage with server-side
encryption (S-02-T03/T04), in transit over TLS; "field-encrypted" adds application-level AES-GCM
(S-03-T04).

| # | Data class | Examples | Personal / financial | Primary location | Backup / copies | Protection | Retention | Task(s) |
|---|---|---|---|---|---|---|---|---|
| D-01 | User accounts and authentication | Name, email, Argon2id password hash, TOTP secret, sessions, locale | Personal | PostgreSQL 16, `hel1` | `hel1` `backups` bucket + `fsn1` copy | Encrypted | Life of account; audit kept six years | A-02 |
| D-02 | Practice and organisation profiles | Legal and display names, Business Number, CRA/RQ program accounts, addresses, time zone | Business / financial | PostgreSQL, `hel1` | as D-01 | Encrypted | Six years after closure | A-01, A-05 |
| D-03 | Contacts | Customer/supplier names, emails, addresses, tax IDs, supplier bank details for EFT | Personal / financial | PostgreSQL, `hel1` | as D-01 | Encrypted; bank details field-encrypted | Six years | B-01…B-03 |
| D-04 | Accounting ledger and documents | Journals, invoices and revisions, quotes, POs, bills, credit notes, bank-statement imports, tax codes | Financial | PostgreSQL, `hel1` | as D-01 | Encrypted; append-only ledger | Six years (CRA) | C-01, C-02, D, E, F |
| D-05 | Tax data | GST/HST/QST returns, tax book and adjustments, CCA schedules, tax computations, tax-payment records | Financial | PostgreSQL, `hel1` | as D-01 | Encrypted | Six years (CRA) | G, I, K-07/K-08 |
| D-06 | Employee and payroll data | SIN, date of birth, address, TD1 claims, employee bank details, pay runs, stubs, T4/RL-1, ROE data, timesheets, leave | Personal (sensitive) / financial | PostgreSQL, `hel1` | as D-01 | Encrypted; **SIN and bank details field-encrypted, masked, never logged**; reveal audited | Six years (CRA) | M, N, S-03-T04/T05 |
| D-07 | Subscription and billing records | Package, invoices and receipts from the platform, Stripe customer/subscription/payment IDs, card brand + last 4 | Financial | PostgreSQL, `hel1`; full payment data at Stripe (P-01) | as D-01 | Encrypted; no card numbers stored | Six years | U-04, P |
| D-08 | Uploaded files and generated documents | Receipts, bill PDFs, attachments, Xero export files, generated invoice/stub PDFs, data exports | Personal / financial | Object Storage bucket `files`, `hel1` (org-prefixed keys, signed URLs 5 min) | Versioned in `hel1`; `backups` bucket + `fsn1` copy | Encrypted (SSE); ClamAV-scanned before release | Six years | A-06, S-02-T03 |
| D-09 | Quarantined uploads | Files awaiting or failing virus scan | Personal / financial | Object Storage bucket `quarantine`, `hel1` | Not backed up | Encrypted; never served to users | Lifecycle expiry (S-02-T03) | A-06 |
| D-10 | Inbound email (bills by email) | Raw message, sender address, attachments to `docs+<token>@in.<domain>` | Personal / financial | Received by the email provider (SP-03), then stored as D-08 in `hel1` | as D-08 | TLS from provider webhook; provider retention minimised | as D-08 | A-06, E-05 |
| D-11 | Audit trail | Who did what, before/after diffs (SIN/bank masked), IP address, user agent | Personal | PostgreSQL (partitioned `audit_event`), `hel1` | as D-01 | Encrypted; hash-chained, append-only | Six years | A-04 |
| D-12 | Cache, sessions and job queues | Session data, Celery task payloads, rate-limit counters | Personal (transient) | Redis 7, `hel1` (private network only) | Not backed up (AOF on the server volume only) | Not exposed publicly; no SIN/bank in task payloads (IDs only) | Minutes to days | A-08, S-06 |
| D-13 | Application logs and metrics | Structured JSON logs (org_id, request id), Prometheus metrics | Personal (limited: IDs, IP) | App server / Loki + Prometheus, `hel1` | Not copied off-site | Scrubbed (rule 3) | Per S-04 log retention policy | S-03-T06, S-04 |
| D-14 | Error and crash reports | Stack traces, request metadata, release tags (web, API, workers, mobile) | Personal (limited, scrubbed) | Error tracker — SP-04 | Provider-managed | Scrubbed with `before_send` (rule 3) | Provider retention, set to the shortest the plan allows | S-03-T06, S-04-T03, Y |
| D-15 | Database and file backups | Base backups + WAL archive (PITR), copies of `files` | All of the above | `backups` bucket, `hel1` | Encrypted copy in `fsn1` | Encrypted; object lock | Six years (S-05) | S-02-T04, S-05 |
| D-16 | Secrets and encryption keys | Django secret, DB passwords, Stripe keys, field-encryption master key | Secret | SOPS + age encrypted files in the GitHub repository; decrypted only on the `hel1` server at deploy | Repository history (ciphertext only) | age private keys held by named people; rotation runbook | Until rotated | S-03-T03, S-03-T04 |
| D-17 | Outbound email | Recipient address, message body, attached PDFs (invoices, statements, pay stubs) | Personal / financial | Transactional email provider — SP-03 (in transit and provider logs) | Provider-managed | TLS; DKIM/SPF/DMARC; provider content retention minimised | Provider retention | A-07 |
| D-18 | Payment data | Card/PAD details, payer name, email, billing address, payouts (subscriptions, invoice pay links, pay-per-service) | Personal / financial | Stripe — SP-02 | Provider-managed | Collected by Stripe Elements/Checkout (PCI out of our scope) | Per Stripe | U-04, P-01…P-05 |
| D-19 | Tax payments sent out | Program account, period, amount, payer bank details | Financial | Tax-payment provider per ADR-003 (SP-05), or a bank file downloaded by the user | Provider-managed / user's bank | Idempotency keys; TLS | Six years in Numo9 (D-05) | P-06, G-09 |
| D-20 | Bank files exported by users | CPA 005 EFT files, positive-pay, bill-payment files, data exports on cancellation | Personal / financial | Generated in `hel1`, then downloaded by the user — leaves Numo9 under the user's control | — | Signed download URL; audited | — | E-06, N-06, U-04 |
| D-21 | Website and public forms | Lead/demo/sign-up form data; cookieless analytics | Personal (form data); none in analytics | PostgreSQL, `hel1`; analytics self-hosted (Plausible) in `hel1` | as D-01 | Anti-spam token check (SP-06) | Leads: until no longer needed | Q-02, Q-04 |
| D-22 | Mobile push notifications | Device push token, notification text (amount-free by default) | Personal (limited) | Token in PostgreSQL, `hel1`; message via SP-07 | Provider-managed | Lock-screen content without amounts by default | Until device unregistered | Y (Phase 7) |
| D-23 | Source code, CI data, container images | Code, test fixtures (synthetic), images | **None** | GitHub / GHCR | GitHub | gitleaks; no personal data in fixtures | — | S-01 |
| D-24 | Development and temporary staging data | Dev databases, Mailpit, MinIO, temporary local staging host | **Synthetic only** | GMA workstations (Amman) | None | Never real Client data (rule 6) | Disposable | S-01-T06, S-01-T12 |

## Sub-processors

Third parties that store or receive personal or financial data. Provider facts were checked on
2026-11-09 from the providers' own documentation and are **re-confirmed when each contract is
signed**; the Client contracts and pays each of them directly (Agreement §8.6).

| # | Sub-processor | Purpose | Data received | Data location | Status | Contract owner |
|---|---|---|---|---|---|---|
| SP-01 | **Hetzner Online GmbH** (Germany) — Cloud servers, Volumes, Object Storage | Hosting of every workload and data store | All data classes D-01…D-16, D-21 | `hel1` Helsinki, Finland; backup copy `fsn1` Falkenstein, Germany | Chosen (ADR-0002); bought at deployment | Client (GMA project until handover) |
| SP-02 | **Stripe** (Stripe Payments Canada, Ltd.) | Subscription billing, invoice payments, PAD, Connect, refunds | D-18; Stripe IDs echoed back to D-07 | Stripe processes and stores data in the **United States** (Stripe privacy policy, cross-border transfers) | Required (U-04, P-01); account opened by the Client | Client |
| SP-03 | **Transactional email provider** (outbound + inbound) | Sending notifications, documents and reminders; receiving bills by email | D-17, D-10 | **To be decided** — must be an EU (preferred) or Canadian region; the provider and region are written here before A-07 goes live | Not yet chosen (Phase 0 client input, A-07) | Client |
| SP-04 | **Error tracking** — Sentry SaaS **EU (Germany) data region**, or self-hosted Sentry/GlitchTip on the `hel1` server | Error and crash reports (backend, frontend, workers, mobile) | D-14 (scrubbed) | Germany (Sentry EU region) or `hel1`. **The Sentry US region is not used** | Not yet set up (S-04-T03) | Client |
| SP-05 | **Tax-payment provider** (ADR-003) | Paying CRA / Revenu Québec from Numo9 | D-19 | **To be decided** with ADR-003 | Not yet chosen; stub and bank-file routes need no provider | Client |
| SP-06 | **Anti-spam service** — Cloudflare Turnstile or hCaptcha | Bot check on public forms | IP address, browser signals (no form content) | Provider's global network | Planned (Q-02-T03) | Client |
| SP-07 | **Expo Push Service → Apple APNs / Google FCM** | Mobile push notifications | D-22 | United States (provider infrastructure) | Planned (Phase 7) | Client (developer accounts) |
| SP-08 | **SMS / WhatsApp provider** (e.g., Twilio, Meta) | Payment reminders | Phone number, reminder text | To be decided | **Hooks only — not enabled** (A-07-T12, D-07-T02) | Client |
| SP-09 | **Paid OCR / extraction provider** | Bill and receipt extraction | Uploaded documents (D-08) | To be decided | **Not used** — default is on-server Tesseract in `hel1` (E-05); added only if the Client elects it | Client |

### Third parties that receive no personal data

Listed so the register is complete; none of them receives Client or user personal data.

| Service | Purpose | What is sent |
|---|---|---|
| GitHub, Inc. (repository, Actions, GHCR) — United States | Source, CI, images | Code, synthetic fixtures, SOPS ciphertext (D-16, D-23) |
| Let's Encrypt / ZeroSSL (via Caddy ACME) | TLS certificates | Domain names only |
| Domain registrar / DNS host (Client's choice, S-02-T07) | DNS | DNS records only |
| Bank of Canada Valet API | Daily FX rates (R-01) | Outbound request only; nothing about users |
| Cloudflare quick tunnel (temporary local staging only, S-01-T12) | SSH path for staging deploys | Encrypted SSH traffic to a host holding synthetic data only; retired when the Hetzner server is live |
| Expo EAS Build / Apple App Store / Google Play | Mobile builds and store listings | App binaries and store metadata |
| Have I Been Pwned — Pwned Passwords range API (A-02-T02) | Breached-password check at sign-up and password change | The first 5 hex characters of the password's SHA-1 only (k-anonymity); no email, account or IP linkage beyond the request itself |

## Changes to this register

| Date | Change | By |
|---|---|---|
| 2026-11-09 | First version (S-02-T09), per ADR-0002 | GMA |

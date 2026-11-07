# NUMO9 — Hypercare & Warranty Implementation Plan

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | H — Hypercare (two windows) & start of the 12-month Warranty |
| **Weeks** | Week 9 (after Phase 5 Go-Live) and Week 13 (after Phase 7 mobile release); Warranty runs 12 months from Go-Live |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment) |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §5.2 (Hypercare + warranty), §6.2–6.3, §7 (IMPROVE: post go-live and warranty), §8 risks, §10 · Project_Phases.md (Hypercare) · Quotation GMA-PFX-2026-003 §05, §08 Warranty · Agreement GMA-PFX-2026-003-A 5.3, 6.1, 7.5, §11, 12.1–12.6, 14, 15.1 · xero_teardown.md (gap rows re-verified in production) · AI Coding Agent — Mandatory Engineering Workflow (Rule 6 structured debugging, Rule 10 reporting) |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE applied to the hypercare process and to every defect fix (each fix is its own atomic task and branch) |

---

## 0. How to use this file

- Hypercare is an operational phase. Its "build" is the support process, tooling and runbooks (prepared before Go-Live) plus every defect fix, each handled as an atomic task with its own branch `fix/<ticket>-<short>` using Rule 6 structured debugging.
- Window 1 (week 9) follows Phase 5 Go-Live; Window 2 (week 13) follows the mobile release. Each window lasts one week (Agreement 5.3) and ends with a closed hypercare log.
- Warranty (12 months from Go-Live, Agreement 12.1): defects + minor adjustments + quarterly statutory data updates + store-compliance updates; feature adjustments per Agreement 12.3.
- Nothing is declared fixed until the reproduction test passes, the regression suite is green and the reporter confirms (or deemed-accepted).

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase

| Area | State |
|---|---|
| Production | Numo9 live on Numo9 domain (T-05 cut-over), Profitex + pilot client migrated with TB 0.00, parallel payroll and GST period run |
| Monitoring | S-04 error tracking (Sentry), metrics/alerts (Prometheus/Grafana or hosted), uptime checks; S-05 backups with PITR and restore drill done |
| Mobile (window 2) | Y-04 apps published under client accounts, crash reporting enabled |
| Process | Sprint reporting cadence; UAT sign-off sheet (T-02); runbook (T-04) |
| Statutory data | Payroll constants by tax year (N-01), CRA tables uploaded (N-12), tax rates effective-dated (G-01), CCA classes (I-01), FX rates job (R-01) |
| Gaps | All §4 gap rows observed in UAT |

### 1.2 Problem definition — the seven questions

1. **Who?** Profitex staff and pilot client users (window 1), mobile users (window 2), Platform Owner, GMA on-call engineers, project lead, client decision-maker.
2. **Outcome:** production issues found early and fixed fast with zero data-integrity loss; hypercare logs closed; warranty operating with predictable SLAs and scheduled statutory updates.
3. **Inputs:** defect reports (in-app "Report a problem", email, portal ticket), monitoring alerts, crash reports, user feedback, CRA/RQ/provincial publications (T4127 July edition, January constants, rate changes, CCA class changes), store policy notices, warranty adjustment requests.
4. **Outputs:** triaged tickets with severity, fixes released with notes, daily hypercare log, closing log per window, KPI dashboard, quarterly statutory-update releases with compliance fixture results, warranty request register.
5. **Business rules:** acknowledgement within one business day for every defect (Agreement 12.1 / Quotation §08); critical defects affecting posting, payroll, billing or payments are worked as first priority; ledger fixes never edit history — corrections via reversal/adjustment with audit; production data accessed only with client authorisation and logged (Agreement §14); statutory data updates as effective-dated data, never code (Agreement 15.1); warranty excludes third-party failures, others' modifications, misuse, inaccurate data (12.4); feature adjustments accepted if they refine existing Schedule A modules and are of comparable effort to a task card, otherwise change request (12.3, §11); minor defects do not block acceptance (7.5).
6. **What could go wrong:** alert fatigue hides a real incident; a hot-fix introduces regression in posting; data repair script runs against wrong organisation; payroll run before constants update; slow acknowledgement breaching SLA; mobile crash rate > 1 %; store rejection of an update; scope creep through "warranty adjustments"; time-zone confusion between Amman and Canadian users for SLA clocks.
7. **Smallest useful implementation:** ticket intake with severity rules, an on-call rota, a daily log template and the alert set for posting/payroll/billing/payments — in place before Go-Live.

### 1.3 Restated objective

- **Currently:** Numo9 is newly live; operational support exists only as runbook text.
- **Change:** run two structured hypercare windows and start a warranty operation with SLAs, triage, monitoring watch, statutory update calendar and a controlled feature-adjustment intake.
- **Why:** the first weeks in production carry the highest risk to ledger integrity, payroll and payments; the client needs guaranteed response and continuously correct statutory data.
- **Done means:** hypercare logs closed after Go-Live and after mobile release; every critical/high defect fixed or with an agreed workaround; crash-free sessions ≥ 99 % in window 2; warranty period running with register, SLA dashboard and the statutory calendar (next events scheduled).

### 1.4 Assumptions & interpretations

1. Business days follow the client's Ontario calendar (Eastern Time) for SLA clocks; GMA works Amman hours with an overlap window 15:00–19:00 Amman (08:00–12:00 ET) plus on-call for critical.
2. Severity definitions (Sev-1…Sev-4) below are proposed by GMA and confirmed by the client decision-maker at hypercare kickoff.
3. Quarterly statutory updates are scheduled in January, April, July (T4127 July edition) and October, plus ad-hoc releases when an authority publishes an in-year change.
4. Ticketing tool: GitHub Issues/Projects (repository already used) with a client-facing form; a dedicated help-desk tool is optional and client-paid.

### 1.5 Client inputs required

| Input | Due | Used by |
|---|---|---|
| Decision-maker and backup contacts for incidents | Before Go-Live | T-05H-T02 |
| Severity matrix confirmation | Before Go-Live | T-05H-T03 |
| Authorisation policy for production data access | Before Go-Live | T-05H-T07 |
| Feedback on closing logs within 5 business days | End of each window | T-05H-T26, T38 |
| Confirmation of CRA/RQ editions for each statutory update (Agreement 9.1(c)) | Before each quarterly release | T-05H-T31…T34 |

---

## 2. BETTER THAN XERO — gap analysis for this phase

| Gap # | Teardown ref | Xero behaviour | Numo9 hypercare/warranty response | Observable proof |
|---|---|---|---|---|
| 5 | §2.1 | "Online payments" card failed with "Unable to load" — reliability gap | Synthetic monitors for every dashboard card and payment widget; card-load failure alerts within 5 min | Uptime/synthetic dashboard; alert test |
| 8 | §2.3, §6.9 | Expired rates stay selectable forever | Quarterly statutory releases end-date old rates and add new ones as effective-dated data, verified by fixtures | Release notes + compliance fixture report |
| 44 | §6.8 | System silently removed "GST Type" with no attribution | Every data correction in hypercare runs as an attributed, audited action (data-fix scripts write audit entries with ticket ID) | Audit log entries tagged `ticket=` |
| 37 | §5.13 | Weak history | Hypercare log + audit trail per fix | Closed log |
| 59 / 36 | §9.6, §5.12 | Exceptions report flags nothing | Daily exceptions-engine run on production orgs during hypercare, reviewed in daily log | Daily log section "Exceptions" |
| 61 | §10.B | Generic upgrade banners, unclear support | In-app "Report a problem" with context capture and status tracking visible to the reporter | Ticket created from app with screenshot + route |

**Beyond-Xero additions**
- Transparent SLA dashboard shared with the client (acknowledgement and resolution times).
- Statutory calendar published to the client (what changes when) and compliance fixture results attached to each update.
- Post-incident reviews (blameless) for every Sev-1/Sev-2 shared with the client.

**[EXTRA] refinements inside scope**
- Release health gate: automatic rollback trigger if error rate or posting failures exceed threshold after deploy.
- Weekly "top friction" UX report from session analytics and support tickets feeding warranty adjustments.

---

## 3. UI/UX DESIGN PLAN (support experience)

### 3.1 UX principles
1. Reporting a problem takes < 60 s and never loses the user's work.
2. Context captured automatically (route, organisation, user role, browser/app version, last API error ID, optional screenshot) — users don't need technical knowledge.
3. Status visible: reporters see *Received → Acknowledged → In progress → Fix released → Closed*.
4. Incident banners are calm, specific and dismissible; they say what is affected and what to do meanwhile.
5. Bilingual EN/FR; WCAG 2.1 AA; mobile parity.

### 3.2 Information architecture added
- Help menu (top bar `?`) → **Report a problem**, **My requests**, **System status**.
- Platform console → **Support** (ticket queue mirror, SLA dashboard, incident banner editor).
- Mobile apps → Settings → **Report a problem** (shake-to-report optional).
- Public `status` page (status.<numo9 domain>).

### 3.3 Screen inventory

| Screen | Primary user | Purpose | Key components | States | Keyboard |
|---|---|---|---|---|---|
| Report a problem dialog | All users | Submit defect/request | Modal, Textarea, SeveritySelect (plain words: "I can't work" / "Something is wrong" / "Question / suggestion"), Screenshot toggle, auto-context preview | submitting / sent (ticket number) / offline (queued) | `Ctrl+Shift+H` open |
| My requests | Reporter | Track status | List, StatusBadge, timeline | empty / list | — |
| System status page | Public / users | Service health | Component list, incident history | operational / degraded / outage | — |
| In-app incident banner | All users | Inform during incident | Banner (role-targeted), link to status | info / warning / resolved | dismiss `Esc` |
| Console › Support queue | GMA on-call, Platform Owner | Triage | DataGrid, filters (severity, module, org), SLA timers | breaching (red), at risk (amber) | `J/K`, `A` acknowledge |
| Console › SLA dashboard | Project lead, client | KPIs | Stat tiles, charts (ack time, resolution time, open by severity) | — | — |
| Console › Incident banner editor | Platform Owner/GMA | Publish banners | Form EN/FR, audience picker, schedule | draft / live / expired | — |
| Mobile Report a problem | Mobile users | Same as web | Native sheet, screenshot attach | offline queue | — |

### 3.4 Key flows
1. **User reports a problem (< 60 s):** `?` → Report a problem → choose "I can't work" → describe → screenshot auto-attached → Send → ticket number + expected acknowledgement time shown.
2. **On-call triage (< 15 min for Sev-1 during overlap):** alert/ticket → console queue → assign severity per matrix → acknowledge (timer stops) → open incident if Sev-1 → banner published.
3. **Fix release:** branch `fix/…` → reproduction test → fix → CI → staging verify → production deploy (lead authorisation) → reporter notified "Fix released" → confirm → close.
4. **Statutory update:** calendar reminder → load new edition data → run compliance fixtures → release notes → client confirmation → effective-dated publish.

### 3.5 Microcopy rules
- Acknowledgement: "We've received your request #1234. A member of our team will respond by Tuesday 10 November, 12:00 ET." FR: « Nous avons reçu votre demande no 1234. Un membre de notre équipe vous répondra d'ici le mardi 10 novembre, 12 h HE. »
- Incident banner: "Payroll pay-stub PDFs are slow to generate (started 09:40 ET). Pay runs and postings are not affected. Next update by 10:30 ET."
- Never blame the user; always give a workaround if one exists.

### 3.6 Usability checks
| Task | Metric |
|---|---|
| Report a problem from invoice editor without losing draft | 100 %, < 60 s |
| Find status of own request | 100 %, < 15 s |
| Understand incident banner impact | ≥ 90 % correct in hallway test |
| axe-core on support screens (EN/FR) | 0 serious/critical |

---

## 4. TOOLS & TECHNOLOGY FOR THIS PHASE

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| Ticketing | GitHub Issues + Projects (board "Hypercare"), issue forms, labels `sev-1..4`, `module/*`, `warranty-adjustment`, `statutory-update` | Defect and request tracking | Free with repo; Zendesk/Freshdesk optional client-paid |
| In-app intake | Numo9 "Report a problem" widget → backend → GitHub API (`PyGithub`) | Context-rich tickets | Built in this phase |
| Error tracking | Sentry (web, backend, React Native) with release tags and source maps | Exceptions, crash-free sessions | Client hosting/subscription cost |
| Metrics & alerting | Prometheus + Alertmanager + Grafana (or hosted Grafana Cloud) | Posting failures, Celery queue depth, webhook failures, p95 latency, DB replication lag | — |
| Uptime & synthetic | Uptime Kuma (self-hosted) or Better Stack; Playwright synthetic journeys every 5 min (login, dashboard cards, invoice create in demo org, payment widget) | Availability | — |
| Status page | Uptime Kuma status page / Cachet | Public status | — |
| On-call paging | Alertmanager → Telegram/Slack/email + phone call via PagerDuty/Opsgenie free tier | Sev-1 paging | — |
| Logs | Loki or OpenSearch with structured JSON logs (org_id, request_id; never SIN/bank) | Investigation | — |
| DB tooling | `pg_stat_statements`, `pgBadger`, PITR restore scripts, read-replica for investigations | Performance & safe analysis | — |
| Data repair | `manage.py data_fix <ticket> --dry-run/--apply` framework writing reversal/adjustment JEs + audit entries | Safe corrections | Built in this phase |
| Reconciliation jobs | Nightly integrity checks: every book TB = 0, AR control = sub-ledger, AR = sum of open current revisions, stock GL = valuation, Stripe balance vs postings, tax-payment status vs provider | Early detection | Built in this phase |
| Exceptions | K-09 engine scheduled daily on production orgs | Data-quality review | Existing |
| Mobile | Sentry RN, App Store Connect / Google Play Console vitals, EAS Update (OTA for JS fixes), EAS Build/Submit | Crash-free ≥ 99 %, fast fixes | Client developer accounts |
| Release | GitHub Actions, feature flags (U-06), canary deploy, automatic rollback script | Safe hot-fixes | — |
| Analytics | PostHog (self-hosted) or Plausible for funnels; session replay off by default (PIPEDA) with masking | Friction report | — |
| Statutory sources | CRA T4127 (Jan/July), CRA payroll deduction tables, CPP/EI rates, Revenu Québec TP-1015.F, GST/HST and provincial rate notices, Income Tax Regulations Schedule II (CCA), Bank of Canada FX | Quarterly updates | Public |
| Compliance tests | `tests/fixtures/compliance` (40 payroll scenarios, provincial tax matrix, GST/QST lines, CCA classes, T2 fixture), CRA XSD validation (`lxml`), PDOC cross-check sheet | Update verification | — |
| Store compliance | Apple/Google policy trackers, `expo-doctor`, target SDK checker | Store updates | — |
| Docs | MkDocs runbook, incident template, PIR template, release-notes template | Communication | — |
| Internal tools to build | Report-a-problem widget; SLA timer service; daily log generator (`manage.py hypercare_daily_log`); closing-log generator; integrity check suite; data-fix framework; statutory update loader & diff report (`manage.py statutory_diff --edition`); warranty request register (GitHub Project view + monthly export) | Phase productivity | — |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 objective
Two closed hypercare windows and an operating 12-month warranty with SLAs, monitoring, safe fixes, statutory updates and controlled feature adjustments.

### 5.2 Level 2 components

| Component | Tasks | Purpose |
|---|---|---|
| H1 Readiness (before Go-Live) | T-05H-T01…T16 | Process, severity matrix, tooling, alerts, integrity checks, data-fix framework, intake UI |
| H2 Window 1 operations (week 9) | T-05H-T17…T26 | Daily watch, triage, fixes, logs, closing |
| H3 Window 2 operations (week 13, mobile) | T-05H-T27…T30, T38 | Mobile watch, crash-free target, store updates, closing |
| H4 Warranty operations | T-05H-T31…T37, T39…T44 | Statutory updates, adjustments intake, store compliance, reporting |

### 5.3 Dependency graph and execution order

```
H1 readiness (T01–T16, done by end of week 8, parallel with T-05 cut-over)
   ├─► H2 window 1 (week 9; parallel with Phase 6) ─► closing log 1
   ├─► H3 window 2 (week 13; after Y-04 release) ─► closing log 2
   └─► H4 warranty (month 1–12; quarterly statutory releases; monthly reports)
```

---

## 6. PLAN — Deliverable card with ATOMIC TASKS

### T-05 (hypercare) · Hypercare & warranty start

- **Branch:** `ops/T-05H-hypercare-readiness` (tooling); each defect `fix/<issue#>-<short>`; each statutory update `data/<YYYY-QN>-statutory-update`.
- **Objective:** run hypercare after Go-Live (week 9) and after mobile release (week 13) with priority defect handling, and start the 12-month warranty including quarterly constants/CRA tables/tax rates/CCA class updates.
- **Current behaviour:** production live; support process undocumented beyond runbook.
- **Expected behaviour:** severity-based triage, ack ≤ 1 business day for all defects, Sev-1 first priority with continuous work; daily hypercare log; closing log per window accepted by client; warranty register and statutory calendar active.
- **Gap #s:** 5, 8, 36/59, 37, 44 (operational assurance).
- **Severity matrix (proposed):**

| Severity | Definition | Examples | Acknowledge | Target workaround / fix |
|---|---|---|---|---|
| Sev-1 Critical | Posting, payroll, billing, payments or data integrity affected; production down; data leak | Unbalanced JE posted; pay run wrong; double charge; tenant leak | ≤ 1 h in overlap / ≤ 4 h otherwise (always ≤ 1 business day) | Work continuously as first priority; workaround ≤ 8 h; fix ≤ 2 business days |
| Sev-2 High | Major function unusable, no workaround | Cannot approve bills; GST worksheet wrong line | ≤ 1 business day | Fix ≤ 5 business days |
| Sev-3 Medium | Function impaired, workaround exists | Filter not saving; slow report | ≤ 1 business day | Next scheduled release |
| Sev-4 Low | Cosmetic / question / suggestion | Label typo; layout nit | ≤ 1 business day | Backlog / warranty adjustment |

- **Business rules:** §1.2 rule 5.
- **Edge cases:** defect caused by third-party service (Stripe, provider, email) → triaged, workaround, classified per 12.4; defect is actually a change request → logged under §11; reporter data error → guidance, not a defect; Sev-1 at weekend → on-call paging.
- **UI/UX notes:** §3.
- **Dependencies:** T-05 (cut-over), S-04, S-05, U-06, K-09, N-01/N-12, G-01, I-01, Y-04.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| T-05H-T01 | Hypercare plan & runbook section: windows, roles (incident lead, on-call engineer, comms), overlap hours, escalation path | DOC | — | Runbook section approved by lead and client | Review |
| T-05H-T02 | Contact & escalation matrix (client decision-maker, backup, GMA on-call rota for weeks 9 and 13) | DOC | T01 | Matrix shared; test page reaches each contact | Paging test |
| T-05H-T03 | Severity matrix and SLA definitions confirmed with client (table above), timezone rule (ET business days) | DOC | T01 | Written confirmation from client | Sign-off |
| T-05H-T04 | GitHub issue forms (defect, request, warranty adjustment, statutory update), labels, "Hypercare" project board with SLA fields | OPS | T03 | Forms live; test issue lands on board with severity | Manual |
| T-05H-T05 | "Report a problem" API `POST /api/v1/support/requests` (auto-context: route, org, role, app version, last error ID, optional screenshot to A-06 storage) → GitHub issue via API; PII scrubbing (no SIN/bank) | BE | T04 | Request creates issue with context; SIN pattern redacted | pytest incl. redaction |
| T-05H-T06 | Report-a-problem dialog (web) + My requests list with status sync from GitHub (webhook) EN/FR | FE | T05 | Submit < 60 s; draft preserved; status updates visible | Playwright |
| T-05H-T07 | Production data-access procedure: authorisation request template, just-in-time read-only DB role, access logged to audit and ticket | OPS/DOC | T03 | Access without ticket impossible (role expires in 4 h) | Manual drill |
| T-05H-T08 | SLA timer service: computes ack/resolve deadlines in ET business days (Ontario holidays), flags at-risk/breached | BE | T04 | Unit cases incl. Friday 16:00 ET and holiday | pytest |
| T-05H-T09 | Console Support queue & SLA dashboard (mirror of board with timers, filters) | FE | T08 | Breaching ticket shown red; dashboard KPIs computed | Playwright |
| T-05H-T10 | Critical alert set: posting errors > 0, unbalanced-JE guard trips, payroll run failures, Stripe webhook failures/backlog, tax-payment status mismatches, Celery queue depth, 5xx rate, p95 > 3 s, DB replication lag, backup job failure, certificate expiry | OPS | S-04 | Each alert fired once in staging drill and routed to on-call | Alert drill log |
| T-05H-T11 | Synthetic monitors (Playwright every 5 min): login, dashboard cards incl. payment widget, create invoice in monitoring demo org, report run, portal login, website pricing | OPS | T10 | Failure of any journey alerts within 5 min | Forced-failure test |
| T-05H-T12 | Public status page + incident banner editor (EN/FR, audience targeting) | OPS/FE | T10 | Banner published and visible to targeted role only | Playwright |
| T-05H-T13 | Nightly integrity check suite: per-book TB = 0, AR/AP control = sub-ledger, AR = sum of open current revisions, inventory GL = valuation, loan liability = schedule, Stripe balance vs postings, tax-payment provider status reconciliation; results to dashboard + alert | BE | — | Seeded inconsistency on staging detected and alerted | pytest + staging drill |
| T-05H-T14 | Data-fix framework `manage.py data_fix <ticket> --org <id> --dry-run/--apply`: corrections only via reversal/adjusting JEs or audited field updates, org scope enforced, ticket ID on every audit entry | BE | T07 | Dry-run shows diff; apply writes audit `ticket=`; cross-org target refused | pytest |
| T-05H-T15 | Release safety: canary deploy, health gate (error rate / posting failures), one-command rollback, hot-fix pipeline from `fix/*` with lead approval | OPS | S-01 | Rollback drill on staging < 10 min | Drill log |
| T-05H-T16 | Templates: daily hypercare log, incident report, blameless post-incident review (PIR), release notes, closing log; generator `manage.py hypercare_daily_log` pulling tickets, alerts, integrity results, exceptions-engine summary | DOC/BE | T09, T13 | Generated log for a staging day contains all sections | Command run |
| T-05H-T17 | Window 1 kickoff (Go-Live +0): on-call rota active, banners ready, client briefed on how to report | OPS | T01–T16 | Kickoff note sent; rota acknowledged | Record |
| T-05H-T18 | Window 1 day 1 watch: monitor alerts, integrity results, exceptions engine on Profitex + pilot org; daily log #1 | OPS | T17 | Log #1 published by 17:00 ET | Log |
| T-05H-T19 | Window 1 day 2 watch + daily log #2 | OPS | T18 | Log #2 published | Log |
| T-05H-T20 | Window 1 day 3 watch + daily log #3 | OPS | T19 | Log #3 published | Log |
| T-05H-T21 | Window 1 day 4 watch + daily log #4 | OPS | T20 | Log #4 published | Log |
| T-05H-T22 | Window 1 day 5 watch + daily log #5 | OPS | T21 | Log #5 published | Log |
| T-05H-T23 | Defect handling procedure per ticket (template atomic task): reproduce → expected vs actual → logs/data → hypothesis → reproduction test → one change → verify → regression → release → reporter confirmation (Rule 6; 30-minute principle) | BE/FE/QA | T15 | Every closed Sev-1/2 ticket links reproduction test and release | Ticket audit |
| T-05H-T24 | Parallel-run follow-up: verify first live GST period and first live pay run after cut-over against Xero/CRA calculator; record differences | QA | T18 | Differences 0.00 or explained and fixed | Reconciliation report |
| T-05H-T25 | Window 1 KPI review: ack times, resolution times, open by severity, integrity results, top modules by defects | OPS | T22 | KPI table in closing log | Dashboard export |
| T-05H-T26 | Window 1 closing log: all Sev-1/2 closed or agreed workaround, open items moved to warranty register with severity and target release; client acceptance | DOC | T25 | Client confirms closing log (or deemed after 10 business days) | Sign-off |
| T-05H-T27 | Mobile watch setup for window 2: Sentry RN release health, crash-free sessions target ≥ 99 %, App Store/Play vitals, EAS Update channel for JS hot-fixes, mobile Report-a-problem | OPS/MOB | Y-04 | Dashboard shows crash-free % per platform | Manual |
| T-05H-T28 | Window 2 daily watch days 1–5 (web + mobile), daily logs #1–#5 including crash-free %, ANR rate, store reviews triage | OPS | T27 | Five logs published | Logs |
| T-05H-T29 | Mobile fix pipeline: OTA for JS-only fixes, binary resubmission for native fixes, store review tracking | MOB | T27 | One OTA rehearsal delivered to internal track | Release record |
| T-05H-T30 | Tenant-isolation sweep re-run through production mobile build against staging data | QA | T27 | Sweep 100 % pass | Sweep report |
| T-05H-T31 | Statutory calendar for 12 months (January year change: CPP/CPP2/EI/QPP/QPIP constants, T4127 January edition, provincial rates; July: T4127 July edition; quarterly: tax rate notices, CCA class changes, Bank of Canada FX source check) published to client | DOC | T03 | Calendar shared; reminders scheduled (A-08 jobs) | Record |
| T-05H-T32 | Statutory update loader & diff: `manage.py statutory_diff --edition` comparing new vs current constants/tables/rates/classes, producing a human-readable diff for client confirmation (Agreement 9.1(c)) | BE | N-01, N-12, G-01, I-01 | Diff of a test edition lists every changed value | pytest |
| T-05H-T33 | Quarterly statutory release procedure (template atomic task): load edition as effective-dated data → run compliance fixtures (40 payroll scenarios, provincial tax matrix, GST/QST lines, CCA fixtures, T2 fixture, XSD) → release notes → client confirmation → publish before effective date | QA/BE | T32 | Fixture report 100 % pass attached to release | Compliance suite |
| T-05H-T34 | First scheduled update rehearsal (January 2027 year-change data set on staging) | QA | T33 | Pay run dated 2027-01-15 uses 2027 constants; 2026 runs unchanged | Fixture run |
| T-05H-T35 | Warranty feature-adjustment intake: form + register (request, module, Schedule A item, effort vs task-card comparison, decision: adjustment / change request per 12.3 & §11, target release) | DOC/OPS | T04 | Register live; first triage meeting held | Record |
| T-05H-T36 | Monthly warranty report: defects by severity, SLA compliance, statutory updates done/upcoming, adjustments delivered, risks | DOC | T35 | First monthly report delivered | Review |
| T-05H-T37 | Store-compliance watch: Apple/Google policy and SDK target deadlines, privacy manifest updates, scheduled maintenance releases | MOB | T27 | Next deadline entered in calendar with release plan | Record |
| T-05H-T38 | Window 2 closing log (web + mobile): crash-free ≥ 99 %, all Sev-1/2 closed or workaround, client acceptance | DOC | T28–T30 | Client confirms closing log | Sign-off |
| T-05H-T39 | Post-incident reviews for every Sev-1/Sev-2 (timeline, root cause, fix, prevention), shared with client within 5 business days | DOC | T23 | PIR published per incident | Record |
| T-05H-T40 | Weekly "top friction" UX report (support tickets + analytics funnels) feeding adjustment backlog [EXTRA] | UX | T35 | Report produced weekly during hypercare; top 3 items triaged | Record |
| T-05H-T41 | Backup restore spot-check during window 1 (restore yesterday's backup to isolated env, verify TB per org) | OPS | S-05 | Restore < 1 h; TB matches production snapshot | Drill log |
| T-05H-T42 | Performance watch: weekly `pg_stat_statements` top 20 review, slow-report list, index proposals as Sev-3 tickets | OPS | T10 | Report produced; regressions ticketed | Report |
| T-05H-T43 | Security watch: weekly dependency audit (pip-audit, npm audit, Trivy), gitleaks, critical CVE patch within SLA Sev-1 | OPS | S-03 | Audit results logged; criticals 0 open | CI reports |
| T-05H-T44 | Warranty end-of-period plan (month 11): summary, open items, optional support-plan proposal (Agreement 12.6) | DOC | T36 | Proposal delivered before warranty end | Record |

- **Deliverable acceptance:** hypercare logs closed after Go-Live and after mobile release; warranty period running (register, SLA dashboard, statutory calendar with next release scheduled); crash-free ≥ 99 % in hypercare.
- **Testing approach:** every fix ships with a reproduction test (unit/integration/E2E as appropriate), full regression suite, tenant-isolation sweep on fixes touching queries, compliance fixtures for statutory updates, alert/rollback/restore drills.
- **Risks & mitigations:** see §10.

---

## 7. TEST — phase test plan

| Category | Scope | Tooling | Target |
|---|---|---|---|
| Unit | SLA timer, redaction, data-fix framework, statutory diff | pytest | ≥ 85 % on new modules |
| Integration | Report-a-problem → GitHub; webhook status sync; alert routing | pytest, staging | All paths |
| Regression | Full suite on every `fix/*` and `data/*` branch | CI | 0 regressions |
| Data validation | Nightly integrity suite; parallel-run reconciliation; restore TB check | Integrity jobs | 0 unexplained differences |
| Compliance | Statutory release fixtures | `tests/fixtures/compliance`, XSD | 100 % pass |
| Security | Redaction, JIT access, dependency audits, isolation sweep | pytest, Trivy, sweep | No high findings |
| Operational drills | Alert drill, rollback drill (< 10 min), restore drill (< 1 h), paging test | Runbook | All passed before window 1 |
| Mobile | Crash-free sessions, OTA rehearsal | Sentry RN, EAS | ≥ 99 % |

**Exit demonstration (per window)**
1. Show SLA dashboard: 100 % of defects acknowledged ≤ 1 business day.
2. Show every Sev-1/Sev-2 ticket with reproduction test, release and PIR.
3. Show nightly integrity results for each day of the window: all green or explained.
4. Show closing log with open items transferred to warranty register.
5. (Window 2) Show crash-free sessions ≥ 99 % on iOS and Android.
6. Show statutory calendar and the scheduled January update rehearsal result.
7. Client confirms closing log.

**Failure handling:** Rule 5.3 and 6 — stop dependent work, reproduce, one change at a time, verify, regression; never close a ticket on an unexecuted test; 30-minute principle triggers re-examination and escalation to project lead for Sev-1.

---

## 8. IMPROVE — post-verification checklist
- Tune alert thresholds to remove noisy alerts (target < 2 non-actionable pages per week).
- Convert repeated support questions into in-app help or UX adjustments (warranty adjustments).
- Turn every Sev-1/2 root cause into a regression test and, where possible, an exceptions-engine or integrity rule.
- Review slow queries and add indexes/caching where measurable.
- Update runbook and FAQ after each window.
- **Performance budgets** (production): report p95 < 3 s; dashboard < 1.5 s; API p95 < 500 ms; uptime ≥ 99.5 % during hypercare.

---

## 9. Git branch plan

| Branch | Base | Purpose | Merge rule |
|---|---|---|---|
| `ops/T-05H-hypercare-readiness` | `main` | Readiness tooling T01–T16 | Before Go-Live |
| `fix/<issue#>-<short>` | `main` (or `release/x.y` for hot-fix) | One defect each | Lead approval; back-merge to `main` |
| `data/<YYYY-QN>-statutory-update` | `main` | Statutory data release | After client confirmation of edition |
| `mobile-fix/<issue#>` | `main` | Mobile fixes; tag `mobile-vX.Y.Z` | Lead approval + store process |
| `adjust/<request#>-<short>` | `main` | Warranty feature adjustment | Register decision = adjustment |

Before each branch: `git status`, base pulled, ticket linked, objective + acceptance restated. Before complete: reproduction test passes, CI green, no unrelated changes, no debug/secrets, release notes, review, lead authorisation; production deploy only with authorisation.

---

## 10. Phase risks register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Hot-fix regression in posting/payroll | Medium | Critical | Reproduction test + full regression + canary + rollback |
| 2 | SLA breach due to timezone gap | Medium | High | Overlap window, on-call paging, ET business-day timers |
| 3 | Data repair on wrong organisation | Low | Critical | Data-fix framework with org scope, dry-run, audit |
| 4 | Payroll run before constants update | Medium | High | Statutory calendar, reminders, effective-dated data loaded in advance |
| 5 | Mobile crash rate > 1 % | Medium | Medium | OTA fixes, staged rollout, Sentry release health |
| 6 | Store rejection of update | Medium | Medium | Policy watch, pre-submission checklist |
| 7 | Warranty scope creep | High | Medium | 12.3 comparison rule, register decisions, change control |
| 8 | Alert fatigue | Medium | Medium | Threshold tuning, alert review weekly |
| 9 | Phase 6 work competes with window 1 | High | Medium | Dedicated on-call engineer separate from Phase 6 team |
| 10 | Third-party outage (Stripe/provider/email) | Medium | Medium | Status monitoring, assisted tax-payment route, retries; classified under 12.4 |

---

## 11. Phase completion checklist (Rule 11) & reporting template (Rule 10)

**UNDERSTAND** — [ ] production state and monitoring inspected · [ ] users and outcomes identified · [ ] intake inputs/outputs defined · [ ] SLA, access and warranty rules identified · [ ] edge cases (third-party, CR vs defect, weekend) considered · [ ] objective restated.
**PLAN** — [ ] readiness, windows and warranty decomposed into atomic tasks · [ ] dependencies mapped · [ ] order defined · [ ] acceptance per task · [ ] drills and tests defined.
**BUILD** — [ ] intake, timers, alerts, integrity checks, data-fix framework built · [ ] existing engines reused · [ ] no unrelated changes in fix branches · [ ] existing behaviour preserved.
**TEST** — [ ] drills passed · [ ] every fix has reproduction + regression · [ ] isolation sweep re-run where relevant · [ ] compliance fixtures for statutory updates · [ ] unverified conditions recorded.
**IMPROVE** — [ ] alerts tuned · [ ] root causes converted to tests/rules · [ ] runbook updated · [ ] behaviour re-verified.
**COMPLETE** — [ ] closing logs accepted (window 1 and 2) · [ ] warranty register, SLA dashboard and statutory calendar live · [ ] documentation updated · [ ] final status reported.

**Reporting template (per ticket / per window)**
- *Before implementation:* 1. Problem understanding (reported vs expected behaviour, severity, affected orgs). 2. Task breakdown (reproduction, fix, tests). 3. Plan (order, acceptance, tests, release route).
- *After implementation:* 1. Changes made (files, data fixes with audit IDs). 2. Testing results (executed / passed / failed / not executed and why). 3. Remaining issues (workarounds, risks). 4. Final status — Complete / Partially complete / Blocked.

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| T-05H | 44 | 66 |
| **Total** | **44** | **66** |

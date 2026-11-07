# NUMO9 — PHASE 5 IMPLEMENTATION PLAN
## Migration, UAT & Go-Live (Week 8)

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | 5 — Migration, UAT & Go-Live |
| **Weeks** | Week 8 (production cut-over and acceptance at end of week 8; hypercare week 9 is covered in the Hypercare file) |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment) |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada (product owner of Numo9) |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §1.8 (11), §3 Component T and S, §4 gap matrix, §5.2, §6, §7 · Project_Phases.md (Phase 5) · Quotation GMA-PFX-2026-003 §04–§06 · Agreement GMA-PFX-2026-003-A §5.3, §07 (7.1–7.6), §8.2 milestone 2, §9.1 · xero_teardown.md (§2.6, §3.3, §5.4–§5.6, §5.8, §6.8–§6.12, §9, §10) · AI Coding Agent — Mandatory Engineering Workflow (Rules 1–11) |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE, applied to the phase, to every deliverable branch and separately to every atomic task |
| **Commercial note** | Payment milestone 2 (CAD 5,000) is due on acceptance of Phase 5 (Agreement 8.2). Go-Live acceptance additionally requires TB difference 0.00 vs Xero for Profitex and the pilot client, completion of the parallel payroll and GST period, and the platform running in production (Agreement 7.6). |

---

## 0. How to use this file

- Each deliverable (T-01, T-02, T-03, T-04, T-05, S-04, S-05) is one Git branch: `feature/<ID>-<short-name>` (ops work uses `ops/…`, documentation `docs/…`).
- Each atomic task in §6 is sized for one focused 1–2 hour session and is worked through the full cycle on its own: **UNDERSTAND → PLAN → BUILD → TEST → IMPROVE**.
- Order inside a deliverable: model → migration → service → API → permission / feature key → UI → i18n keys → tests → docs.
- Mocks (fixture Xero exports, fake S3, stub alert channel) are allowed while building, but **no deliverable is complete until it runs against the real dependency**: real Profitex and pilot-client Xero exports, real production infrastructure, real alert channel, real backup bucket.
- Nothing is reported complete until its acceptance criteria are **observed** (on staging for UAT, in production for cut-over) and recorded in the UAT sign-off sheet.
- Phase 5 changes data in production for real clients. Every step that writes to production is listed in the cut-over runbook, rehearsed on staging first, and executed only with the project lead's authorisation (Plan §5.4).

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase

At the start of week 8 the following are built, merged to `main` and running on staging (Phases 0–4):

| Area | Exists (from earlier phases) | Relevance to Phase 5 |
|---|---|---|
| Tenancy & security | Practice / Organisation tenancy (A-01), auth + 2FA (A-02), RBAC with approval limits (A-03), append-only audit log (A-04), lock dates per module (A-05), documents inbox (A-06), Celery jobs (A-08) | Importer runs as an org-scoped background job; every imported record is audited with `source=xero_import`; lock dates are set after import |
| Ledger | CoA with sub-accounts, Canadian template with GIFI defaults (C-01), posting engine with book dimension (C-02), journal types (C-03), conversion balances blocked while unbalanced (C-05), period close (C-06) | Importer posts through the **same** posting engine and conversion-balance service — no direct SQL inserts |
| Sub-ledgers | Contacts with stable external ID import (B-03), sales documents with revisions (D-01…D-09), bills/PO/credits (E-01…E-07), bank accounts never locked + statement import with duplicate detection (F-01…F-07), items/stock (H-01…H-13), fixed assets with CCA (I-01…I-05), loans (FN-01…FN-05) | Importer maps Xero records onto existing models and services |
| Tax | Effective-dated codes (G-01), place of supply (G-02), GST/HST and QST worksheets (G-03, G-04), filing-cycle engine (G-03a/b), tax payments (G-09) | Xero's 36 flat tax rates are mapped to effective-dated Numo9 codes; parallel GST period is filed from Numo9 |
| Reporting | Report engine (K-01), core statements (K-02), AR/AP reconciliation (K-03), exceptions engine (K-09), two-book engine (K-07/K-08) | TB tie-out uses K-02; exceptions report on import uses K-09 |
| Payroll | Full Canadian payroll with uploaded CRA tables (N-01…N-13) | Parallel payroll run for one pay period |
| SaaS & web | Packages, billing, trial, demo, founding offer (U), accountant workspace (V), practice/portal (O), payments (P), website on staging (Q), public API (W-01) | Profitex and pilot client get real subscriptions in production; website moves to the production domain |
| Infrastructure | Repo + CI/CD (S-01), Canadian hosting (S-02), security baseline (S-03), multi-tenant scale baseline (S-06) | Production environment is provisioned in this phase; monitoring and backups become production-grade |

**Does not yet exist:** any Xero importer code; production monitoring/alerting; production backups with PITR and restore drill; UAT sign-off sheet; training material; admin / platform-owner / accountant guides, runbook, data dictionary, ADR-001…004 as finished documents; production environment with real data.

### 1.2 Problem definition — the seven questions for this phase

**1. Who uses this functionality?**

| Actor | Use in Phase 5 |
|---|---|
| Profitex (Platform Owner + first practice) | Migrates its own books from Xero; runs UAT; signs off; receives training and documentation; goes live |
| Pilot client organisation | Second migrated organisation; parallel GST period and payroll period run in both Xero and Numo9 |
| Accountant (any practice, after go-live) | Uses the **self-service** Xero importer for any organisation they manage |
| Organisation owner | Reviews migrated data, approves the go-live of their own organisation, uses the reconciliation screen |
| UAT testers (client-nominated) | Execute UAT scripts and record pass/fail with evidence |
| GMA QA engineer | Prepares UAT scripts, fixtures, gap-closure checklist; triages defects |
| GMA DevOps | Production environment, monitoring, backups, restore drill, scale test, cut-over |
| Project lead (Obadah Abu Odeh) | Authorises production writes, cut-over go/no-go, acceptance package |
| System | Import jobs, reconciliation jobs, backup jobs, alert rules, synthetic checks |

**2. What is the desired outcome?** Profitex and one pilot client run their live books on Numo9 in production; every opening balance and historic transaction ties to Xero to the cent; every component and every Xero gap row is observed working by the client in UAT; staff are trained; documentation is delivered; monitoring and backups protect production; Phase 5 is accepted and milestone 2 is invoiced.

**3. What are the inputs?** Xero export files for Profitex and the pilot client (Chart of Accounts CSV, Contacts CSV, Inventory Items CSV, Invoices/Credit Notes CSV, Bills/Supplier Credits CSV, Manual Journals export, Bank statement lines / Account Transactions report, Fixed Asset register CSV, Trial Balance report XLSX, Aged Receivables/Payables Detail XLSX, Tax Rates list, GST/HST return history, Payroll history from the client's payroll tool); CRA/RQ business numbers and program accounts; conversion date chosen by the client; UAT testers and their availability; decision-maker sign-off within 5 business days; Stripe live access; production hosting account; production domain DNS access.

**4. What are the outputs?** Two migrated, reconciled organisations in production; import reports (mapping review, retype list, tax-code mapping, dry-run report, TB tie-out = 0.00, AR/AP aging tie-out, exceptions report); self-service importer available to every practice; UAT sign-off sheet with one row per component acceptance criterion and one row per §4 gap row (61 rows), each with evidence; recorded training sessions + quick guides; documentation set in `docs/` and PDF (admin guide, platform-owner guide, accountant guide, runbook, API docs, ADR-001…004, data dictionary); production deployment on the Numo9 domain; monitoring dashboards and alert rules; encrypted backups with PITR and a timed restore drill report; scale test report (500 orgs × 100k lines p95 < 3 s); parallel-run reconciliation report (payroll + GST); Phase 5 acceptance package.

**5. What are the business rules?**
- The importer never writes to the ledger except through the posting engine (C-02) and the conversion-balance service (C-05); unbalanced opening balances **block** finalisation (never a silent "historical adjustment" account as in Xero teardown §6.11).
- Re-running an import with the same file is idempotent: matched on Xero's stable IDs (ContactID, InvoiceID, AccountID, JournalID) stored in `external_ref`, never by name (gap #21).
- No imported transaction may be dated inside a locked or filed period unless the import is the conversion import itself.
- Tax codes are mapped to effective-dated Numo9 codes by document date; an expired Xero rate (e.g. MB RST pre-1 Jul 2019, NS HST 15 % pre-1 Apr 2025) maps to the code valid on the document date, never to a current code.
- Mis-typed Xero accounts (1500 Inventory typed Current Asset; intangibles typed Fixed Asset; single 820 Sales Tax) are proposed for retyping/splitting and require human approval before finalisation.
- Imported invoices keep their Xero number as the Numo9 base number; later edits follow the revision rule (INV-0001 → INV-0001-1).
- Go-live requires: TB difference 0.00 for both orgs; parallel payroll period reconciled; parallel GST period reconciled; production running (Agreement 7.6).
- CRA six-year retention: backups and soft-deleted data retained ≥ 6 years; backups encrypted at rest; restore drill < 1 hour.
- No production write, merge to `main`, or deploy without the project lead's authorisation.

**6. What could go wrong?**
- Xero export formats vary (date formats DD-MM-YYYY vs "26 Oct 2026", decimal separators, tax-inclusive vs exclusive amounts, multi-line documents spread over rows, UTF-8 BOM, Windows-1252 encoding).
- Opening TB does not balance because Xero's 840 Historical Adjustment hides the difference.
- Rounding: Xero computes tax per line vs per document; Numo9 totals differ by 0.01 per document.
- Duplicate contacts in Xero (same name, different IDs) or contacts renamed between exports.
- Partially paid invoices; overpayments and prepayments; credit notes allocated across invoices.
- Manual journals posted to bank accounts duplicated by bank statement lines.
- Fixed assets without a CCA class; register not tied to CoA balances.
- Payroll parallel run differs from the external payroll tool by cents due to rounding method.
- Production outage during cut-over; DNS propagation; email deliverability on the new domain; Stripe live webhooks not configured.
- Restore drill exceeds 1 hour on the real database size.
- Alerts not reaching anyone (wrong channel, muted).
- UAT testers unavailable, feedback late (Agreement 6.3 extends timeline).

**7. What is the smallest useful implementation?** A Xero importer that takes CoA + contacts + opening TB at the conversion date + open AR/AP documents, produces a dry-run report and a TB tie-out, and finalises only at 0.00 — enough for Profitex to go live on opening balances. Historic transaction import (invoices, bills, journals, bank lines, assets, items) is layered on top, each type as its own atomic tasks, each re-verifying the tie-out.

### 1.3 Restated objective

- **Currently:** Numo9 is feature-complete for Phases 0–4 on staging, with fixture data only. Profitex and its clients still run on Xero. There is no way to bring Xero data in, no production environment with real data, no production-grade monitoring or backups, no UAT evidence, no training, no finished documentation.
- **Change:** Build a self-service, idempotent, dry-run-first Xero importer with mapping review and a reconciliation screen; migrate Profitex and the pilot client with TB tie-out 0.00; run UAT against every component acceptance criterion and every gap row; deliver training and documentation; provision production with monitoring, alerting, encrypted backups, PITR and a timed restore drill; prove the S-06 scale target; cut over with a parallel payroll and GST period.
- **Why:** Go-live is the contractual acceptance point (Agreement 7.6) and payment milestone 2; it proves Numo9 replaces Xero for real books; the self-service importer is the acquisition funnel for every future organisation switching from Xero.
- **Done means:** Profitex and pilot client live in production; TB tie-out 0.00 and exceptions report produced for both; UAT sign-off sheet complete (every component and every gap row observed); recordings and attendance delivered; documentation in `docs/` and PDF; alerts fire on test incidents; restore drill < 1 h; 500 orgs × 100k lines p95 < 3 s; parallel payroll and GST period reconciled; Phase 5 accepted in writing (or deemed accepted per 7.4).

### 1.4 Assumptions and interpretations

1. Xero has no bulk "export everything" button; the importer accepts the standard Xero CSV/XLSX exports listed in §1.2(3). A Xero API connector is **not** built (client decision 4 — no third-party integrations); file-based import only.
2. Conversion date is chosen by the client (default: first day of the current fiscal year, 1 Jan 2026, so the 2026 activity — incl. the REFINED journals of 3 Jun and 15 Jun 2026 — is imported as history).
3. History imported: full current fiscal year of documents and journals; prior years as opening balances + comparative TB only (Plan §1.8 (11)). Client may request more years; each extra year is the same importer re-run.
4. Payroll history is imported as YTD balances per employee per box (needed for CPP/EI maximums and T4), not as individual historic pay runs.
5. The pilot client is nominated by Profitex by the start of week 8; if not, Profitex's own books alone go live and the pilot follows within hypercare (documented as a client delay under Agreement 6.3).
6. Training sessions are recorded video (screen + voice) with quick-reference PDFs; live sessions are scheduled with the client.
7. UAT environment = staging with a copy of the dry-run imported data (anonymised where personal data is not needed).
8. Production region = the Canadian region decided in ADR-001.

**Open questions for the client (not blocking build):** conversion date; pilot client identity; parallel-run pay period and GST period; who receives production alerts after hours.

### 1.5 Client inputs required

| Input | Due | Used by |
|---|---|---|
| Xero exports for Profitex (full list §1.2) | Start of week 8 (day 1) | T-01 |
| Xero exports for pilot client | Start of week 8 (day 1) | T-01 |
| CRA BN + RT/RP/RC program accounts, RQ numbers for both orgs | Day 1 | T-01, T-05 |
| Conversion date decision | Day 1 | T-01 |
| UAT testers (names, roles, availability) | Day 1 | T-02 |
| Decision-maker sign-off within 5 business days | End of week 8 | T-02, T-05 |
| Stripe live keys, production hosting account, DNS access, transactional email domain | Day 2 | T-05, S-04, S-05 |
| Alert recipients (email / phone / chat) | Day 2 | S-04 |
| Training attendees and session times | Day 3 | T-03 |
| Payroll tool history (YTD per employee) for both orgs | Day 1 | T-01, T-05 |

---

## 2. BETTER THAN XERO — gap analysis for this phase

| Gap # | Teardown ref | What Xero does / fails to do | What Numo9 does instead (better) | Observable proof (test tag) |
|---|---|---|---|---|
| 15 | §2.6 | Invoice import is CSV only, headers must match exactly, no column-mapping step, no dry-run preview; direct URL without `?type` silently redirects | Import wizard accepts CSV, XLSX and TXT; auto-detects Xero export type from headers; column-mapping step with saved mappings; full dry-run with row-level results before any write; every wizard URL is valid and explains missing parameters | `gap-15` Playwright: upload XLSX with re-ordered headers → mapping auto-filled → dry-run shows 0 writes |
| 21 | §3.3 | Contact import matches on name (renames create duplicates); blank columns delete people; max 5 extra people; 1,000 contacts per import | Matching on Xero ContactID stored as `external_ref`; blank cells never delete; unlimited people; no row cap (streamed, chunked job) | `gap-21` pytest: re-import → 0 creates, 0 updates; renamed contact updated in place |
| 29 | §5.4 | Mis-typed template (Inventory as Current Asset, intangibles as Fixed Asset), single 820 Sales Tax, mixed 3/4-digit codes | Importer **detects** mis-typing and proposes retype; splits 820 Sales Tax into GST/HST payable, ITC receivable, PST, QST by tax-component history; proposes renumbering 610/800/820/960 into the 4-digit scheme | `gap-29` fixture REFINED: 1500 proposed → Inventory; goodwill → Non-current Asset; 820 split proposed |
| 30 | §5.5 | 0 of 139 accounts mapped to GIFI | Every imported account receives a suggested GIFI code (name/type matching + Numo9 template); unmapped count shown and must reach 0 or be explicitly accepted | `gap-30` REFINED import: unmapped GIFI = 0 after review |
| 45 | §6.9 | 142 accounts default Tax Exempt; no zero-rated vs exempt; no effective dates | Importer flags "Tax Exempt on normally taxable expense account" and proposes home-province purchase code; maps Xero rates to effective-dated Numo9 codes by document date; zero-rated vs exempt chosen in mapping review | `gap-45` mapping report lists 142 → proposed defaults |
| 47 | §6.11 | Unbalanced conversion balances silently pushed to 840 Historical Adjustment | Finalisation blocked while difference ≠ 0.00; the reconciliation screen names the difference per account and per source file; 840 balance is surfaced as an item to resolve, never carried silently | `gap-47` pytest: TB off by 0.01 → finalise refused with named account |
| 33 / 36 / 59 | §5.8, §5.12, §9.6 | Petty cash −994.17 via journals, no contact, all exempt; exceptions report flags nothing | Exceptions engine (K-09) runs automatically at the end of every import and lists every teardown issue with a draft correcting entry | `gap-59` REFINED import: exceptions report lists negative petty cash, journal-only expenses, exempt coding, no BN, no lock date |
| 37 | §5.13 | History export PDF/Excel only, 7-day default | Import audit report: every created/updated record with source file, row and before/after values; CSV/XLSX/PDF | `gap-37` import audit export = screen |
| 44 | §6.8 | No lock date; registration status changed silently by "System Generated" | Cut-over sets per-module lock dates at the conversion date; every registration change during import is attributed to the importing user | `gap-44` after finalise: GL/AR/AP/Bank/Tax locks set; audit shows user |
| 48 | §6.12 | Export only to a list of (mostly AU/NZ) practice tools; no generic ledger export | Before cut-over, the full Numo9 ledger is exported (CSV/JSON) and archived as the go-live baseline; same export available to every org | `gap-48` export checksum stored |
| 54–57 | §9.1–§9.4 | No AR/AP control reconciliation; TB unsorted, YTD only | Tie-out screen compares Xero TB vs Numo9 TB sorted by code with opening/movement/closing; AR/AP aging vs control per contact | `gap-54`, `gap-57` |
| 61 | §10.B | No clear plan/feature matrix | Training and admin guide include the in-app feature matrix walk-through | T-03 checklist |

**Gap-closure verification (T-02):** every one of the 61 rows of Plan §4 is executed as a UAT check in this phase, tagged `gap-01` … `gap-61`, with evidence (screenshot / test log / report export).

**Beyond-Xero additions in this phase**
- Self-service migration from Xero for any organisation (Xero offers import from other tools only piecemeal, CSV by CSV, with no tie-out).
- Automatic TB tie-out to the cent at conversion date and at every month-end of the imported history.
- Account retyping and control-account splitting assistant.
- Exceptions report on import with draft correcting entries (e.g. the teardown's suggested Dr 1000 Petty Cash 994.17 / Cr 2900 Shareholder Loan 994.17, left as a draft for the accountant).
- CCA class suggestions for every imported fixed asset (Xero has no CCA book).
- Parallel-run reconciliation report (payroll and GST) comparing the legacy figures to Numo9.
- Timed, documented restore drill and scale proof as release gates.

**Xero strengths matched conceptually (original design)**
- Xero's step-by-step conversion guide (bank balances → invoices → bills → other → confirm) is matched by an original five-step "Move to Numo9" checklist with live progress, but each step validates instead of just guiding.
- Xero's find-and-recode audit report is matched by an import batch audit report with undo of a whole import batch before finalisation.

**[EXTRA] improvements within scope (refinements of T-01 / T-05 / S-04 / S-05)**
- [EXTRA] Import "undo batch" before finalisation (delete everything created by batch N, audited) — refinement of T-01.
- [EXTRA] Month-by-month tie-out (not only the closing TB) so a difference is pinned to the month it appears in.
- [EXTRA] Encoding/date-format auto-detection with a preview of the first 20 parsed rows.
- [EXTRA] Saved mapping profiles per practice so the second, third … organisation imports faster.
- [EXTRA] Migration readiness score (0–100 %) on the org's home screen during migration.
- [EXTRA] Synthetic "golden path" monitor in production (login → open dashboard → run TB) every 5 minutes.
- [EXTRA] Status page for the Numo9 product (internal first, public later) driven by the same synthetic checks.
- [EXTRA] Go-live baseline snapshot: full-ledger export + DB snapshot + checksum stored before the first live transaction.

---

## 3. UI/UX DESIGN PLAN

### 3.1 UX principles applied in this phase

1. **Dry-run first, always.** Nothing touches the ledger until the user has seen exactly what will be created, updated, skipped or rejected. The primary button after upload is "Check my files", not "Import".
2. **One wizard, one mental model.** The whole migration is one guided flow ("Move to Numo9") with a persistent left-side stepper and a progress percentage; each step can be revisited.
3. **Progressive disclosure.** Summary first (counts, totals, difference), details on demand (row-level table, per-account drill-down).
4. **No silent decisions.** Every automatic choice (retype, tax mapping, GIFI suggestion, duplicate merge) is shown as a suggestion with its reason ("Suggested because the account name contains 'Inventory' and Numo9 needs an Inventory-type account to track stock") and needs Accept / Change / Skip.
5. **Bulk where it is safe, one-by-one where it matters.** "Accept all suggestions in this group" for GIFI codes; account retypes and the 820 split are confirmed one by one.
6. **Errors name the cause and the fix,** with a link to the exact row and column in the source file.
7. **Forgiving inputs.** Any column order, CSV or XLSX, BOM or no BOM, Windows-1252 or UTF-8, "26 Oct 2026" or "26-10-2026" — detected and previewed.
8. **Undo over confirm.** An import batch can be undone until finalisation; finalisation is the only irreversible action and it is behind a clear summary and a typed confirmation ("FINALISE").
9. **Difference is the hero number.** The reconciliation screen shows one large figure — "Difference: 0.00" — green when zero, amber otherwise, with "Explain this difference" listing the accounts responsible.
10. **Keyboard-first for accountants.** Mapping review grid supports ↑/↓, Enter to accept, E to edit, S to skip, `/` to search.
11. **Long-running work is visible and resumable.** Import runs as a job with a progress bar, ETA, row counter; the user can leave the page and receives a notification when done.
12. **Accessibility:** WCAG 2.1 AA; colour never the only signal (icons + text for pass/fail); focus order follows the stepper; status updates announced via `aria-live`.
13. **Localisation-ready:** all strings in en-CA / fr-CA catalogues; layouts hold with +30 % strings; amounts formatted per locale (1,234.56 / 1 234,56 $).
14. **Responsive:** wizard usable on a tablet (UAT testers often review on iPad); the mapping grid collapses to cards below 768 px.
15. **Operational screens are calm:** ops dashboards (monitoring, backups) use the same design system, traffic-light status, and plain-language runbook links on every alert.

### 3.2 Information architecture / navigation added in this phase

```
Organisation menu
 └─ Settings
     └─ Data
         ├─ Move to Numo9 (Xero importer)      ← new (also offered on empty dashboard of a new org)
         │    ├─ 1 Conversion date & files
         │    ├─ 2 Check files (parse + preview)
         │    ├─ 3 Review mappings (accounts, tax codes, GIFI, contacts, items, assets)
         │    ├─ 4 Dry run report
         │    ├─ 5 Import & reconcile (tie-out)
         │    └─ 6 Finalise & lock
         ├─ Import history (batches, audit report, undo)
         └─ Export full ledger (W-01 export)
Practice workspace
 └─ Migrations board (all orgs being migrated, status, difference, readiness %)   ← new
Platform-owner console
 ├─ Operations › Monitoring (dashboards, alert rules, incidents)                 ← new
 ├─ Operations › Backups & restores (schedule, last backup, last drill)          ← new
 ├─ Operations › Scale test results                                              ← new
 └─ Go-live › UAT sign-off sheet, Cut-over checklist                              ← new
Help
 └─ Guides (admin / platform owner / accountant), Training videos, API docs      ← new
```

### 3.3 Screen inventory

| Screen | Primary user | Purpose | Key components (design system) | States | Keyboard shortcuts |
|---|---|---|---|---|---|
| Move to Numo9 — Start | Accountant / owner | Choose source (Xero), conversion date, see checklist of files needed | Stepper, DatePicker, Checklist, FileDropZone | Empty (no files) / partial (some files) / locked (already finalised → read-only summary) | `Ctrl+U` upload |
| File check & preview | Accountant | Show detected export type, encoding, date format, row count, first 20 rows | FileCard, DataPreviewTable, Badge (detected type), InlineAlert | Loading (parsing) / error (unreadable file, wrong type) / success | `Tab` between files |
| Column mapping | Accountant | Map unknown columns when headers differ | MappingGrid (source → target), Select, SavedProfile picker | Auto-mapped / needs attention / saved profile applied | `↑/↓`, `Enter`, `/` |
| Account review | Accountant | Approve retype, renumber, split 820, sub-account placement, GIFI suggestion | ReviewGrid with Suggestion chips, ReasonTooltip, BulkAcceptBar | Suggestion / accepted / changed / skipped | `Enter` accept, `E` edit, `S` skip |
| Tax-code mapping | Accountant | Map each Xero tax rate to effective-dated Numo9 codes, zero-rated vs exempt | ReviewGrid, EffectiveDateRange pill, Warning chip | Mapped / ambiguous / unmapped (blocks dry run) | as above |
| Contact & item review | Accountant | Duplicates, role (customer/supplier/both), province, currency | DuplicateCard (merge / keep both), RolePicker | Clean / duplicates found | `M` merge |
| Fixed-asset review | Accountant | CCA class suggestions, book method, link to CoA | ReviewGrid, CCAClassPicker | Suggested / confirmed | as above |
| Dry-run report | Accountant / owner | Counts per type: create / update / skip / reject; reasons; downloadable | SummaryTiles, ResultTable (virtualised), FilterChips, Export button | Clean (0 rejects) / has rejects (blocks import) | `F` filter |
| Import progress | Accountant | Live job progress | ProgressBar, RowCounter, ETA, Notification toggle | Running / paused / failed (with retry) / done | — |
| Reconciliation (tie-out) | Accountant / owner / reviewer | Xero TB vs Numo9 TB, by account, by month; AR/AP aging vs control | HeroDifference figure, ComparisonTable sorted by code, MonthStrip, DrillDown drawer | 0.00 green / ≠ 0 amber with "Explain" | `D` drill down, `[` `]` month |
| Exceptions on import | Accountant | K-09 results with draft correcting entries | ExceptionList, SeverityBadge, "Create draft journal" | None / list | — |
| Finalise & lock | Accountant (approver) | Summary, typed confirmation, set lock dates | SummaryPanel, TypedConfirm, LockDate pickers | Blocked (difference ≠ 0 / rejects) / ready / done | — |
| Import history | Accountant / auditor | Batches, audit report, undo before finalise | Table, AuditDiff drawer, Undo button | — | — |
| Migrations board | Practice admin | All orgs migrating: stage, difference, readiness % | Kanban/List toggle, ProgressRing | Empty / list | `G` group |
| UAT sign-off sheet | QA / UAT tester / decision-maker | Rows per component criterion and gap row; pass/fail/evidence/sign | ChecklistTable, EvidenceUploader, SignatureBlock, Filter by component | Not started / in progress / failed / passed / signed | `P` pass, `X` fail |
| Cut-over checklist | Project lead / DevOps | Runbook steps with owner, time, status | StepList with timers, Go/No-go gate | Pending / running / done / rolled back | — |
| Monitoring dashboard | Platform owner / DevOps | Health, errors, latency, queues, alerts | StatusTiles, TimeSeries, IncidentList | Healthy / degraded / down | — |
| Backups & restores | Platform owner / DevOps | Last backup, PITR window, last drill time, retention | StatusTiles, Timeline, DrillReport | OK / overdue / failed | — |
| Guides & training | All | Read guides, watch recordings | DocViewer, VideoPlayer with chapters, Search | — | `/` search |

### 3.4 Key user flows

**Flow A — Self-service migration from Xero (accountant, target ≤ 30 min of active work for a small org)**
1. Open new org → empty dashboard card "Coming from Xero? Move your books in 6 steps" → click (1 click).
2. Pick conversion date (default: start of current fiscal year) → see checklist of the 11 Xero exports with "How to export this from Xero" help (text written by Numo9, no Xero screenshots).
3. Drag all files at once into the drop zone (1 action) → each file shows detected type, rows, encoding, date format in ≤ 5 s per 10k rows.
4. If a file's headers are unusual → column mapping opens pre-filled; confirm (≤ 3 clicks).
5. Review mappings: accounts (retype/split/GIFI), tax codes, contacts, items, assets — "Accept all safe suggestions" per tab, then resolve the remaining flagged rows one by one.
6. Run dry run (1 click) → report: e.g. "139 accounts, 0 rejects · 2 journals · TB difference 0.00 (expected)".
7. Import (1 click) → progress → notification "Import finished".
8. Reconciliation screen opens automatically: Difference 0.00 → green; exceptions list shows teardown-style issues with draft fixes.
9. Finalise: type FINALISE → lock dates set at conversion date → org enters live mode.

**Flow B — Difference investigation (target: find the cause in ≤ 3 clicks)**
1. Reconciliation shows "Difference 12.34".
2. Click "Explain" → accounts with differences ranked by amount.
3. Click account → month strip highlights the first month with a difference → drill to the rows (source file row numbers and Numo9 records side by side).

**Flow C — UAT (tester)**
1. Open UAT sign-off sheet filtered to "My rows".
2. Each row: criterion text, linked script, "Open in staging" deep link.
3. Execute → mark Pass with evidence (screenshot paste / file) or Fail with a defect description → defect auto-created with row reference.
4. Decision-maker filters "All passed" → signs the sheet.

**Flow D — Cut-over (project lead)**
1. Open cut-over checklist; go/no-go gate shows prerequisites (UAT signed, rehearsal done, backups verified, alerts tested).
2. Execute steps in order with timers; each step records who/when; rollback steps visible beside each step.

### 3.5 Microcopy & error-message rules

Rules: say what happened, why, and what to do next; reference the file, row and column; never blame the user; use Canadian terms (Province, Postal code, GST/HST, cheque); amounts always with currency; never show stack traces.

| Situation | Message |
|---|---|
| Unknown file | "We couldn't tell which Xero export this is. It has columns *Name, Amt, Dt*. Choose the export type or map the columns yourself." |
| Date ambiguity | "Dates like 03-06-2026 could be 3 June or 6 March. We read them as day-month-year because 25-12-2026 appears in row 14. Change if needed." |
| Unbalanced TB | "Your opening balances are off by 12.34 CAD. You can't finalise until the difference is 0.00. The biggest difference is on 1000 Petty Cash (−994.17 in Xero, −981.83 in Numo9)." |
| Historical Adjustment | "Xero has 840 Historical Adjustment with a balance of 250.00. That account usually hides an opening difference. Tell us where this amount belongs before you finalise." |
| Mis-typed account | "1500 Inventory is set up as a Current Asset in Xero. Numo9 needs it to be an Inventory account to track stock. Suggested: change type to Inventory." |
| Tax code mapping | "'MB GST/RST on Purchases (pre 1 July '19)' was valid until 30 June 2019. Documents dated after that will use 'MB GST 5 % + RST 7 % (purchases)'." |
| Re-import | "This file was already imported on 12 Nov 2026. 0 new rows, 0 changes. Nothing to do." |
| Locked | "This organisation was finalised on 14 Nov 2026 and is live. To import more history, unlock the period first (Settings › Lock dates)." |
| Alert (ops) | "Error rate for /api/v1/invoices is 3.2 % (threshold 1 %) for 5 minutes. Runbook: RB-04 API errors." |

### 3.6 Accessibility & usability test plan

| # | Usability task | Participant | Success metric |
|---|---|---|---|
| U1 | Migrate the REFINED fixture from Xero exports to finalise | Profitex accountant | Completed unaided in ≤ 30 min; ≤ 1 help lookup |
| U2 | Find why the TB is off by 0.01 (seeded rounding fixture) | Profitex accountant | Cause found in ≤ 3 clicks / ≤ 2 min |
| U3 | Accept all GIFI suggestions but change two | Accountant | ≤ 1 min; no wrong code accepted |
| U4 | Record a failed UAT row with evidence | UAT tester | ≤ 1 min |
| U5 | Find the runbook for a firing alert | DevOps / platform owner | ≤ 30 s |
| U6 | Find a training video chapter on invoice revisions | Org owner | ≤ 30 s via search |

Accessibility: axe-core zero serious/critical violations on every new screen; keyboard-only completion of Flow A; screen-reader pass (NVDA + VoiceOver) on reconciliation screen; contrast ≥ 4.5:1; reduced-motion respected on progress animations.

---

## 4. TOOLS & TECHNOLOGY FOR THIS PHASE

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| Backend | Python 3.12, Django 5, DRF | Importer services and APIs | GMA core stack |
| Backend | Celery + Redis | Chunked import jobs, reconciliation jobs, backup verification jobs | Idempotency keys per batch/chunk |
| Parsing | `csv` (stdlib) + `charset-normalizer` | CSV parsing with encoding detection (UTF-8/BOM/Windows-1252) | MIT |
| Parsing | `openpyxl` | XLSX exports (TB, aging, asset register) | MIT |
| Parsing | `python-dateutil` | Ambiguous date parsing with explicit dayfirst detection | BSD |
| Parsing | `pandas` (optional, offline analysis scripts only) | Ad-hoc reconciliation analysis in QA notebooks | Not in request path |
| Validation | `pydantic` v2 | Row schemas per Xero export type | MIT |
| Money | `decimal.Decimal` with ROUND_HALF_UP; `py-moneyed` | Exact amounts, per-line vs per-document tax rounding | Never float |
| Matching | `rapidfuzz` | Fuzzy name matching for duplicate contacts and GIFI suggestions | MIT |
| Storage | S3-compatible storage (Canadian region), `django-storages`, `boto3` | Uploaded export files (encrypted, 30-day lifecycle after finalise) | Hosting cost: client |
| DB | PostgreSQL 16, `pg_partman` | Partitioned posting/audit tables; scale test | — |
| Backups | `pgBackRest` (or WAL-G) | Full + incremental backups, WAL archiving, PITR, encryption | Client pays storage |
| Backups | `restic` | File/object storage backups (documents bucket) | Encrypted |
| Backups | `age` / KMS | Backup encryption keys | Keys in secrets manager |
| Observability | Sentry (or GlitchTip self-hosted) | Error tracking backend/frontend/Celery | S-04 |
| Observability | Prometheus + `django-prometheus` + `celery-exporter` + `postgres_exporter` + `redis_exporter` + `node_exporter` | Metrics | — |
| Observability | Grafana | Dashboards, alerting | — |
| Observability | Alertmanager (or Grafana alerting) | Routing to email / SMS / chat | Client provides recipients |
| Observability | Loki + Promtail (or hosted equivalent) | Central structured logs | — |
| Observability | `structlog` / `python-json-logger` | JSON logs with org_id, request_id, job_id; SIN never logged | — |
| Observability | OpenTelemetry SDK | Traces for slow reports and import jobs | — |
| Synthetic | Uptime Kuma / Grafana synthetic + Playwright script | Golden-path checks every 5 min; status page | [EXTRA] |
| Load | k6 | 500 orgs × 100k lines p95 < 3 s; 50 concurrent users per org | S-06 target |
| Data gen | Faker + factory_boy + custom `make_scale_practice` command | 500-org fixture practice | Build in this phase |
| Testing | pytest, pytest-django, Hypothesis | Importer unit/property tests (idempotency, TB invariance) | — |
| Testing | Playwright | Wizard E2E, UAT scripts, gap-NN checks | — |
| Testing | Vitest + Testing Library | Wizard components | — |
| Testing | Storybook + Chromatic (or Playwright visual snapshots) | Visual regression of new screens | — |
| Testing | axe-core / @axe-core/playwright, Lighthouse CI | Accessibility & performance | — |
| Testing | `pytest-benchmark` | Parser throughput (rows/s) | — |
| Quality | ruff, mypy, eslint, prettier, pre-commit, import-linter, semgrep | Static checks; import-linter forbids importer writing outside services | — |
| Security | OWASP ZAP (production baseline scan), pip-audit, npm audit, gitleaks, Trivy (images), `sslyze`/SSL Labs, securityheaders check | Go-live security gate | No high findings |
| Security | ClamAV hook (A-06) | Scan uploaded export files | — |
| Infra | Docker Compose, Caddy, GitHub Actions, Terraform (or provider CLI scripts) | Production provisioning and deploy | ADR-001 region |
| Infra | Secrets manager (provider KMS / Doppler / SOPS) | Production secrets | — |
| DNS / mail | Provider DNS, transactional email provider, `checkdmarc` / mail-tester | SPF/DKIM/DMARC on production domain | — |
| Payments | Stripe CLI, Stripe Dashboard (live) | Live webhook endpoints, test charges | Client account |
| Docs | MkDocs Material + `mkdocs-pdf` (WeasyPrint) | Guides, runbook, data dictionary → site + PDF | — |
| Docs | drf-spectacular + Redoc | API docs (OpenAPI 3) | — |
| Docs | `django-schema-graph` / `eralchemy` / `django-extensions graph_models` | ER diagrams for data dictionary | — |
| Docs | ADR template (MADR) | ADR-001…004 | — |
| Docs | Mermaid | Runbook flowcharts | — |
| Training | OBS Studio, DaVinci Resolve / Shotcut, Whisper (captions), ffmpeg | Recording, editing, EN captions, chapter markers | Free tools |
| Training | Loom (optional) | Quick clips | Client licence if used |
| UAT | Numo9 UAT sheet (built in-app) + XLSX export via openpyxl | Sign-off evidence | Built here |
| Defects | GitHub Issues + Projects, labels `uat`, `gap-NN`, `severity/*` | Defect tracking | — |
| Design | Figma | Wizard and reconciliation wireframes / prototypes | — |
| Internal tools to BUILD | `xero_import` package (parsers, mappers, loaders), `manage.py import_xero --dry-run`, `manage.py tieout <org> <date>`, `manage.py undo_import_batch`, `make_xero_fixture` (REFINED + pilot-style fixtures), `make_scale_practice --orgs 500 --lines 100000`, `restore_drill.sh` with timing report, `cutover.sh` checklist runner, `uat_seed` (rows from §3 + §4), `ledger_export_baseline` with SHA-256 checksum, alert test trigger endpoint (`/ops/test-alert`, platform-owner only) | — |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 objective

Move Profitex and one pilot client from Xero to Numo9 in production with a to-the-cent tie-out, prove every component and gap with client-observed UAT, train users, document the system, and run production with monitoring, alerting, encrypted backups, PITR and proven scale — so that Phase 5 is accepted and Go-Live is achieved.

### 5.2 Level 2 components

| Component | Deliverables | Purpose |
|---|---|---|
| Migration | T-01 | Self-service Xero importer with dry run, mapping review, tie-out, exceptions report |
| Assurance | T-02 | UAT sign-off sheet per component and gap row |
| Enablement | T-03, T-04 | Training and documentation |
| Operations | S-04, S-05 (+ S-06 target proof) | Monitoring, logging, alerting; backups, retention, restore drill, scale |
| Cut-over | T-05 | Production deployment, parallel payroll and GST period, go-live |

### 5.3 Dependency graph and execution order

```
S-04 Monitoring ──┐
S-05 Backups ─────┼──────────────────────────────┐
                  │                              │
T-01 Importer ────┼─► (dry-run on staging) ─► T-02 UAT ─► T-05 Cut-over ─► Go-Live acceptance
                  │                              ▲
T-04 Docs ────────┴─► T-03 Training ─────────────┘
```

Execution order (week 8, parallel tracks):
1. **Day 1 (parallel):** T-01 parsers & models · S-04 production metrics/errors · S-05 backup tooling · T-04 doc skeleton/ADRs · T-02 UAT sheet model & seed.
2. **Day 2:** T-01 mappers & review UI · S-04 alert rules · S-05 PITR + first backup · T-04 guides.
3. **Day 3:** T-01 loaders, tie-out, exceptions · dry-run of Profitex + pilot on staging · S-05 restore drill · S-06 scale run · T-03 recordings start.
4. **Day 4:** T-02 UAT execution (components + gap rows) · defect fixing · T-05 cut-over rehearsal on staging.
5. **Day 5:** T-05 production cut-over · parallel period start · T-03 live sessions · acceptance package.
6. **Week 9 (hypercare):** parallel payroll / GST period completes and is reconciled (closing condition of Agreement 7.6).

---
## 6. PLAN — Deliverable cards with ATOMIC TASKS (Rule 3)

### T-01 · Xero importer

- **Branch:** `feature/T-01-xero-importer`
- **Objective:** a self-service importer that moves any organisation's books from Xero exports into Numo9 with dry run, mapping review, retyping review, tax-code mapping, TB tie-out to 0.00 and an exceptions report — used first for Profitex and the pilot client.
- **Current behaviour:** no importer; organisations can only start fresh or use B-03 contact import and F-02 statement import.
- **Expected behaviour (better than Xero):** one wizard accepting CSV/XLSX in any column order; detection of each Xero export type; idempotent re-import keyed on Xero IDs; non-destructive updates; mis-typed accounts and the single 820 Sales Tax account proposed for correction; Xero tax rates mapped to effective-dated Numo9 codes by document date; GIFI suggested for every account; CCA class suggested for every asset; dry run before any write; import through the posting engine; TB and AR/AP tie-out per month; finalisation blocked unless difference 0.00; exceptions report with draft correcting entries; lock dates set on finalise; undo of a batch before finalise.
- **Gap #s closed / proven:** 15, 21, 29, 30, 45, 47, 33/36/59 (on import), 37, 44, 54, 57.
- **Business rules:** see §1.2(5). Additionally: import job is org-scoped (A-01) and requires permission `data.import` (A-03); feature key `platform.migration` is included in every package and the trial (never gated — migration is the acquisition funnel); one active (unfinalised) batch per organisation; finalised org cannot run conversion import again, only "history import" into unlocked periods.
- **Edge cases:** multi-line invoices across rows; tax-inclusive documents; partial payments; overpayments/prepayments; credit-note allocations; voided/deleted items (skipped and reported); contacts archived in Xero; duplicate ContactName with different IDs; accounts archived but with balance; bank lines that duplicate journals; foreign-currency documents (R-01 rates from file); zero-amount documents; documents dated before conversion date (opening AR/AP only); documents in locked Numo9 periods; files > 100k rows; encoding issues; Xero "Historical Adjustment" and "Rounding" system accounts.
- **UI/UX notes:** §3.3 screens "Move to Numo9" through "Import history"; Flow A and B (§3.4); hero difference figure; suggestion chips with reasons; typed confirmation on finalise; progress job with notification.
- **Dependencies:** A-01, A-03, A-04, A-05, A-06, A-08, B-01, B-03, C-01, C-02, C-05, C-06, D-03a, D-05, D-06, E-02, E-03, F-01, F-02, G-01, G-02, H-01, I-01, I-03, K-02, K-03, K-09, N (YTD), R-01.

**Atomic tasks**

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| T-01-T01 | Restate T-01 objective and acceptance in PR description; inventory existing services the importer must reuse (posting engine, conversion balances, B-03 contact importer, F-02 statement importer) and record "reuse, don't duplicate" list | DOC | — | PR description lists reused services and acceptance criteria | Review |
| T-01-T02 | Collect real Xero export samples (REFINED teardown org + anonymised Profitex samples) and build `tests/fixtures/xero/` with one folder per export type and a README describing each file's columns | QA | T01 | 11 export types present; README lists headers per type | Fixture loads in pytest |
| T-01-T03 | Wireframes in Figma for wizard steps 1–6, reconciliation screen, mapping review grids; review with Profitex accountant | UX | T01 | Figma link approved in PR; covers all states in §3.3 | Design review |
| T-01-T04 | Models `ImportBatch` (org, source=`xero`, conversion_date, status draft/checked/mapped/dry_run/importing/imported/finalised/undone, created_by, stats JSON) and `ImportFile` (batch, export_type, storage key, encoding, date_format, row_count, sha256) extending `OrgOwnedModel` | DB | T01 | Migration applies; models in tenant sweep registry | Unit: creation, tenancy scoping |
| T-01-T05 | Model `ImportRow` (file, row_no, raw JSON, parsed JSON, status ok/warning/rejected/skipped, messages[], target_ct + target_id) with index on (batch, status); partitioned by batch for large files | DB | T04 | 100k-row insert < 10 s on staging | Perf test with pytest-benchmark |
| T-01-T06 | Model `ExternalRef` (org, source, external_type, external_id, target_ct, target_id, unique(org, source, external_type, external_id)) used for idempotent matching | DB | T04 | Duplicate insert raises IntegrityError | Unit |
| T-01-T07 | Model `MappingDecision` (batch, kind account/tax/gifi/contact/item/asset/column, source_key, suggestion JSON, reason text, decision accepted/changed/skipped, final JSON, decided_by, decided_at) | DB | T04 | Decisions audited (A-04 hook) | Unit + audit assertion |
| T-01-T08 | Upload API `POST /api/v1/imports/xero/batches/{id}/files` with A-06 storage, 25 MB per file default (configurable to 100 MB for import), MIME + ClamAV scan, SHA-256 dedupe within batch | API | T04 | Same file twice → second rejected with "already uploaded" message; virus test file rejected | Integration |
| T-01-T09 | Encoding & dialect detector (charset-normalizer, BOM strip, delimiter sniff, XLSX sheet pick) returning preview of first 20 rows | BE | T08 | UTF-8-BOM, Windows-1252 and XLSX fixtures all preview correctly | Unit (parametrised) |
| T-01-T10 | Export-type detector: header signature table for the 11 Xero exports (CoA, Contacts, Items, Sales invoices/credit notes, Bills/supplier credits, Manual journals, Account transactions / bank lines, Fixed assets, Trial balance, Aged receivables detail, Aged payables detail) + tax rates list | BE | T09 | Each fixture detected; unknown headers → `unknown` with suggestion list | Unit |
| T-01-T11 | Date-format detector (day-first vs month-first vs "26 Oct 2026") using unambiguous rows; decision stored on `ImportFile` and editable | BE | T09 | REFINED journals "03-06-2026" read as 3 Jun 2026 when another row has day > 12 | Unit + Hypothesis on random dates |
| T-01-T12 | Column-mapping service and saved mapping profiles per practice (`ImportMappingProfile`) for non-standard headers | BE | T10 | Re-ordered / renamed header fixture maps after one confirmation; second org reuses profile | Unit + integration |
| T-01-T13 | Pydantic row schemas per export type with Decimal amounts, required fields, enum normalisation (e.g. "Tax Exclusive"/"Tax Inclusive"/"No Tax") | BE | T10 | Invalid rows produce field-level messages; valid rows parse | Unit per schema |
| T-01-T14 | Parser job (Celery, chunked 2,000 rows, idempotency key = file sha + chunk) writing `ImportRow` with status/messages; progress events via notification channel | BE | T05, T13 | 100k-row file parses with progress updates; restart resumes without duplicates | Integration (kill worker mid-job) |
| T-01-T15 | CoA mapper: Xero type → Numo9 type/sub-type table; code normalisation; archived accounts with balance kept active-archived; system accounts 610/800/801/803/820/840/860/877/960 mapped to Numo9 system accounts | BE | T13 | REFINED 139 accounts map; 0 unmapped types | Unit on REFINED fixture |
| T-01-T16 | Retyping rules engine producing suggestions with reasons: "Inventory" named Current Asset → Inventory; Goodwill/Incorporation Costs/R&D/Licenses/Software typed Fixed Asset → Non-current Asset (intangible); paired Accum. Amort. kept next to its asset; mixed 3-digit system codes → renumber proposal into 4-digit scheme | BE | T15 | REFINED: 1500 + 5 intangibles flagged; 610/800/820/960 renumber proposals | Unit |
| T-01-T17 | Sales-tax control split proposal: analyse tax components on documents/journals to split Xero 820 Sales Tax into GST/HST payable, ITC receivable, PST payable, QST payable, QST ITR; opening balance split by component | BE | T15 | Fixture with mixed GST/PST lines splits to the cent; total equals 820 balance | Unit + property (split sums equal) |
| T-01-T18 | GIFI suggestion engine (Numo9 template match by code range, type, rapidfuzz on name) with confidence score; unmapped count | BE | T15 | REFINED: every account gets a suggestion; ≥ 90 % match Numo9 template expectation | Unit |
| T-01-T19 | Tax-code mapper: each Xero rate (36 on REFINED) → effective-dated Numo9 codes; date-dependent mapping (pre-1 Jul 2019 MB RST, pre-1 Apr 2025 NS 15 %); zero-rated vs exempt question for "Exempt Sales"/"Tax Exempt"; non-recoverable component → recoverable split | BE | T13, G-01 | Every REFINED rate maps or is listed as needing a decision; expired rate never mapped to a current code for a document after its end date | Unit + Hypothesis over dates |
| T-01-T20 | "Exempt on taxable expense account" detector proposing home-province purchase code as account default (gap #45) | BE | T19 | REFINED: 142 accounts listed with proposed default | Unit |
| T-01-T21 | Contact mapper: ContactID → ExternalRef; role inferred from documents then shown for explicit confirmation; Province from address; currency; duplicate detection (same name/email/tax ID, different IDs) with merge/keep proposal; unlimited people; blank cells never clear fields | BE | T13, B-01, B-03 | Re-import → 0 creates/0 updates; renamed contact updates in place; duplicate pair shown | Unit + integration |
| T-01-T22 | Item mapper: code, name, purchase/sale accounts and tax, tracked flag → H-01 items; inventory account auto-assigned when tracked; opening quantities/costs from Items export at conversion date | BE | T15, H-01 | Tracked item imports with on-hand and value equal to Xero; services never affect stock | Unit |
| T-01-T23 | Fixed-asset mapper: register → I-01 assets with cost, in-service date, accumulated depreciation; book method mapping; CCA class suggestion (keyword + account → class, e.g. furniture → Class 8 20 %, computers → Class 50 55 %, vehicles → Class 10 / 10.1 by cost) with UCC opening entered/derived | BE | T15, I-01 | Each asset has suggestion + reason; register cost total = CoA fixed-asset balances (difference listed otherwise) | Unit |
| T-01-T24 | Mapping review API: `GET/PATCH /api/v1/imports/xero/batches/{id}/decisions?kind=` with bulk accept, filter by status, keyboard-friendly pagination; permission `data.import` | API | T07, T15–T23 | Bulk accept 139 GIFI decisions in one call; audit records per decision | Integration |
| T-01-T25 | Wizard step 1–2 UI: start screen, conversion date, file checklist with help, drop zone, file cards with detected type/encoding/date format/preview | FE | T03, T08–T11 | Flow A steps 1–3 complete on fixture; empty/error/loading states render | Vitest + Playwright |
| T-01-T26 | Column-mapping UI (MappingGrid) with saved profiles | FE | T12, T25 | Renamed-header fixture mapped in ≤ 3 clicks | Playwright |
| T-01-T27 | Review UI — Accounts tab: retype/renumber/split/GIFI suggestion chips with reason tooltips, accept/change/skip, bulk accept per group, keyboard shortcuts | FE | T24 | Keyboard-only review completes; axe 0 serious | Playwright + axe |
| T-01-T28 | Review UI — Tax codes, Contacts (duplicates merge cards, role picker), Items, Fixed assets (CCA class picker) tabs | FE | T24 | All tabs functional on REFINED + pilot fixture | Playwright |
| T-01-T29 | Dry-run engine: runs all loaders inside a transaction that is rolled back (SAVEPOINT per type) and records would-create/update/skip/reject counts, totals, projected TB | BE | T15–T23 | Dry run writes 0 business rows (asserted by row counts before/after) | Integration |
| T-01-T30 | Dry-run report UI + export (CSV/XLSX/PDF): summary tiles, virtualised row table, filters, rejects block "Import" | FE | T29 | Rejects present → Import disabled with reason; export equals screen | Playwright |
| T-01-T31 | Loader — Chart of accounts + GIFI + account tax defaults, applying accepted decisions; sub-accounts preserved | BE | T29 | Imported CoA equals decisions; ExternalRef created per account | Integration |
| T-01-T32 | Loader — Contacts (via B-03 service) | BE | T21, T31 | Idempotent re-run | Integration |
| T-01-T33 | Loader — Opening balances at conversion date via C-05 conversion-balance service (TB at conversion date − open AR/AP documents); never posts a balancing line | BE | T31 | Unbalanced TB → C-05 blocks finalise with named difference (gap #47) | Integration + gap-47 test |
| T-01-T34 | Loader — Open AR at conversion date by document (Aged Receivables Detail) as opening invoices with outstanding amount; ties to opening AR control | BE | T32, T33 | AR aging at conversion date = Xero aged receivables total | Integration |
| T-01-T35 | Loader — Open AP at conversion date by document (Aged Payables Detail) as opening bills | BE | T32, T33 | AP aging = Xero aged payables total | Integration |
| T-01-T36 | Loader — Sales invoices and credit notes after conversion date (multi-row grouping by InvoiceNumber, tax inclusive/exclusive, line + tax rounding per Xero line method, Xero number kept as base number), posted via D-03a / D-06 | BE | T19, T32, T31 | Fixture invoices: totals equal file to the cent; JE balanced; numbers preserved | Integration + property (sum of lines = total) |
| T-01-T37 | Loader — Payments and allocations on invoices/credit notes (partial, over-payment → credit, prepayments) via D-05 | BE | T36 | AR per contact = Xero aged receivables at each month-end | Integration |
| T-01-T38 | Loader — Bills and supplier credits after conversion date via E-02/E-03, incl. supplier invoice no. uniqueness (duplicates reported, not blocked, for historic data) | BE | T19, T32 | Bills total = file; duplicates listed in report | Integration |
| T-01-T39 | Loader — Bill payments and allocations | BE | T38 | AP per contact = Xero aged payables at each month-end | Integration |
| T-01-T40 | Loader — Manual journals (narration, date, lines, tax rate per line, posted-by/posted-on metadata) via C-02 with journal type `general`; contact empty (as in Xero) and flagged by K-09 | BE | T19, T31 | REFINED journals #1 417.22 and #2 576.95 imported line by line; Petty Cash −994.17 | Integration on REFINED |
| T-01-T41 | Loader — Bank accounts (F-01 types: chequing, savings, credit card…) and bank transactions from Account Transactions export (spend/receive/transfer), with de-duplication against journals and documents already imported (same account, date, amount, reference) | BE | T31, T36–T40 | No double counting: bank balance per account = Xero TB | Integration + property |
| T-01-T42 | Loader — Items opening stock and fixed assets (accepted CCA classes, opening accumulated depreciation, UCC by class) | BE | T22, T23, T31 | Inventory valuation = GL inventory; register = CoA fixed-asset balances | Integration |
| T-01-T43 | Loader — Payroll YTD per employee per box (CPP/CPP2/EI/QPP/QPIP/tax/gross) from client's payroll export into N-01/N-08 YTD tables | BE | N-08 | YTD maximums respected in the next pay run | Integration + payroll fixture |
| T-01-T44 | Import orchestrator job: runs loaders in dependency order, per-type transaction, resumable, idempotent, audit `source=xero_import` with file + row reference on every record | BE | T31–T43 | Kill worker mid-run → resume finishes with identical result | Integration (chaos) |
| T-01-T45 | Tie-out engine: Xero TB (from TB export) vs Numo9 TB by account, at conversion date and at every month-end through the latest TB date; AR/AP aging vs control per contact; difference ranking | BE | T44, K-02, K-03 | Profitex + pilot difference = 0.00; seeded 0.01 fixture pinpoints account and month | Unit + data validation |
| T-01-T46 | Reconciliation UI: hero difference, comparison table sorted by code with opening/movement/closing, month strip, drill-down drawer to source rows and Numo9 records, "Explain this difference" | FE | T45 | Flow B ≤ 3 clicks; screen = export | Playwright + usability U2 |
| T-01-T47 | Exceptions on import: trigger K-09 for the org after import; list with severity; "Create draft correcting journal" (e.g. Dr 1000 Petty Cash 994.17 / Cr 2900 Shareholder Loan 994.17 left as draft) | BE/FE | T44, K-09 | REFINED: negative petty cash, journal-only expenses, all-exempt, no BN, no lock date, unmapped GIFI (if any) flagged (gap #59) | Integration + gap-59 |
| T-01-T48 | Undo batch (before finalise): reverse/delete every record created by the batch through services, ExternalRefs removed, audit entry; disabled after finalise | BE/FE | T44 | Undo leaves org identical to pre-import snapshot (row counts + TB) | Integration |
| T-01-T49 | Finalise: preconditions (difference 0.00, 0 rejects, all decisions made, GIFI unmapped = 0 or accepted), typed confirmation, set per-module lock dates at conversion date (A-05), status `finalised`, notification to org owner | BE/FE | T45, T47 | Finalise refused with exact reason when any precondition fails; locks visible in settings and audit | Integration + Playwright |
| T-01-T50 | Import audit report (per batch): every created/updated record with source file/row and before/after, export CSV/XLSX/PDF (gap #37) | BE/FE | T44 | Export rows = screen rows | Integration |
| T-01-T51 | Management commands `import_xero --org --dir --dry-run`, `tieout <org> <date>`, `undo_import_batch <id>` for operator-run migrations | OPS | T44, T45, T48 | Commands run on staging for both orgs | Manual + CI smoke |
| T-01-T52 | Migrations board (practice workspace): orgs in migration with stage, difference, readiness % | FE | T45 | Board shows Profitex + pilot; counts drill to batches | Playwright |
| T-01-T53 | Feature key `platform.migration` + permission `data.import` declared; endpoints registered in tenant-isolation sweep; org B cannot read org A batch | API/QA | T24 | Sweep passes; cross-org batch ID → 404 | Security sweep |
| T-01-T54 | i18n keys en-CA/fr-CA for all wizard strings, messages and report headers (FR filled in Phase 6) | FE | T25–T30, T46 | Missing-key gate passes for en-CA; fr-CA keys exist | i18n lint |
| T-01-T55 | Property test suite: for random generated Xero datasets (Hypothesis) — import then TB equals source TB; re-import changes nothing; undo restores | QA | T44, T48 | 500 examples pass | Hypothesis |
| T-01-T56 | Performance: 100k invoice lines + 50k bank lines import < 15 min on staging; parser ≥ 5k rows/s | QA | T44 | Timing recorded in report | Benchmark |
| T-01-T57 | Dry-run + import of **Profitex** real exports on staging; resolve all mapping decisions with Profitex accountant; tie-out 0.00 | OPS/QA | T49 | Tie-out report 0.00 signed by Profitex | Data validation |
| T-01-T58 | Dry-run + import of **pilot client** real exports on staging; tie-out 0.00 | OPS/QA | T49 | Tie-out report 0.00 | Data validation |
| T-01-T59 | Self-service documentation: "Move from Xero to Numo9" guide (how to export each file, wizard walkthrough, troubleshooting) — original wording, no Xero screenshots | DOC | T57 | Guide published in Help; linked from step 1 | Review |
| T-01-T60 | ADR note in data dictionary: ExternalRef matching and conversion rules | DOC | T44 | Merged in `docs/` | Review |

- **Deliverable acceptance criteria:** TB difference 0.00 for Profitex and pilot client; exceptions report produced on import; self-service for any org (an accountant other than GMA completes Flow A on a fixture org unaided); re-import creates 0 duplicates and 0 changes; finalisation impossible while difference ≠ 0.00; dry run writes nothing.
- **Testing approach:** unit (parsers, detectors, mappers, rules), property (TB invariance, idempotency, undo), integration (each loader through real services), functional E2E (Flow A, B), data validation (tie-outs), security (tenant sweep, permission), performance (benchmarks), usability (U1–U3).
- **Risks & mitigations:** Xero export variance → header signatures + mapping profiles + preview; rounding differences → replicate per-line rounding and report per-document 0.01 variances explicitly; hidden 840 balances → surfaced as decisions; large files → chunked resumable jobs; bad decisions → dry run + undo before finalise.

---

### T-02 · UAT

- **Branch:** `feature/T-02-uat-signoff`
- **Objective:** a client-observed UAT in which every component acceptance criterion (Plan §3) and every gap row (Plan §4, 61 rows) is executed on staging with evidence and signed off.
- **Current behaviour:** acceptance evidence is scattered across CI runs and sprint demos; no single sign-off artefact.
- **Expected behaviour:** an in-app UAT sign-off sheet (platform-owner console) seeded with one row per acceptance criterion and per gap row, each linked to a script and a staging deep link, with Pass/Fail/Blocked, evidence attachments, tester, timestamp, defect link, and a decision-maker signature; exports to XLSX/PDF for the acceptance package.
- **Gap #s:** all 1–61 (verification).
- **Business rules:** a row is Passed only with evidence; Failed rows create a defect linked to the row; a phase is accepted only when all rows Pass or the client lists remaining defects as minor (Agreement 7.5); silence > 10 business days = deemed acceptance (7.4) — the sheet records delivery date to compute it.
- **Edge cases:** criterion depending on a client input not yet supplied (marked Blocked — client input, does not count against GMA); flaky environment; tester disagreement on expected result (escalate to decision-maker).
- **UI/UX notes:** checklist table grouped by component; filter "My rows / Failed / Blocked"; inline evidence paste; progress ring per component; signature block with typed name + date.
- **Dependencies:** T-01 (staging data), all Phase 0–4 deliverables, A-03 (UAT roles), A-06 (evidence files).

**Atomic tasks**

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| T-02-T01 | Models `UATRun` (phase, environment, delivered_at, status, signed_by, signed_at) and `UATRow` (run, component, ref e.g. `D-03b-AC1` / `gap-27`, criterion text, script ref, status not_started/passed/failed/blocked, tester, evidence files, defect_url, notes) | DB | — | Migration applies; platform-owner scoped | Unit |
| T-02-T02 | `uat_seed` command: parses Plan §3 acceptance criteria and §4 gap rows into rows (one per criterion and one per gap row); idempotent | OPS | T01 | 61 gap rows + all component criteria created; re-run adds 0 | Unit |
| T-02-T03 | UAT sheet API + permissions (`uat.test`, `uat.sign`) | API | T01 | Tester cannot sign; decision-maker can | Integration |
| T-02-T04 | UAT sheet UI: grouped table, filters, progress rings, evidence paste/upload, defect link creation (GitHub issue template with row ref) | FE | T03 | Flow C ≤ 1 min per row | Playwright + U4 |
| T-02-T05 | Sign-off block + XLSX/PDF export of the sheet with evidence index | FE/BE | T04 | Export equals screen; PDF includes signature | Integration |
| T-02-T06 | UAT environment preparation: staging refreshed from Profitex + pilot dry-run imports (personal data anonymised where not needed), UAT user accounts per tester role | OPS | T-01-T57, T-01-T58 | Testers log in with their roles | Manual |
| T-02-T07 | UAT test scripts — Component A (Platform core: tenancy, auth/2FA, RBAC + limits, audit, settings/locks, documents, notifications, jobs, search, design system) | QA | T02 | Script per criterion, with expected result | Review |
| T-02-T08 | UAT scripts — Component U (catalogue, packages, entitlements, Stripe billing, trial, console, demo, founding offer) | QA | T02 | as above | Review |
| T-02-T09 | UAT scripts — Component V (directory, groups/tags, bulk edit, dashboards, staff) | QA | T02 | as above | Review |
| T-02-T10 | UAT scripts — Component B (contacts, statements, import) | QA | T02 | as above | Review |
| T-02-T11 | UAT scripts — Component C (CoA, posting, journal types, recurring/approval, conversion, close, recode) | QA | T02 | as above | Review |
| T-02-T12 | UAT scripts — Component D (grid, quotes, invoices, **revisions 101 → 101-1**, recurring, payments, credit notes, reminders, overview, pay link) | QA | T02 | as above | Review |
| T-02-T13 | UAT scripts — Component E (PO/GRN/3-way match, bills, recurring/credits, expense claims, OCR capture, batch payments/cheques, early-payment discount) | QA | T02 | as above | Review |
| T-02-T14 | UAT scripts — Component F (never-locked accounts, import, rules, reconciliation, transfers, negative-balance controls) | QA | T02 | as above | Review |
| T-02-T15 | UAT scripts — Component G (codes, place of supply, GST/HST return, cycle switch, out-of-cycle, stop/restart, QST, tax reports, settings page, GIFI/T2, corporate tax, tax payments) | QA | T02 | as above | Review |
| T-02-T16 | UAT scripts — Component H incl. H-09…H-13 analytics/EOQ/price optimisation | QA | T02 | as above | Review |
| T-02-T17 | UAT scripts — Finance FN-01…FN-05 (loans, schedules, posting, credit-terms interest, reports) | QA | T02 | as above | Review |
| T-02-T18 | UAT scripts — Component I (register, SL/DB runs, CCA discretionary + full-CCA-as-loss, templates importer, disposals) | QA | T02 | as above | Review |
| T-02-T19 | UAT scripts — Components J (projects/time) and L (Sheets) | QA | T02 | as above | Review |
| T-02-T20 | UAT scripts — Component K (engine, statements, AR/AP, budgets, dashboard, pack, two-book, tax-purpose BS/IS, exceptions, adjusted TB) | QA | T02 | as above | Review |
| T-02-T21 | UAT scripts — Components M and N (HR; payroll multi-province vs CRA calculator, CPP/CPP2/EI, slips T4/T4A/T5 XML, ROE, worker classification, CRA tables upload) | QA | T02 | as above | Review |
| T-02-T22 | UAT scripts — Components O and P (practice/portal; Stripe, invoice pay, service checkout, PAD, refunds, tax-payment adapter) | QA | T02 | as above | Review |
| T-02-T23 | UAT scripts — Components Q, R, W (website on staging, multi-currency, public API/webhooks) | QA | T02 | as above | Review |
| T-02-T24 | UAT scripts — Component T and S (importer, monitoring, backups, scale) | QA | T02 | as above | Review |
| T-02-T25 | Gap-closure checklist scripts gap-01 … gap-20 (one check per row, expected closing behaviour from Plan §4) | QA | T02 | 20 scripts with automated test link where exists | Review |
| T-02-T26 | Gap-closure scripts gap-21 … gap-40 | QA | T02 | 20 scripts | Review |
| T-02-T27 | Gap-closure scripts gap-41 … gap-61 | QA | T02 | 21 scripts | Review |
| T-02-T28 | Automated evidence pull: CI job attaches latest Playwright/pytest results for rows tagged `gap-NN` or criterion IDs to the sheet | OPS | T05 | Rows show linked green test run | Integration |
| T-02-T29 | UAT kickoff session with testers (30 min): how to use sheet, severity definitions, defect workflow | QA | T06 | Attendance recorded | — |
| T-02-T30 | UAT execution day 1 — Components A, U, V, B, C, D, E, F (testers; GMA on call) | QA | T07–T14 | Rows executed with evidence | Functional |
| T-02-T31 | UAT execution day 2 — Components G, H, FN, I, J, L, K, M, N, O, P, Q, R, W, T, S and gap rows | QA | T15–T28 | Rows executed with evidence | Functional |
| T-02-T32 | Defect triage (daily): severity, owner, fix branch `fix/<ID>-…`, retest; failing rows block dependent rows (Rule 5.3) | QA | T30 | Every failed row has defect + retest result | Regression |
| T-02-T33 | Regression run on `main` after fixes (full suite + nightly 500-org) before sign-off | QA | T32 | CI green; no known regressions | Regression |
| T-02-T34 | Sign-off meeting with decision-maker; sheet signed or minor-defect list agreed (7.5) | QA | T33 | Signed PDF in acceptance package | — |

- **Deliverable acceptance criteria:** every component and every gap row observed (Pass with evidence) or listed as minor defect agreed by the client; signed sheet exported.
- **Testing approach:** functional (scripted manual + automated evidence), regression after fixes, data validation for migrated orgs.
- **Risks & mitigations:** tester availability → schedule in T-02-T29, timeline extension per 6.3; scope disputes → criteria quoted verbatim from Plan; flaky staging → monitored by S-04.

---
### T-03 · Training

- **Branch:** `docs/T-03-training`
- **Objective:** role-based recorded training (plus live Q&A) so every user type can operate Numo9 from day one.
- **Current behaviour:** none.
- **Expected behaviour:** short, chaptered recordings (5–15 min each) per role, captions, quick-reference PDFs, in-app "Help › Training" library with search; live sessions recorded; attendance logged.
- **Gap #s:** 41/61 (feature-matrix walkthrough), supports adoption of all gaps.
- **Business rules:** training uses demo/fixture data only — never real client personal data on screen; recordings delivered to client (Agreement 5.3).
- **Edge cases:** features changed after recording (re-record affected chapter only); French versions in Phase 6.
- **UI/UX notes:** video player with chapter markers and transcript; "watched" tick per user; contextual "Watch how" links on key screens (wizard, revision, cycle switch, pay run).
- **Dependencies:** T-04 (guides as script source), U-07 demo org, all features stable after T-02 day 1.

**Atomic tasks**

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| T-03-T01 | Training plan: roles × modules matrix (platform owner, practice admin, accountant, payroll specialist, org owner, org user, employee), session list and durations | DOC | — | Matrix approved by Profitex | Review |
| T-03-T02 | Prepare training org from U-07 demo seed with revision, filed GST periods, payroll, assets, loans | OPS | U-07 | Training org resettable | Manual |
| T-03-T03 | Script + record: Platform-owner — packages/prices, founding counter, demo manager, impersonation audit, feature flags, monitoring/backups screens | DOC | T01, T02 | Recording + captions | Review |
| T-03-T04 | Script + record: Accountant workspace — directory, groups/tags, saved views, bulk edit, cross-org dashboards, staff assignment | DOC | T02 | as above | Review |
| T-03-T05 | Script + record: Move from Xero — wizard, mapping review, reconciliation, finalise | DOC | T-01 | as above | Review |
| T-03-T06 | Script + record: Core books — CoA, journals with types/approval, sales incl. invoice revision 101-1, purchases with 3-way match, banking without feeds, rules, reconciliation | DOC | T02 | as above | Review |
| T-03-T07 | Script + record: Tax — codes/place of supply, GST/HST + QST returns, cycle switch, out-of-cycle, stop/restart, tax payments | DOC | T02 | as above | Review |
| T-03-T08 | Script + record: Two books, CCA (incl. full-CCA-as-loss), corporate tax computation, adjusted TB, Sheets | DOC | T02 | as above | Review |
| T-03-T09 | Script + record: Inventory + analytics/EOQ/pricing; Finance module loans | DOC | T02 | as above | Review |
| T-03-T10 | Script + record: Payroll & HR — CRA tables upload, worker classification, pay run, remittance, slips | DOC | T02 | as above | Review |
| T-03-T11 | Script + record: Org owner & portal — dashboard, approvals, subscription view, paying invoices/taxes; Employee self-service | DOC | T02 | as above | Review |
| T-03-T12 | Script + record: SaaS admin — subscriptions, trials, dunning, cancellations/export | DOC | T02 | as above | Review |
| T-03-T13 | Edit videos (chapters), generate captions (Whisper → reviewed SRT), export MP4 + transcript | DOC | T03–T12 | Each video has chapters + captions | Review |
| T-03-T14 | Quick-reference PDFs (1–2 pages) per role, generated from MkDocs | DOC | T-04 | PDFs delivered | Review |
| T-03-T15 | In-app Training library (Help › Training): list, search, player with chapters/transcript, watched tick; contextual "Watch how" links | FE/BE | T13 | Usability U6 ≤ 30 s | Playwright |
| T-03-T16 | Deliver live sessions (recorded) and Q&A; attendance log | DOC | T13 | Attendance sheet + recordings | — |
| T-03-T17 | Handover pack: recordings, transcripts, PDFs, attendance into acceptance package | DOC | T16 | Package complete | Review |

- **Deliverable acceptance criteria:** attendance and recordings delivered; every role in the matrix has at least one recording; captions present.
- **Testing approach:** review by Profitex; usability U6.
- **Risks & mitigations:** late UI changes → record after T-02 day 1 freeze, re-record chapters only.

---

### T-04 · Documentation

- **Branch:** `docs/T-04-documentation`
- **Objective:** complete documentation set in `docs/` and as PDF: admin guide, platform-owner guide, accountant guide, runbook, API docs, ADR-001…004, data dictionary (+ Move-from-Xero guide).
- **Current behaviour:** partial ADR drafts and in-code docs from earlier phases.
- **Expected behaviour:** MkDocs site built in CI to HTML and PDF; versioned with release tags; searchable in-app Help; runbook entries linked from every alert.
- **Business rules:** docs use Canadian English and Numo9 original wording; no Xero screenshots or text; no secrets in docs.
- **Edge cases:** docs drift — CI check that every API endpoint appears in OpenAPI and every alert has a runbook entry.
- **UI/UX notes:** task-based structure ("How do I…"), screenshots from the training org, callouts for irreversible actions.
- **Dependencies:** all features; S-04 (alert list); S-05 (backup/restore procedures); W-01 (OpenAPI).

**Atomic tasks**

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| T-04-T01 | MkDocs Material site skeleton in `docs/` with nav (guides, runbook, API, ADR, data dictionary), PDF build via WeasyPrint plugin, CI job publishing artefacts on tag | OPS | — | `mkdocs build` + PDF in CI | CI |
| T-04-T02 | ADR-001 Hosting & data residency (final: region, provider, rationale, consequences) | DOC | S-02 | MADR format, accepted | Review |
| T-04-T03 | ADR-002 Invoice revisions (reversal + re-post, numbering, filed-period rules) | DOC | D-03b | as above | Review |
| T-04-T04 | ADR-003 Tax-payment route/provider (chosen provider, assisted fallback, idempotency) | DOC | P-06 | as above | Review |
| T-04-T05 | ADR-004 Two-book model (book dimension, tax-adjustment journals, reconciliation) | DOC | K-07 | as above | Review |
| T-04-T06 | Data dictionary: generated ER diagrams per app + table/field descriptions from model docstrings/`help_text`; manual notes for ledger, revisions, ExternalRef | DOC/OPS | — | Every business model listed; CI fails on model without help_text | CI check |
| T-04-T07 | API docs: drf-spectacular OpenAPI 3 + Redoc page; auth (keys/OAuth), scopes = feature keys, webhooks catalogue, rate limits, idempotency, examples | DOC | W-01 | Contract tests pass against published spec | Contract test |
| T-04-T08 | Platform-owner guide: packages/prices, founding offer, demo manager, trials/dunning, impersonation, feature flags, monitoring/backups screens, UAT sheet | DOC | — | Reviewed by Profitex | Review |
| T-04-T09 | Admin guide (organisation admin): settings, registrations, lock dates, users/roles/limits, custom sending domain, subscription | DOC | — | as above | Review |
| T-04-T10 | Accountant guide part 1: workspace, migration, CoA/journals, sales/purchases/banking | DOC | — | as above | Review |
| T-04-T11 | Accountant guide part 2: tax engine/returns/cycles/payments, two books/CCA/corporate tax, inventory/finance, payroll/HR, Sheets, reports/exceptions, period close | DOC | — | as above | Review |
| T-04-T12 | Runbook: deploy/rollback, migrations, scaling, incident response, alert-by-alert entries (RB-01…), backup/restore/PITR, secret rotation, Stripe webhook replay, tax-payment provider outage, CRA tables/rates update procedure (warranty quarterly updates) | DOC | S-04, S-05 | Every alert rule links to an entry (CI check) | CI check |
| T-04-T13 | Cut-over runbook (T-05) and rollback plan as a dedicated runbook chapter | DOC | T-05 | Rehearsed on staging | Rehearsal |
| T-04-T14 | In-app Help integration: guides searchable from Help panel, deep links from settings pages | FE | T01 | Search "lock date" finds the guide page | Playwright |
| T-04-T15 | Docs QA: link checker, spell check en-CA (Canadian spelling list), "no Xero wording" check | QA | T08–T13 | 0 broken links; 0 flagged spellings | CI |
| T-04-T16 | PDF set exported and added to acceptance package | DOC | T15 | PDFs present | Review |

- **Deliverable acceptance criteria:** all listed documents in `docs/` and PDF; ADR-001…004 accepted; API docs generated from the live spec.
- **Testing approach:** CI docs build, link check, coverage checks (models, endpoints, alerts).
- **Risks & mitigations:** drift → CI coverage checks; time → write from task cards and training scripts.

---

### T-05 · Go-live (cut-over)

- **Branch:** `ops/T-05-go-live`
- **Objective:** production deployment on the Numo9 domain with Profitex and pilot client live, parallel payroll and GST period reconciled.
- **Current behaviour:** staging only.
- **Expected behaviour:** rehearsed, checklist-driven cut-over with go/no-go gate, baseline snapshot, real data imports in production, lock dates set, live Stripe and tax-payment routes, DNS/mail on production domain, parallel run with a reconciliation report.
- **Business rules:** Agreement 7.6 conditions; no step without project lead authorisation; production writes logged; rollback plan for every step; Xero remains the system of record until the parallel period reconciles.
- **Edge cases:** DNS propagation delays; Stripe webhook secret mismatch; email domain not verified; import finds new transactions entered in Xero after the staging dry run (delta import); payroll rounding differences.
- **UI/UX notes:** cut-over checklist screen with timers and owners; banner-free production (no "beta" banners in working screens); org owner receives a clear "You're live" notification with next steps.
- **Dependencies:** T-01, T-02 (signed), T-03 (in progress acceptable), T-04 runbook, S-04, S-05, S-06 target.

**Atomic tasks**

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| T-05-T01 | Cut-over plan: timeline, owners, go/no-go criteria, rollback per step, communication plan (who is told what, when) | DOC | — | Approved by project lead + Profitex | Review |
| T-05-T02 | Cut-over checklist model + screen (steps, owner, planned/actual time, status, rollback note) seeded from plan | FE/BE | T01 | Steps executable and timed | Playwright |
| T-05-T03 | Production infrastructure provisioning (Canadian region): app, workers, beat, Postgres primary + read replica, Redis, object storage, Caddy TLS, secrets manager | OPS | S-02 | Health endpoints green | Smoke |
| T-05-T04 | Production configuration: env vars, feature flags, Sentry DSN, email provider, storage keys; `check --deploy` clean | OPS | T03 | Django deploy check 0 warnings | CI |
| T-05-T05 | DNS on Numo9 domain: app, portal, api, website, status; HSTS; TLS A+ (SSL Labs) | OPS | T03 | A+ rating; HSTS preload-ready headers | sslyze |
| T-05-T06 | Mail DNS for production domain: SPF, DKIM, DMARC; transactional provider verified; test email passes DMARC | OPS | T05 | mail-tester ≥ 9/10; DMARC pass | checkdmarc |
| T-05-T07 | Stripe live: platform account keys, Connect/per-org keys, live webhook endpoints + signing secrets, PAD enabled; $1 live test charge refunded | OPS | P-01 | Webhook received and verified in production | Manual |
| T-05-T08 | Tax-payment route production config per ADR-003 (provider credentials or bank-file route; assisted route always on) | OPS | P-06 | Provider status check green or assisted route active | Manual |
| T-05-T09 | Security gate on production: ZAP baseline, securityheaders, Trivy on images, gitleaks on release tag | OPS | T05 | No high findings | Security scans |
| T-05-T10 | Rehearsal 1 on staging: full checklist incl. import of both orgs from scratch, timing each step | OPS | T02, T-01 | Rehearsal report with timings; issues fixed | Rehearsal |
| T-05-T11 | Rehearsal 2 (after fixes) incl. rollback drill of the deploy step | OPS | T10 | Clean run; rollback < 15 min | Rehearsal |
| T-05-T12 | Go/no-go meeting: UAT signed, rehearsal clean, S-04 alerts tested, S-05 backup + drill done, S-06 target met | DOC | T11, T-02, S-04, S-05 | Go decision recorded | — |
| T-05-T13 | Production deploy of release tag `v1.0.0`; migrations; seed reference data (tax codes, CCA classes, CRA tables, packages/prices from client) | OPS | T12 | Release live; reference data checksums match staging | Smoke |
| T-05-T14 | Create Profitex practice, organisations, users (2FA enforced for platform owner/practice admin), subscriptions in production | OPS | T13 | Users can log in with 2FA | Manual |
| T-05-T15 | Final Xero exports taken at cut-over date (delta since dry run) for both orgs | OPS | T14 | Files stored with checksums | — |
| T-05-T16 | Production import of Profitex: dry run → import → tie-out 0.00 → exceptions report → finalise with lock dates | OPS | T15 | Tie-out report 0.00 in production | Data validation |
| T-05-T17 | Production import of pilot client: same steps | OPS | T15 | Tie-out report 0.00 in production | Data validation |
| T-05-T18 | Go-live baseline: full-ledger export (CSV/JSON) + DB snapshot + SHA-256 checksums stored | OPS | T16, T17 | Baseline files + checksums in backup bucket | Checksum verify |
| T-05-T19 | Production smoke suite (Playwright, read-only + sandbox actions on a dedicated smoke org) | QA | T13 | All smoke tests pass | E2E |
| T-05-T20 | Parallel GST period setup: same period processed in Xero and Numo9 for both orgs (where registered) | OPS | T16, T17 | Period exists in both | — |
| T-05-T21 | Parallel payroll period setup: one pay period run in legacy payroll tool and Numo9 (with imported YTD) | OPS | T16, T17, T-01-T43 | Pay run drafted in Numo9 | — |
| T-05-T22 | Parallel-run reconciliation report: GST return lines 101–115 and payroll register (gross, CPP, CPP2, EI, tax, net per employee) compared, differences explained | BE/OPS | T20, T21 | Report shows 0.00 or each difference explained and accepted | Data validation |
| T-05-T23 | Go-live communication: "You're live" notifications, support contact, hypercare schedule | DOC | T16, T17 | Sent | — |
| T-05-T24 | Acceptance package: release notes, test results, UAT signed sheet, tie-out reports, parallel-run report, exceptions reports, restore-drill and scale reports, training + docs | DOC | T22, T-02, T-03, T-04 | Package delivered; acceptance requested in writing (7.2) | Review |
| T-05-T25 | Milestone 2 invoice prepared upon written (or deemed, 7.4) acceptance | DOC | T24 | Invoice issued | — |
| T-05-T26 | Hypercare handoff: open defects list, monitoring watch rota for week 9 | DOC | T24 | List and rota published | — |

- **Deliverable acceptance criteria:** production live; parallel run reconciled; TB 0.00 for both orgs in production (Agreement 7.6).
- **Testing approach:** rehearsals, smoke tests, data validation, security gate.
- **Risks & mitigations:** outage during cut-over → rehearsals + rollback; delta changes in Xero → final export at cut-over + delta import; payroll differences → parallel report with explained differences.

---

### S-04 · Monitoring & logging

- **Branch:** `ops/S-04-monitoring`
- **Objective:** error tracking, metrics, logs, traces, dashboards and alerting for production, with every alert linked to a runbook entry.
- **Current behaviour:** basic container logs and staging Sentry from earlier phases.
- **Expected behaviour:** production observability stack; SLOs; alert rules for availability, errors, latency, queues, DB, backups, Stripe webhooks, tax-payment provider, import failures, certificate expiry; synthetic golden-path checks; alerts fire on test incidents.
- **Business rules:** no SIN, bank numbers, card data or passwords in logs (masking filter); org_id and request_id on every log line; logs retained per policy (90 days hot, archive per S-05).
- **Edge cases:** alert storms (grouping/inhibition); muted channels; monitoring itself down (dead-man's switch).
- **UI/UX notes:** platform-owner console "Operations › Monitoring": status tiles, top errors, latency charts, incident list; each alert message names metric, threshold, duration and runbook link.
- **Dependencies:** S-01, S-02, T-05-T03.

**Atomic tasks**

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| S-04-T01 | Define SLOs and alert catalogue (availability 99.5 %, API p95 < 800 ms, report p95 < 3 s, dashboard < 1.5 s, queue lag < 60 s, error rate < 1 %) | DOC | — | Catalogue approved | Review |
| S-04-T02 | Structured JSON logging (structlog) with request_id, org_id, user_id, job_id; PII masking filter (SIN, bank, card, tokens) | BE | — | Log sample contains ids; SIN test value never appears | Unit (log capture) |
| S-04-T03 | Sentry production projects (backend, frontend, Celery, later mobile) with release tagging and source maps; PII scrubbing | OPS | T02 | Test exception visible with release tag | Integration |
| S-04-T04 | Prometheus exporters: django-prometheus, celery-exporter, postgres_exporter, redis_exporter, node_exporter, Caddy metrics | OPS | — | Targets up in Prometheus | Smoke |
| S-04-T05 | Business metrics: posting rate, import job duration/failures, webhook processing lag, tax-payment status counts, dunning queue | BE | T04 | Metrics exposed and scraped | Unit + scrape |
| S-04-T06 | Log aggregation (Loki/Promtail or hosted) with retention policy | OPS | T02 | Logs searchable by org_id | Manual |
| S-04-T07 | OpenTelemetry traces for report runs and import jobs | BE | T04 | Trace of a 12-month report visible | Manual |
| S-04-T08 | Grafana dashboards: Platform overview, API, Workers & queues, Database, Billing & payments, Imports | OPS | T04, T05 | Dashboards provisioned as code | Review |
| S-04-T09 | Alert rules as code (availability, error rate, latency, queue lag, DB connections/replica lag/disk, Redis memory, backup age, cert expiry, webhook failures, provider errors, import failures) | OPS | T08, T01 | Rules loaded; each has runbook URL label | CI lint (promtool) |
| S-04-T10 | Alert routing (Alertmanager) to client-provided recipients; severity routing; grouping/inhibition; dead-man's switch heartbeat | OPS | T09 | Heartbeat missing → alert received | Test incident |
| S-04-T11 | Synthetic golden-path monitor (Playwright script: login smoke user → dashboard → run TB) every 5 min + status page | OPS | T-05-T13 | Failure triggers alert | Test incident |
| S-04-T12 | Platform-owner console "Operations › Monitoring" page reading status/alerts/incidents via internal API | FE/BE | T08 | Page shows live status | Playwright |
| S-04-T13 | Test-incident drill: trigger each alert class (`/ops/test-alert`, kill worker, block DB, expire test cert) and record receipt time | QA | T10, T11 | Every alert class fires and is received; report filed | Drill report |
| S-04-T14 | CI check: every alert rule has a runbook entry in T-04 | OPS | T09, T-04-T12 | CI fails on missing entry | CI |

- **Deliverable acceptance criteria:** alerts fire on test incidents (all classes); dashboards live; PII never logged.
- **Testing approach:** drill report, log-capture unit tests, promtool lint.
- **Risks & mitigations:** noise → grouping and severity; missed alerts → dead-man's switch and drill.

---

### S-05 · Backups & retention (incl. S-06 scale target proof)

- **Branch:** `ops/S-05-backups`
- **Objective:** encrypted backups with PITR, CRA six-year retention, a restore drill < 1 hour, and verification of the S-06 scale target (500 orgs × 100k lines, report p95 < 3 s).
- **Current behaviour:** staging snapshots only; S-06 baseline (pooling, partitioning, rate limits) from Phase 0.
- **Expected behaviour:** pgBackRest full weekly + incremental daily + continuous WAL archiving; object-storage backups; encryption at rest with managed keys; retention ≥ 6 years for yearly archives; timed restore drill documented; nightly scale run report; console page showing backup status and last drill.
- **Business rules:** CRA six-year records; soft-delete only; backups in Canadian region; restore never overwrites production without authorisation (restore to new instance then switch).
- **Edge cases:** WAL archive gaps; key loss (key escrow procedure); restore to a point mid-import (documented).
- **UI/UX notes:** "Operations › Backups & restores": last backup, PITR window, next scheduled, last drill duration, retention summary; traffic-light status.
- **Dependencies:** S-02, S-06 baseline, T-05-T03, S-04 (backup alerts).

**Atomic tasks**

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| S-05-T01 | Backup & retention policy doc: RPO ≤ 5 min, RTO < 1 h, schedules, retention tiers (daily 35 d, monthly 13 m, yearly 7 y ≥ CRA 6 y), encryption, key custody | DOC | — | Approved | Review |
| S-05-T02 | pgBackRest configuration: repo in Canadian object storage, encryption, full weekly / diff daily / WAL archive continuous | OPS | T01 | First full backup completes; WAL archiving green | Manual + metric |
| S-05-T03 | Object-storage (documents) backup with restic to a separate bucket/account, versioning + lifecycle | OPS | T01 | Snapshot listed; file restore works | Manual |
| S-05-T04 | Backup verification job: nightly `pgbackrest check` + restore of latest backup to a scratch instance + row-count/checksum queries | OPS | T02 | Job result metric; failure alerts via S-04 | Integration |
| S-05-T05 | Retention lifecycle rules and yearly archive job (immutable / object-lock where available) | OPS | T02, T03 | Lifecycle policy visible; test object locked | Manual |
| S-05-T06 | Key management: backup keys in secrets manager, escrow copy procedure with client, rotation procedure | OPS | T02 | Procedure in runbook; test decrypt with escrow key | Drill |
| S-05-T07 | `restore_drill.sh`: provision instance → restore to latest and to a chosen PITR timestamp → run TB tie-out against go-live baseline → timing report | OPS | T02, T-05-T18 | Script completes and prints duration | Drill |
| S-05-T08 | Restore drill execution on production-sized data; record duration (< 1 hour) and integrity (TB of both orgs = baseline) | QA | T07 | Drill report: < 1 h; TB match | Drill |
| S-05-T09 | Console page "Operations › Backups & restores" | FE/BE | T04 | Shows last backup/drill status | Playwright |
| S-05-T10 | `make_scale_practice --orgs 500 --lines 100000` fixture generator (realistic distribution of documents, journals, bank lines, tax codes) on a staging-sized database | OPS | S-06 | 500 orgs × 100k lines generated | Manual |
| S-05-T11 | k6 scale scenarios: 12-month P&L/BS/TB per org (read replica), directory search over 2,000 orgs, dashboard, 50 concurrent users per org on sampled orgs | QA | T10 | Scripts in `tests/perf/` | k6 |
| S-05-T12 | Scale run + tuning loop (indexes, partition pruning, query plans, cache) until targets met: report p95 < 3 s, directory < 300 ms, dashboard < 1.5 s | OPS/BE | T11 | Report: targets met | k6 report |
| S-05-T13 | Nightly scale job in CI on the 500-org fixture with trend chart | OPS | T12 | Nightly result posted | CI |
| S-05-T14 | Runbook entries: backup failure, PITR restore, full restore, key rotation, scale degradation | DOC | T08, T12 | Entries in T-04 runbook | Review |

- **Deliverable acceptance criteria:** restore drill < 1 hour; S-06 scale target (500 orgs × 100k lines p95 < 3 s) met; encrypted backups with PITR; six-year retention configured.
- **Testing approach:** drills, verification jobs, k6 load.
- **Risks & mitigations:** slow restore on large DB → parallel restore, incremental strategy; scale target missed → tuning loop with plan analysis before go/no-go.

---
## 7. TEST — phase test plan (Rules 5–6)

### 7.1 Test matrix

| Category | Scope in Phase 5 | Tooling | Target |
|---|---|---|---|
| Unit | Encoding/type/date detectors, row schemas, mappers, retyping rules, tax mapping by date, GIFI suggestion, 820 split, logging masks | pytest, Hypothesis | ≥ 85 % on `xero_import` package |
| Property | Import TB = source TB; re-import idempotent; undo restores; split sums equal original | Hypothesis | 500 examples per property |
| Integration | Each loader through real services; job resume after worker kill; webhook/live Stripe in production; backup verification | pytest + DRF client, Celery, Stripe CLI | One happy + one failure test per endpoint |
| Functional (E2E) | Flow A (self-service migration), Flow B (difference investigation), Flow C (UAT row), cut-over checklist, production smoke | Playwright | All flows pass |
| Regression | Full suite on every fix PR; nightly 500-org run | GitHub Actions | 0 known regressions at go-live |
| Data validation | TB tie-out at conversion date and each month-end; AR/AP aging vs control; inventory valuation vs GL; asset register vs CoA; parallel payroll register; parallel GST return lines | `tieout` command, reconciliation scripts | 0.00 or explained & accepted |
| Security | Tenant sweep incl. import endpoints; permissions `data.import`, `uat.sign`; ZAP baseline on production; headers; TLS; secrets scan; PII-in-logs test | Sweeps, ZAP, sslyze, gitleaks, Trivy | No high findings |
| Performance | Parser ≥ 5k rows/s; 100k-line import < 15 min; S-06 report p95 < 3 s; directory < 300 ms; dashboard < 1.5 s | pytest-benchmark, k6 | Targets met |
| Resilience | Restore drill < 1 h; deploy rollback < 15 min; alert drills | Drill scripts | Met and documented |
| Accessibility/usability | Wizard, reconciliation, UAT sheet; U1–U6 | axe-core, NVDA/VoiceOver, sessions | 0 serious; success metrics met |
| Localisation | en-CA complete; fr-CA keys present | i18n gate | 0 missing en-CA keys |
| Gap closure | gap-01 … gap-61 all executed in UAT | Playwright + pytest tags | 61/61 observed |

### 7.2 Compliance / migration fixtures

- `fixtures/xero/refined/` — the teardown organisation: 139 accounts, 2 manual journals (417.22 on 3 Jun 2026, 576.95 on 15 Jun 2026), Petty Cash −994.17, 36 tax rates, 142 accounts on Tax Exempt, 0 GIFI mapped, no BN, no lock date. Expected: import succeeds, TB ties, exceptions report lists all six teardown issues, retype proposals for 1500 and intangibles, 820 split proposal, GIFI suggestions for all.
- `fixtures/xero/pilot_style/` — full-year mixed org: invoices with partial payments, credit notes, prepayments, bills with supplier credits, bank lines with transfers, items, assets, foreign-currency invoice, tax-inclusive documents, archived account with balance, duplicate contacts.
- `fixtures/xero/rounding/` — per-line tax rounding vs per-document (0.01 difference cases).
- `fixtures/xero/unbalanced/` — opening TB off by 0.01 and 840 Historical Adjustment 250.00.
- `fixtures/xero/encoding/` — UTF-8 BOM, Windows-1252 accents (Québec names), XLSX, re-ordered headers.
- `fixtures/payroll/ytd/` — YTD per employee near CPP/EI maximums to prove next pay run stops at the maximum.

### 7.3 Exit demonstration script (on staging, then production for 7.6)

1. Open Profitex organisation → Settings › Data › Import history → show finalised batch: TB difference **0.00** at conversion date and at each month-end. Expected: green hero figure, month strip all green.
2. Open pilot client organisation → same: **0.00**.
3. Open exceptions report from import for each org. Expected: report exists; issues listed with severity; draft correcting entries present where proposed.
4. Re-upload the same Xero contacts file to a fixture org → dry run. Expected: 0 creates, 0 updates.
5. Demonstrate self-service: a Profitex accountant runs Flow A on a fixture org unaided. Expected: finalised with 0.00.
6. Open the UAT sign-off sheet. Expected: every component row and gap-01…gap-61 Passed (or listed minor defects agreed), signed by the decision-maker.
7. Show training library and attendance; open docs site and PDF set; open ADR-001…004.
8. Show monitoring dashboard; trigger `/ops/test-alert`. Expected: alert received by client recipient within 2 minutes, with runbook link.
9. Show backup page and restore-drill report. Expected: drill < 1 hour; TB of restored DB = go-live baseline.
10. Show S-06 scale report. Expected: 500 orgs × 100k lines report p95 < 3 s.
11. Show production: Numo9 domain over HTTPS (A+), both orgs live with lock dates at conversion date.
12. Show parallel-run reconciliation report (payroll register and GST return lines). Expected: 0.00 or each difference explained and accepted by Profitex.

### 7.4 Failure handling

Per Rule 5.3: a failing test stops dependent tasks; identify the exact failing condition; classify code / data / configuration / wrong assumption; one focused correction; re-run affected tests then regression; continue only when acceptance criteria are met. A migration difference is never "fixed" by a balancing entry — it is traced to its source row. Tests are never skipped to make CI pass; tests that could not run (e.g. provider sandbox down) are reported as not executed with the reason. Structured debugging (Rule 6) and the 30-minute principle apply to every tie-out difference.

---

## 8. IMPROVE — post-verification review (Rule 8)

Run after acceptance criteria are observed, then re-run relevant tests:

- **Correctness:** every loader goes through domain services (import-linter contract `xero_import` → services only); no direct model `.save()` on ledger tables.
- **Readability:** one parser + one mapper + one loader module per export type; mapping rules declared as data tables (YAML/py dicts), not if-chains.
- **Maintainability:** saved mapping profiles and rules reusable for future importers (e.g. QuickBooks) without code changes to the wizard.
- **Performance budgets:** parser ≥ 5k rows/s; 100k-line import < 15 min; reconciliation screen first paint < 1.5 s for 500 accounts × 12 months; UAT sheet loads < 1 s for 1,000 rows; production API p95 < 800 ms; report p95 < 3 s.
- **Reliability:** import jobs resumable; alerts deduplicated; backup verification nightly; dead-man's switch.
- **Security:** uploaded exports encrypted and deleted 30 days after finalise (configurable); import endpoints in sweep; PII masking verified.
- **Consistency:** design-system components only; Canadian English; error messages follow §3.5.
- **Clean-up:** remove dry-run debug logging, temporary fixtures from production, test smoke data isolated in a smoke org.

---

## 9. Git branch plan (Rule 7)

| Branch | Base | Deliverable | Merge order |
|---|---|---|---|
| `ops/S-04-monitoring` | `main` | S-04 | 1 (parallel) |
| `ops/S-05-backups` | `main` | S-05 (+ S-06 target proof) | 1 (parallel) |
| `feature/T-01-xero-importer` | `main` | T-01 | 2 |
| `docs/T-04-documentation` | `main` | T-04 | 3 (continuous, final merge after T-05 runbook) |
| `feature/T-02-uat-signoff` | `main` | T-02 | 3 |
| `docs/T-03-training` | `main` | T-03 | 4 |
| `ops/T-05-go-live` | `main` | T-05 | 5 (tag `v1.0.0`) |
| `fix/<ID>-<short>` | `main` | UAT defects | as raised |

**Before starting each branch:** `git status` clean; pull `main`; restate objective + acceptance criteria in PR description; list dependencies; never discard others' uncommitted work.
**Before declaring complete:** all atomic tasks done; acceptance observed; CI green (tenant sweep, i18n gate, compliance fixtures, gap tags); no unrelated changes; no debug code; no secrets (gitleaks); docs updated; second-engineer review; diff reviewed. No merge to `main`, production deploy or production import without the project lead's authorisation.

---

## 10. Phase risks register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Xero export formats differ from fixtures | Medium | High | Type detection + mapping profiles + early sample collection (T-01-T02) |
| 2 | TB does not tie (hidden 840, rounding) | Medium | High | Month-by-month tie-out; rounding replication; 840 surfaced as decision; no balancing entries |
| 3 | Pilot client not nominated / exports late | Medium | Medium | Profitex goes live alone; pilot in hypercare; timeline extension per Agreement 6.3 |
| 4 | UAT testers unavailable or late sign-off | Medium | Medium | Scheduled sessions; 5-business-day window; deemed acceptance after 10 days (7.4) |
| 5 | Production cut-over failure | Low | High | Two rehearsals, rollback per step, go/no-go gate |
| 6 | Restore drill > 1 hour | Medium | Medium | Parallel restore, tuned pgBackRest, rehearsed early (day 3) |
| 7 | Scale target not met | Medium | Medium | Tuning loop on read replica, partition pruning, indexes before go/no-go |
| 8 | Parallel payroll differs by cents | Medium | Medium | Rounding rules documented; differences explained in parallel report |
| 9 | Email deliverability on new domain | Medium | Medium | SPF/DKIM/DMARC before go-live; warm-up; mail-tester |
| 10 | Live Stripe webhook misconfiguration | Low | High | Live test charge + webhook verification (T-05-T07); replay runbook |
| 11 | Alerts unseen out of hours | Medium | High | Client-provided rota; dead-man's switch; drill |
| 12 | Personal data exposed in training videos | Low | High | Training org only; review before publishing |
| 13 | Docs drift from product | Medium | Low | CI coverage checks; docs merged last |

---

## 11. Phase completion checklist (Rule 11) and reporting template (Rule 10)

### 11.1 Mandatory execution checklist — per deliverable and for the phase

**UNDERSTAND**
- [ ] Investigated existing services reused by the importer, monitoring and backups
- [ ] Identified users (accountant, owner, UAT tester, DevOps, project lead) and outcomes
- [ ] Defined inputs (Xero exports, client accounts) and outputs (tie-out, reports, sign-off)
- [ ] Identified business rules (no balancing entries, idempotency, 7.6 conditions, six-year retention)
- [ ] Considered edge cases (§T-01 edge cases, cut-over risks)
- [ ] Restated objective in each PR

**PLAN**
- [ ] Decomposed into the atomic tasks in §6
- [ ] Dependencies identified (§5.3) and ordered
- [ ] Acceptance criteria defined per task and deliverable
- [ ] Testing procedures defined (§7)

**BUILD**
- [ ] Smallest working piece first (CoA + contacts + opening TB before history)
- [ ] Existing architecture followed (services only, design system)
- [ ] No unrelated changes; existing functionality preserved
- [ ] Feature key `platform.migration` and i18n keys declared

**TEST**
- [ ] Behaviour verified on fixtures and real exports
- [ ] Edge cases tested (rounding, encoding, unbalanced, duplicates)
- [ ] Failures investigated and resolved (no balancing entries)
- [ ] Regression suite + nightly 500-org run green
- [ ] Tenant-isolation sweep run incl. import endpoints
- [ ] Unverified conditions recorded

**IMPROVE**
- [ ] Code reviewed against §8
- [ ] Temporary artefacts removed
- [ ] Readability improved where needed
- [ ] Behaviour re-verified after improvements

**COMPLETE**
- [ ] Final diff reviewed
- [ ] Documentation updated (T-04)
- [ ] Changes and test results reported
- [ ] Acceptance criteria confirmed: TB 0.00 × 2 orgs; exceptions report × 2; UAT signed; training + docs delivered; alerts fired on test incidents; restore drill < 1 h; scale p95 < 3 s; production live; parallel run reconciled
- [ ] Final status reported; acceptance requested in writing (Agreement 7.2); milestone 2 invoice prepared on acceptance

### 11.2 Reporting template

**Before implementation (per deliverable)**
1. Problem understanding — objective; existing behaviour; expected behaviour.
2. Task breakdown — components; atomic tasks (IDs from §6); dependencies.
3. Implementation plan — execution order; acceptance criteria; testing strategy.

**After implementation (per deliverable)**
1. Changes made — completed tasks; files/components modified; important decisions (e.g. mapping rules, rounding method).
2. Testing results — tests executed; passed; failed; not executed and why.
3. Remaining issues — known limitations; unresolved defects; risks or dependencies (client inputs outstanding).
4. Final status — Complete / Partially complete / Blocked.

**Phase 5 report to Profitex (end of week 8):** exit demonstration results (§7.3, steps 1–12 with evidence), tie-out reports, UAT sheet, parallel-run status (closing in week 9 hypercare if the pay/GST period ends after week 8), open defects with severity, acceptance request.

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| T-01 | 60 | 90 |
| T-02 | 34 | 51 |
| T-03 | 17 | 25.5 |
| T-04 | 16 | 24 |
| T-05 | 26 | 39 |
| S-04 | 14 | 21 |
| S-05 | 14 | 21 |
| **Total** | **181** | **271.5** |

# NUMO9 — PHASE 3 IMPLEMENTATION PLAN
## People: HR & Payroll (Weeks 5–6)

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Phase** | 3 — People: Staff & HR (Component M) and Payroll — Canada (Component N), incl. [v2.1] extended payroll |
| **Weeks** | 5–6 from kickoff |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment) |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada |
| **Date** | 7 November 2026 |
| **References** | Numo9 Project Plan v2.0 §1.4, §1.7, §3 (Components M, N), §4, §5.2, §6 · Project_Phases.md (Phase 3) · Quotation GMA-PFX-2026-003 §4 (★ Payroll — extended) · Agreement GMA-PFX-2026-003-A clauses 4.3, 9.1(c), 15.1 · xero_teardown.md §5.4, §5.6, §6.2, §6.5, §7.2 · AI Coding Agent — Mandatory Engineering Workflow (Rules 1–11) |
| **Methodology** | UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE — applied to the phase, to every deliverable (one Git branch each) and separately to every atomic task |

---

## 0. How to use this file

- Every deliverable below (M-01 … N-13) is **one Git branch** named `feature/<ID>-<short-name>` off `main`.
- Every atomic task (`<ID>-Tnn`) is sized for one focused 1–2 h session, is independently testable (fixtures/mocks allowed) and is executed **UNDERSTAND → PLAN → BUILD → TEST → IMPROVE** on its own.
- Tasks are listed in dependency order: model → migration → service → API → permission/feature key → UI → i18n keys → tests → docs.
- Deliverables marked **[v2.1]** / **(prov.)** come from Quotation §4 ★ and Agreement 4.3; their IDs stay provisional until Plan v2.1 is approved in writing.
- **Nothing is complete until its acceptance criteria are observed** on staging, and the Phase 3 exit demonstration (§7.4) has been run in front of the client.
- Statutory figures (CPP, CPP2, EI, QPP, QPIP, T4127 brackets, claim codes, provincial vacation rules) are **data, never code**: they live in versioned tables loaded from the CRA editions the client uploads or confirms (Agreement 9.1(c), 15.1).

---

## 1. UNDERSTAND (Rule 1)

### 1.1 What exists before this phase

Phases 0–2 have delivered (and Phase 3 reuses — never duplicates):

| Area | Already built | Used in Phase 3 for |
|---|---|---|
| Tenancy (A-01) | `Practice`, `Organisation`, `PracticeAssignment`, `OrgOwnedModel`, scoped managers, router isolation sweep | Every HR/payroll model inherits `OrgOwnedModel`; N-10 practice-run access |
| Auth & RBAC (A-02, A-03) | Roles incl. org **Payroll**, **HR**, **Employee**, practice **Payroll Specialist**; custom roles; **approval limits by amount** (pay runs listed) | Pay-run approval limits; employee self-service scope |
| Audit (A-04) | Append-only field diffs | SIN/bank changes logged **without values**; run lifecycle audit |
| Settings & locks (A-05) | BN + **RP** program account, province, FYE, **Payroll lock date** | Remitter account; posting locks |
| Files (A-06) | S3 storage, virus scan, attach to any record | TD1 uploads, HR documents, stubs/slips PDFs, uploaded CRA tables |
| Notifications (A-07) | EN/FR templates, bounce tracking | Stub ready, leave approval, remittance due |
| Jobs (A-08) | Celery + beat, idempotency keys | Pay-run calculation, stub generation, remittance reminders, accrual jobs |
| Search (A-09) | Global search & quick-create | Employees, pay runs, slips searchable; quick-create "Pay run" |
| Design system (A-10) | Shared grid, forms, pickers, empty states, i18n lint | All Phase 3 screens |
| Entitlements (U-01/U-03) | Feature keys, 402 gating, in-app matrix | Payroll product keys `payroll.*`; HR keys `hr.*` |
| Contacts (B-01) | Explicit roles incl. **employee**, T4A/withholding flag | Contractor ↔ contact link for T4A |
| Ledger (C-01…C-07) | CoA with **payroll liability control accounts by type**, posting engine, `payroll` journal type, period close | Payroll JE posting |
| Banking (F-01) | Never-locked chequing accounts | Net-pay and remittance clearing |
| Tax engine (G) | Registrations page (RP account) | Remitter type & RP number |
| Projects & time (J-02) | Timesheets, approval | Hours imported into pay runs |
| Expense claims (E-04) | Claims and reimbursement | Reimbursement via payroll option; self-service submission |
| Sheets (L) | Working papers | Payroll reconciliation template (T4 vs GL) |

Not existing yet: any employee master, HR structure, leave, payroll constants, calculations, stubs, EFT, remittances, slips, ROE, worker classification, CRA table storage. **Xero (teardown org "REFINED") had no Canadian payroll at all** — only "Wages Payable 803", "Source Deductions" liability accounts and a UK/AU-labelled "Employee entitlements (wages, annual leave, etc)" report code; the home dashboard advertised a third-party payroll app (Wagepoint). Canadian payroll is therefore entirely beyond Xero.

### 1.2 Problem definition — the seven questions (Phase 3)

| # | Question | Answer for Phase 3 |
|---|---|---|
| 1 | **Who uses it?** | Organisation Owner (approves runs, pays remittances); Organisation Payroll officer (prepares runs); HR user (employee records, leave, documents); practice **Payroll Specialist** running payroll inside assigned client orgs (N-10); Employee (self-service: stubs, slips, leave, claims, timesheets); System (accrual jobs, remittance calendar, stub emails, year-end slip generation); Platform Owner (uploads/approves CRA table editions for all orgs). |
| 2 | **Desired outcome** | A Canadian organisation can hire, classify, pay and report on its workers entirely inside Numo9: correct CPP/CPP2/EI/QPP/QPIP and federal + provincial tax per T4127 for any province, posted payroll journals, pay stubs, direct-deposit file, remittance amounts (paid in Phase 4 via G-09), and year-end T4/T4A/T5/RL-1 + ROE data validated against CRA schemas. |
| 3 | **Inputs** | Employee/contractor master data (SIN, address, province of employment, TD1 claims, bank details), positions/departments, pay schedules, earnings/deduction/benefit types, hours (manual or from J-02 timesheets), leave requests, worker-classification answers, uploaded CRA tables per tax year (T4127 edition, CPP/EI/QPP/QPIP constants, claim codes), provincial vacation/stat-holiday rules, dividend/interest payments for T5, termination details for ROE. |
| 4 | **Outputs** | Pay runs (draft → calculated → approved → posted → paid), pay stubs (PDF, EN/FR), payroll register, posted payroll JE (book = both), CPA 005 EFT file, remittance schedule with amounts per RP account and due dates, PD7A-style summary, T4/T4 Summary, T4A/T4A Summary, T5/T5 Summary XML (CRA e-file schema), RL-1 export, ROE data export, leave balances, HR letters, org chart, onboarding checklists, worker-classification determinations. |
| 5 | **Business rules** | Constants selected by **pay date's tax year** and edition effective date; CPP basic exemption pro-rated by pay periods; CPP stops at YTD max (4,230.45 in 2026), CPP2 on earnings between YMPE 74,600 and YAMPE 85,000 at 4 % (max 416.00); EI employee 1.63 % to MIE 68,900 (max 1,123.07), employer 1.4×; Quebec: QPP 6.3 % (max 4,479.30) + QPP2 4 %, EI 1.30 %, QPIP employee 0.430 % / employer 0.602 % to 103,000; income tax per T4127 Option 1 with TD1 claim codes; a run cannot post twice; posting respects Payroll lock date; approval limits per user; approver ≠ preparer; SIN encrypted at rest, masked on screen (`*** *** 123`), never logged; contractor classification removes CPP/EI/tax withholding and routes to T4A; taxable benefits land in the correct T4 box/code and increase insurable/pensionable earnings per CRA rules; employee sees only own records; practice specialist sees only assigned orgs; CRA six-year retention; slips due last day of February; e-file mandatory > 5 slips; Numo9 never files on the client's behalf (it produces filing-ready XML). |
| 6 | **What could go wrong** | Wrong constants edition (mid-year July T4127 change); CPP exemption pro-ration error for irregular periods; YTD maxima crossed mid-run; multi-province employees; Quebec flag mis-set; rounding drift between stub and register; double posting from double-click/worker retry; retro-pay or off-cycle runs mixing tax years (pay date in January for December work); negative net pay; SIN leakage into logs, Sentry or exports; uploaded table malformed; switching edition silently recomputing posted runs; contractor wrongly classified; benefit mapped to wrong T4 code; EFT file rejected by bank; leave accrual double-counting on rehire; terminated employee still in next run; employee accessing a colleague's stub via ID guessing; practice specialist keeping access after unassignment. |
| 7 | **Smallest useful implementation** | One Ontario salaried employee, bi-weekly schedule, 2026 constants loaded as data, gross → CPP/CPP2/EI/federal/ON tax → net, approved run posted as one balanced payroll JE, PDF stub, register equal to the JE. Every other deliverable extends this skeleton (provinces, Quebec, benefits, EFT, slips…). |

### 1.3 Restated objective

- **Currently:** Profitex and its clients run payroll in separate tools (Xero has no Canadian payroll; the teardown org pushes a third-party payroll app on its dashboard). Ledger postings, remittances and slips are reconciled by hand.
- **Change:** Build Numo9 HR (M-01…M-06) and Canadian payroll (N-01…N-13) inside the same ledger: versioned CRA constants uploaded per tax year, worker classification, taxable benefits, statutory calculations for every province including Quebec, stubs, register, EFT, remittance schedule ready for in-system payment, T4/T4A/T5/RL-1 XML, ROE data, and practice-run payroll for assigned client orgs.
- **Why:** Payroll is part of the Payroll product sold in packages; it removes a paid third-party tool, keeps payroll journals, liabilities and remittances consistent with the GL and tax books, and is one of Numo9's clearest advantages over Xero in Canada.
- **Done means:** the 40-scenario CRA fixture passes against uploaded tables; a multi-province pay run (ON, BC, AB, QC, NS) matches the CRA payroll deduction calculator (PDOC) to the cent; CPP/CPP2/EI maxima stop correctly; register totals = posted JE; CPA 005 file validates; T4, T4A and T5 XML validate against CRA XSD; RL-1 export and ROE data complete for fixtures; employee self-service shows only own records; Phase 3 exit demonstration observed on staging.

### 1.4 Assumptions & interpretations

1. "Upload CRA default tables" (N-12) means a structured import (XLSX/CSV/JSON per a Numo9 template) of the **constants and rate tables published in T4127** and related CRA/RQ publications; Numo9 computes tax by **T4127 formula (Option 1)** using those uploaded values — the tables themselves are the source of rates/brackets/thresholds, not a lookup of PDF tables.
2. Editions are effective-dated (e.g., T4127 January 2026 and July 2026 editions); a run uses the edition in force on its **pay date**. Switching edition on a *draft* run re-computes; *posted* runs are never re-computed (difference reports only).
3. The worker-classification factor set (N-11) is the six CRA factors (control, tools & equipment, financial risk, opportunity for profit, integration, intention) unless the client supplies a different set before Phase 3 (Agreement 9.1(c)); the tool records a **documented determination**, it does not give legal advice (Agreement 15.1).
4. T5 slips cover dividends and interest paid by the organisation; payments are recorded from the ledger (dividend/interest accounts flagged) or entered on a T5 worksheet.
5. RL-1 = export file (Revenu Québec format/data set), not an e-filing submission; ROE = data export for ROE Web (no ROE Web API submission).
6. Remittance **payment** (G-09) is built in Phase 4; Phase 3 delivers remittance amounts, calendar, PD7A-style summary and a "mark as paid" hook that G-09 will call.
7. Employee self-service in Phase 3 is the **web** experience; mobile is Phase 7 (Y-03) and reuses the same API.
8. French templates (EN/FR keys) exist from day one; French copy is filled in Phase 6.
9. Workers' compensation (WSIB/WCB) and provincial employer health taxes (EHT ON, BC EHT, MB HE levy, NL HAPSET, QC HSF/CNESST) are supported as **configurable employer contribution types** (rate + threshold data) because they post to payroll liabilities; they are not separately listed deliverables.

Open questions for the client (do not block; defaults above apply): editions to load (Jan 2026 + Jul 2026 T4127), factor set confirmation, list of benefit types beyond automobile/group insurance/housing/allowances, banks used for direct deposit (CPA 005 originator IDs).

### 1.5 Client inputs required (Agreement 9.1(c) — no later than start of Phase 3)

| Input | Used by | Due |
|---|---|---|
| CRA default tables per tax year (payroll deduction tables / T4127 constants, CPP/CPP2/EI/QPP/QPIP constants, claim codes) **or** confirmation of the editions GMA loads | N-01, N-04, N-12 | Start of week 5 |
| Worker-classification factor set confirmation | N-11 | Start of week 5 |
| Anonymised past payroll runs (multi-province if available) | N-04 fixtures, parallel run in Phase 5 | Start of week 5 |
| Provincial vacation/stat-holiday rule confirmation for provinces in use | M-03, N-13 | Week 5 |
| Bank originator details for CPA 005 test file (or bank's test spec) | N-06 | Week 6 |
| French HR letter templates or glossary (optional; Phase 6 otherwise) | M-05 | Week 6 |

---

## 2. BETTER THAN XERO — gap analysis for this phase

Xero org "REFINED" exposes **no payroll module for Canada**: payroll is pushed to an App Store partner (Wagepoint ad on Home, teardown §1), the CoA carries payroll liabilities (Source Deductions, WCB, Vacation payable, 803 Wages Payable) with nothing posting to them, and report codes use UK/AU terms ("annual leave", teardown §5.6). Every Phase 3 capability is therefore beyond Xero; the rows below map the teardown findings that touch people and payroll.

| Gap # | Teardown ref | What Xero does / fails to do | What Numo9 does instead (better) | Observable proof (test tag) |
|---|---|---|---|---|
| 31 | §5.6 | "Employee entitlements (wages, annual leave, etc)" and "Value added tax" labels for a Canadian org | Canadian terms everywhere: vacation pay, statutory holiday pay, source deductions, CPP/QPP, EI, RP account; i18n lint blocks UK/AU terms | `gap-31` — label lint finds 0 of "annual leave", "PAYE", "superannuation" |
| 29 | §5.4 | Payroll liabilities lumped / nothing posts to them | Separate payroll control accounts per type (CPP payable, EI payable, income tax payable, QPP/QPIP/RQ tax payable, vacation payable, benefits payable, net pay clearing); every run posts there | `gap-29` — register by liability = GL control balance |
| 40 | §6.2 | Coarse roles; no approval limits; dormant subscriber keeps Manage users | Payroll/HR roles separated (prepare vs approve vs view SIN); approval limits on pay runs; SIN-view permission audited | `gap-40` — $20,000 limit blocks $20,001 run; preparer cannot approve |
| 33 | §5.8 | Expenses booked by manual journal with no contact; no journal type | Payroll posts a **typed `payroll` journal** with employee contact per line from the run, never a free manual journal | `gap-33` — payroll JE lines carry employee contact & run link |
| 42 | §6.5 | No per-contact language; no custom sending domain | Stubs, slips and HR letters per employee language (EN/FR) sent from the org's verified domain | `gap-42` — FR employee receives FR stub email (keys present; copy Phase 6) |
| 43 | §6.6–6.7 | US Letter with cm margins; NZ sample data | Stub/slip PDFs on Letter with inch margins, Canadian sample employee in previews | `gap-43` — PDF snapshot: 8.5×11 in, 0.75 in margins |
| 51 | §7.2 | Expenses and Projects (timesheets) are paid add-ons | Expense claims and timesheets included and feed payroll (reimbursement + hours) in self-service | `gap-51` — approved timesheet hours appear on draft run |
| 37 | §5.13 | History 7-day default; no diffs | Payroll audit trail with field diffs (masked for SIN/bank), 90-day default | `gap-37` — rate change shows old→new |
| 52 | §8.1 | Search misses records | Employees, runs, slips, remittances in global search (SIN never searchable in clear) | `gap-52` — search "pay run 2026-14" opens run |

### Beyond-Xero additions in this phase
- Full Canadian payroll engine: CPP + **CPP2** with exemption pro-ration and YTD max, EI (employer 1.4×, QC rate), QPP/QPP2/QPIP, federal + provincial tax per T4127, for all 13 jurisdictions.
- **Uploaded CRA tables** by tax year and edition, versioned, with diff view and recompute-preview (N-12).
- **Worker-classification tool** with documented, audited determinations driving source-deduction treatment (N-11).
- **Taxable benefits** with T4 box/code mapping (automobile standby/operating, group term life, housing, allowances) (N-03).
- Year-end **T4/T4A/T5** + Summaries as CRA e-file XML validated against XSD; RL-1 export; ROE data (N-08, N-09).
- Vacation & statutory holiday pay by province (N-13), leave with provincial accrual rules (M-03).
- Remittance calendar by remitter type (quarterly / regular / accelerated 1 & 2) ready for in-system payment (N-07 → G-09).
- Practice-run payroll for assigned client orgs (N-10).
- HR: org chart, onboarding/offboarding with TD1, HR letters EN/FR, policy library, self-service.

### Xero strengths matched conceptually (original design)
- Keyboard quick-create (`Alt+P` → new pay run) and column chooser/saved views on employee and run lists (teardown §0, §10.B).
- Activity heatmap concept reused for payroll officers (V-05 data).
- Inbound-email/document inbox reused for TD1 and void-cheque uploads (A-06).

### [EXTRA] improvements (inside Schedule A scope, refinements only)
- [EXTRA] **Pre-flight checks** before calculation: missing TD1, missing bank details, SIN invalid (Luhn), employee terminated with hours, negative net pay, province changed mid-period — shown as a checklist, each with a one-click fix link.
- [EXTRA] **Variance panel** on run review: each employee's net vs last run, flagged when > ±15 % or new/terminated.
- [EXTRA] **"Explain this deduction"** drawer: shows the T4127 formula steps (A, K1, K2, K4, T3, T1/T2…) with values for one employee — builds accountant trust and speeds PDOC comparisons.
- [EXTRA] **SIN validation** (Luhn check, temporary "9" SIN expiry date captured with reminder).
- [EXTRA] **Off-cycle runs** (bonus, termination, correction) using the bonus method of T4127 for lump sums.
- [EXTRA] **Payroll-to-GL reconciliation** working-paper template in Sheets (L-03) tying T4 Summary boxes to GL control accounts.
- [EXTRA] **Year-end readiness dashboard**: counts slips ready/blocked, PIER-style review (CPP/EI over/under deduction check per employee).
- [EXTRA] Employer health tax / WCB as configurable employer contributions with thresholds (data-driven).

---

## 3. UI/UX DESIGN PLAN

### 3.1 UX principles applied in this phase
1. **Task-first navigation:** "People" top-level menu with *Employees · Pay runs · Leave · Remittances · Year-end · HR documents · Settings*; the most frequent job (run payroll) is one click from the dashboard and from `Alt+P`.
2. **Wizard for risky, repeatable work:** pay runs use a 5-step stepper (Period → Hours & earnings → Review → Approve → Post & pay) with a persistent summary rail (gross, deductions, employer cost, net, cash needed).
3. **Progressive disclosure:** employee form shows essentials (name, province, pay type, rate, start date) first; TD1, benefits, bank and tax overrides open in tabs; Quebec-specific fields appear only when province = QC.
4. **Zero silent redirects / explicit gating:** an org without the Payroll product sees the People menu with a "Payroll is included in package X — view packages" panel (U-03), never a redirect.
5. **Forgiving inputs:** SIN input auto-formats `123 456 789`, validates Luhn inline; postal code auto-uppercases; hours accept `7.5`, `7:30`, `7h30`.
6. **Undo over confirm where safe:** draft-run edits autosave with undo; posting is irreversible so it uses a typed confirmation summary (amount + period), and correction is via a reversal run.
7. **Privacy by design:** SIN and bank numbers masked by default; "Reveal" requires `payroll.sin.view` permission and re-authentication within 5 min; every reveal is audited.
8. **Keyboard-first for accountants:** grid navigation with arrows/Enter on hours grid, `Ctrl+Enter` to recalculate, `?` shows shortcuts.
9. **Explain numbers:** every computed amount has an info affordance opening the "Explain this deduction" drawer.
10. **Accessibility:** WCAG 2.1 AA, focus order matches visual order, stepper announces step via `aria-live`, colour never the only signal (status chips have icons + text), 4.5:1 contrast.
11. **Localisation-ready:** all strings in en-CA/fr-CA catalogues; layouts tested with +30 % pseudo-locale; currency `1,234.56 $`-ready formatting via the locale formatter; dates per locale.
12. **Documents:** Letter size, inch margins, employee language, org branding; stubs readable on a phone.
13. **Employee self-service simplicity:** big cards ("Latest pay", "Vacation balance", "Documents", "Submit claim"), plain-language labels ("Take-home pay" with "Net pay" as secondary term).

### 3.2 Information architecture added in this phase
```
People
├── Employees (list) ── Employee profile [Overview · Job & pay · Tax (TD1) · Benefits · Bank · Leave · Documents · Pay history · Audit]
├── Contractors (list, classification badge)
├── Org chart
├── Pay runs (list) ── Pay run wizard [1 Period · 2 Hours & earnings · 3 Review · 4 Approve · 5 Post & pay]
├── Leave (calendar · requests · balances)
├── Remittances (calendar · PD7A-style summary)
├── Year-end (T4 · T4A · T5 · RL-1 · ROE)
├── HR documents (templates · policy library · letters)
└── Payroll settings [Schedules · Earnings types · Deductions · Benefits · Employer contributions · Vacation & stat rules · CRA tables & editions · Remitter type · GL mapping · Approval]
Platform console → CRA tables (upload edition for all orgs)
Self-service (Employee role) → My pay · My slips · My leave · My claims · My timesheets · My profile
```

### 3.3 Screen inventory

| Screen | Primary user | Purpose | Key components | States | Keyboard shortcuts |
|---|---|---|---|---|---|
| Employees list | Payroll/HR | Find, filter, bulk actions | DataGrid, filter chips, column chooser, saved views | empty (CTA "Add first employee" + import), loading skeleton, gated, read-only | `N` new, `/` search |
| Employee profile | Payroll/HR | Maintain master data | Tabbed form, MaskedField (SIN/bank), AddressForm (Province), DatePicker | draft/active/terminated, masked/revealed, validation inline | `Ctrl+S` save, `Alt+1..9` tabs |
| Add employee wizard | Payroll/HR | Onboard in < 3 min | Stepper, TD1 claim helper | partial save, resume | `Enter` next |
| Contractor profile + classification | Payroll | Decide employee vs contractor | Questionnaire, factor scoring, determination card | undecided/employee/contractor, needs-review | `Alt+C` |
| Departments & positions | HR | Structure | Tree editor, drag-drop | empty, cycle error | — |
| Org chart | Owner/HR | Visualise reporting lines | Zoomable tree (d3-hierarchy), search | empty, large-org collapsed | `+/-` zoom |
| Leave calendar | HR/Employee | See absences | Month calendar, legend | empty, conflict overlap | arrows |
| Leave request modal | Employee | Request leave | Date range, type, balance preview | insufficient balance warning | — |
| Onboarding checklist | HR | Track hire tasks | Checklist component, progress bar, e-acknowledge | not started/in progress/complete | — |
| HR letters | HR | Generate letter | Template picker, merge preview, PDF | missing-field warning | — |
| Policy library | HR/Employee | Publish policies, track acknowledgement | Document list, acknowledgement status | unread/acknowledged | — |
| Pay schedules | Payroll | Define frequencies | Form + period preview list | — | — |
| Earnings/deductions/benefits types | Payroll | Configure items with T4 mapping | Grid, T4 box/code picker, flags (pensionable/insurable/taxable) | system vs custom | — |
| CRA tables & editions (org + platform) | Platform Owner/Payroll | Upload & activate editions | Upload dropzone, validation report, diff viewer | invalid file, pending activation, active, superseded | — |
| Pay run wizard — step 1 Period | Payroll | Pick schedule/period/pay date | Period picker, pre-flight checklist | blocked by checks | `Enter` |
| Step 2 Hours & earnings | Payroll | Enter hours/one-offs | Editable grid (virtualised), import timesheets button | changed cells highlighted | arrows, `Ctrl+Enter` recalc |
| Step 3 Review | Payroll/Owner | Verify results | Summary rail, variance panel, per-employee breakdown, Explain drawer | warnings, stale (needs recalculation) | `E` explain |
| Step 4 Approve | Approver | Approve within limit | Approval card, limit indicator | over-limit (routes to next approver), self-approval blocked | — |
| Step 5 Post & pay | Payroll | Post JE, stubs, EFT | Result card with links (JE, register, EFT, stubs) | posted, paid | — |
| Payroll register | Payroll/Accountant | Report per run/period | Report engine (K-01) | — | — |
| Pay stub viewer | Employee | Read stub | Responsive document view + PDF | — | — |
| Remittances calendar | Payroll/Owner | Due amounts & dates | Calendar + list, status chips (due, overdue, paid) | none due | — |
| Year-end hub | Payroll/Accountant | Generate/validate slips | Readiness cards, validation results, XML download | blocked (errors list), ready, generated | — |
| ROE data | Payroll | Export ROE fields | Form prefilled from history, block-by-block validation | incomplete | — |
| Self-service home | Employee | Own pay/leave/docs | Cards, lists | first-login onboarding tour | — |

### 3.4 Key user flows (with targets)
1. **Add an Ontario employee** (target < 3 min, ≤ 12 fields required): People → Employees → New → name, email, province ON, start date, pay type salary, annual amount, schedule bi-weekly → TD1 (default basic personal amount; "upload signed TD1" optional) → bank (optional, can invite employee to fill via self-service) → Save. Invitation to self-service sent.
2. **Run bi-weekly payroll** (target < 5 min for 20 salaried staff; ≤ 6 clicks when nothing changes): Dashboard "Run payroll" → Step 1 (period pre-selected, pre-flight green) → Step 2 (salaried auto-filled; hourly from approved timesheets) → Calculate → Step 3 review variance panel → Submit for approval → approver approves (email/in-app) → Post → stubs emailed, EFT downloaded, remittance updated.
3. **Classify a worker** (target < 4 min): Contractors → New → questionnaire (6 factors, each with guidance text and evidence upload) → determination suggested with rationale → user confirms with reason → saved, audited; treatment applied.
4. **Upload a CRA edition** (Platform Owner, target < 2 min): Console → CRA tables → upload template → validation report (row-level errors) → diff vs current edition → set effective date → activate → orgs see banner-free notice in payroll settings.
5. **Year-end T4** (target < 10 min for 50 employees): Year-end → T4 → readiness check (CPP/EI review, missing SIN/addresses) → fix links → Generate → XSD validation passes → download XML + PDFs → employees get slips in self-service.
6. **Employee requests vacation** (target < 1 min): Self-service → Leave → dates → balance preview → Submit → manager approves → calendar updated, accrual reduced, pay run picks up vacation pay.

### 3.5 Microcopy & error-message rules
- Name the **cause** and the **fix**, never a code alone: "This pay run can't be posted because the Payroll lock date is 31 Oct 2026. Ask an adviser to move the lock date or change the pay date."
- Use Canadian payroll terms: vacation pay, statutory holiday pay, source deductions, Record of Employment, TD1, RP account.
- Warnings vs blocks are visually distinct (amber "Check" vs red "Fix before continuing").
- Examples:
  - "SIN 046 454 287 doesn't pass the CRA check digit test. Please re-check the number on the employee's SIN letter."
  - "Maya Chen reached the 2026 CPP maximum (4,230.45) on this run. No CPP is deducted for the rest of 2026."
  - "This run uses the July 2026 tax tables because the pay date is 17 Jul 2026."
  - "You can approve pay runs up to 20,000.00. This run (24,850.12) will be sent to Omar Haddad for approval."
  - "Contractor treatment selected: no CPP, EI or income tax will be withheld, and payments will appear on a T4A."
- Empty states teach: "No pay runs yet. Set up a pay schedule, then run your first payroll — it takes about five minutes."

### 3.6 Accessibility & usability test plan

| Test | Participants | Task | Success metric |
|---|---|---|---|
| Moderated usability | 3 payroll officers (incl. Profitex staff) | Add ON employee and run first payroll | 100 % completion, median < 8 min, ≤ 1 assist |
| Moderated usability | 2 accountants | Compare one employee to PDOC using Explain drawer | Identify each line in < 2 min |
| Unmoderated | 5 employees | Find latest stub and vacation balance in self-service | < 30 s, SUS ≥ 80 |
| Automated a11y | CI | axe-core on every Phase 3 route | 0 serious/critical violations |
| Keyboard-only | QA | Complete pay-run wizard with keyboard | Possible end-to-end |
| Screen reader | QA (NVDA + VoiceOver) | Read stub, submit leave | All controls labelled |
| Pseudo-locale | CI | +30 % strings on wizard and stub | No clipping/overflow |

---

## 4. TOOLS & TECHNOLOGY FOR THIS PHASE

| Category | Tool / library | Used for | Notes |
|---|---|---|---|
| Backend | Django 5 + DRF | Models, APIs | GMA core stack |
| Backend | Python `decimal` (ROUND_HALF_UP context) | All payroll arithmetic | Never float; one helper `money()` |
| Backend | `django-pgcrypto-fields` or `cryptography` (Fernet/AES-GCM) + KMS key | SIN/bank field-level encryption | Key rotation command |
| Backend | `python-stdnum` (`ca.sin`, `ca.bn`) | SIN/BN validation | MIT/LGPL |
| Backend | `python-dateutil` (rrule) | Pay-period generation, remittance due dates | — |
| Backend | `holidays` (Canada provinces) as seed source + editable table | Stat-holiday calendar per province | Seed only; data editable |
| Backend | Celery + Redis | Calculation jobs, stub generation, accrual jobs, reminders | A-08 |
| Backend | `django-fsm` (or explicit state machine) | Pay-run / leave / classification lifecycles | — |
| Backend | `openpyxl`, `pandas` (import only) | CRA table upload parsing (XLSX/CSV) | — |
| Backend | `pydantic` | Schema for uploaded edition files | Row-level validation report |
| Backend | `lxml` + `xmlschema` | T4/T4A/T5 XML generation and **CRA XSD validation** | CRA e-file XSD kept in `backend/payroll/xsd/<year>/` |
| Backend | Custom `cpa005` builder (internal module) | Direct-deposit EFT file | Fixed-width 1464-byte records; validated with test spec |
| Backend | WeasyPrint | Stub, register, slip, letter PDFs | Letter / inch margins |
| Backend | Jinja2 / Django templates | HR letter merge | EN/FR variants |
| Backend | `django-simple-history` not used — A-04 audit engine reused | Audit | Masked diffs |
| Frontend | Next.js 15, TypeScript, React Query | Screens | One design system |
| Frontend | TanStack Table + virtualisation | Hours grid, employee lists | Shared grid (A-10) |
| Frontend | React Hook Form + Zod | Employee/TD1 forms | Zod schemas generated from OpenAPI |
| Frontend | `d3-hierarchy` / `react-flow` | Org chart | — |
| Frontend | FullCalendar (or design-system calendar) | Leave calendar, remittance calendar | Licence check (MIT core) |
| Frontend | `react-imask` | SIN/postal code input masks | — |
| Design | Figma (+ FigJam for flows) | Wireframes, wizard prototype, stub layout | — |
| Design | Storybook | Component states (MaskedField, Stepper, SummaryRail, ExplainDrawer) | Chromatic visual tests |
| Testing | pytest, pytest-django, factory_boy, Faker (`en_CA`, `fr_CA`) | Unit/integration | — |
| Testing | Hypothesis | Property tests: YTD maxima never exceeded, net = gross − deductions, register = JE | — |
| Testing | **PDOC comparison fixtures** (`tests/fixtures/compliance/payroll/pdoc_2026_*.json`) | 40-scenario CRA fixture; expected values captured from CRA Payroll Deductions Online Calculator | Captured manually by QA with screenshots stored |
| Testing | syrupy (snapshot) | PDF/XML snapshots | — |
| Testing | Playwright | Pay-run wizard E2E, self-service E2E | — |
| Testing | Vitest + Testing Library | Frontend units | — |
| Testing | axe-core, Lighthouse CI | Accessibility | — |
| Testing | k6 | 500-employee run calculation perf | Target < 30 s |
| Testing | `pdfplumber` | Assert stub PDF text values | — |
| Quality | ruff, mypy (strict on `payroll`), eslint, prettier, pre-commit, import-linter (payroll may not import sales), semgrep rule "no SIN in logger calls" | Static checks | — |
| Security | gitleaks, pip-audit, npm audit, OWASP ZAP, Trivy | Scans | — |
| Security | Sentry `before_send` scrubber + custom log filter | Drop SIN/bank patterns | Tested |
| Observability | Sentry, Prometheus metrics (`payroll_run_duration`, `payroll_calc_errors`) | Monitoring | — |
| Docs | drf-spectacular (OpenAPI), MkDocs, ADR template | API & docs | ADR-005 payroll constants model |
| Dev productivity | Docker Compose, Makefile, mailpit, MinIO | Local stack | — |
| Internal tools to build | `manage.py load_payroll_edition` | Load/validate an edition file | N-12 |
| Internal tools to build | `manage.py payroll_fixture_runner` | Run 40-scenario fixture & print diff table | N-04 |
| Internal tools to build | `manage.py seed_payroll_demo` | Demo org employees/runs (U-07 seed) | — |
| Internal tools to build | `manage.py rotate_pii_key` | Re-encrypt SIN/bank with new key | M-01 |
| Internal tools to build | `manage.py validate_slips <year>` | XSD-validate all slips for an org | N-08 |
| Internal tools to build | CPA 005 viewer (dev page) | Human-readable decode of EFT file | N-06 |
| Internal tools to build | Explain-deduction trace (calculation trace object) | Debug + UI drawer | N-04 |
| Internal tools to build | Payroll tenant sweep extension | Adds all payroll/HR endpoints + self-service scope | M-06/N-10 |

---

## 5. DECOMPOSE (Rule 2)

### 5.1 Level 1 — Objective
Canadian HR and payroll inside Numo9: workers recorded, classified and paid correctly for any province, payroll posted to the ledger, remittances scheduled, year-end slips and ROE data produced, employees served through self-service — all driven by versioned CRA data.

### 5.2 Level 2 — Components

| Component | Deliverables | Purpose |
|---|---|---|
| M1 — Worker records | M-01, M-02 | Employee/contractor master, structure, org chart |
| M2 — HR operations | M-03, M-04, M-05, M-06 | Leave, on/offboarding, documents, self-service |
| N1 — Statutory data | N-01, N-12 | Constants by year, uploaded CRA tables & editions |
| N2 — Pay configuration | N-02, N-03, N-11, N-13 | Schedules/runs, earnings/deductions/benefits, classification, vacation & stat pay |
| N3 — Calculation & output | N-04, N-05, N-06 | Statutory engine, stubs/register, EFT |
| N4 — Compliance outputs | N-07, N-08, N-09 | Remittances, year-end slips, ROE |
| N5 — Practice operation | N-10 | Payroll by the practice inside client orgs |

### 5.3 Dependency graph and execution order
```
M-01 ─┬─ M-02 ─┬─ M-04 ─┐
      │        └─ M-05  │
      ├─ N-11           │
      ├─ M-03 ── N-13 ──┤
N-12 ─┴─ N-01 ── N-02 ── N-03 ── N-04 ─┬─ N-05 ── N-06
                                       ├─ N-07
                                       ├─ N-08 ── (T4/T4A/T5/RL-1)
                                       ├─ N-09
                                       └─ N-10
M-06 (after M-03, M-05, N-05) — self-service
```
Execution order (‖ = parallel track):
1. M-01 Employee & contractor master ‖ N-12 CRA tables upload (data model + importer)
2. N-01 Constants by tax year ‖ M-02 Departments & org chart
3. N-02 Pay schedules & runs ‖ N-11 Worker classification ‖ M-03 Leave
4. N-03 Earnings, deductions & benefits ‖ M-04 Onboarding/offboarding
5. N-04 Statutory calculations (critical path) ‖ N-13 Vacation & stat holiday pay ‖ M-05 HR documents
6. N-05 Stubs & register → N-06 EFT ‖ N-07 Remittances
7. N-08 Year-end slips ‖ N-09 ROE
8. N-10 Practice payroll ‖ M-06 Self-service
9. Phase regression, compliance fixtures, exit demonstration

---

## 6. PLAN — Deliverable cards with ATOMIC TASKS (Rule 3)

### M-01 · Employee & contractor master
- **Branch:** `feature/M-01-worker-master`
- **Objective:** one secure record per worker (employee or contractor) holding identity, employment, tax, pay and bank data used by HR and payroll.
- **Current behaviour:** no worker model; B-01 contacts have an "employee" role flag only.
- **Expected behaviour (better than Xero):** `Worker` record with type (employee/contractor), province of employment, SIN encrypted at rest and masked on screen, bank details encrypted, linked contact for T4A/expense reimbursements, employment status lifecycle (draft → active → on leave → terminated → rehired), CSV/XLSX import by stable ID, audit with masked diffs. Xero has no Canadian employee record at all.
- **Gap #s closed:** 31, 37, 40 (permission split), 52 (search).
- **Business rules:** SIN unique per org among active workers; SIN Luhn-valid; temporary SIN (starts with 9) requires expiry date; province of employment required (drives tax/plan); Quebec province → QPP/QPIP flags; termination date ≥ hire date; a terminated worker cannot be added to a regular run after termination date (off-cycle termination run allowed); SIN never logged, never exported except on slips/ROE; view of unmasked SIN needs `payroll.sin.view` + re-auth.
- **Edge cases:** rehire keeps history and YTD in same year; employee moving province mid-year (effective-dated province record); name change; duplicate SIN across two orgs (allowed — different employers); missing bank details (cheque pay method); deleted (soft) worker with posted runs (archive only).
- **UI/UX notes:** list with status chips, column chooser, saved views; profile tabs; add-employee wizard; MaskedField with Reveal + countdown; inline Luhn validation; import wizard with mapping and dry-run.
- **Dependencies:** A-01, A-03, A-04, A-06, A-10, B-01.

| Task ID | Atomic task (what is built; expected behaviour) | Layer | Depends | Acceptance (observable) | Test |
|---|---|---|---|---|---|
| M-01-T01 | Figma wireframes: employee list, profile tabs, add-employee wizard, MaskedField states | UX | — | Reviewed by project lead; states listed (empty/masked/revealed/error) | Design review |
| M-01-T02 | `Worker` model (`OrgOwnedModel`): type, legal first/last, preferred name, DOB, language, email, phone, address (Province, Postal code), hire_date, termination_date, status, pay_method, linked `contact` | DB | A-01 | Migration applies; lint passes (inherits OrgOwnedModel) | Unit |
| M-01-T03 | `EncryptedField` for SIN and bank (institution, transit, account) using AES-GCM with KMS-held key; `sin_last3` cached for masked display | DB/BE | M-01-T02 | DB column contains ciphertext; ORM returns plaintext only through service accessor | Unit |
| M-01-T04 | `WorkerProvinceHistory` (effective-dated province of employment) | DB | M-01-T02 | Province on a date resolves to the right row; no overlaps (constraint) | Unit + property |
| M-01-T05 | SIN validator service (python-stdnum Luhn, 9-prefix temporary → expiry required, uniqueness among active workers in org) | BE | M-01-T03 | Invalid SIN rejected with message; temp SIN without expiry rejected | Unit |
| M-01-T06 | Status state machine (draft/active/on_leave/terminated) with rehire creating new `EmploymentPeriod` | BE | M-01-T02 | Illegal transitions rejected; rehire preserves history | Unit |
| M-01-T07 | Log/Sentry scrubber: filter removing SIN/bank patterns from logs, exceptions and audit diffs (`***`) + semgrep rule | OPS/BE | M-01-T03 | Test logs a SIN → captured log contains mask only | Unit + semgrep CI |
| M-01-T08 | Audit integration: masked diffs for encrypted fields ("SIN changed", no values); reveal events audited with user/IP | BE | A-04, M-01-T03 | Audit shows "SIN changed by X"; reveal entry recorded | Integration |
| M-01-T09 | Permissions: `hr.worker.view/edit`, `payroll.sin.view`, `payroll.bank.view`; re-auth (password/TOTP) within 5 min for reveal | API | A-03 | User without `payroll.sin.view` gets 403 on reveal endpoint | RBAC matrix |
| M-01-T10 | REST API `/api/v1/people/workers/` CRUD + `/reveal-sin/` + filters (status, type, province, department) ; feature key `hr.core` | API | M-01-T02..T09 | OpenAPI documented; tenant sweep registered; 402 when product absent | Integration + sweep |
| M-01-T11 | Employee list screen (DataGrid, filters, saved views, column chooser, bulk export without SIN) | FE | M-01-T10 | Lists 1,000 workers < 1 s; export has no SIN column | Playwright |
| M-01-T12 | Profile screen with tabs (Overview, Job & pay, Tax, Benefits, Bank, Leave, Documents, Pay history, Audit) — Job & pay and Tax tabs stubbed for N-02/N-03 | FE | M-01-T10 | Tabs navigable via `Alt+1..9`; unsaved-changes guard | Playwright |
| M-01-T13 | MaskedField component (SIN/bank) with Reveal, countdown re-mask after 60 s, copy disabled when masked | FE | M-01-T09 | Storybook states; screen reader announces "masked" | Vitest + Chromatic |
| M-01-T14 | Add-employee wizard (essentials → TD1 placeholder → bank optional → invite to self-service) | FE | M-01-T12 | ON employee added in < 3 min in usability test | Playwright |
| M-01-T15 | Worker import (CSV/XLSX): mapping, stable `external_id`, non-destructive updates, dry-run report, SIN validated | BE/FE | M-01-T05 | Re-import same file → 0 changes; invalid SIN rows reported with row number | Integration |
| M-01-T16 | i18n keys en-CA/fr-CA for all M-01 screens & messages | FE | M-01-T11..T15 | Missing-key gate passes (FR placeholders) | CI |
| M-01-T17 | Global search registration (name, employee no.; never SIN) | BE | A-09 | Search "Chen" returns worker; searching SIN digits returns nothing | Integration |
| M-01-T18 | Key rotation command `rotate_pii_key` | OPS | M-01-T03 | After rotation all values decrypt with new key; old key retired | Integration |
| M-01-T19 | Docs: data dictionary entries, privacy note (PIPEDA, masking, retention 6 years) | DOC | all | Docs merged in `docs/` | Review |

- **Deliverable acceptance:** SIN never logged (log/Sentry capture test); masked on screen; reveal audited; tenant sweep passes; import non-destructive.
- **Testing approach:** unit (validators, state machine, encryption), integration (API, import), security (log scrub, RBAC, sweep), functional (wizard E2E).
- **Risks & mitigations:** key loss → KMS + documented backup procedure; SIN leaking through debug toolbar/serializer → serializer whitelist test that fails if `sin` appears in any non-reveal response.

### M-02 · Departments, positions & org chart
- **Branch:** `feature/M-02-org-structure`
- **Objective:** model the organisation's structure and reporting lines; render an org chart.
- **Current → Expected:** none → `Department` (hierarchical), `Position` (title, department, default pay grade), `WorkerAssignment` (worker, position, manager, effective dates); org chart renders from data; departments usable as payroll cost centres (tracking dimension) and for bill/approval routing (E-02).
- **Gap #s:** 46 (tracking hierarchy reused for departments).
- **Business rules:** no cycles in manager chain or department tree; one primary assignment per worker per date; department deletion blocked while assigned (archive).
- **Edge cases:** worker with no manager (top); matrix (secondary manager) shown dashed; > 500 nodes collapse.
- **UI/UX:** tree editor drag-drop with undo; org chart zoom/pan/search; click node → profile.
- **Dependencies:** M-01, C-01 tracking categories.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| M-02-T01 | Wireframes: department tree editor, org chart, assignment panel | UX | — | Reviewed | Design review |
| M-02-T02 | `Department` model (parent FK, code, name, cost-centre link to tracking option) | DB | A-01 | Migration; unique code per org | Unit |
| M-02-T03 | Cycle-prevention validator for department tree | BE | M-02-T02 | Moving parent under child rejected | Unit + property |
| M-02-T04 | `Position` model (title, department, FTE, pay grade min/max) | DB | M-02-T02 | CRUD works | Unit |
| M-02-T05 | `WorkerAssignment` effective-dated (worker, position, manager, primary flag) with no-overlap constraint | DB | M-01 | Overlapping primary assignment rejected | Unit |
| M-02-T06 | Manager-chain cycle check + "reports to" resolver on a date | BE | M-02-T05 | A→B→A rejected; resolver returns correct manager on dates | Unit + property |
| M-02-T07 | Department ↔ tracking-category sync (department becomes a tracking option for payroll JE lines) | BE | C-01 | Payroll lines can carry department tracking | Integration |
| M-02-T08 | APIs `/api/v1/people/departments/`, `/positions/`, `/assignments/`, `/org-chart/?date=` (feature `hr.core`) | API | T02–T07 | OpenAPI; sweep registered | Integration + sweep |
| M-02-T09 | Department tree editor UI (drag-drop, archive, undo toast) | FE | M-02-T08 | Drag move persists; undo reverts | Playwright |
| M-02-T10 | Org chart component (d3-hierarchy), zoom/pan, search, collapse > 50 children | FE | M-02-T08 | 500-node chart renders < 2 s | Playwright + perf |
| M-02-T11 | Assignment panel on profile (position, manager, history) | FE | M-02-T08 | History shows effective dates | Playwright |
| M-02-T12 | i18n keys + a11y (org chart has list alternative view) | FE | T09–T11 | axe 0 serious; list view reachable by keyboard | axe CI |
| M-02-T13 | Docs (structure model) | DOC | — | Merged | Review |

- **Acceptance:** org chart renders from data; cycles impossible; department usable as tracking on payroll lines.
- **Testing:** unit/property (cycles), integration, functional, perf.
- **Risks:** large orgs → virtualised list fallback.

### M-03 · Leave management
- **Branch:** `feature/M-03-leave`
- **Objective:** leave types, accrual by provincial rules, requests and approvals, balances feeding payroll.
- **Current → Expected:** none → `LeavePolicy` per org (type: vacation, sick, personal, bereavement, family responsibility, unpaid, statutory), accrual method (per pay period % of earnings, per hours worked, annual entitlement by years of service — data from `ProvincialLeaveRule`), carry-over, negative balance rule; requests with approval; balances; leave calendar; vacation taken flows to N-13 vacation pay.
- **Gap #s:** 31 ("annual leave" → "vacation").
- **Business rules:** entitlement per province and years of service (e.g., ON 2 weeks/4 % < 5 yrs, 3 weeks/6 % ≥ 5 yrs; SK 3 weeks; QC 4 % < 3 yrs / 6 % ≥ 3 yrs; federal-regulated per Canada Labour Code) loaded as **data** in `ProvincialLeaveRule` (client confirms); request cannot exceed balance unless policy allows negative; approver = manager (M-02) or HR; overlapping requests flagged.
- **Edge cases:** part-day leave; leave spanning year end; rehire resets service unless policy keeps it; stat holiday inside leave not deducted.
- **UI/UX:** calendar with team view; request modal with live balance preview; approval inbox with bulk approve.
- **Dependencies:** M-01, M-02, A-07.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| M-03-T01 | Wireframes: leave calendar, request modal, balances tab, approval inbox | UX | — | Reviewed | Design review |
| M-03-T02 | `ProvincialLeaveRule` table (province, leave type, service threshold, weeks, vacation %, effective dates) + seed for 13 jurisdictions + federal | DB | — | Seed loads; rows effective-dated | Unit |
| M-03-T03 | `LeavePolicy` model (org-level, type, accrual method, carry-over cap, negative allowed) linked to rule | DB | M-03-T02 | CRUD | Unit |
| M-03-T04 | `LeaveBalance` ledger (append-only entries: accrual, taken, adjustment, carry-over, payout) | DB | M-01 | Balance = sum of entries | Unit + property |
| M-03-T05 | Accrual service: per-period % of earnings, per-hour, annual grant; years-of-service resolver | BE | M-03-T03, T04 | ON employee at 5 yrs moves 4 %→6 % on anniversary | Unit (provincial fixtures) |
| M-03-T06 | Year-end carry-over job (cap, expiry) on Celery beat | BE | M-03-T05, A-08 | Runs once per year-end; cap applied | Integration |
| M-03-T07 | `LeaveRequest` model + state machine (draft/submitted/approved/rejected/cancelled) | DB/BE | M-03-T04 | Approved request posts "taken" entry once | Unit |
| M-03-T08 | Working-day calculator excluding weekends and province stat holidays (N-13 calendar) | BE | N-13-T02 | 5-day request spanning Victoria Day counts 4 | Unit |
| M-03-T09 | Approval routing (manager → HR fallback) + notifications | BE | M-02, A-07 | Manager notified; self-approval blocked | Integration |
| M-03-T10 | APIs `/leave/policies/`, `/leave/requests/`, `/leave/balances/`, `/leave/calendar/` (feature `hr.leave`) | API | T03–T09 | OpenAPI; sweep | Integration + sweep |
| M-03-T11 | Leave calendar UI (month/team views, legend with icons) | FE | M-03-T10 | Keyboard navigable | Playwright |
| M-03-T12 | Request modal with live balance preview and insufficient-balance warning | FE | M-03-T10 | Warning shown when request > balance | Playwright |
| M-03-T13 | Approval inbox (bulk approve/reject with reason) | FE | M-03-T10 | 10 requests approved in one action | Playwright |
| M-03-T14 | Balances tab on profile + manual adjustment with reason (audited) | FE | M-03-T10 | Adjustment appears in audit | Playwright |
| M-03-T15 | Provincial accrual fixtures (ON, BC, AB, QC, NS, federal) | QA | M-03-T05 | All pass | Fixture suite |
| M-03-T16 | i18n keys; Canadian terms ("vacation", not "annual leave") | FE | — | Lint passes | CI |
| M-03-T17 | Docs: leave policy configuration guide | DOC | — | Merged | Review |

- **Acceptance:** accruals match provincial fixtures; balance = sum of entries; approved leave appears on calendar and in next pay run.
- **Testing:** unit + provincial fixtures, property (balance), integration, functional.
- **Risks:** rule differences per province — data-driven with client confirmation.

### M-04 · Onboarding / offboarding
- **Branch:** `feature/M-04-on-offboarding`
- **Objective:** checklist-driven hiring and termination with TD1 federal/provincial capture, direct-deposit collection and acknowledgements.
- **Current → Expected:** none → `ChecklistTemplate` (onboarding/offboarding, tasks with owner role, due offset), instantiated per worker; TD1 federal + provincial (TD1ON, TD1BC, … TP-1015.3 for QC) claim amounts captured as structured data (total claim amount / claim code) with signed form upload; direct deposit via self-service with void-cheque upload; acknowledgements (policies) tracked; offboarding triggers final pay (off-cycle run), vacation payout, ROE data (N-09), access revocation.
- **Business rules:** active status requires TD1 (default basic personal amount used and flagged if missing); offboarding completion requires final pay posted and ROE data prepared; checklist completion tracked per worker.
- **Edge cases:** employee with multiple employers (TD1 claim 0 / code 0); non-resident; exempt indicator (TD1 "will not exceed total claim").
- **UI/UX:** checklist with progress bar, assignee avatars, due dates; TD1 helper explains each line; employee completes own TD1 in self-service.
- **Dependencies:** M-01, M-02, A-06, N-01 (claim codes).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| M-04-T01 | Wireframes: checklist view, TD1 helper, offboarding wizard | UX | — | Reviewed | Design review |
| M-04-T02 | `ChecklistTemplate` / `ChecklistTask` models + default onboarding & offboarding templates | DB | A-01 | Templates seeded | Unit |
| M-04-T03 | `WorkerChecklist` instantiation on hire/termination (Celery signal) | BE | M-04-T02, M-01 | Hire creates checklist with due dates | Integration |
| M-04-T04 | `TD1Claim` model (jurisdiction, tax year, total claim amount, claim code, additional tax, exempt flags, signed file) | DB | N-01 | Federal + provincial row per worker/year | Unit |
| M-04-T05 | Claim-code resolver from total claim amount using edition claim-code table (N-12) | BE | N-12 | Amount maps to correct code per edition | Unit |
| M-04-T06 | Default TD1 (basic personal amount) applied and flagged "TD1 missing" when absent | BE | M-04-T04 | Pre-flight shows warning (N-02) | Unit |
| M-04-T07 | Direct-deposit capture flow (bank fields encrypted, void-cheque upload, verification status) | BE/FE | M-01-T03 | Bank set by employee; HR sees masked | Integration |
| M-04-T08 | Acknowledgement model (worker, document version, acknowledged_at, IP) | DB | M-05 | Acknowledgement stored | Unit |
| M-04-T09 | Offboarding wizard: last day, reason (ROE code), final pay off-cycle run draft, vacation payout, access revocation, ROE draft | BE/FE | N-02, N-09, N-13 | Completing wizard creates draft final run and ROE draft; self-service access ends after last day + 90 days (slips remain) | Playwright |
| M-04-T10 | APIs `/checklists/`, `/td1/`, `/direct-deposit/`, `/offboarding/` (feature `hr.core`) | API | T02–T09 | OpenAPI; sweep | Integration + sweep |
| M-04-T11 | Checklist UI (progress, assignee, due, complete with note) | FE | M-04-T10 | Completion % updates live | Playwright |
| M-04-T12 | TD1 helper UI (line-by-line guidance, totals, upload signed copy) | FE | M-04-T10 | Total computes; code shown | Vitest |
| M-04-T13 | i18n + a11y | FE | — | Gates pass | CI |
| M-04-T14 | Tests: hire → checklist → TD1 → active; terminate → final run draft | QA | all | E2E green | Playwright |
| M-04-T15 | Docs | DOC | — | Merged | Review |

- **Acceptance:** checklist completion tracked per employee; TD1 data drives tax calc; offboarding produces final-pay draft and ROE draft.
- **Testing:** unit, integration, functional.
- **Risks:** TD1 form changes yearly → claim-code table per edition.

### M-05 · HR documents & letters
- **Branch:** `feature/M-05-hr-documents`
- **Objective:** generate HR letters from templates (EN/FR) and publish a policy library with acknowledgements.
- **Current → Expected:** none → `LetterTemplate` (employment offer, confirmation of employment, salary change, termination, reference) with merge fields from worker/assignment/pay; PDF on Letter/inch margins; stored on worker documents; `Policy` with versions and acknowledgement tracking.
- **Gap #s:** 42, 43.
- **Business rules:** letters use worker's language; missing merge fields block generation with list; policy new version requires re-acknowledgement.
- **UI/UX:** template editor with merge-field picker and live preview; generate dialog; policy list with acknowledgement %.
- **Dependencies:** M-01, M-02, A-06, A-07.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| M-05-T01 | Wireframes: template editor, generate dialog, policy library | UX | — | Reviewed | Design review |
| M-05-T02 | `LetterTemplate` model (type, language, body with merge tags, version) + 5 seeded EN templates (FR keys) | DB | — | Seeded | Unit |
| M-05-T03 | Merge-field registry (worker, position, manager, salary, dates, org) with safe sandboxed rendering | BE | M-01, M-02 | Unknown tag rejected; no code execution | Unit + security |
| M-05-T04 | PDF render service (WeasyPrint, Letter, 0.75 in margins, org branding) | BE | A-10 | Snapshot matches | Snapshot |
| M-05-T05 | Generate endpoint: produce PDF, attach to worker documents, optional email (A-07) | API | T03, T04 | Letter appears in worker Documents tab | Integration |
| M-05-T06 | Missing-field check returns list before generation | BE | M-05-T03 | Missing salary → listed | Unit |
| M-05-T07 | `Policy` + `PolicyVersion` models; publish triggers acknowledgement requests | DB/BE | M-04-T08 | New version resets acknowledgement | Integration |
| M-05-T08 | Template editor UI with merge picker and live preview | FE | T02–T06 | Preview updates on typing | Playwright |
| M-05-T09 | Policy library UI (acknowledgement %, reminders) | FE | M-05-T07 | % accurate | Playwright |
| M-05-T10 | APIs + feature key `hr.documents`; sweep | API | — | Sweep passes | Sweep |
| M-05-T11 | i18n; FR template variants slots | FE | — | Gate passes | CI |
| M-05-T12 | Tests: generate letter with employee data (acceptance) | QA | — | PDF contains employee name/salary | pdfplumber |
| M-05-T13 | Docs | DOC | — | Merged | Review |

- **Acceptance:** letter generated from template with employee data; policy acknowledgements tracked.
- **Testing:** unit, snapshot, security (template injection), integration.
- **Risks:** template injection → sandboxed renderer, whitelisted tags.

### M-06 · Employee self-service (web)
- **Branch:** `feature/M-06-self-service`
- **Objective:** employees see and act on their own pay, slips, leave, claims and timesheets.
- **Current → Expected:** none → Employee role home with cards; stubs (N-05), slips (N-08), leave (M-03), expense claims (E-04), timesheets (J-02), profile (address, bank, TD1, emergency contact) with change requests where HR approval required.
- **Gap #s:** 51.
- **Business rules:** employee sees only records where `worker.user = request.user`; profile changes to bank/TD1 take effect from next unprocessed run; address change audited; terminated employees keep access to slips/stubs for configured period.
- **Edge cases:** employee in two orgs (org switcher); employee also a manager (manager views via normal roles); ID guessing on stub URLs → 404.
- **UI/UX:** mobile-first responsive cards; plain language; large touch targets; first-login tour.
- **Dependencies:** M-01, M-03, M-04, N-05, N-08, E-04, J-02, A-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| M-06-T01 | Wireframes (mobile-first): home cards, stubs list, stub view, leave, claims, timesheets, profile | UX | — | Reviewed | Design review |
| M-06-T02 | `SelfServiceScope` queryset mixin: worker-bound filtering for all self-service endpoints | BE | M-01 | Other worker's IDs → 404 | Unit |
| M-06-T03 | Self-service API namespace `/api/v1/me/` (pay-stubs, slips, leave, claims, timesheets, profile) | API | M-06-T02 | OpenAPI; only own data | Integration |
| M-06-T04 | Isolation sweep extension: every `/me/` endpoint tested with two employees in same org | QA | M-06-T03 | Sweep green | Security sweep |
| M-06-T05 | Profile change requests (bank/TD1 → HR approval optional per org; address immediate) | BE | M-04 | Change effective from next run | Integration |
| M-06-T06 | Home screen cards (Latest pay, Vacation balance, Documents, Submit claim, Timesheet) | FE | M-06-T03 | Loads < 1.5 s | Playwright |
| M-06-T07 | Pay stubs list + viewer + PDF download | FE | N-05 | Stub figures = register | Playwright |
| M-06-T08 | Slips list (T4/T4A/RL-1) | FE | N-08 | Only own slips | Playwright |
| M-06-T09 | Leave screens (reuse M-03 components) | FE | M-03 | Request submitted | Playwright |
| M-06-T10 | Claims and timesheets entry points (reuse E-04/J-02 components in employee scope) | FE | E-04, J-02 | Claim submitted with receipt photo | Playwright |
| M-06-T11 | First-login onboarding tour + invite acceptance | FE | A-02 | Tour dismissible, remembered | Playwright |
| M-06-T12 | i18n; employee language default | FE | — | Gate | CI |
| M-06-T13 | Usability test (5 employees, SUS ≥ 80) | UX | all | Metric met | Usability |
| M-06-T14 | Docs: employee guide | DOC | — | Merged | Review |

- **Acceptance:** employee sees only own records (sweep); stub, slip, leave, claim, timesheet flows work.
- **Testing:** security sweep, functional, usability.
- **Risks:** data exposure → dedicated namespace + sweep in CI.

### N-12 (prov.) · CRA default tables upload [v2.1]
*(Built first with N-01 because every calculation reads its data.)*
- **Branch:** `feature/N-12-cra-tables-upload`
- **Objective:** upload CRA/RQ payroll tables, rate sheets, constants and claim codes per tax year and edition; store them versioned; every calculation and every T4 box uses the edition in force.
- **Current → Expected:** none → `PayrollEdition` (jurisdiction set, tax year, edition name e.g. "T4127 July 2026", effective_from, status draft/validated/active/superseded, source file, checksum, uploaded_by) with child tables: federal brackets & rates (R, K), provincial brackets/rates/constants (V, KP, surtax, health premium, tax reductions, low-income reductions), basic personal amounts and indexation, CPP/CPP2/EI/QPP/QPP2/QPIP constants, claim-code table, Canada Employment Amount, K4/K4P, LCF, Ontario health premium table, etc. Template-driven upload (XLSX/CSV/JSON), row-level validation report, diff viewer vs previous edition, activation with effective date; platform-level editions (Platform Owner) with org-level override only by Platform Owner.
- **Business rules:** active editions never edited (new version instead); exactly one active edition per jurisdiction per date; switching edition recomputes **draft** runs only; posted runs show a "computed with edition X" stamp; activation audited; checksum prevents duplicate upload.
- **Edge cases:** missing province in file; overlapping effective dates; mid-year edition (July) with pay date 1 Jul; QC tables separate (TP-1015.F) — QC provincial tax fields required when QC employees exist.
- **UI/UX:** upload dropzone → validation report table (row, field, error) → diff (changed values highlighted) → choose effective date → activate; edition list with status chips.
- **Dependencies:** A-04, A-06, U-06 (platform console).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-12-T01 | Define Numo9 edition template (XLSX sheets: federal, provinces, statutory, claim_codes, metadata) + JSON schema; publish template download | DOC/BE | — | Template documented in `docs/payroll/edition-template.md` | Review |
| N-12-T02 | `PayrollEdition` model + status machine (draft→validated→active→superseded) | DB | — | Illegal transitions rejected | Unit |
| N-12-T03 | Child tables: `FederalBracket`, `ProvincialBracket`, `ProvincialConstant`, `StatutoryConstant` (CPP/CPP2/EI/QPP/QPP2/QPIP), `ClaimCode`, `MiscConstant` keyed by edition | DB | N-12-T02 | Migration; FK cascade on draft delete only | Unit |
| N-12-T04 | Parser (openpyxl/CSV/JSON) → pydantic rows with row-level errors | BE | N-12-T01 | Malformed file → error list with sheet/row/field | Unit |
| N-12-T05 | Semantic validators: brackets ascending & contiguous, rates 0–1, YMPE < YAMPE, max contribution = rate × (YMPE − exemption) within 0.01, all 13 jurisdictions present | BE | N-12-T04 | Wrong CPP max flagged | Unit |
| N-12-T06 | Checksum + duplicate-upload guard | BE | N-12-T02 | Same file twice → "already uploaded" | Unit |
| N-12-T07 | Diff service (edition vs previous active) | BE | N-12-T03 | Diff lists changed values only | Unit |
| N-12-T08 | Activation service: effective_from, no overlap, supersede previous, audit | BE | N-12-T02 | Two actives on same date impossible | Unit + property |
| N-12-T09 | Edition resolver `edition_for(jurisdiction, pay_date)` (cached) | BE | N-12-T08 | Pay date 17 Jul 2026 → July edition | Unit |
| N-12-T10 | Draft-run recompute job on activation (posted runs untouched; difference report available) | BE | N-02, N-04 | Draft recomputed; posted unchanged | Integration |
| N-12-T11 | `load_payroll_edition` management command (CI fixture loading) | OPS | N-12-T04..T08 | Loads Jan + Jul 2026 fixtures | Integration |
| N-12-T12 | Seed fixture editions: 2026 January and July (values from Plan §1.7 for CPP/EI/QPP/QPIP; T4127 brackets as confirmed) | QA | N-12-T11 | Fixture constants: YMPE 74,600; exemption 3,500; CPP 5.95 %; max 4,230.45; CPP2 4 % to YAMPE 85,000 max 416.00; EI MIE 68,900, 1.63 %, max 1,123.07, employer ×1.4, QC EI 1.30 %; QPP 6.3 % max 4,479.30, QPP2 4 %; QPIP 0.430 %/0.602 % to 103,000 | Fixture test |
| N-12-T13 | APIs: platform `/api/v1/platform/payroll-editions/` (upload, validate, diff, activate); org read-only `/payroll/editions/` | API | T02–T10 | Org users cannot upload (403); platform owner can | RBAC |
| N-12-T14 | Console UI: upload, validation report, diff viewer, activate dialog | FE | N-12-T13 | Flow < 2 min in test | Playwright |
| N-12-T15 | Org payroll settings: "Tables in use" panel (edition per jurisdiction, effective dates) | FE | N-12-T13 | Shows July edition after 1 Jul | Playwright |
| N-12-T16 | Acceptance test: switching edition re-computes fixtures correctly | QA | N-04 | Draft fixture run values match new edition expected | Fixture |
| N-12-T17 | ADR-005 "Payroll constants as versioned data" | DOC | — | ADR merged | Review |

- **Acceptance:** uploaded edition drives calculations; switching edition re-computes fixtures correctly; posted runs never change.
- **Testing:** unit (parser/validators), property (no overlap), integration (recompute), fixture.
- **Risks:** wrong data uploaded → semantic validators + diff review + two-person activation (uploader ≠ activator).

### N-01 · Constants by tax year
- **Branch:** `feature/N-01-constants-by-year`
- **Objective:** a single service exposing all statutory constants for a pay date, tax year and jurisdiction, backed by N-12 editions.
- **Current → Expected:** none → `PayrollConstants` value object returned by `constants_for(pay_date, province, quebec=bool)`; includes T4127 edition name; cached per edition; used by N-04, N-08, N-13.
- **Business rules:** tax year = pay date year (not work period); constants immutable within a run once calculated (snapshot stored on run).
- **Edge cases:** pay date 2 Jan for December work → new year constants and YTD reset; leap years irrelevant; QC both federal + RQ.
- **UI/UX:** read-only "Constants in use" panel with values and edition.
- **Dependencies:** N-12.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-01-T01 | `PayrollConstants` frozen dataclass (all fields typed Decimal) | BE | N-12-T03 | Instantiates from edition rows | Unit |
| N-01-T02 | `constants_for(pay_date, jurisdiction)` using edition resolver; cache keyed by edition id | BE | N-12-T09 | Pay date's tax year selects constants | Unit |
| N-01-T03 | Year-boundary rule tests (work in Dec, paid Jan → next year) | QA | N-01-T02 | Passes | Unit |
| N-01-T04 | Run-level constants snapshot (JSON with edition ids) stored at calculation | BE | N-02 | Snapshot present on calculated run | Integration |
| N-01-T05 | Cache invalidation on activation | BE | N-12-T08 | New edition visible immediately | Integration |
| N-01-T06 | API `/payroll/constants/?date=&province=` (feature `payroll.core`) | API | N-01-T02 | Returns values + edition | Integration |
| N-01-T07 | UI "Constants in use" panel in payroll settings and run review | FE | N-01-T06 | Displays edition and key values | Playwright |
| N-01-T08 | i18n + docs | FE/DOC | — | Gate | CI |

- **Acceptance:** constants selected by pay date's tax year.
- **Testing:** unit, integration.
- **Risks:** stale cache → invalidation tests.

### N-02 · Pay schedules & runs
- **Branch:** `feature/N-02-pay-schedules-runs`
- **Objective:** define pay frequencies and run the payroll lifecycle with approvals and single posting.
- **Current → Expected:** none → `PaySchedule` (weekly 52, bi-weekly 26, semi-monthly 24, monthly 12; anchor date; pay-date offset; holiday adjustment rule) generating `PayPeriod`s; `PayRun` (regular / off-cycle: bonus, termination, correction, reversal) with lifecycle **draft → calculated → submitted → approved → posted → paid** (+ voided via reversal run); approval limits per user (A-03); pre-flight checks; posting creates one `payroll` JE (C-03) respecting Payroll lock date; idempotent post.
- **Gap #s:** 40, 33, 29.
- **Business rules:** run cannot post twice (DB unique on run_id in JE source + idempotency key + row lock); preparer ≠ approver; approver limit ≥ run total (gross + employer cost); editing a calculated run marks it stale and requires recalculation; posting date = pay date; lock date respected; reversal run negates a posted run fully.
- **Edge cases:** pay date on a holiday → previous business day (configurable); 27 bi-weekly pay dates in a year (pay periods count per year used for annualisation stays 26 per T4127, flagged); employee joining mid-period (pro-rate); concurrent clicks on Post.
- **UI/UX:** 5-step wizard with summary rail; pre-flight checklist with fix links; stale banner inline (not modal); approval card shows limit.
- **Dependencies:** M-01, N-01, A-03, A-05, C-02, C-03, A-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-02-T01 | Figma prototype of 5-step pay-run wizard + summary rail + pre-flight | UX | — | Prototype tested with 2 users | Usability |
| N-02-T02 | `PaySchedule` model (frequency, periods/year, anchor, pay-date offset, holiday rule) | DB | — | CRUD | Unit |
| N-02-T03 | Period generator (dateutil rrule) incl. holiday adjustment and 27-period year detection | BE | N-02-T02, N-13-T02 | Bi-weekly 2026 periods correct; 27th flagged | Unit + property (no gaps/overlaps) |
| N-02-T04 | `PayRun` + `PayRunLine` (per worker) + `PayRunItem` (earning/deduction/benefit/statutory lines) models | DB | M-01 | Migration | Unit |
| N-02-T05 | Run state machine with transitions & guards (stale on edit, preparer≠approver) | BE | N-02-T04 | Illegal transitions rejected | Unit |
| N-02-T06 | Pre-flight checks service (TD1 missing, bank missing for DD, invalid SIN, terminated with hours, province change, negative net, missing GL mapping) | BE | M-01, M-04 | Each check returns code, message, fix URL | Unit |
| N-02-T07 | Run population: active workers on schedule, salaried amounts pro-rated by days for joiners/leavers | BE | N-02-T04 | Joiner mid-period paid pro-rata | Unit |
| N-02-T08 | Approval service using A-03 limits; routing to next approver when over limit; notifications | BE | A-03, A-07 | $20,000 limit routes $24,850.12 run | Integration |
| N-02-T09 | GL mapping settings (`PayrollGLMap`: gross wages expense by dept, each liability control account, net pay clearing/bank) | DB/BE | C-01 | Missing mapping blocks post with message | Unit |
| N-02-T10 | Posting service: build balanced `payroll` JE (lines per mapping, department tracking, employee contact), lock-date check, idempotency key, `select_for_update` | BE | C-02, C-03, N-02-T09 | Double post (2 parallel requests) → one JE | Concurrency test |
| N-02-T11 | Reversal run (full negation, linked) | BE | N-02-T10 | Reversal JE nets original to zero | Unit |
| N-02-T12 | Off-cycle run types (bonus, termination, correction) flagged for N-04 bonus method | BE | N-02-T04 | Off-cycle created without affecting regular period | Unit |
| N-02-T13 | APIs `/payroll/schedules/`, `/payroll/runs/` (+ `/calculate/`, `/submit/`, `/approve/`, `/post/`, `/reverse/`) feature `payroll.core` | API | T02–T12 | OpenAPI; sweep; 402 without Payroll | Integration + sweep |
| N-02-T14 | Schedules settings UI with period preview list | FE | N-02-T13 | Preview shows next 6 pay dates | Playwright |
| N-02-T15 | Wizard step 1 (period, pay date, pre-flight checklist with fix links) | FE | N-02-T13 | Blocking check disables Next with reason | Playwright |
| N-02-T16 | Wizard step 2 hours & earnings grid (virtualised, keyboard, changed-cell highlight, import timesheets J-02) | FE | N-02-T13, J-02 | Approved timesheet hours imported | Playwright |
| N-02-T17 | Wizard step 3 review: summary rail, variance panel (±15 %), per-employee breakdown | FE | N-04 | Variance flags shown | Playwright |
| N-02-T18 | Wizard steps 4–5 approve & post: limit indicator, typed confirmation, result card (JE, register, EFT, stubs links) | FE | N-02-T08, T10 | Post produces links; second post button disabled | Playwright |
| N-02-T19 | Pay-runs list (status chips, filters, saved views) + quick-create `Alt+P` | FE | N-02-T13 | Shortcut opens wizard | Playwright |
| N-02-T20 | i18n, audit hooks for every transition, docs | FE/BE/DOC | — | Audit rows per transition | Integration |

- **Acceptance:** run cannot post twice; approval limits enforced; lock date respected; JE balanced.
- **Testing:** unit, property (periods), concurrency, integration, functional, RBAC.
- **Risks:** double posting → DB uniqueness + idempotency; lock bypass → central posting service only.

### N-03 · Earnings, deductions & benefits (incl. taxable benefits [v2.1])
- **Branch:** `feature/N-03-earnings-deductions-benefits`
- **Objective:** configurable earning, deduction, benefit and employer-contribution types with correct tax treatment and T4 box/code mapping.
- **Current → Expected:** none → `PayItemType` with category (earning / pre-tax deduction / post-tax deduction / taxable benefit / non-taxable reimbursement / employer contribution), flags (taxable federal, taxable provincial, QC taxable, pensionable CPP/QPP, insurable EI, QPIP-insurable, vacationable), calculation (fixed, rate × hours, % of gross, formula from rate table), GL account, T4 box (14, 16, 16A, 17, 17A, 18, 20, 22, 24, 26, 44, 46, 52, 55, 56) and other-information code (30 housing, 34 automobile standby/operating, 40 other taxable allowances/benefits, 36 interest-free loans, 42 employment commissions, 57–62 if applicable, 66–69 retiring allowance, 71 status Indian exempt, 77 WC refund, 85 private health premiums, 87 emergency volunteer exemption…), RL-1 box mapping; seeded system types: regular, overtime 1.5×, double time, vacation pay, stat holiday pay, commission, bonus, retroactive pay, RRSP (pre-tax via payroll), union dues (box 44), charitable donations (box 46), group term life (code 40 / box 14 non-cash), automobile standby & operating (code 34), housing (code 30), allowances (code 40), employer EHT/WCB contributions. Worker-level assignments with effective dates.
- **Business rules:** non-cash taxable benefits increase taxable and (per CRA) pensionable income; non-cash benefits are **not** insurable for EI except where cash; group term life premiums taxable non-cash, pensionable not insurable; automobile standby charge & operating benefit computed from inputs (cost/lease, days available, personal km) per CRA formula data; union dues reduce tax (deductible); RRSP via payroll reduces taxable income at source; every type maps to exactly one T4 box/code or "not reported" explicitly.
- **Edge cases:** benefit with no cash pay in period (negative net risk → warn); QC benefits subject to QPIP/QPP differently; reimbursement not taxable.
- **UI/UX:** types grid with flags as icon chips; box/code picker with search and description; worker "Benefits" tab with effective-dated assignments; automobile benefit calculator modal.
- **Dependencies:** N-01, N-02, C-01.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-03-T01 | Wireframes: types grid, box/code picker, worker benefits tab, automobile calculator | UX | — | Reviewed | Design review |
| N-03-T02 | `PayItemType` model with category, flags, calc method, GL account, T4 box/code, RL-1 box | DB | — | Migration | Unit |
| N-03-T03 | `T4BoxCode` reference table seeded (boxes and other-information codes with descriptions, slip type T4/T4A/RL-1) | DB | — | Seeded; FR descriptions keys | Unit |
| N-03-T04 | Seed system item types (list above) with tax treatment flags | DB | N-03-T02 | Seeds load per org on payroll activation | Integration |
| N-03-T05 | Validation: each taxable benefit has box/code; flag combinations sane (e.g., reimbursement cannot be taxable) | BE | N-03-T02 | Invalid combo rejected | Unit |
| N-03-T06 | `WorkerPayItem` assignment (amount/rate, start/end dates, frequency) | DB | M-01 | Effective-dated | Unit |
| N-03-T07 | Item calculation service (fixed, hours × rate × multiplier, % of base) producing `PayRunItem`s | BE | N-02-T04 | OT 1.5× correct | Unit |
| N-03-T08 | Taxable-benefit service: adds to taxable/pensionable bases, not insurable for non-cash; QC variants | BE | N-03-T07 | Non-cash benefit increases tax & CPP, not EI | Unit (fixtures) |
| N-03-T09 | Automobile standby charge & operating benefit calculator (data-driven rates/km from edition MiscConstant) | BE | N-12-T03 | Fixture matches CRA example | Unit |
| N-03-T10 | Group term life, housing, allowances handlers | BE | N-03-T08 | Box/code assigned correctly | Unit |
| N-03-T11 | Employer contribution types (EHT, WCB/WSIB, RRSP match) with thresholds/rates data | BE | N-03-T02 | ON EHT exemption threshold honoured | Unit |
| N-03-T12 | APIs `/payroll/item-types/`, `/workers/{id}/pay-items/` feature `payroll.core` | API | T02–T11 | Sweep | Integration + sweep |
| N-03-T13 | Types grid UI + box/code picker | FE | N-03-T12 | Picker searchable by box and words | Playwright |
| N-03-T14 | Worker Benefits/Pay items tab + automobile calculator modal | FE | N-03-T12 | Calculator fills item amount | Playwright |
| N-03-T15 | Fixture set: one employee per benefit type → expected T4 boxes | QA | N-08 | Each benefit lands in correct box/code | Fixture |
| N-03-T16 | i18n + docs (benefit treatment table) | FE/DOC | — | Gate | CI |

- **Acceptance:** each benefit lands in the correct T4 box/code.
- **Testing:** unit, fixture, integration.
- **Risks:** treatment errors → treatment table reviewed by client accountant; fixtures per type.

### N-11 (prov.) · Worker-classification tool [v2.1]
- **Branch:** `feature/N-11-worker-classification`
- **Objective:** document whether a worker is an employee or self-employed contractor using CRA factors; drive source-deduction treatment.
- **Current → Expected:** none → `ClassificationAssessment` (worker, factor set version, answers per factor: control, tools & equipment, financial risk, opportunity for profit, integration, intention; evidence files; suggested outcome with rationale; final determination; determined_by; date; reason); determination stored on worker record; contractor → no CPP/EI/tax withholding, payments reported on T4A (box 048 fees for services) via AP or contractor runs; employee → full statutory treatment; reassessment history.
- **Business rules:** final determination always by a user (tool suggests, never decides); change of determination audited and effective from a date; contractor cannot be placed in a regular payroll run with statutory deductions; disclaimer (software, not legal advice — Agreement 15.1); factor set versioned (client confirms per 9.1(c)).
- **Edge cases:** mixed (employee who also invoices) → two worker roles disallowed, flag; Quebec additional criteria noted in guidance text; incomplete questionnaire.
- **UI/UX:** guided questionnaire, one factor per card with plain-language guidance and examples; scoring meter; determination card with "why" bullets; badge on worker list.
- **Dependencies:** M-01, N-02, N-04, B-01 (T4A flag).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-11-T01 | Wireframes: questionnaire, determination card, badge | UX | — | Reviewed | Design review |
| N-11-T02 | `ClassificationFactorSet` + `Factor` + `FactorQuestion` (versioned; seed CRA six factors) | DB | — | Seeded v1 | Unit |
| N-11-T03 | `ClassificationAssessment` + `FactorAnswer` + evidence attachments | DB | M-01, A-06 | Migration | Unit |
| N-11-T04 | Suggestion engine (weighted indicators per question → employee-leaning / contractor-leaning / inconclusive with rationale list) | BE | N-11-T02 | Fixture answers → expected suggestion | Unit |
| N-11-T05 | Determination service: user confirms, effective date, reason, audit; updates `worker.type` & treatment | BE | N-11-T04, A-04 | Determination stored and audited | Integration |
| N-11-T06 | Treatment enforcement: contractor excluded from statutory calc; regular run add blocked with message; T4A flag set on linked contact | BE | N-04, B-01 | Contractor classification removes CPP/EI/tax withholding | Unit + integration |
| N-11-T07 | Contractor payments path: payments via bill/AP or contractor run without deductions, mapped to T4A box 048 | BE | N-08 | Payment appears on T4A worksheet | Integration |
| N-11-T08 | APIs `/people/classifications/` feature `payroll.classification` | API | T03–T07 | Sweep | Integration + sweep |
| N-11-T09 | Questionnaire UI (factor cards, guidance, evidence upload, progress) | FE | N-11-T08 | Complete in < 4 min (usability) | Playwright |
| N-11-T10 | Determination card + history timeline + worker badge | FE | N-11-T08 | Badge visible on list | Playwright |
| N-11-T11 | Disclaimer and guidance copy (EN, FR keys) | UX/FE | — | Copy approved | Review |
| N-11-T12 | Tests: reclassify employee→contractor mid-year; YTD retained; next run excludes deductions | QA | all | Passes | Functional |
| N-11-T13 | Docs | DOC | — | Merged | Review |

- **Acceptance:** determination stored and audited; contractor classification removes CPP/EI/tax withholding.
- **Testing:** unit, integration, functional.
- **Risks:** perceived legal advice → wording + user-made determination.

### N-13 (prov.) · Vacation & statutory holiday pay [v2.1]
- **Branch:** `feature/N-13-vacation-stat-pay`
- **Objective:** compute vacation pay and statutory (public) holiday pay per provincial rules.
- **Current → Expected:** none → `StatHolidayCalendar` per jurisdiction per year (seeded, editable); `StatPayRule` per province (eligibility e.g. ON: worked last scheduled day before and first after; formula e.g. ON: regular wages + vacation pay in 4 weeks before ÷ 20; BC: average day's pay over 30 days, 15 of 30 days worked; AB: average daily wage, 5 of 9 weeks; QC: 1/20 of wages in 4 full weeks before; federal: 1/20 of wages in 4 weeks) as data; vacation pay methods: accrue % each period (paid when taken) or pay out each period (% on stub); vacation pay on termination; premium pay for working on a holiday (1.5× + substitute day/holiday pay per rule).
- **Business rules:** vacation % from M-03 rule (years of service); vacationable earnings flags from N-03; formulas are data with parameters, versioned per effective date; client confirms provincial rules.
- **Edge cases:** part-time eligibility; holiday falling on a non-working day (substitute day); employee on leave; mid-year province change.
- **UI/UX:** holiday calendar editor; per-run "Stat holidays in this period" panel with eligible employees and computed amounts; vacation method chosen at policy level with clear explanation.
- **Dependencies:** M-03, N-03, N-02, N-12.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-13-T01 | Wireframes: holiday calendar editor, run stat-holiday panel | UX | — | Reviewed | Design review |
| N-13-T02 | `StatHolidayCalendar` model + seed 2026–2027 for 13 jurisdictions + federal (holidays lib as source, editable) | DB | — | ON 2026 has 9 public holidays; editable | Unit |
| N-13-T03 | `StatPayRule` model (eligibility params, lookback window, divisor, premium multiplier) seeded ON, BC, AB, QC, NS, MB, SK, federal | DB | — | Seeds load | Unit |
| N-13-T04 | Eligibility evaluator (data-driven rules) | BE | N-13-T03, J-02 | ON fixture eligible/ineligible cases pass | Unit |
| N-13-T05 | Stat-pay calculator (lookback earnings ÷ divisor; average day's pay variants) | BE | N-13-T04 | Provincial fixtures match | Unit (fixtures) |
| N-13-T06 | Premium pay for hours worked on a holiday (multiplier + substitute day option) | BE | N-13-T05 | 8 h on Canada Day at 1.5× + holiday pay | Unit |
| N-13-T07 | Vacation pay accrual (% of vacationable earnings each period → M-03 balance in $) | BE | M-03, N-03 | Balance $ = % × vacationable earnings | Unit + property |
| N-13-T08 | Vacation pay payout modes: when taken / each period / on termination | BE | N-13-T07 | Termination pays remaining balance | Unit |
| N-13-T09 | Integration into run population (auto-add stat holiday and vacation items) | BE | N-02-T07 | Run with Labour Day shows stat pay lines | Integration |
| N-13-T10 | APIs + feature key `payroll.core`; sweep | API | — | Sweep | Sweep |
| N-13-T11 | Holiday calendar editor UI + run panel | FE | N-13-T10 | Panel lists eligible employees | Playwright |
| N-13-T12 | Provincial fixtures (ON, BC, AB, QC, NS, federal) for stat and vacation pay | QA | T05–T08 | All pass | Fixture |
| N-13-T13 | i18n + docs (rules table with sources, client confirmation) | FE/DOC | — | Gate | CI |

- **Acceptance:** matches provincial fixtures.
- **Testing:** unit + fixtures, property, integration.
- **Risks:** rule ambiguity → client confirmation recorded per province.

### N-04 · Statutory calculations
- **Branch:** `feature/N-04-statutory-calculations`
- **Objective:** compute CPP + CPP2, EI, QPP + QPP2, QPIP, federal and provincial income tax per T4127 Option 1 for every province/territory, with YTD maxima and a full calculation trace.
- **Current → Expected:** none → pure, deterministic `calculate_line(worker, period, items, ytd, constants) → CalcResult(trace)`; matches the CRA Payroll Deductions Online Calculator (PDOC) to the cent on 40 scenarios; "Explain this deduction" trace shown in UI.
- **Business rules (2026 fixture values, stored as data):** CPP 5.95 % employee/employer on pensionable earnings above pro-rated basic exemption (3,500 ÷ P) up to YMPE 74,600, YTD max 4,230.45; CPP2 4.00 % on earnings between YMPE 74,600 and YAMPE 85,000, max 416.00 each; EI 1.63 % on insurable earnings to MIE 68,900 (max 1,123.07), employer 1.4× (or reduced rate if org has rate-reduction number); QC: EI 1.30 %, QPP 6.3 % (max 4,479.30) + QPP2 4 %, QPIP employee 0.430 % / employer 0.602 % to 103,000; federal tax: annualise (A = P × (I − F − F2 − F5A − U1) − HD − F1), T3 = R×A − K − K1 − K2 − K3 − K4, LCF, T1, per-period tax = (T1 + T2)/P; provincial T2 with KP, K1P, K2P, K3P, K4P, surtax (ON), Ontario health premium, provincial tax reductions (ON S, BC S), low-income reductions; Quebec provincial tax per RQ TP-1015.F formula (Quebec abatement 16.5 % on federal); CPP enhancement deductions (F5/F5A, F5B for CPP2) per T4127; bonus/lump-sum method for off-cycle; rounding at final per-period amount to cents (ROUND_HALF_UP); YTD maxima across runs (incl. off-cycle) never exceeded; employer portions computed alongside.
- **Edge cases:** employee reaching maximum mid-run; age < 18 / ≥ 70 CPP exemption (and CPP opt-out election CPT30 for 65–70); CPP disability exemption; EI-exempt (owner with > 40 % shares) flag; multiple jurisdictions (province of employment change mid-year); 27-period years; negative taxable income → 0; non-periodic bonus tax; commission employees (TD1X) out of scope unless client asks (documented); Indian Act exempt income.
- **UI/UX:** Explain drawer showing each formula variable with value and edition; per-employee breakdown table; maxima reached badges.
- **Dependencies:** N-01, N-12, N-02, N-03, M-04 (TD1), N-11, N-13.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-04-T01 | Calculation architecture note: pure functions, input/output DTOs, trace object, rounding policy (ADR-006) | DOC | — | ADR merged | Review |
| N-04-T02 | Input DTO assembly: gross by base (taxable, pensionable, insurable, QPIP-insurable), period count P, TD1 claims, YTD per worker per tax year | BE | N-02, N-03, M-04 | DTO built from run line | Unit |
| N-04-T03 | YTD accumulator service (per worker, employer BN/RP, tax year; incl. posted & current-run lines) | BE | N-02-T10 | YTD = sum of posted lines | Unit + property |
| N-04-T04 | Calculation trace object (variable, value, formula ref, edition) | BE | N-04-T01 | Trace serialisable to JSON | Unit |
| N-04-T05 | CPP base contribution: pro-rated exemption (3,500/P), 5.95 %, YTD cap 4,230.45, age/election/disability exemptions | BE | N-04-T02..T04 | Fixture cases incl. cap mid-run | Unit (fixtures) |
| N-04-T06 | CPP2 contribution: 4 % on YTD earnings between YMPE and YAMPE, cap 416.00 | BE | N-04-T05 | Earnings crossing 74,600 mid-run split correctly | Unit + property |
| N-04-T07 | EI premium: 1.63 %, MIE 68,900 cap 1,123.07; EI-exempt flag; employer 1.4× or reduced-rate multiplier | BE | N-04-T02 | Fixtures pass; employer = 1.4 × employee | Unit |
| N-04-T08 | Quebec QPP + QPP2 (6.3 % / 4 %), QC EI 1.30 %, QPIP 0.430 % / 0.602 % to 103,000 | BE | N-04-T05..T07 | QC fixtures pass | Unit |
| N-04-T09 | Federal annual taxable income A (incl. F, F2, F5A, U1, HD, F1) | BE | N-04-T02 | Matches T4127 worked examples | Unit |
| N-04-T10 | Federal basic tax T3: R/K from brackets, K1 (TC × lowest rate), K2 (CPP/EI credits incl. enhancement split), K3, K4 (Canada employment amount) | BE | N-04-T09 | Matches examples | Unit |
| N-04-T11 | Federal T1 (incl. LCF, Quebec abatement for QC) and per-period federal tax | BE | N-04-T10 | Fixtures | Unit |
| N-04-T12 | Provincial engine generic part: T4 = V×A − KP − K1P − K2P − K3P − K4P per province (data) | BE | N-12 | Generic provinces (AB, SK, MB, NB, NL, PE, NS, NT, NU, YT) pass fixtures | Unit (fixtures) |
| N-04-T13 | Ontario specifics: surtax (V1), tax reduction (S), Ontario Health Premium (V2) | BE | N-04-T12 | ON fixtures pass | Unit |
| N-04-T14 | British Columbia specifics: tax reduction (S) | BE | N-04-T12 | BC fixtures pass | Unit |
| N-04-T15 | Other province specifics as data (MB, NS, NL, YT, PE low-income/surtax items per edition) | BE | N-04-T12 | Fixtures pass | Unit |
| N-04-T16 | Quebec provincial income tax (TP-1015.F formula, TP-1015.3 claims) | BE | N-12 | QC fixtures pass vs WinRAS/PDOC-equivalent | Unit |
| N-04-T17 | Bonus / lump-sum (non-periodic) method for off-cycle runs | BE | N-04-T11, T12 | Bonus fixture matches PDOC bonus calculation | Unit |
| N-04-T18 | Rounding & negative-tax floor; per-period amounts to cents ROUND_HALF_UP | BE | all | Property: no negative tax; totals stable | Property |
| N-04-T19 | Orchestrator `calculate_run(run)`: per-line calc in Celery chunk, constants snapshot, stale flag cleared, totals | BE | N-04-T05..T18 | 500-employee run < 30 s | k6/perf |
| N-04-T20 | Multi-jurisdiction handling (province change mid-year uses province on pay date; YTD per employer) | BE | M-01-T04 | Fixture with ON→BC move passes | Unit |
| N-04-T21 | **40-scenario CRA fixture set**: capture PDOC outputs (2026 Jan & Jul editions) for ON, BC, AB, QC, NS, MB, SK, NB, NL, PE, NT, NU, YT; weekly/bi-weekly/semi-monthly/monthly; low/mid/high incomes; CPP/EI max crossing; CPP2; bonus; TD1 non-default; benefits; QC | QA | — | 40 JSON fixtures with screenshots in `tests/fixtures/compliance/payroll/` | Fixture |
| N-04-T22 | `payroll_fixture_runner` command: run all fixtures, print diff table (expected vs actual per line), exit non-zero on any cent difference | OPS/QA | N-04-T21 | Runs in CI | CI |
| N-04-T23 | Property tests: net = gross − Σ deductions; YTD maxima never exceeded across random run sequences; employer EI = 1.4 × employee | QA | N-04-T19 | 1,000 examples pass | Hypothesis |
| N-04-T24 | API: `/payroll/runs/{id}/lines/{id}/explain/` returns trace | API | N-04-T04 | Trace returned; permission `payroll.run.view` | Integration |
| N-04-T25 | Explain drawer UI (variables, values, formula names, edition) | FE | N-04-T24 | Accountant identifies each line in < 2 min | Usability |
| N-04-T26 | Per-employee breakdown table + maxima badges in review step | FE | N-04-T19 | Badge "CPP max reached" shows | Playwright |
| N-04-T27 | i18n of trace labels; docs: calculation reference (formula ↔ code map) | FE/DOC | — | Gate; doc merged | CI |

- **Acceptance:** 40-scenario CRA fixture passes to the cent; multi-province run matches PDOC; CPP/CPP2/EI maxima respected.
- **Testing:** unit per formula, compliance fixtures, property, performance, regression on every PR.
- **Risks:** formula misread → worked examples from T4127 as unit tests + PDOC fixtures; July edition → effective-dated editions.

### N-05 · Stubs & register
- **Branch:** `feature/N-05-stubs-register`
- **Objective:** produce pay stubs per employee and a payroll register per run/period that equals the posted JE.
- **Current → Expected:** none → stub PDF (Letter, inch margins, EN/FR by employee language, org branding): employer name/address, employee, pay period, pay date, earnings (hours/rate/current/YTD), taxable benefits, deductions (CPP, CPP2, EI, QPP, QPIP, federal tax, provincial tax, other), employer contributions (optional), net pay, vacation balance, deposit masked account; email + self-service; payroll register report in K-01 engine (per employee rows, per item columns, totals, by department), exports PDF/XLSX/CSV.
- **Gap #s:** 43, 42, 29.
- **Business rules:** stub figures = calculated line; register totals = posted payroll JE per account; stubs generated only after post; re-issue keeps version history; masked bank digits only.
- **UI/UX:** stub viewer responsive; register with drill-down to employee line and JE.
- **Dependencies:** N-02, N-04, K-01, A-07.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-05-T01 | Stub layout design (Figma), mobile and print | UX | — | Approved | Design review |
| N-05-T02 | Stub data assembler (current + YTD per item, vacation balance) | BE | N-04 | Values = run line | Unit |
| N-05-T03 | Stub PDF template (WeasyPrint, EN/FR keys, Letter 0.75 in) | BE | N-05-T02 | Snapshot; pdfplumber reads correct net | Snapshot |
| N-05-T04 | Bulk generation job after post (Celery chord), storage in A-06, versioning | BE | N-02-T10 | 500 stubs < 2 min | Integration/perf |
| N-05-T05 | Stub email (employee language, org domain) + self-service availability | BE | A-07, M-06 | Email sent once per stub | Integration |
| N-05-T06 | Register report definition in K-01 (rows employees, columns items, totals, dept grouping) | BE | K-01 | Report renders | Integration |
| N-05-T07 | Register ↔ JE tie-out check (per GL account) run after post; failure raises alert | BE | N-02-T10 | Register totals = posted payroll JE | Integration + property |
| N-05-T08 | APIs `/payroll/runs/{id}/stubs/`, `/payroll/reports/register/` | API | — | Sweep; employee scope via M-06 | Sweep |
| N-05-T09 | Stub viewer UI + register UI with drill-down | FE | N-05-T08 | Drill to JE works | Playwright |
| N-05-T10 | Re-issue stub (after correction) with version stamp | BE/FE | N-05-T04 | v2 shown, v1 retained | Integration |
| N-05-T11 | i18n + docs | FE/DOC | — | Gate | CI |

- **Acceptance:** register totals = posted payroll JE.
- **Testing:** unit, snapshot, integration, property, perf.
- **Risks:** rounding drift → single calculation source; tie-out check.

### N-06 · Direct-deposit EFT file (CPA 005)
- **Branch:** `feature/N-06-cpa005-eft`
- **Objective:** generate a CPA Standard 005 file for net pay direct deposits.
- **Current → Expected:** none → `cpa005` builder: header record "A" (originator ID, file creation number, creation date Julian 0YYDDD, destination data centre, currency), detail records "C" (credit) with up to 6 segments per 1464-byte record (transaction type 200 payroll, amount in cents, due date, institution/transit/account, payee name, originator short/long name, cross-reference, return account), trailer "Z" (totals and counts); file creation number sequence per org/bank; download and mark "file generated"; reuse for E-06 batch payments (shared builder).
- **Business rules:** only workers with verified bank details and pay method DD; file total = Σ net pay DD; creation number unique & incrementing; bank details decrypted only inside builder; file stored encrypted; generation audited.
- **Edge cases:** employee with split deposit (two accounts by % / fixed) — supported if client wants (default single); payee names with accents (transliterate to bank character set); amount > 10 digits rejected.
- **UI/UX:** step 5 "Download direct-deposit file" with bank selector and summary (count, total, due date); dev decoder page.
- **Dependencies:** N-02, N-05, M-04-T07, F-01.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-06-T01 | Collect CPA 005 spec + bank-specific variants (originator ID, data centre codes) into `docs/payments/cpa005.md` | DOC | — | Spec documented | Review |
| N-06-T02 | `EFTOriginator` settings model (bank, originator ID, short/long name, data centre, return account) — encrypted | DB | — | CRUD | Unit |
| N-06-T03 | Record builders A/C/Z with fixed-width padding, Julian dates, cents | BE | N-06-T01 | Byte-exact vs reference sample | Unit (golden files) |
| N-06-T04 | Segmentation (6 detail segments per C record) | BE | N-06-T03 | 13 payees → 3 C records | Unit |
| N-06-T05 | Character transliteration & validation (field lengths, numeric fields) | BE | N-06-T03 | Accented names transliterated | Unit |
| N-06-T06 | File creation number sequence (per org/originator, locked increment) | BE | N-06-T02 | Concurrent generations get distinct numbers | Concurrency |
| N-06-T07 | Validator (re-parse file, check totals/counts/lengths) | BE | N-06-T03 | File validates | Unit |
| N-06-T08 | Run integration: build from posted run net-pay DD lines; store encrypted; audit | BE | N-02-T10 | Total = Σ net DD | Integration |
| N-06-T09 | API `/payroll/runs/{id}/eft-file/` + permission `payroll.eft.generate` | API | N-06-T08 | Sweep; RBAC | Integration |
| N-06-T10 | UI in wizard step 5 + dev decoder page | FE | N-06-T09 | Download works; decoder shows rows | Playwright |
| N-06-T11 | Expose builder as shared service for E-06 | BE | N-06-T03 | E-06 tests reuse builder | Integration |
| N-06-T12 | Docs + i18n | DOC/FE | — | Gate | CI |

- **Acceptance:** file validates.
- **Testing:** golden files, unit, concurrency, integration.
- **Risks:** bank variants → configurable originator settings; client bank test file.

### N-07 · Remittances
- **Branch:** `feature/N-07-remittances`
- **Objective:** compute source-deduction remittances per RP account and due date, by remitter type, ready for payment from the system (G-09, Phase 4).
- **Current → Expected:** none → `RemitterProfile` (RP account from A-05/G-06, remitter type: quarterly, regular, accelerated threshold 1, accelerated threshold 2; AMWA reference; effective dates) and `Remittance` (period, due date, amounts: CPP employee+employer, CPP2, EI employee+employer, federal + provincial tax; QC: RQ separate — QPP, QPIP, QC tax, HSF/CNESST where configured; status: open → due → paid/overdue); due-date rules as data (regular: 15th of following month; quarterly: 15th after quarter; accelerated T1: 25th for 1–15 and 10th for 16–end; T2: 3 working days after end of period 7th/14th/21st/end); PD7A-style summary (gross payroll, number of employees, remittance amount); reminders; "mark paid" hook for G-09 (and manual record payment until Phase 4).
- **Business rules:** remittance amount = Σ liability postings for runs with pay date in period; due date by pay date; posting on payment Dr liabilities / Cr bank; paid only after G-09 confirmation (or manual with reference, audited).
- **Edge cases:** off-cycle run in a closed remittance period → adds to that period, recalculated with flag; due date on weekend/holiday → next business day per CRA; remitter type change on 1 Jan.
- **UI/UX:** calendar + list; status chips with icons; PD7A summary card; "Pay now" button disabled with "available when tax payments are enabled (Phase 4)" — explicit, not hidden.
- **Dependencies:** N-02, N-04, A-05, G-06, A-07, A-08.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-07-T01 | Wireframes: remittance calendar, PD7A summary card | UX | — | Reviewed | Design review |
| N-07-T02 | `RemitterProfile` model (RP account, type, effective dates) | DB | A-05 | CRUD; one active per date | Unit |
| N-07-T03 | `RemittanceRule` data (period boundaries, due-day rules per type) seeded | DB | — | Seeds | Unit |
| N-07-T04 | Period/due-date generator per remitter type incl. business-day adjustment (N-13 calendar + federal holidays) | BE | N-07-T03 | Accelerated T1 fixtures correct | Unit + property |
| N-07-T05 | `Remittance` model + aggregation from posted runs by pay date | BE | N-02-T10 | Amount = Σ liabilities | Integration |
| N-07-T06 | Quebec RQ remittance split (QPP, QPIP, QC tax, HSF) | BE | N-04-T08 | RQ amounts separate | Unit |
| N-07-T07 | PD7A-style summary (gross, employees, amount by component) | BE | N-07-T05 | PD7A-style summary correct on fixture | Unit |
| N-07-T08 | Status machine + overdue job + reminders (7/3/1 days) | BE | A-08, A-07 | Reminder sent once per threshold | Integration |
| N-07-T09 | Payment hook `mark_paid(remittance, confirmation, bank_account)` posting Dr liabilities / Cr bank; idempotent (for G-09) | BE | C-02 | Second call no-op | Unit + idempotency |
| N-07-T10 | Manual record-payment flow (reference, date, bank) until G-09 | BE/FE | N-07-T09 | Status paid; JE posted | Integration |
| N-07-T11 | Calendar feed to O-04/V-04 deadlines (event emitted) | BE | — | Event published | Integration |
| N-07-T12 | APIs `/payroll/remittances/` feature `payroll.core` | API | — | Sweep | Sweep |
| N-07-T13 | Calendar + list + PD7A card UI; explicit "Pay from Numo9 — available in Tax payments" state | FE | N-07-T12 | Disabled state explains | Playwright |
| N-07-T14 | i18n + docs | FE/DOC | — | Gate | CI |

- **Acceptance:** PD7A-style summary correct; marked paid after G-09 confirmation (hook tested with stub now).
- **Testing:** unit, property (due dates), integration, idempotency.
- **Risks:** due-date rule errors → fixture per remitter type.

### N-08 · Year-end slips (T4, T4A, T5, RL-1 + Summaries)
- **Branch:** `feature/N-08-year-end-slips`
- **Objective:** produce T4/T4 Summary, T4A/T4A Summary, T5/T5 Summary as CRA e-file XML validated against the CRA schema, RL-1 export, and PDFs for employees.
- **Current → Expected:** none → `SlipYear` (org, tax year, status: open → reviewed → generated → amended), slip generators: **T4** from payroll YTD (boxes 14, 16, 16A, 17, 17A, 18, 20, 22, 24, 26, 28 exemptions, 29 employment code, 44, 46, 50, 52, 55, 56, other info codes from N-03); **T4A** from contractor payments (box 048) and other payments (pension 016, lump-sum 018, etc. as configured) via N-11/B-01 flags; **T5** from dividend (eligible box 24/25/26, other than eligible 10/11/12) and interest (box 13) payments recorded in ledger accounts flagged or entered on a T5 worksheet; Summaries with totals, remittances made, difference; amended slips (code A) and cancelled (C); XML per CRA T619 transmitter + return structure; XSD validation (lxml/xmlschema with CRA XSD for the year); RL-1 data export per RQ specification (boxes A, B, B-1, C, D, E, G, H, I, J, …); readiness review (PIER-style CPP/EI over/under deduction check); employee slip PDFs in self-service.
- **Business rules:** due last day of February (calendar reminder); e-file required > 5 slips (UI notes; Numo9 provides XML, client files); T4 box 14 = Σ taxable employment income incl. taxable benefits; box 24 insurable ≤ MIE; box 26 pensionable ≤ YMPE; box 16A CPP2 and 17A QPP2 separate; slip totals = Summary; Summary deductions vs remittances difference shown; SIN required (blank invalid SIN rules per CRA → warn); transmitter number (MM…) captured in settings.
- **Edge cases:** employee in two provinces (one slip per province of employment); QC employees get T4 (federal part) + RL-1; employees with no SIN; corrections after filing → amended XML; zero-amount slips not issued.
- **UI/UX:** Year-end hub with readiness cards (ready / needs attention with fix links), validation result list, download XML + PDFs, "issue to employees" action; amendment flow.
- **Dependencies:** N-03, N-04, N-07, N-11, M-01, B-01, C-01 (dividend/interest accounts).

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-08-T01 | Wireframes: year-end hub, readiness cards, slip review grid, amendment flow | UX | — | Reviewed | Design review |
| N-08-T02 | Obtain CRA XSD bundle for tax year (T619, T4, T4A, T5, Summaries) into `backend/payroll/xsd/2026/` + version manifest | OPS/DOC | — | XSDs load in xmlschema | Unit |
| N-08-T03 | `SlipYear`, `Slip` (type, box values JSON, status original/amended/cancelled), `SlipSummary` models | DB | — | Migration | Unit |
| N-08-T04 | Transmitter settings (transmitter number, type, contact) on org payroll settings | DB/FE | — | Saved | Unit |
| N-08-T05 | T4 box aggregator from posted payroll lines and N-03 box mapping (one slip per worker per province of employment) | BE | N-03, N-04 | Fixture employee boxes correct | Unit (fixtures) |
| N-08-T06 | T4 caps & consistency checks (box 24 ≤ MIE, 26 ≤ YMPE, 16/16A/17/17A/18 vs rates) | BE | N-08-T05 | Violations listed | Unit |
| N-08-T07 | PIER-style review: expected vs deducted CPP/CPP2/EI per employee, shortfall report | BE | N-08-T05 | Shortfall fixture detected | Unit |
| N-08-T08 | T4 Summary (totals, remittances from N-07, difference) | BE | N-07 | Summary = Σ slips | Unit + property |
| N-08-T09 | T4A aggregator (box 048 fees from contractor payments/bills flagged T4A; other configured boxes) | BE | N-11, B-01, E-02 | Contractor fixture → T4A 048 | Unit |
| N-08-T10 | T4A Summary | BE | N-08-T09 | Totals tie | Unit |
| N-08-T11 | T5 worksheet: dividends/interest from flagged ledger accounts + manual recipients (SIN/BN, recipient type) | BE/FE | C-01 | Worksheet lists payments | Integration |
| N-08-T12 | T5 box mapping (eligible dividends 24/25/26, other 10/11/12 with gross-up/credit rates from edition data, interest 13) | BE | N-08-T11, N-12 | Fixture boxes correct | Unit |
| N-08-T13 | T5 Summary | BE | N-08-T12 | Totals tie | Unit |
| N-08-T14 | XML writer (lxml) for T619 + T4/T4A/T5 returns incl. Summaries; amended/cancelled report type codes | BE | T05–T13 | XML generated | Unit |
| N-08-T15 | XSD validation service + `validate_slips <year>` command; errors mapped to slip/box with human message | BE/OPS | N-08-T02, T14 | **T4, T4A, T5 XML validate against CRA schema** | Integration (CI) |
| N-08-T16 | RL-1 data export (box mapping from N-03 RL fields; RQ file layout as data) | BE | N-04-T08 | Export contains all QC employees with boxes | Unit |
| N-08-T17 | Slip PDFs (employee copies) EN/FR keys, Letter | BE | N-08-T05 | Snapshot | Snapshot |
| N-08-T18 | Issue to employees (self-service + email) and lock SlipYear "generated" | BE | M-06 | Employee sees own slip only | Sweep |
| N-08-T19 | Amendment flow: change after generation → amended slip, new XML with amendment code, history | BE | N-08-T14 | Amended XML validates | Integration |
| N-08-T20 | APIs `/payroll/year-end/{year}/…` feature `payroll.yearend` | API | — | Sweep | Sweep |
| N-08-T21 | Year-end hub UI: readiness cards, review grids (T4/T4A/T5), validation results, downloads | FE | N-08-T20 | Flow < 10 min for 50 employees | Playwright |
| N-08-T22 | Due-date reminder (last day of February) + "> 5 slips: e-file required" notice | BE/FE | A-07 | Reminder scheduled | Integration |
| N-08-T23 | Fixtures: 10 employees (ON/QC/BC, benefits, max crossings), 3 contractors, 3 T5 recipients | QA | — | Fixtures committed | Fixture |
| N-08-T24 | Sheets template "T4 Summary vs GL reconciliation" (L-03) | BE | L-03 | Ties to GL on fixture | Integration |
| N-08-T25 | i18n + docs (year-end guide) | FE/DOC | — | Gate | CI |

- **Acceptance:** T4, T4A, T5 XML validate against CRA schema; RL-1 export complete; slip totals = Summary.
- **Testing:** unit, fixture, XSD validation in CI, snapshot, security sweep.
- **Risks:** schema changes yearly → versioned XSD manifest; warranty quarterly update.

### N-09 · ROE data
- **Branch:** `feature/N-09-roe-data`
- **Objective:** prepare Record of Employment data for ROE Web (export), complete for terminations and interruptions.
- **Current → Expected:** none → `ROE` (worker, reason code A–Z/K etc. from Service Canada list as data, first day worked, last day for which paid, final pay period ending date, pay period type, insurable hours block 15A, insurable earnings by pay period block 15B/15C per pay-period-type rules (e.g., last 27 periods bi-weekly), vacation pay block 17A, statutory holiday pay 17B, other monies 17C, expected recall, comments); auto-filled from payroll history; validation; export (XML per ROE Web bulk-upload layout as data, plus printable summary); serial tracking of submitted ROE numbers (entered by user).
- **Business rules:** created when termination/leave ≥ 7 days without pay; due within 5 calendar days after interruption or pay period end (reminder); amended ROE supported.
- **Edge cases:** employees with multiple pay schedules in lookback; zero-earnings periods; QC.
- **UI/UX:** form prefilled block by block; validation per block; export button.
- **Dependencies:** M-04 offboarding, N-02, N-04, N-13.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-09-T01 | Document ROE block requirements and reason codes as data (`docs/payroll/roe.md`) | DOC | — | Documented | Review |
| N-09-T02 | `ROE` model + reason code table | DB | — | Migration, seeds | Unit |
| N-09-T03 | Auto-fill service: dates, insurable hours & earnings per period for required lookback by pay-period type | BE | N-04-T03 | Fixture terminations correct | Unit (fixtures) |
| N-09-T04 | Block 17 (vacation, stat holiday, other monies) from final pay | BE | N-13 | Values match final run | Unit |
| N-09-T05 | Validation rules per block | BE | N-09-T03 | Incomplete → errors listed | Unit |
| N-09-T06 | Export (ROE Web bulk XML layout as data) + printable summary PDF | BE | N-09-T05 | Export produced | Integration |
| N-09-T07 | Reminder 5 days after interruption; amended ROE | BE | A-07 | Reminder sent | Integration |
| N-09-T08 | APIs + feature `payroll.yearend`; sweep | API | — | Sweep | Sweep |
| N-09-T09 | ROE form UI (prefilled blocks, validation chips) | FE | N-09-T08 | Usable from offboarding wizard | Playwright |
| N-09-T10 | Fixtures: 5 terminations (bi-weekly, weekly, semi-monthly, QC, rehire) | QA | — | Fields complete for fixture terminations | Fixture |
| N-09-T11 | i18n + docs | FE/DOC | — | Gate | CI |

- **Acceptance:** fields complete for fixture terminations.
- **Testing:** unit, fixtures, integration.
- **Risks:** layout changes → data-driven layout.

### N-10 · Payroll by the practice inside client orgs
- **Branch:** `feature/N-10-practice-payroll`
- **Objective:** a practice Payroll Specialist runs payroll for organisations assigned to them, with access strictly limited to those orgs.
- **Current → Expected:** none → practice role "Payroll Specialist" gets payroll permissions inside assigned orgs only (A-01 `PracticeAssignment` with role); practice dashboard tile "Payroll due" across assigned orgs (V-04); org owner remains approver unless delegated; all actions attributed "on behalf of practice X".
- **Business rules:** unassignment revokes within one request (A-01 sweep); specialist cannot see SIN unless org grants `payroll.sin.view` to practice role; org-level approval limits apply to specialist.
- **UI/UX:** practice "Payroll" view listing assigned orgs with next pay date, status, run button opening the org's wizard; banner-free org context header showing which org is active.
- **Dependencies:** A-01, A-03, V-04, N-02.

| Task ID | Atomic task | Layer | Depends | Acceptance | Test |
|---|---|---|---|---|---|
| N-10-T01 | Wireframe: practice payroll overview | UX | — | Reviewed | Design review |
| N-10-T02 | Map practice role Payroll Specialist → org payroll permission set (configurable per org) | BE | A-03 | Permissions resolved via assignment | Unit |
| N-10-T03 | Cross-org query for "payroll due" over assigned orgs only | BE | A-01 | Unassigned org never appears | Unit + property |
| N-10-T04 | "On behalf of practice" attribution in audit and approvals | BE | A-04 | Audit shows practice name | Integration |
| N-10-T05 | API `/practice/payroll/overview/` | API | N-10-T03 | Sweep (practice) | Sweep |
| N-10-T06 | Practice payroll overview UI + launch org wizard | FE | N-10-T05 | Opens correct org context | Playwright |
| N-10-T07 | V-04 dashboard tile "Payroll due / remittances due" | FE | V-04, N-07 | Drill-down lists orgs | Playwright |
| N-10-T08 | Security tests: assignment revoked → 404 on every payroll endpoint of that org | QA | A-01 sweep | Access limited to assigned orgs | Security sweep |
| N-10-T09 | Docs + i18n | DOC/FE | — | Gate | CI |

- **Acceptance:** access limited to assigned orgs (A-01 sweep).
- **Testing:** security sweep, property, functional.
- **Risks:** leak via cached permissions → cache keyed by assignment version.

---

## 7. TEST — Phase 3 test plan (Rules 5–6)

### 7.1 Test matrix

| Category | Scope | Tooling | Target |
|---|---|---|---|
| Unit | Validators (SIN, TD1), state machines (run, leave, classification, edition), every T4127 formula step, CPP/CPP2/EI/QPP/QPIP, stat/vacation pay, CPA 005 records, slip aggregators | pytest, Hypothesis | ≥ 85 % coverage on `payroll`, `hr` |
| Integration | API ↔ DB ↔ posting engine; Celery jobs; PDF/XML generation; email; storage | pytest + DRF client, MinIO, mailpit | Happy + failure path per endpoint |
| Functional (E2E) | Add employee → run payroll → post → stub → EFT → remittance; classification; leave → vacation pay; year-end T4; self-service | Playwright | One script per deliverable |
| Regression | Full suite per PR; nightly with 500-employee fixture org | GitHub Actions | 0 regressions |
| Data validation | Register = JE; remittance = Σ liabilities; T4 Summary = Σ slips = GL YTD; leave balance = Σ entries | Reconciliation scripts | 100 % tie-out |
| Security | Tenant sweep incl. `/me/` and practice paths; RBAC matrix (prepare/approve/view SIN/EFT); log scrubbing; encryption at rest; ZAP | Custom sweeps, semgrep, ZAP | No high findings |
| Performance | 500-employee calculation < 30 s; stubs 500 < 2 min; employee list 1,000 < 1 s | k6, pytest-benchmark | Met on staging |
| Compliance fixtures | 40 PDOC scenarios; provincial leave/vacation/stat fixtures; benefit → T4 box fixtures; T4/T4A/T5 XSD; CPA 005 golden files; ROE fixtures | `tests/fixtures/compliance/payroll` | 100 % pass |
| Localisation | Missing-key gate; pseudo-locale on wizard/stub; Canadian-term lint | CI, Playwright | 0 missing; no clipping |
| Accessibility | axe-core on all Phase 3 routes; keyboard-only wizard | axe, Playwright | 0 serious |
| Gap closure | gap-29, 31, 33, 37, 40, 42, 43, 51, 52 | Playwright + pytest tags | All observed |

### 7.2 Compliance fixtures
- `pdoc_2026_jan_*.json` and `pdoc_2026_jul_*.json` (40 scenarios total) — inputs (province, frequency, gross, TD1, YTD, benefits) and expected per-line amounts captured from CRA PDOC with screenshot evidence.
- Edition switch fixture: same scenario under Jan vs Jul edition (expected both).
- Provincial vacation/stat fixtures: ON, BC, AB, QC, NS, MB, SK, federal.
- Year-end: 10 employees + 3 contractors + 3 T5 recipients with expected boxes.
- CPA 005 golden file; ROE 5 terminations.

### 7.3 Failure handling
Stop dependent tasks on failure → identify the exact failing fixture line → classify (code / data edition / config / assumption) → one focused fix → rerun fixture runner and full regression → continue only when acceptance met. Never skip a compliance fixture; if PDOC values cannot be captured (site unavailable), report the scenario as **not verified**.

### 7.4 Exit demonstration script (staging)
1. Platform Owner uploads the 2026 July edition file → validation report clean → diff shown → activated effective 1 Jul 2026. *Expected:* edition active; draft runs recomputed.
2. In a demo org, add employees in ON, BC, AB, QC and NS (one each), plus one contractor classified via N-11. *Expected:* contractor badge; no statutory deductions for contractor.
3. Create a bi-weekly run with pay date in July; pre-flight green; import timesheet hours for the hourly employee; calculate. *Expected:* each employee's CPP/CPP2/EI (QPP/QPIP/QC EI for QC) and federal + provincial tax equal the PDOC values to the cent (comparison table shown from fixture runner).
4. Show a high earner crossing YMPE: CPP stops at 4,230.45 YTD, CPP2 applied between 74,600 and 85,000. *Expected:* badges and amounts correct.
5. Submit → approver over limit routing → approve → post. *Expected:* one balanced payroll JE; second post refused; register totals = JE.
6. Download CPA 005 file → validator passes.
7. Open remittance calendar → PD7A-style summary correct; manual record-payment hook ready for G-09.
8. Employee logs into self-service → sees only own stub; another employee's stub ID → 404.
9. Generate year-end for fixture year → T4, T4A and T5 XML validate against CRA XSD; RL-1 export for QC employee; ROE data complete for a terminated fixture employee.

---

## 8. IMPROVE — post-verification review checklist (Rule 8)

- **Correctness:** all fixtures green; tie-outs (register = JE, remittance = liabilities, slips = GL) green.
- **Readability:** formula code mirrors T4127 variable names with docstrings citing section; trace labels readable.
- **Maintainability:** constants only in editions; no magic numbers (semgrep rule banning numeric literals like `0.0595` in `payroll/`).
- **Performance budgets:** calc 500 employees < 30 s; explain endpoint < 300 ms; stub PDF < 250 ms each; employee list < 1 s; self-service home < 1.5 s.
- **Reliability:** idempotent post and payment hooks; Celery retries with backoff; partial stub-generation failures retried, never lost.
- **Security:** SIN/bank scrub verified; key rotation tested; reveal audit; sweep green.
- **Consistency:** design-system components only; Canadian terms lint; EN/FR keys present.
- **UX review:** usability metrics met (§3.6); empty/error states reviewed; microcopy reviewed by client accountant.
- Re-run full regression after any improvement.

---

## 9. Git branch plan (Rule 7)

| # | Branch | Base | Deliverable | Merge order |
|---|---|---|---|---|
| 1 | `feature/M-01-worker-master` | main | M-01 | 1 |
| 2 | `feature/N-12-cra-tables-upload` | main | N-12 | 1 (parallel) |
| 3 | `feature/N-01-constants-by-year` | main (after N-12) | N-01 | 2 |
| 4 | `feature/M-02-org-structure` | main (after M-01) | M-02 | 2 |
| 5 | `feature/N-02-pay-schedules-runs` | main | N-02 | 3 |
| 6 | `feature/N-11-worker-classification` | main | N-11 | 3 |
| 7 | `feature/M-03-leave` | main | M-03 | 3 |
| 8 | `feature/N-03-earnings-deductions-benefits` | main | N-03 | 4 |
| 9 | `feature/M-04-on-offboarding` | main | M-04 | 4 |
| 10 | `feature/N-13-vacation-stat-pay` | main | N-13 | 5 |
| 11 | `feature/N-04-statutory-calculations` | main | N-04 | 5 |
| 12 | `feature/M-05-hr-documents` | main | M-05 | 5 |
| 13 | `feature/N-05-stubs-register` | main | N-05 | 6 |
| 14 | `feature/N-06-cpa005-eft` | main | N-06 | 7 |
| 15 | `feature/N-07-remittances` | main | N-07 | 7 |
| 16 | `feature/N-08-year-end-slips` | main | N-08 | 8 |
| 17 | `feature/N-09-roe-data` | main | N-09 | 8 |
| 18 | `feature/N-10-practice-payroll` | main | N-10 | 9 |
| 19 | `feature/M-06-self-service` | main | M-06 | 9 |

**Before each branch:** `git status` clean, pull `main`, restate objective + acceptance in PR description, list dependencies merged.
**Before declaring complete:** acceptance observed; CI green (isolation sweep, i18n gate, compliance fixtures, XSD validation, semgrep SIN rule); no unrelated changes; no debug code; no secrets or real SINs in fixtures (use CRA-valid test SINs generated by Faker); docs updated; second-engineer review. No merge to `main` without project-lead authorisation.

---

## 10. Phase risks register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Payroll calculation errors | Medium | High | 40 PDOC fixtures per edition; formula unit tests from T4127 examples; parallel run in Phase 5 |
| 2 | Late or wrong CRA tables from client | Medium | High | GMA loads published editions if client confirms; semantic validators; two-person activation |
| 3 | July edition mid-year handling | Medium | Medium | Effective-dated editions; edition-switch fixture |
| 4 | SIN/bank data leak | Low | Critical | Field encryption, masking, scrubbers, semgrep, sweep, reveal audit |
| 5 | Double posting / double payment | Low | High | DB uniqueness, idempotency keys, row locks |
| 6 | Wrong benefit T4 mapping | Medium | Medium | Mapping table reviewed by client accountant; fixture per type |
| 7 | XSD/RL-1/ROE layout changes | Medium | Medium | Versioned XSD/layout data; warranty quarterly updates |
| 8 | Provincial rule ambiguity (vacation/stat) | Medium | Medium | Data-driven rules confirmed by client |
| 9 | Worker classification perceived as legal advice | Low | Medium | User makes determination; disclaimer (Agreement 15.1) |
| 10 | Schedule pressure (20 deliverables in 2 weeks) | High | High | Parallel tracks per §5.3; skeleton first (ON salaried) then provinces; QC as separate task block |
| 11 | Practice access leak | Low | High | Assignment-versioned permission cache; sweep |
| 12 | Bank rejects CPA 005 | Medium | Medium | Golden files; client bank test file before go-live |

---

## 11. Phase completion checklist (Rule 11) & reporting template (Rule 10)

### 11.1 Mandatory execution checklist (per deliverable and for the phase)

**UNDERSTAND**
- [ ] Investigated existing implementation (A, B, C, F, G, J, E-04, L outputs)
- [ ] Identified users and outcomes (payroll officer, approver, HR, employee, practice specialist, platform owner)
- [ ] Defined inputs/outputs (§1.2)
- [ ] Identified business rules (statutory, permissions, posting)
- [ ] Considered edge cases (max crossings, year boundary, QC, multi-province, terminations)
- [ ] Restated objective (§1.3)

**PLAN**
- [ ] Decomposed into atomic tasks (§6)
- [ ] Identified dependencies (§5.3)
- [ ] Ordered tasks logically
- [ ] Defined acceptance criteria per deliverable
- [ ] Defined testing procedures (§7)

**BUILD**
- [ ] Smallest working piece first (ON salaried skeleton)
- [ ] Followed existing architecture (posting engine, entitlements, design system)
- [ ] Avoided unnecessary changes
- [ ] Preserved existing functionality
- [ ] Declared feature keys (`hr.core`, `hr.leave`, `hr.documents`, `payroll.core`, `payroll.classification`, `payroll.yearend`) and i18n keys

**TEST**
- [ ] 40-scenario CRA fixture passes
- [ ] Provincial fixtures pass
- [ ] XSD validation passes (T4, T4A, T5)
- [ ] CPA 005 validates
- [ ] Tie-outs green
- [ ] Tenant/self-service/practice sweeps green
- [ ] Regressions checked; unverified conditions recorded

**IMPROVE**
- [ ] Code quality reviewed; magic-number rule clean
- [ ] Temporary artifacts removed
- [ ] Performance budgets met
- [ ] Behaviour re-verified

**COMPLETE**
- [ ] Final diff reviewed
- [ ] Docs updated (ADR-005, ADR-006, payroll guides, employee guide)
- [ ] Changes and test results reported
- [ ] Acceptance criteria confirmed on staging
- [ ] Exit demonstration (§7.4) observed by client
- [ ] Final status reported

### 11.2 Reporting template

**Before implementation (per deliverable/branch)**
1. Problem understanding — objective; existing behaviour; expected behaviour.
2. Task breakdown — components; atomic tasks (IDs); dependencies.
3. Implementation plan — execution order; acceptance criteria; testing strategy.

**After implementation**
1. Changes made — completed tasks (IDs); files/components modified; key decisions (ADR links).
2. Testing results — tests executed; passed; failed; not executed and why (e.g., PDOC scenario not captured).
3. Remaining issues — known limitations; unresolved bugs; risks/dependencies (e.g., G-09 payment in Phase 4).
4. Final status — Complete / Partially complete / Blocked.

---

## 12. Atomic task count summary

Estimate uses 1.5 h per atomic task (each task is sized 1–2 h per Rule 2.2).

| Deliverable | Atomic tasks | Est. hours |
|---|---|---|
| M-01 | 19 | 28.5 |
| M-02 | 13 | 19.5 |
| M-03 | 17 | 25.5 |
| M-04 | 15 | 22.5 |
| M-05 | 13 | 19.5 |
| M-06 | 14 | 21 |
| N-12 | 17 | 25.5 |
| N-01 | 8 | 12 |
| N-02 | 20 | 30 |
| N-03 | 16 | 24 |
| N-11 | 13 | 19.5 |
| N-13 | 13 | 19.5 |
| N-04 | 27 | 40.5 |
| N-05 | 11 | 16.5 |
| N-06 | 12 | 18 |
| N-07 | 14 | 21 |
| N-08 | 25 | 37.5 |
| N-09 | 11 | 16.5 |
| N-10 | 9 | 13.5 |
| **Total** | **287** | **430.5** |

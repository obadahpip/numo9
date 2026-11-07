# NUMO9 — Project Phases & Deliverables

| | |
|---|---|
| **Project** | Numo9 Platform — "Numbers build a brighter tomorrow" |
| **Prepared by** | Gray Matter AI (Obadah Abu Odeh Information Technology Establishment) |
| **Prepared for** | Profitex — Accounting & Tax Services, Canada |
| **References** | Numo9 Project Plan v2.0 (§2, §3, §4, §5.2) · Quotation GMA-PFX-2026-003 · Agreement GMA-PFX-2026-003-A · Xero teardown (26 Oct 2026) · AI Coding Agent — Mandatory Engineering Workflow |
| **Date** | 7 November 2026 |
| **Total duration** | 90 days (13 weeks) from kickoff, including hypercare |

---

## How to read this document

- The phases follow **§5.2 of the Project Plan** (Phases 0–8 + Hypercare) and the week schedule of the Quotation/Agreement §06.
- Each **deliverable** is one task card from §3 of the Project Plan (same ID). Each deliverable will later be broken into **ATOMIC TASKS** using the Mandatory Engineering Workflow (UNDERSTAND → DECOMPOSE → PLAN → BUILD → TEST → IMPROVE), one Git branch per deliverable (`feature/<ID>-<short-name>`).
- Deliverables marked **[v2.1]** come from the scope added in Quotation GMA-PFX-2026-003 §4 (items ★) and Agreement clause 4.3 (Plan to be re-issued as v2.1). Their IDs are **provisional** until Plan v2.1 is approved.
- `Gap #` = row in the Xero gap-closure matrix (Plan §4) closed by that deliverable.
- A phase is complete only when every deliverable meets its acceptance criteria **and** the phase exit demonstration is observed on staging (Agreement §07).

### Phase overview

| Phase | Name | Weeks | Deliverables | Exit demonstration (summary) |
|---|---|---|---|---|
| 0 | Foundation & SaaS Core | 1 | 33 | Accountant signs up free, opens demo, creates trial org, groups/searches orgs; balanced posting under concurrency |
| 1 | Core Books | 2 | 37 | Invoice → revise to 101-1 → pay → spend money without a feed → switch GST cycle, file out-of-cycle period → P&L / BS |
| 2 | Operations, Finance & Two Books | 3–4 | 40 | SKU/margin dashboards; EOQ reorder → PO; loan schedule posted; full-CCA-as-loss; accounting vs tax statements with computed tax |
| 3 | People (HR & Payroll) | 5–6 | 20 | Multi-province pay run matches CRA calculator from uploaded tables; CPP/CPP2/EI; T4, T4A, T5 XML validated |
| 4 | Practice, Payments & Web | 7 | 21 | Org subscribes and pays; invoice paid online; GST and payroll remittance paid from the system (sandbox); website on staging |
| 5 | Migration, UAT & Go-Live | 8 | 7 | TB reconciles to Xero (0.00); parallel payroll/GST period; production live |
| 6 | French Language | 9 | 3 | Quebec contact receives French invoice from English-UI user; 0 missing keys |
| 7 | Native Mobile Apps | 10–12 | 4 | Invoice revised on web appears on mobile; both apps published |
| 8 | Companion-App Roadmap | 12 | 2 | Companion-app registry live; Numo9 Commerce annex approved |
| H | Hypercare | 9 and 13 | 1 | Hypercare logs closed after Go-Live and after mobile release |

### Dependency chain (Plan §2, Level 3)

```
A Core → U SaaS/Billing → (V, B, C) → (D, E, F, G) → (H, I, J, K, L, R, Finance) → (M → N) → (O, P) → Q → (X, Y, W) → T
S Infrastructure runs continuously from Phase 0.
```

---

## PHASE 0 — Foundation & SaaS Core  (Week 1)

**Objective:** stand up the infrastructure, two-level tenancy, security model, SaaS commercial layer (packages, billing, trial, demo, founding offer), accountant workspace, contacts, chart of accounts and the posting engine.

**Depends on:** kickoff decisions — hosting region (ADR-001), Stripe Canada account, Numo9 domain, brand assets, package names/products/prices, founding-offer wording.

### 0.1 Infrastructure & Security (Component S)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| S-01 | Repository, CI/CD, environments | Monorepo (`backend/`, `frontend/`, `mobile/`, `infra/`, `docs/`), GitHub Actions, dev/staging/prod, i18n extraction job, root/legacy URL redirects (Gap #2) | CI green on `main`; staging deploy from tag |
| S-02 | Hosting & data residency | Canadian-region hosting per ADR-001, Docker Compose, Caddy, TLS | ADR-001 recorded; staging live on HTTPS |
| S-03 | Security baseline | TLS/HSTS/CSP, secrets management, field-level encryption, dependency audit, secrets scan | No high findings in ZAP/pip-audit/npm audit/gitleaks |
| S-06 | Multi-tenant scale (baseline) | Connection pooling, partitioned posting/audit tables, per-org rate limits, usage metering hooks | Baseline in place; full scale target verified in Phase 5 |

### 0.2 Platform Core (Component A)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| A-01 | Practice & Organisation tenancy | Practice, PracticeMember, Organisation, OrganisationMember, PracticeAssignment; scoped manager/middleware; `OrgOwnedModel`; cross-org permission class; lint rule | Removed practice member gets 404 on every record; cross-org ID → 404; router sweep passes |
| A-02 | Authentication, sessions & sign-up | Email/password, verification, reset, TOTP 2FA, session list, all invitation flows | Unverified users blocked; single-use invites; owner invites accountant → assigned |
| A-03 | Roles & permissions (RBAC + approval limits) | Platform/practice/org roles, custom roles, amount limits per user, permission catalogue (Gap #25, #40) | Role × endpoint × method matrix; $5,000 limit blocks $5,001 bill; undeclared permission fails CI |
| A-04 | Audit log & history | Append-only, field diffs, IP/device, global viewer, 90-day default, CSV/XLSX/PDF (Gap #37) | Old/new values shown; DB rejects UPDATE; export = screen |
| A-05 | Org settings, fiscal year, per-module lock dates | Canadian address (Province/Postal code), BN + RT/RP/RC, QST no., FYE, CAD, TZ, numbering, terms; GL/AR/AP/Bank/Payroll/Tax locks (Gap #3, #39, #44, #55) | Posting before lock refused naming the lock; changes audited and attributed |
| A-06 | File storage & documents inbox | Upload/attach/preview, virus-scan hook, S3 storage, per-org inbound email, period tagging, create bill/expense/asset from file (Gap #32) | Org isolation; 25 MB limit; MIME validated; inbound email lands < 60 s |
| A-07 | Notifications, email & custom sending domain | In-app centre, branded templates, EN/FR variants, bounce tracking, SPF/DKIM/DMARC (Gap #42) | Verified domain passes DMARC; bounces flagged on contact |
| A-08 | Background jobs & scheduling | Celery + Redis + beat, job dashboard, idempotency keys | Retry with backoff visible; no double tick across workers |
| A-09 | Global search & quick-create | Search over all record types incl. journals, accounts, settings, reports; keyboard quick-create (Gap #52) | Journal narration found; "lock date" opens settings; shortcuts documented |
| A-10 | Design system & localisation baseline | One component library, Canadian English, one date format per locale, Letter/inch documents, no banners (Gap #1, #12, #22, #26, #31, #38, #43, #60) | Visual regression passes; i18n lint rejects hard-coded strings; editors share one grid |

### 0.3 SaaS, Packages & Billing (Component U)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| U-01 | Product catalogue | Accounting, Tax, Payroll, Inventory **and Finance [v2.1]**, free Practice/Portal sets, future companion apps; feature keys (Gap #51) | Every gated endpoint/screen declares a feature key; matrix exported in-app |
| U-02 | Packages & pricing | Packages of products, monthly/annual CAD, effective-dated prices, promo codes, founding flag | Future-dated price change leaves current subscriptions; retiring a package safe |
| U-03 | Entitlement engine | Org → subscription → package → products → features, cached; explicit gating; 402 API (Gap #6, #11, #14, #41) | Downgrade removes write, keeps read; no silent redirects |
| U-04 | Subscription billing (Stripe) | Card/PAD, proration, renewals, platform invoices/receipts, dunning 3/5/7 days, cancellation export (Gap #13) | Webhook replay no duplicate; grace → read-only on schedule; practice users never billed |
| U-05 | 30-day free trial | Configurable package, 7/3/1-day reminders, loss-free conversion, one trial per BN/email | Conversion at day 30 23:59 local keeps all data; 2nd trial same BN refused |
| U-06 | Platform-owner console | Practices/orgs, subscription state, MRR/churn/funnel, package editor, founding counter, demo manager, audited impersonation, feature flags | Impersonation time-boxed and in org audit log |
| U-07 | Demo organisation | Seeded Canadian dataset, resettable, watermarked, excluded from analytics, auto-purge 30 days, convert to trial | Created < 10 s; never in metrics; reset restores seed exactly |
| U-08 | Founding offer (first 1,000) | Atomic counter on first payment, all-products entitlement, badge in app/website, marketing hooks | 1,500 concurrent payments → exactly 1,000 founding entitlements |

### 0.4 Accountant Workspace (Component V)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| V-01 | Organisation directory | Full-text search, filters, sort, column chooser, saved views, keyboard nav | 2,000 orgs search < 300 ms p95; saved view persists per user |
| V-02 | Groups & tags | Hierarchical groups, colour tags, multi-group, group-level staff assignment | Group assignment grants/revokes access to every org in it |
| V-03 | Bulk edit & bulk actions | Group/tags/staff/safe settings, message, export; preview; audit per org | 200 orgs in one job with per-row result, no silent partial failure |
| V-04 | Cross-organisation dashboards | Deadlines, unreconciled lines, unfiled returns, expiring trials, approvals, workload | Every figure drills down to its org list |
| V-05 | Practice staff management | Invite, roles, per-org/group assignment, dormant alert 60 days, activity heatmap (Gap #40) | Dormant alert at 60 days; heatmap = audit counts |

### 0.5 Contacts (Component B)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| B-01 | Contact model | Explicit roles, addresses with Province, default accounts, province tax default, terms master, credit limit warn/block, currency, T4A flag, exemption certificate, portal flag, custom fields (Gap #19, #20, #43) | QC contact → GST+QST; duplicate warning while typing; merge keeps history |
| B-02 | Contact activity & statements | Timeline; customer/supplier statements; supplier statement reconciliation (Gap #23) | Statement total = AR aging total for the contact on the same date |
| B-03 | Import/export | CSV/XLSX, column mapping, stable external ID, non-destructive updates, dry-run, unlimited people (Gap #15, #21) | Re-import → 0 duplicates, 0 changes; renamed contact updates in place |

### 0.6 General Ledger — foundation (Component C)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| C-01 | Chart of accounts | Types/sub-types, sub-accounts, renumberable system accounts, correct Canadian template, separate GST/HST/ITC/PST/QST/payroll control accounts, default GIFI, require-contact/tracking/attachment flags, archive (Gap #18, #29, #30, #44, #45, #46) | 0 unmapped GIFI; system account cannot be archived; renumbering updates every reference |
| C-02 | Journal posting engine | ≥2 lines, balanced to the cent, atomic, append-only, reverse(), Draft → Awaiting approval → Posted → Reversed, **book dimension** per line | Unbalanced rejected; 1,000 concurrent postings → gap-free sequence; TB of each book = 0 |

**Phase 0 client inputs:** brand assets, domain, package names/mixes/prices, founding-offer wording, Stripe Canada account, hosting account, demo sample-data sign-off.

---

## PHASE 1 — Core Books (Week 2)

**Objective:** a paying organisation runs real books — ledger controls, sales with invoice revisions, purchases with credit terms, never-locked banking, tax engine with filing cycles, core reports, exceptions engine, dashboard.

**Depends on:** Phase 0 (A, U, B, C-01, C-02).

### 1.1 General Ledger & Journals (Component C)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| C-03 | Journal types, contacts on lines, negative-balance controls | General/adjusting/closing/reclass/tax-adjustment/payroll/depreciation; contact per line; negative cash warning; attachment+contact rules; auto-reverse (Gap #33) | Petty Cash below zero blocked/warned; expense journal without attachment refused when rule on |
| C-04 | Manual, recurring & approval workflow | Manual JE UI, recurring templates, threshold approval, approver ≠ creator (Gap #33) | One recurring JE per period; self-approval impossible |
| C-05 | Conversion balances | Opening TB, AR/AP by document, finalisation blocked while unbalanced (Gap #47) | Cannot finalise while difference ≠ 0.00; difference named |
| C-06 | Period close & year-end | Close per module, retained-earnings roll, reopen with reason | Closed-period posting blocked; year-end roll correct on fixture |
| C-07 | Find & recode with undo | Conditional search, recode, preview, audit report, batch undo (Gap #35) | 500 lines → one audit batch; undo restores every line |

### 1.2 Sales (Component D)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| D-01 | Shared sales document grid | One grid for quotes/invoices/recurring/credit notes; line + document discount; filtered account & tax pickers; inclusive/exclusive; required due date (Gap #1, #7, #10, #12, #17) | No purchase codes/expense accounts on sales lines; expired rate unselectable; 50 fixtures match |
| D-02 | Quotes | Send/accept/decline, optional lines, deposit, e-signature, convert, consistent "Expired" (Gap #5, #17) | Accepted quote converts identically; expired cannot be accepted |
| D-03a | Invoices & posting | Lifecycle, branded PDF, numbering, attachments, copy, AR/revenue/tax posting (Gap #43) | Approval posts balanced JE; PDF matches fixture |
| D-03b | Invoice revisions (editable posted invoices) | `InvoiceRevision`, 101 → 101-1 → 101-2, reversal + re-post in one transaction, payment re-allocation, PDF stamp, history panel, reports follow current revision, filed-period rules | 1,130.00 → 1,017.00 gives 101-1, AR −113.00, two linked JEs, tax report 1,017.00; property test AR = sum of open current revisions; concurrent edit → conflict |
| D-04 | Recurring invoices | Same grid, schedule, placeholders, proration, auto-send/draft (Gap #13) | Exactly one invoice per tick after worker restart |
| D-05 | Payments received & allocation | One/many invoices, overpayment credit, prepayments, bank account choice | AR decreases by exactly the payment |
| D-06 | Credit notes | Full page (no redirect), apply or refund (Gap #14) | Applying reduces balance and reverses revenue/tax |
| D-07 | Reminders & statements | Before/after-due steps, escalation, opt-out, late-fee/interest line, SMS/WhatsApp hooks, statement runs (Gap #16) | No reminder for paid/disputed; before-due reminder on schedule |
| D-09 | Sales overview & lists | Shared overview pattern, Overdue tile, credit-notes tab, saved filters, column chooser, bulk statements, revision badge (Gap #5, #6, #22) | Tile counts = list counts |

### 1.3 Purchases (Component E)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| E-01 | Purchase orders, receiving & 3-way match | GRN partial receipt, statuses, PO/received/billed match, approval limits, commitment report (Gap #24, #25) | Receive 6 of 10 → 4 outstanding, stock +6; bill for 12 vs PO 10 flagged |
| E-02 | Bills | Shared grid, supplier invoice-no. uniqueness, duplicate review, routing by amount/department, holdback, AP/ITC posting (Gap #23, #24) | Duplicate supplier invoice no. blocked; thresholds respected |
| E-03 | Recurring bills & supplier credits | Same pattern as D-04/D-06 | Parallel to D-04/D-06 |
| E-04 | Expense claims | Receipt photo, category, tax, mileage (CRA rate), approval, reimbursement bill (Gap #51) | Submitter cannot approve own claim |
| E-06 | Batch payments & cheques | CPA 005 EFT file, cheque print, register with void/stale tracking, positive-pay export (Gap #26) | Batch total = bills; CPA 005 validates; voided cheque reverses payment |
| E-07 | Early-payment discount capture | 2/10 net 30 terms on bills and invoices, discount posting (Gap #10, #23) | Payment inside window posts discount automatically |

### 1.4 Banking (Component F)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| F-01 | Never-locked bank, credit-card & cash accounts | Chequing, Savings, Credit card, LOC, Loan, Cash/Petty cash, Clearing; usable with no feed; ledger balance; optional statement balance (Gap #27) | Spend money from new chequing account with no import → on BS; delete with transactions refused; no-bank prompt (not block) |
| F-02 | Statement import | CSV/OFX/QFX/QBO/XLSX, saved Canadian bank mappings, duplicate detection, preview | Same file twice adds 0 lines |
| F-04 | Bank rules | Contains/not-contains/regex/range, fixed + % allocations, priority, history preview, auto-apply (Gap #28) | Order respected; preview shows affected history |
| F-05 | Optional reconciliation | Match/split/find, report, unreconcile with audit, never blocking | Reconciled balance = statement; a line matched once only |
| F-06 | Transfers | Between accounts, auto-match both sides | Nets to zero in GL |
| F-07 | Negative-balance & cash controls | Warn/block, overdrawn bank as liability, exceptions rule (Gap #27, #33) | Petty Cash −994.17 scenario caught at entry and by exceptions engine |

*(F-03 removed by client decision 4 — replaced by internal `BankStatementSource` interface.)*

### 1.5 Tax Engine — core (Component G)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| G-01 | Tax codes & rates | Effective-dated GST/HST/PST/QST, groups, zero-rated/exempt/out-of-scope, recoverable split, partial ITC %, separate sales/purchase lists (Gap #7, #8, #45) | Every provincial combo to the cent; MB RST 8 % pre-2019 unselectable in 2026; 50 % ITC posts half to expense |
| G-02 | Place-of-supply defaulting | From contact province + registrations, line override, PST-registration warning, exports zero-rated (Gap #9, #45) | ON customer → HST 13 %; US customer → zero-rated |
| G-03 | GST/HST return worksheet | Lines 101–115, quick method, mark filed, period locking, late adjustments (Gap #54) | Line 105 = tax report; filed period refuses back-dated docs without flag |
| G-03a | Filing-cycle engine (switch & out-of-cycle) | Monthly/quarterly/annual, effective-dated switch, custom stub periods, renumbering, instalments, due dates, CRA approval history | Quarterly → monthly from 1 Jul keeps Q1/Q2; 1 Jan–15 Mar stub + quarters accepted; no gaps/overlaps (property test) |
| G-03b | Stop & restart filing | Stop at end date, block new periods, sales defaults → out-of-scope, restart with frequency, audited | After stop 30 Jun no July period; 15 Jul GST doc warns; restart 1 Jan recreates periods |
| G-05 | Tax reports | By code, by document, audit report, ITC/ITR detail, tax-to-GL tie-out (Gap #54) | Totals tie to GL control accounts |
| G-06 | Tax settings on one page | Registrations, numbers, frequencies, basis, defaults, history (Gap #3, #44, #49) | No tax setting on more than one page |

### 1.6 Reporting — core (Component K)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| K-01 | Report engine | Ranges/presets, comparisons, cash/accrual, **book selector**, tracking, drill-down, layout editor, Draft/Published/Custom, exports, name header (Gap #46, #49, #54, #55) | 12-month report on 100k-line GL < 3 s p95; numeric-only legal name rejected |
| K-02 | Core financial statements (accounting book) | P&L, BS (GAAP, overdrawn bank as liability), Cash Flow indirect + direct, TB sorted by code with opening/movement/closing, GL, Journal report, Equity, Account transactions (Gap #54, #56, #57, #58) | BS balances; NI = change in RE; every figure drills down |
| K-03 | Receivables/payables reports | AR/AP aging, control vs sub-ledger reconciliation (Gap #54) | Aging = control; reconciliation 0 on fixtures, names offending journal otherwise |
| K-05 | Dashboard | Bank balances widget default, cash in/out, owed/to pay, deadlines, P&L snapshot, watchlist, role widgets, no ads (Gap #4, #60) | Figures = report totals; empty shows 0, never "—k" |
| K-09 | Exceptions engine (assurance) | Negative cash, journals to cash, missing contact/attachment, exempt on taxable accounts, backdating, round amounts, weekends, SoD, duplicates, unmapped GIFI, missing BN/lock date, dormant users; draft correcting entry (Gap #36, #53, #59) | Every teardown issue flagged on the migrated fixture |

**Phase 1 client inputs:** sample documents, CRA business numbers for fixtures.

---

## PHASE 2 — Operations, Finance & Two Books (Weeks 3–4)

**Objective:** inventory with analytics and price optimisation, fixed assets with SL/DB and CCA, finance module (loans, interest, credit terms), projects & time, Sheets, multi-currency, budgets, two-book engine with tax-purpose statements and corporate tax computation, QST return, GIFI export, OCR capture.

**Depends on:** Phase 1 (C, D, E, F, G core, K core).

### 2.1 Inventory & Quantity Management (Component H)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| H-01 | Items catalog | Tracked/untracked, SKU/barcode, categories, price lists, customer pricing, accounts, tax codes, images, suppliers, auto inventory account (Gap #18) | SKU unique; services never affect stock; price list applies per contact |
| H-02 | Units of measure | Base/purchase/sales units and conversions | 2 boxes of 12 add 24 |
| H-03 | Locations & stock on hand | Multiple locations, stock card, negative stock blocked unless back-ordering | On-hand = sum of movements |
| H-04 | Stock movements | Receipts, issues, adjustments, transfers; every movement posts | GL inventory = valuation report |
| H-05 | Costing | Moving average default, FIFO option, landed cost | Fixtures with known answers |
| H-06 | Batch/serial & expiry | Optional per item, traceability | Serial exists in one location only |
| H-07 | Reorder & stock reports | Reorder points, suggested POs, valuation, movement, aging, stock-take | Alert when on-hand < reorder point |
| H-08 | Simple assemblies (BOM) | Build from components, issues + finished-goods receipt | Build 10 consumes per BOM, finished +10 |

### 2.2 Inventory Analytics & Profit Optimisation [v2.1] (Quotation §4 ★)
| ID (prov.) | Deliverable | Scope | Acceptance (to be finalised in v2.1) |
|---|---|---|---|
| H-09 | Best-selling SKU rankings | By quantity, revenue and margin over any period | Rankings tie to sales and COGS postings for the period |
| H-10 | Stock-movement analysis | Sales velocity, days of cover, dead and slow stock | Figures reproduce on fixtures with known movements |
| H-11 | EOQ reorder engine | Client-supplied EOQ equation; per-SKU demand, ordering cost, holding cost, safety stock, lead time; one-click PO creation | EOQ output = client's worked example; suggestion → PO in one action |
| H-12 | COGS-to-profit & price optimisation | Gross profit, contribution margin, margin % per SKU/category/location; what-if price scenarios; bulk price-list updates | Contribution margin = revenue − variable cost on fixtures; scenario does not change live prices until applied |
| H-13 | Management-accounting KPIs & dashboard | KPIs and formulas from client's management-accounting material; dashboard and exports | Each KPI matches the client's source formula on a fixture |

### 2.3 Finance Module — Loans, Interest & Credit Terms [v2.1] (Quotation §4 ★)
| ID (prov.) | Deliverable | Scope | Acceptance (to be finalised in v2.1) |
|---|---|---|---|
| FN-01 | Loan register | Vehicle/equipment loans, LOC, shareholder and lease-type financing; principal, rate, term, compounding, frequency, start date | Loan creates liability account link; data validated |
| FN-02 | Payment calculator & amortisation schedule | Principal/interest split per payment; YTD interest; total interest over term; early repayment and rate-change recalculation | Schedule matches reference calculator to the cent; recalculation preserves past payments |
| FN-03 | Automatic loan posting | Liability, principal reduction, interest expense, accrued interest on each payment/period end | Loan liability in GL = schedule balance after each payment |
| FN-04 | Credit-terms interest handling | Early-payment discount (2/10 net 30), late-payment interest charged by suppliers / to customers, effective annual cost of forgoing a discount, ledger posting (extends E-07, D-07) | Late interest and discounts post to configured accounts; cost-of-forgoing figure matches formula |
| FN-05 | Loan & interest reports + finance KPIs | Reports in accounting and tax books; KPIs from client material | Reports tie to GL in both books |

### 2.4 Fixed Assets & CCA (Component I)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| I-01 | Asset register with book & tax settings | From bill or manual; SL/DB book method; Schedule II CCA classes seeded; half-year, AII flags; usable immediately (Gap #34) | Class 8 10,000 mid-year → CCA 1,000 yr 1, 1,800 yr 2; opens with no setup |
| I-02 | Book depreciation runs (SL & DB) | Monthly/annual runs, schedule preview, continuity report | JE = schedule; SL/DB match client templates to the cent |
| I-03 | Discretionary CCA claim incl. full-CCA-as-loss | UCC per class, max CCA, claim 0…max, "claim maximum even if loss", recapture/terminal loss, tax-book posting | NI 500, max CCA 1,800: full claim → −1,300 and 1,300 carry-forward; claim 500 → 0; accounting book unchanged |
| I-04 | Client depreciation templates importer | XLSX/CSV templates, validation, practice/org defaults, versioned by tax year | Client furniture template → Class 8 DB 20 % default; output = worked example |
| I-05 | Disposals | Sale/scrap, gain/loss (book), proceeds vs UCC (tax) | Fixtures correct in both books |

### 2.5 Projects & Time (Component J)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| J-01 | Projects / engagements | Budgets, tasks, project P&L (Gap #51) | Project P&L correct on fixture |
| J-02 | Timesheets | Timers, billable rates, approval | Approved time recorded once |
| J-03 | Time & expense to invoice | Pull billable entries into invoice | Billed entries excluded from next pull |

### 2.6 Sheets — Working Papers (Component L)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| L-01 | Grid editor | In-app spreadsheet with formulas | Grid 200×50 performance target |
| L-02 | GL-linked functions | `=GL(account, from, to, book)` | Lead schedule in tax book = tax-book TB |
| L-03 | Templates & versioning | Lead schedules, reconciliations, CCA continuity, loan continuity [v2.1], book reconciliation; period lock | Template versions retained; locked period read-only |
| L-04 | Import/export | XLSX import/export | Round-trip preserves values and formulas |

### 2.7 Multi-currency (Component R)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| R-01 | Currencies & rates | Daily rates, manual override, currency per contact (Gap #11, #20) | Rate used = rate on document date |
| R-02 | Foreign documents & FX | Foreign invoices/bills/bank accounts, realised/unrealised FX, show-currency-code option | FX gain/loss correct on fixtures |

### 2.8 Two-Book Reporting & Tax (Components K, G)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| K-04 | Budgets | Budget vs actual with variance | Variance = actual − budget |
| K-06 | Management pack & adviser templates | One-click pack; NTR/Compilation (CSRS 4200)/Review templates in Numo9 wording | Pack < 10 s; templates editable per practice |
| K-07 | Two-book engine | `book ∈ {accounting, tax, both}`; tax-adjustment journals tax-only; book filter; Book Reconciliation report | Accounting NI − adjustments = tax NI on every fixture; reconciliation nets to 0 |
| K-08 | Tax-purpose BS & IS with tax amount | CCA replaces amortisation, non-deductibles removed, computed income-tax line (G-08), side-by-side view, PDF/XLSX | T2 fixture: tax NI and computed tax = known answer; columns reconcile per line |
| K-10 | Adjusted trial balance | Proposed adjustments columns, post to chosen book (Gap #57) | Adjusted TB = TB + adjustments per line |
| G-04 | QST return worksheet | FPZ-500 equivalent, same cycle engine | Parallel to G-03 |
| G-07 | GIFI & T2 export | GIFI mapping editor, schedule 100/125/141 export (Gap #30) | Export balances to tax-book TB |
| G-08 | Corporate tax computation (tax book) | NI for tax, Schedule 1 adjustments, CCA, loss application, SBD/general and provincial rates as data, instalments, provision JE | T2 fixture computes to the dollar; rates are data |

### 2.9 Purchases — capture (Component E)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| E-05 | Receipt & bill capture (inbound email + OCR) | Per-org forwarding address, pluggable extraction, per-field confidence, confirmation required (Gap #32, #51) | ≥ 80 % field accuracy on fixtures; confidence shown per field |

**Phase 2 client inputs (due by start of Phase 2 — Agreement 9.1(b)):** depreciation templates and methods, EOQ equation and parameters, management-accounting material for inventory/pricing/finance KPIs.

---

## PHASE 3 — People: HR & Payroll (Weeks 5–6)

**Objective:** HR records and self-service; extended Canadian payroll with uploaded CRA tables, worker classification, taxable benefits and year-end slips (T4, T4A, T5, RL-1).

**Depends on:** Phase 1 (ledger, banking, tax), A-06 documents, A-03 roles.

### 3.1 Staff & HR (Component M)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| M-01 | Employee & contractor master | Encrypted/masked SIN and bank details | SIN never logged; masked on screen |
| M-02 | Departments, positions & org chart | Structure and reporting lines | Org chart renders from data |
| M-03 | Leave management | Provincial accrual rules (vacation pay) | Accruals match provincial fixtures |
| M-04 | Onboarding / offboarding | Checklists, TD1 federal/provincial, direct deposit, acknowledgements | Checklist completion tracked per employee |
| M-05 | HR documents & letters | EN/FR templates, policy library | Letter generated from template with employee data |
| M-06 | Employee self-service | Stubs, slips, leave, claims, timesheets (web) | Employee sees only own records |

### 3.2 Payroll — Canada (Component N)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| N-01 | Constants by tax year | CPP/CPP2/EI/QPP/QPIP, T4127 edition, versioned | Constants selected by pay date's tax year |
| N-02 | Pay schedules & runs | Frequencies, run lifecycle, approval limits | Run cannot post twice |
| N-03 | Earnings, deductions & benefits | Earnings/deduction types; **taxable benefits [v2.1]** (automobile, group insurance, housing, allowances) with T4 box/code mapping | Each benefit lands in the correct T4 box/code |
| N-04 | Statutory calculations | CPP + CPP2 with exemption pro-ration and YTD max, EI (employer 1.4×, QC rate), QPP/QPIP, federal + provincial tax per T4127 | 40-scenario CRA fixture passes |
| N-05 | Stubs & register | Pay stubs and payroll register | Register totals = posted payroll JE |
| N-06 | Direct-deposit EFT file | CPA 005 | File validates |
| N-07 | Remittances | Remittance calendar by remitter type; payable from the system via G-09 (Phase 4) | PD7A-style summary correct; marked paid after G-09 confirmation |
| N-08 | Year-end slips | T4/T4 Summary, RL-1 export; **T4A/T4A Summary and T5/T5 Summary [v2.1]**; CRA e-file XML | T4, T4A, T5 XML validate against CRA schema |
| N-09 | ROE data | Record of Employment data export | Fields complete for fixture terminations |
| N-10 | Payroll by the practice inside client orgs | Practice payroll specialist runs payroll for assigned orgs | Access limited to assigned orgs (A-01 sweep) |
| N-11 (prov.) | Worker-classification tool [v2.1] | CRA factors (control, tools, financial risk, profit opportunity, integration, intention); documented determination on worker record; drives source-deduction treatment | Determination stored and audited; contractor classification removes CPP/EI/tax withholding |
| N-12 (prov.) | CRA default tables upload [v2.1] | Upload payroll deduction tables, rate sheets, constants, claim codes per tax year; versioned storage used for every T4 box | Uploaded edition drives calculations; switching edition re-computes fixtures correctly |
| N-13 (prov.) | Vacation & statutory holiday pay [v2.1] | Provincial rules | Matches provincial fixtures |

**Phase 3 client inputs (due by start of Phase 3 — Agreement 9.1(c)):** CRA default tables per tax year (or confirmation of editions), worker-classification factor set, anonymised past payroll runs.

---

## PHASE 4 — Practice, Payments, Tax Payments & Website (Week 7)

**Objective:** practice management and client portal, Stripe payments, in-system tax payments, public API, Numo9 product website.

**Depends on:** Phases 0–3 (U-04 billing, D invoices, G returns, N remittances).

### 4.1 Practice Management & Client Portal (Component O)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| O-01 | Service catalog | Practice services with prices | Services purchasable via P-03 |
| O-02 | Engagements | Engagement pipeline | Status transitions audited |
| O-03 | Document requests | Checklists sent to organisations | Uploads land in the org's documents |
| O-04 | Deadline calendar | Driven by filing-cycle engine and remittance type | G-03a cycle switch updates calendar within one job cycle |
| O-05 | Client portal | Dashboard, messaging, approvals, e-signature, subscription/package view, loan [v2.1] and tax-payment views, revision badges | Client sees only own org; current revision shown with badge |
| O-06 | Staff task board | Tasks per staff/org | Tasks filter by staff and org |

### 4.2 Online Payments (Component P)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| P-01 | Stripe connection | Platform account for subscriptions; Connect/per-org keys for invoices; test/live; PAD | Test-mode checkout end to end on both |
| P-02 | Invoice payment | Pay links follow current revision; superseded link redirects | Payment posts and allocates; old revision link → current |
| P-03 | Pay-per-service checkout | Practice service purchase | Checkout creates invoice and payment |
| P-04 | PAD mandates & recurring billing | Mandates, recurring charges | Mandate stored at Stripe only (PCI out of scope) |
| P-05 | Refunds & disputes | Refund and dispute handling with posting | Refund reverses payment posting |
| P-06 | Tax-payment provider adapter | `TaxPaymentProvider` (quote/initiate/status/cancel), sandbox stub, production provider per ADR-003, bank bill-payment file fallback | Swapping providers changes no G-09 screen; stub drives full state machine in CI |

### 4.3 Tax Payments & Sales (Components G, D)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| G-09 | Tax Payments | Amounts owing by registration/period (GST/HST, QST, payroll, corporate instalments); provider route and assisted route; idempotency, statuses, confirmation, posting, reminders, receipts | 1,234.56 GST paid via test provider posts exactly; second "pay" refused; assisted route posts the same; remittance calendar shows paid |
| D-08 | Online invoice pay link | Delivered through P-02 | As P-02 |

### 4.4 Public Website (Component Q)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| Q-01 | Site design & content | Original Numo9 brand (yellow/black), Home, Products, Packages & live Pricing, founding counter, For Accountants, Demo, Trial, Resources, About, Contact, Legal; sign-up funnels | Lighthouse ≥ 90; WCAG 2.1 AA; trial sign-up to first screen < 2 min |
| Q-02 | Lead capture & demo requests | Forms and routing | Leads stored and notified |
| Q-03 | CMS | Headless CMS in Django admin | Pages editable without deploy |
| Q-04 | SEO, analytics, domain, mail DNS | Structured data, analytics, Numo9 domain, TLS, SPF/DKIM/DMARC | DNS verified; SEO checks pass |

### 4.5 Open API (Component W)
| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| W-01 | Versioned public API & webhooks | OpenAPI 3, API keys/OAuth per org, scopes = feature keys, webhooks, rate limits, full-ledger export (Gap #48, #50) | Contract tests from spec; webhook replay idempotent |

**Phase 4 client inputs:** tax-payment route/provider and account (ADR-003), Stripe live access, website content and legal pages.

---

## PHASE 5 — Migration, UAT & Go-Live (Week 8)

**Objective:** migrate Profitex and one pilot client from Xero, complete UAT, training and documentation, production cut-over with parallel payroll and GST period.

**Depends on:** Phases 0–4.

| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| T-01 | Xero importer | CoA with re-typing review, contacts, items, invoices, bills, journals, bank transactions, assets with CCA class suggestions, TB; tax-code mapping; self-service for any org | TB difference 0.00 for Profitex and pilot client; exceptions report on import |
| T-02 | UAT | UAT sign-off sheet per component acceptance criteria; gap-closure checklist (Plan §4, one check per row) | Every component and every gap row observed |
| T-03 | Training | Role-based recorded sessions incl. accountant workspace and SaaS admin | Attendance and recordings delivered |
| T-04 | Documentation | Admin, platform-owner, accountant guides; runbook; API docs; ADR-001…004; data dictionary | In `docs/` and as PDF |
| T-05 | Go-live (cut-over) | Production deployment, parallel payroll and GST period | Production live; parallel run reconciled |
| S-04 | Monitoring & logging | Error tracking, metrics, alerting | Alerts fire on test incidents |
| S-05 | Backups & retention | Encrypted backups, PITR, CRA six-year retention, restore drill | Restore drill < 1 hour; S-06 scale target (500 orgs × 100k lines p95 < 3 s) met |

**Payment milestone 2 (CAD 5,000) on Phase 5 acceptance (Agreement 8.2).**
**Phase 5 client inputs:** Xero exports, CRA/RQ numbers, UAT testers, decision-maker sign-off within 5 business days.

---

## PHASE 6 — French Language (Week 9)

**Objective:** complete French-Canadian interface, documents, emails, website and portal.

**Depends on:** all screens built with EN/FR keys from Phase 0 (Plan §5.3 rule 5).

| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| X-01 | i18n infrastructure | Catalogues backend/frontend, locale per user/org, fr-CA formats (1 234,56 $), pluralisation, CI extraction, missing-key report | 0 missing fr-CA keys; layouts hold with +30 % strings |
| X-02 | French UI, emails & documents | All screens, notifications, PDFs (invoice, revision stamp, credit note, statement, quote, PO, pay stub, slips, tax and loan [v2.1] reports), CRA/RQ terminology, per-contact language (Gap #42, #43) | QC contact (FR) receives French invoice from EN-UI user; glossary approved by client |
| X-03 | Bilingual website & portal | FR pages with hreflang; portal language per user | Lighthouse SEO ≥ 90 on both locales |

**Phase 6 client inputs:** French glossary reviewer and sign-off.

---

## PHASE 7 — Native Mobile Apps (Weeks 10–12)

**Objective:** iOS and Android apps for organisation owners and employees, published in both stores.

**Depends on:** W-01 API, A-02 auth, Phases 1–4 features.

| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| Y-01 | Mobile foundation | React Native (Expo), shared API/auth, biometric unlock, secure token storage, push, offline capture queue | Login, org switch, dashboard on both platforms; tenant sweep through mobile client |
| Y-02 | Organisation-owner app | Dashboard, invoices (create/send/revise/pay link), bill approvals, bank spend/receive, receipt capture → E-05, tax-payment status, subscription status, loan status and SKU analytics [v2.1], notifications | Invoice revised on web appears on mobile within one sync |
| Y-03 | Employee app | Pay stubs, slips (T4/T4A), leave, expense claims with camera, timesheets | Employee sees only own records |
| Y-04 | Store release & maintenance | App Store and Google Play listings under client accounts, crash reporting, release pipeline, EN/FR store copy | Both apps approved and published; crash-free ≥ 99 % in hypercare |

**Phase 7 client inputs:** Apple Developer and Google Play accounts.

---

## PHASE 8 — Companion-App Roadmap (Week 12)

**Objective:** registry for Numo9's own companion apps and the Numo9 Commerce discovery annex (build under change control).

**Depends on:** W-01, U-01/U-03 entitlements.

| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| W-02 | Companion-app registry (Numo9-owned only) | App registration, per-org install, entitlement as product; planned: Numo9 Commerce, Numo9 Bank (`BankStatementSource`), Numo9 Receipts (within Y) | Install grants exactly its scopes; uninstall revokes; no third-party marketplace |
| W-03 | Numo9 Commerce discovery annex | Requirements, data model (H items, D orders → invoices, H stock, P payments), estimate and plan as change-controlled annex | Annex approved by client before build |

---

## HYPERCARE (Weeks 9 and 13) & WARRANTY

| ID | Deliverable | Scope | Acceptance |
|---|---|---|---|
| T-05 (hypercare) | Hypercare & warranty start | One week after Phase 5 Go-Live (week 9) and one week after mobile release (week 13) per Agreement §5.3; priority defect handling; 12-month warranty from Go-Live incl. quarterly constants/CRA tables/tax rates/CCA class updates | Hypercare logs closed; warranty period running |

---

## Next step

For each phase, every deliverable above will be decomposed into **ATOMIC TASKS** following *AI CODING AGENT — MANDATORY ENGINEERING WORKFLOW* (Rules 1–11): problem understanding, components, atomic tasks (1–2 h, independent, ordered), dependencies, task cards (ID, objective, current/expected behaviour, steps, acceptance criteria, testing approach, risks), one Git branch per deliverable.

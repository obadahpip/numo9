# Assurance rules — catalogue (K-09)

K-09-T01 · The exceptions engine's rule catalogue: for every rule its **code**, the **condition**
that raises a finding, its **parameters** (with defaults and limits), its default **severity**,
the **subject** a finding is about, whether it runs **incrementally** on posting, and its **fix
template**. Sign-off = merging the PR that adds this file (as earlier batches).

The engine closes gaps **36** (assurance ignores journals; no SoD, round-number, weekend,
duplicate-payment checks), **53** (flags symptoms, not fixes), **59** (GL Exceptions flags
nothing) and the detection side of **33**. The acceptance scenario is the Xero teardown
organisation REFINED (docs/xero_teardown.md §5.4, §5.8, §6.11, §10.A).

## Common rules of the engine

- **Rules are plug-ins** (`numo9.assurance.rules`): a code, i18n name and description, a default
  severity, typed parameters with defaults, `evaluate(org, scope)` → hits and an optional
  `propose_fix(finding)` → draft journal payload.
- **Severity**: `info` · `warning` · `critical`. Each organisation can switch a rule off, change
  its severity and its parameters (*Rule settings*); parameters are validated against the rule's
  schema (type, minimum, maximum, choices) and a change re-evaluates on the next run.
- **Finding** = (rule, subject). The **fingerprint** is `sha256(rule code | subject type |
  subject id)`. There is at most **one open or acknowledged finding per fingerprint**
  (database constraint). Statuses: `open` → `acknowledged` → `resolved`, or `false_positive`
  (with a reason).
  - Re-running never duplicates: the finding's `last_seen`, amount and details are refreshed.
  - A **resolved** finding whose condition recurs is **reopened** (same row, status open).
  - A **false positive** stays silent while the condition recurs with the **same amount**; a
    different amount is a **new finding** (the earlier false positive is kept).
  - When the condition clears, an open or acknowledged finding is **resolved automatically**
    (`resolved_by_run`).
- **Runs**: on demand (*Run checks*), nightly (every organisation, the job
  `numo9.assurance.nightly`), and **incrementally on posting** — only the rules marked
  *incremental*, only for the journals, documents and accounts the posting touched.
- **Fixes** are never posted automatically: a proposal becomes a **draft journal** (C-04) linked
  to the finding; posting that draft re-checks the finding at once and resolves it when the
  condition is gone.
- **Tenancy and roles**: findings belong to one organisation (row-level security); practice
  staff see the findings of their assigned organisations only. Viewing needs
  `accounting.assurance.view`; running, acknowledging, marking false positive, creating a fix and
  changing rule settings need `accounting.assurance.manage`. Feature key
  `accounting.assurance.read` (every package with Accounting).
- **Audit**: every status change, rule-settings change and fix draft is an audit event
  (`assurance.finding.*`, `assurance.ruleconfig.*`).
- **Dates and times** are the organisation's: a weekend is Saturday or Sunday in the
  organisation's time zone, "today" is its local date.
- The **ledger view** of a rule is the accounting book (lines in both books or the accounting
  book) of posted and reversed entries, as the cash guard (C-03-T07) reads it.

## Assurance score

`score = max(0, round(100 − penalty))`, where each **open** finding costs its severity weight —
critical 15, warning 5, info 1 — an **acknowledged** one half of it, and each rule counts at most
**3** findings (one noisy rule can't empty the score on its own). Resolved and false-positive
findings cost nothing. The summary gives the score, counts by severity and status, and the open
findings by rule. A practice-level aggregation (V-04) reads `summary(org)` for each assigned
organisation (`practice_summary(orgs)` — average and lowest score, critical count).

## Catalogue

| Code | Condition (a finding is raised when…) | Parameters (default) | Severity | Subject | Incremental | Fix template |
|---|---|---|---|---|---|---|
| `NEG_CASH` | A bank or cash account (asset, sub-type Bank) has an end-of-day balance below zero at any point: its **lowest** running balance, the day it was reached and today's balance | `fix_source` = `auto` (`auto`, `transfer`, `shareholder_loan`); `shareholder_loan_account` = `2900` | critical | account | yes | Draft dated the first day the balance went negative: **Dr the account / Cr a funded bank** (another bank account whose balance covers the shortfall — "transfer") or, when none, **Dr the account / Cr Shareholder loan** (the account with code `shareholder_loan_account`, else the first liability named "Shareholder loan"), amount = the shortfall (−lowest). Teardown: Dr 1000 Petty Cash 994.17 / Cr 2900 Shareholder Loan 994.17 |
| `JOURNAL_TO_CASH` | A posted **manual** journal (not a reversal) has a line on a bank or cash account | `min_amount` = 0.00 | warning | journal | yes | — (explain: record money in and out as spend/receive money, a bill payment or a transfer so it is reconciled) |
| `EXPENSE_JOURNAL_NO_CONTACT` | A posted manual journal has an expense line without a contact | `min_amount` = 0.00 | warning | journal | yes | — (explain: enter purchases as bills or spend money with the supplier) |
| `EXPENSE_JOURNAL_NO_ATTACHMENT` | A posted manual journal with an expense line has no supporting document attached | `min_amount` = 0.00 | warning | journal | yes | — (explain: attach the receipt) |
| `EXEMPT_ON_TAXABLE_ACCOUNT` | The organisation is a **registrant** (a GST/HST or QST registration that isn't closed) and a posted line on an **expense account normally taxable** (operating expense or cost of sales, not in `exclude_accounts`) is coded with an **Exempt** tax code | `exclude_accounts` = [] (account codes) | warning | journal line | yes | **Recode tax** through find & recode (C-07): a prefilled search (journal number, account, exempt code) and the suggested code (the account's default when taxable, else the purchase standard code of the organisation's province) |
| `BACKDATED` | A posted journal, invoice or bill was posted more than **N days** after its document date (posting date in the organisation's time zone − document date) | `days` = 7 (1–365) | warning | journal / invoice / bill (the source document when there is one) | yes | — |
| `ROUND_AMOUNT` | A posted manual journal's total is ≥ `threshold` and a multiple of `multiple` | `threshold` = 1,000.00; `multiple` = 100.00 | info | journal | yes | — |
| `WEEKEND_POSTING` | A journal was posted by a person on a Saturday or Sunday in the organisation's time zone (optionally on a statutory holiday) | `include_holidays` = false; `province` = "" (federal holidays when empty) | info | journal | yes | — |
| `SOD_SAME_CREATOR_APPROVER` | The same person created and approved a journal (C-04 approval) or a bill (E-02 approval). Pay runs: placeholder until payroll (P-phase) registers its source | — | warning | journal / bill | yes | — |
| `DUPLICATE_PAYMENT` | Two posted payments out of a bank or cash account to the **same contact**, for the **same amount**, within `window_days` of each other (neither reversed) | `window_days` = 3 (0–60) | warning | the later journal | no | — (explain: void or reverse the duplicate) |
| `DUPLICATE_SUPPLIER_INVOICE` | Two bills of the same supplier (not void) whose supplier invoice numbers are the same after normalising (case, spaces, dashes, leading zeros), or whose totals are within `tolerance_pct` and dates within `window_days` | `window_days` = 10; `tolerance_pct` = 1 | warning | the later bill | no | — |
| `UNMAPPED_GIFI` | Active accounts without a GIFI code (C-01) — one finding per organisation with the count and the list | `only_with_activity` = false | warning | organisation | no | — (link: chart of accounts, GIFI column) |
| `MISSING_BN` | The organisation has a GST/HST (RT), QST, payroll (RP) or corporate (RC) registration that isn't closed, but no Business Number (BN) registration | — | critical | organisation | no | — (link: Tax registrations) |
| `MISSING_LOCK_DATE` | Posted activity exists in a month that ended more than **N days** ago and the general-ledger lock date is empty or before that month's end | `days` = 30 (1–365) | warning | organisation | no | — (suggested lock date: that month's end) |
| `UNBALANCED_CONVERSION` | A conversion (C-05) exists and its opening balances don't balance, have no equity line ("opening equity missing", the C-05-T14 signal) or are empty | — | critical | conversion | no | — (link: Conversion balances) |
| `DORMANT_USER_WITH_ADMIN` | A person with user-management rights (`organisation.members.manage`) hasn't signed in for `days` days (never signed in: counted from joining) | `days` = 60 (7–365) | warning | user | no | — (link: Users and roles) |
| `CONTACT_BANK_DETAILS_CHANGED` | A contact's bank or payment details changed in the last `lookback_days` (audit log: masked bank fields) — check the change with the supplier before paying | `lookback_days` = 30 | warning | contact | no | — |
| `TAX_CODE_OVERRIDE_RATE` | Over the last `lookback_days`, the share of posted lines whose tax code differs from their account's default exceeds `threshold_pct` (at least `min_lines` lines with a default) | `threshold_pct` = 20; `min_lines` = 20; `lookback_days` = 90 | info | organisation | no | — |

## Plain-language explanations

Each finding carries the numbers its explanation needs (`details`), and the screen writes the
explanation from the rule's i18n template, e.g.:

- NEG_CASH — "Petty Cash went below zero: −994.17 on 15 Jun 2026 (today −994.17). Cash on hand
  can't be negative: money was spent from it that was never put in."
- JOURNAL_TO_CASH — "Journal 1 (3 Jun 2026) posts 417.22 to Petty Cash. Money in or out of a bank
  or cash account should be recorded as a bank transaction so it can be reconciled."
- BACKDATED — "Journal 1 is dated 3 Jun 2026 but was posted on 15 Jun 2026 (12 days later; the
  limit is 7)."

## Teardown acceptance (REFINED)

On the REFINED-like fixture (Petty Cash 1000, Shareholder Loan 2900, the two manual journals of
3 and 15 June 2026 all coded *Exempt*, journal 1 posted on 15 June, a GST/HST registration without
BN, no lock date, no GIFI mapping, an empty conversion at 1 Jan 2025 and an owner who hasn't
signed in for four months) the engine raises at least: NEG_CASH (−994.17, fix Dr 1000 / Cr 2900),
JOURNAL_TO_CASH ×2, EXPENSE_JOURNAL_NO_CONTACT ×2, EXPENSE_JOURNAL_NO_ATTACHMENT ×2,
EXEMPT_ON_TAXABLE_ACCOUNT (every expense line), BACKDATED (journal 1), MISSING_BN,
MISSING_LOCK_DATE, UNMAPPED_GIFI, UNBALANCED_CONVERSION and DORMANT_USER_WITH_ADMIN — at least 7
rule groups on the Assurance page.

# Assurance rules reference

K-09-T27 · Deliverable K-09 (exceptions engine). What each assurance rule checks, the numbers its
finding shows, the settings you can change, and what to do about it. The design behind the rules
(fingerprints, statuses, the score formula, runs) is the rule catalogue,
[Assurance rules — catalogue](../specs/assurance-rules.md); the screens are in
[the K-09 wireframes](../design/wireframes/K-09-assurance.md).

Go to **Accounting › Assurance** (`/o/<organisation>/accounting/assurance`). Seeing it needs
*View assurance findings* (`accounting.assurance.view`); running the rules, acknowledging,
marking a false positive, creating a fix and changing rule settings need *Manage assurance*
(`accounting.assurance.manage`). Practice staff see the organisations they are assigned to only.

## How the page works

| Tab | What it shows |
|---|---|
| **Findings** | The assurance score (0–100), the open findings by severity, filters (severity chips, status, search) and the findings grouped by rule, most severe first. Each finding says, in plain words and with its numbers, why it was raised, and offers *View source*, *Propose fix* (when the rule has one), *Acknowledge* and *Mark false positive* (a reason is required). *Run the rules* starts a full run in the background. |
| **Rule settings** | Every rule with an on/off switch, its severity and its parameters. Values are checked as you type (whole numbers, amounts with two decimals, minimum, maximum, choices); *Save* stores what changed — **changes apply on the next run** — and *Reset to defaults* puts every rule back to its defaults. Every change is in the audit log. |
| **Activity** | The user-activity heatmap: one square per day of the last 12 months in the organisation's time zone, shaded by the number of actions in the audit log, filterable by person, with *Show as table* (the same numbers as a table) and each person's total and last activity — a dormant administrator stands out. |

The **Accounting** item of the top navigation carries a badge with the number of **open critical
and warning** findings (info and acknowledged findings don't count). It disappears at zero.

### When the rules run

- **Nightly**, every organisation (job `numo9.assurance.nightly`, 03:47 Toronto time).
- **On posting**: every posted journal queues an incremental run of the rules marked *Also checked
  on posting* below, for that journal and the accounts it touched.
- **On demand**: *Run the rules*.

### Findings and their statuses

A finding is one rule about one subject (an account, a journal, a line, a bill, a person, the
organisation). Running the rules again never duplicates it: its numbers are refreshed.

| Status | Meaning |
|---|---|
| Open | The problem is there. Counts fully in the score. |
| Acknowledged | Someone has seen it and is dealing with it. Counts half. *Reopen* puts it back to open. |
| Resolved | The condition is gone — set automatically by the next run, or at once when the draft fix is posted. A resolved finding whose condition comes back is reopened. |
| False positive | Not a problem, with the reason given. It stays quiet while the condition comes back with the **same amount**; a different amount opens a new finding. |

**Assurance score** = 100 − (15 per open critical, 5 per open warning, 1 per open info; half for an
acknowledged one; at most 3 findings counted per rule), never below 0.

### Proposed fixes

*Propose fix* opens a drawer with **Why this entry** (the rule's reasoning) and the proposed
correcting entry as an editable draft journal: date, narration and lines (account, debit, credit,
description), with the totals and *Out of balance by …* until debits equal credits. Other options
the rule found (for example a transfer from a funded bank account) are listed with *Use this
option*. **Create draft journal** saves it as a **draft** in **Accounting › Journals › Draft** —
nothing is ever posted for you. Review it there and post it (approval rules apply as for any
journal); posting it re-checks the finding and resolves it when the problem is gone. For exempt
tax codes the fix is a prefilled search in **Find and recode** instead of a journal.

## The rules

Severity is the default; each organisation can change it. "On posting" = also checked
incrementally when a journal is posted. French names are those of the fr-CA interface.

| Code | Name (en-CA) | Nom (fr-CA) | Severity | On posting | Fix |
|---|---|---|---|---|---|
| `NEG_CASH` | Negative cash or bank balance | Solde de caisse ou de banque négatif | Critical | Yes | Draft journal |
| `JOURNAL_TO_CASH` | Manual journal posts to a bank or cash account | Écriture manuelle dans un compte de banque ou de caisse | Warning | Yes | — |
| `EXPENSE_JOURNAL_NO_CONTACT` | Expense journal without a contact | Écriture de dépense sans contact | Warning | Yes | — |
| `EXPENSE_JOURNAL_NO_ATTACHMENT` | Expense journal without an attachment | Écriture de dépense sans pièce jointe | Warning | Yes | — |
| `EXEMPT_ON_TAXABLE_ACCOUNT` | Exempt code on a normally taxable account | Code exonéré dans un compte normalement taxable | Warning | Yes | Find and recode |
| `BACKDATED` | Backdated posting | Comptabilisation antidatée | Warning | Yes | — |
| `ROUND_AMOUNT` | Round amount journal | Écriture d'un montant rond | Info | Yes | — |
| `WEEKEND_POSTING` | Weekend posting | Comptabilisation la fin de semaine | Info | Yes | — |
| `SOD_SAME_CREATOR_APPROVER` | Created and approved by the same person | Saisi et approuvé par la même personne | Warning | Yes | — |
| `DUPLICATE_PAYMENT` | Possible duplicate payment | Paiement possiblement en double | Warning | No | — |
| `DUPLICATE_SUPPLIER_INVOICE` | Possible duplicate supplier invoice | Facture fournisseur possiblement en double | Warning | No | — |
| `UNMAPPED_GIFI` | Accounts not mapped to GIFI | Comptes non associés à l'IGRF | Warning | No | — |
| `MISSING_BN` | Registered without a Business Number | Inscrit sans numéro d'entreprise | Critical | No | — |
| `MISSING_LOCK_DATE` | No lock date | Aucune date de verrouillage | Warning | No | — |
| `UNBALANCED_CONVERSION` | Conversion balances incomplete or unbalanced | Soldes de conversion incomplets ou déséquilibrés | Critical | No | — |
| `DORMANT_USER_WITH_ADMIN` | Dormant user with user-management rights | Utilisateur inactif ayant le droit de gérer les utilisateurs | Warning | No | — |
| `CONTACT_BANK_DETAILS_CHANGED` | Contact bank details changed | Coordonnées bancaires d'un contact modifiées | Warning | No | — |
| `TAX_CODE_OVERRIDE_RATE` | Tax codes often changed from the account default | Codes de taxe souvent différents du code par défaut du compte | Info | No | — |

### Cash and journals

**`NEG_CASH` — Negative cash or bank balance.** A bank or cash account's running balance went
below zero: money was spent that was never in it. The finding shows the lowest balance and its
day, the day it first went negative and today's balance.
Parameters: *Fix source* — `Automatic` (a funded bank account when one covers the shortfall, else
the shareholder loan), `Transfer from a bank account` or `Shareholder loan`; *Shareholder loan
account code* (default `2900`).
Fix: a draft dated the first negative day, **Dr the account / Cr the funded bank or the
shareholder loan**, for the shortfall — e.g. Dr 1000 Petty Cash 994.17 / Cr 2900 Shareholder Loan
994.17 when the owner paid personally.
To clear it: post the draft (or record the missing deposit or transfer).

**`JOURNAL_TO_CASH` — Manual journal posts to a bank or cash account.** Money in or out of a
bank or cash account recorded by manual journal instead of a bank transaction, a payment or a
transfer — so it can't be reconciled. Parameter: *Minimum amount* (default 0.00).
To clear it: reverse the journal and record the money as spend or receive money, a bill payment or
a transfer.

**`EXPENSE_JOURNAL_NO_CONTACT` — Expense journal without a contact.** A manual journal records
an expense without saying who it was paid to (no accounts payable, no audit trail of the payment).
Parameter: *Minimum amount*. To clear it: enter purchases as bills or spend money with the
supplier, or set the contact on the expense lines.

**`EXPENSE_JOURNAL_NO_ATTACHMENT` — Expense journal without an attachment.** A manual journal
records an expense with no receipt attached. Parameter: *Minimum amount*. To clear it: attach the
receipt to the journal.

**`ROUND_AMOUNT` — Round amount journal.** A large manual journal for a round amount — an
estimate or a plug? Parameters: *From* (default 1,000.00, at least 1) and *Multiple of* (default
100.00). Acknowledge it when the estimate is intended (an accrual), with the reason.

**`WEEKEND_POSTING` — Weekend posting.** A journal posted by a person on a Saturday or Sunday in
the organisation's time zone (not UTC). Parameters: *Holidays too* (off) and *Province of the
holidays* (federal holidays when empty). Imports and system postings don't count.

**`BACKDATED` — Backdated posting.** A journal, invoice or bill posted more than *Days* after its
date (default 7, 1–365): it changes periods that may already have been reported. The finding
shows the document date, the posting date and the gap. Raising *Days* re-evaluates on the next run.

**`SOD_SAME_CREATOR_APPROVER` — Created and approved by the same person.** One person entered and
approved the same journal or bill (rows brought in by an import, or approvals within that person's
limit): no second pair of eyes. Pay runs join when payroll exists. No parameters.

**`DUPLICATE_PAYMENT` — Possible duplicate payment.** The same contact was paid the same amount
twice from a bank or cash account within *Days apart* (default 3, 0–60). To clear it: void or
reverse the duplicate, or mark it a false positive (two genuine payments).

**`DUPLICATE_SUPPLIER_INVOICE` — Possible duplicate supplier invoice.** Two bills of the same
supplier with the same invoice number once case, spaces, dashes and leading zeros are ignored
("INV-00123" = "inv 123"), or with totals within *Total within %* (default 1.00) and dates within
*Days apart* (default 10, 0–90).

### Tax

**`EXEMPT_ON_TAXABLE_ACCOUNT` — Exempt code on a normally taxable account.** The organisation is
registered (GST/HST or QST) and a line on an expense account that is normally taxable (operating
expenses, cost of sales) is coded *Exempt*: the input tax credit may be missed. One finding per
line. Parameter: *Accounts to leave out* (account codes separated by commas).
Fix: *Open Find & recode* with the search prefilled (journal, account, exempt code) and the
suggested code; the recode reverses and re-posts the journal with undo available.

**`TAX_CODE_OVERRIDE_RATE` — Tax codes often changed from the account default.** Over *Days
back* (default 90), more than *Share above (%)* (default 20) of the lines use another tax code
than their account's default, with at least *Minimum lines* (default 20): the defaults may be
wrong. To clear it: fix the accounts' default tax codes in the chart of accounts.

### Set-up and people

**`UNMAPPED_GIFI` — Accounts not mapped to GIFI.** Active accounts without a GIFI code: the T2
financial statements can't be prepared from the ledger as it is. One finding per organisation with
the count and the codes. Parameter: *Only accounts used* (off). To clear it: map the accounts in
**Accounting › Chart of accounts** (GIFI column).

**`MISSING_BN` — Registered without a Business Number.** The organisation has a CRA or Revenu
Québec registration (GST/HST, QST, payroll, corporate) but no Business Number on file. To clear
it: add the BN in **Settings › Tax registrations**.

**`MISSING_LOCK_DATE` — No lock date.** Posted activity exists in a month that ended more than
*Days* ago (default 30) and the lock date is empty or earlier: anyone can still change those
periods. The finding suggests that month's end as the lock date. To clear it: set it in
**Settings › Lock dates**.

**`UNBALANCED_CONVERSION` — Conversion balances incomplete or unbalanced.** The opening balances
brought over from the previous system are empty, don't balance or have no equity (no share
capital, shareholder loan or retained earnings). To clear it: complete **Accounting › Conversion
balances**.

**`DORMANT_USER_WITH_ADMIN` — Dormant user with user-management rights.** Someone who can add
people and change roles hasn't signed in for *Days* (default 60, 7–365; never signed in: counted
from joining). To clear it: remove the right in **Settings › Users and roles**, or acknowledge it.

**`CONTACT_BANK_DETAILS_CHANGED` — Contact bank details changed.** A supplier's or employee's bank
details changed in the last *Days back* (default 30): confirm the change with them, by a number you
already have, before paying.

## Teardown example (REFINED)

On the organisation as the Xero teardown found it (docs/xero_teardown.md §10.A) one nightly run
raises: `NEG_CASH` (Petty Cash −994.17, fix Dr 1000 / Cr 2900 994.17), `JOURNAL_TO_CASH`,
`EXPENSE_JOURNAL_NO_CONTACT` and `EXPENSE_JOURNAL_NO_ATTACHMENT` on both journals,
`EXEMPT_ON_TAXABLE_ACCOUNT` on all five expense lines, `BACKDATED` on journal 1 (dated 3 Jun,
posted 15 Jun), `MISSING_BN`, `MISSING_LOCK_DATE`, `UNMAPPED_GIFI` (0 of 7 mapped),
`UNBALANCED_CONVERSION` and `DORMANT_USER_WITH_ADMIN` — the gap tests gap-36, gap-53 and gap-59
(`backend/tests/test_assurance_teardown.py`, `frontend/e2e/gap-36-53-59.spec.ts`).

## Performance

An incremental run (one posting) takes well under the 2-second budget on a 100,000-line ledger,
and the nightly run of 500 organisations fits its window; the measurements and the full-scale
command (`make perf-assurance`) are in the [performance baseline](../perf/baseline-report.md).

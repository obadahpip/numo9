# ADR-0007: A bank account never depends on a feed, an import or a reconciliation

| | |
|---|---|
| **Status** | accepted (2026-11-28, on merge) |
| **Date** | 2026-11-28 |
| **Deciders** | Numo9 engineering; Profitex (product owner) through the Phase 1 plan, deliverable F-01 |
| **Deliverable / task** | F-01-T17 (gap-27, with F-07) |

## Context and problem statement

In the Xero teardown (docs/xero_teardown.md §5.1, gap 27) the bank module was tied to the plan
and to bank feeds: only "Credit card / Other" accounts were offered without a feed, and REFINED
ran with **no bank account at all**, booking cash by manual journal (which then drove Petty Cash
to −994.17). Numo9 adds statement imports (F-02), bank rules (F-04), reconciliation (F-05) and,
later, live feeds. The question is whether any of them may become a precondition for using a bank
account.

## Decision drivers

- A small business must be able to record money in and out on day one (gap 27).
- The ledger is the single source of truth; a bank balance shown anywhere must equal the trial
  balance and the Balance Sheet.
- Feeds are third-party services that fail, lag or aren't available for every institution.
- Banking is never a paid gate (the package matrix gives `accounting.banking.read` / `.write` to
  every package).

## Considered options

1. **Feed-optional bank accounts** — a bank account is a ledger account with a profile;
   transactions are entered by hand (spend / receive money, transfers F-06) and post through the
   posting engine at once; imports, feeds and reconciliation only *add* or *match* transactions.
2. Feed-first — a bank account needs a connected feed or an imported statement before
   transactions can be recorded (the Xero pattern).
3. Reconcile-to-post — transactions entered by hand stay "unconfirmed" until matched to a
   statement line, and reports exclude them meanwhile.

## Decision outcome

**Chosen option:** 1, "feed-optional bank accounts", because it is the only one that lets an
organisation work with no feed and keeps one balance — the ledger's.

- Creating a bank account (`POST bank-accounts`, type, name, institution, currency) creates its
  ledger account (F-01-T03) and the account is usable at once; nothing in its creation, its
  transactions or the reports reads a feed, a statement or a reconciliation.
- The balance shown is always the **ledger balance** (posted lines of its ledger account,
  F-01-T06). A statement balance is optional information beside it, never a replacement.
- Spend / receive money post a balanced journal straight away through `numo9.ledger.services`
  with the normal controls (tax codes G-01/G-02, contact and attachment rules C-03, lock dates,
  the cash guard).
- Statement imports, bank rules, feeds and reconciliation (F-02, F-04, F-05 and later) may create or match
  transactions; they never block posting, reporting, filing or closing, and "not reconciled" is
  shown as optional.
- An organisation without a bank account gets a dismissible prompt, never a block (F-01-T12).

### Consequences

- Good: gap 27 closed — a new organisation adds a chequing account and spends from it with no
  import, and the Balance Sheet shows it (`backend/tests/test_banking_gap27.py`,
  `frontend/e2e/gap-27.spec.ts`, marker `gap-27`).
- Good: one balance everywhere; no "bank balance vs book balance" ambiguity in reports.
- Bad: hand-entered transactions can later be duplicated by an import. Mitigated by matching on
  import (F-02 fingerprints, F-05 match suggestions) and the assurance rule `DUPLICATE_PAYMENT` (K-09).
- Bad: books can drift from the bank when nobody reconciles. Mitigated by the optional statement
  balance shown beside the ledger balance and the "Not reconciled — optional" chip; reconciliation
  stays a choice.

### Confirmation

The gap-27 tests above (CI `gap-tests` job) and the banking API tests; a change that makes a
banking write, a report or a filing depend on a feed, a statement or a reconciliation violates this
ADR and needs a superseding one.

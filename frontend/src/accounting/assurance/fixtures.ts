/**
 * Teardown-style findings (REFINED, docs/xero_teardown.md §10.A) as the API returns them — for
 * the component tests and the Playwright spec of the Assurance page (K-09-T21).
 */
import type { Finding, Severity, Summary } from "./api";

let seq = 0;

export function finding(
  rule: string,
  ruleName: string,
  severity: Severity,
  explanation: string,
  extra: Partial<Finding> = {},
): Finding {
  seq += 1;
  return {
    id: `f-${seq}`,
    rule,
    rule_name: ruleName,
    severity,
    status: "open",
    subject: { type: "ledger.JournalEntry", id: `s-${seq}`, label: `JE-00000${seq}` },
    amount: null,
    details: {},
    explanation,
    has_fix: false,
    source: { kind: "journal", path: `accounting/journals/s-${seq}` },
    first_seen: "2026-11-26T15:00:00Z",
    last_seen: "2026-11-26T15:00:00Z",
    resolved_at: null,
    ack_by: null,
    ack_at: null,
    reason: "",
    fix_entry: null,
    ...extra,
  };
}

export const TEARDOWN_FINDINGS: Finding[] = [
  finding(
    "NEG_CASH",
    "Negative cash or bank balance",
    "critical",
    "Petty Cash went below zero: −994.17 on 15 Jun 2026 (today −994.17). Cash on hand can't be negative: money was spent from it that was never put in.",
    {
      id: "neg-cash",
      amount: "-994.17",
      has_fix: true,
      subject: { type: "ledger.Account", id: "acc-1000", label: "1000 · Petty Cash" },
      source: { kind: "account", path: "accounting/chart-of-accounts?account=acc-1000" },
    },
  ),
  finding(
    "MISSING_BN",
    "Registered without a Business Number",
    "critical",
    "The organisation is registered (GST/HST program account (RT)) but has no Business Number (BN).",
    { source: { kind: "settings", path: "settings/tax-registrations" } },
  ),
  finding(
    "UNBALANCED_CONVERSION",
    "Conversion balances incomplete or unbalanced",
    "critical",
    "The conversion at 1 Jan 2025: no opening balances were entered.",
  ),
  ...["JE-000001", "JE-000002"].map((journal, i) =>
    finding(
      "JOURNAL_TO_CASH",
      "Manual journal posts to a bank or cash account",
      "warning",
      `${journal} posts ${i ? "576.95" : "417.22"} to Petty Cash.`,
      { amount: i ? "576.95" : "417.22" },
    ),
  ),
  finding(
    "EXPENSE_JOURNAL_NO_CONTACT",
    "Expense journal without a contact",
    "warning",
    "JE-000001 (3 Jun 2026) records 417.22 of expenses with no supplier.",
    { amount: "417.22" },
  ),
  finding(
    "EXPENSE_JOURNAL_NO_ATTACHMENT",
    "Expense journal without an attachment",
    "warning",
    "JE-000001 (3 Jun 2026) records 417.22 of expenses with no receipt attached.",
    { amount: "417.22" },
  ),
  finding(
    "EXEMPT_ON_TAXABLE_ACCOUNT",
    "Exempt code on a normally taxable account",
    "warning",
    "JE-000001 line 1: 300.00 on 5590 · Business Fees & Licenses is coded purchase.exempt.",
    { amount: "300.00", has_fix: true },
  ),
  finding(
    "BACKDATED",
    "Backdated posting",
    "warning",
    "JE-000001 is dated 3 Jun 2026 but was posted on 15 Jun 2026 (12 days later; the limit is 7).",
  ),
  finding(
    "MISSING_LOCK_DATE",
    "No lock date",
    "warning",
    "The general ledger lock date is not set.",
  ),
  finding(
    "UNMAPPED_GIFI",
    "Accounts not mapped to GIFI",
    "warning",
    "7 of 7 active accounts have no GIFI code.",
  ),
  finding(
    "DORMANT_USER_WITH_ADMIN",
    "Dormant user with user-management rights",
    "warning",
    "Dana Lee can manage users but hasn't signed in since 26 Jul 2026 (123 days).",
  ),
];

export const TEARDOWN_SUMMARY: Summary = {
  score: 20,
  open: { critical: 3, warning: 10, info: 0 },
  statuses: { open: 13, acknowledged: 0, resolved: 0, false_positive: 0 },
  attention: 13,
  rules: [],
  last_run: {
    id: "run-1",
    trigger: "nightly",
    started_at: "2026-11-26T08:47:00Z",
    finished_at: "2026-11-26T08:47:05Z",
  },
};

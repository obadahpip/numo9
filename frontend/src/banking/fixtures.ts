/** Bank accounts as the API returns them (F-01-T07), for component tests and stories. */
import type { BankAccount } from "./api";

export const ORG = "refined";

export function bankAccount(over: Partial<BankAccount> = {}): BankAccount {
  return {
    id: "6ca1b880-64f7-4053-80e3-0c3618895553",
    type: "chequing",
    type_label: "Chequing",
    display_name: "TD Business Chequing",
    institution: "TD Canada Trust",
    currency: "CAD",
    masked_number: "•••• 4821",
    ledger_account: { id: "a1", code: "1000", name: "TD Business Chequing" },
    ledger_balance: "12450.30",
    statement_balance: null,
    statement_balance_date: null,
    is_reconciled_tracking: false,
    is_liability: false,
    archived_at: null,
    transaction_count: 4,
    last_activity: "2026-06-15",
    ...over,
  };
}

export const ACCOUNTS: BankAccount[] = [
  bankAccount({ statement_balance: "12500.00", statement_balance_date: "2026-06-30" }),
  bankAccount({
    id: "7b3c1d2e-0000-4000-8000-000000000002",
    type: "credit_card",
    type_label: "Credit card",
    display_name: "Visa Business",
    institution: "RBC Royal Bank",
    masked_number: "•••• 0042",
    ledger_account: { id: "a2", code: "2100", name: "Visa Business" },
    ledger_balance: "-1200.00",
    is_liability: true,
    last_activity: "2026-06-12",
  }),
  bankAccount({
    id: "8c4d2e3f-0000-4000-8000-000000000003",
    type: "cash",
    type_label: "Cash / petty cash",
    display_name: "Petty Cash",
    institution: "",
    masked_number: "",
    ledger_account: { id: "a3", code: "1010", name: "Petty Cash" },
    ledger_balance: "-417.22",
    transaction_count: 0,
    last_activity: null,
  }),
];

export function serveJson(
  handler: (url: string, init?: RequestInit) => { status?: number; body: unknown },
) {
  return async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/api/v1/auth/csrf")) {
      return new Response(JSON.stringify({ csrfToken: "t" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    const { status = 200, body } = handler(url, init);
    return new Response(status === 204 ? null : JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  };
}

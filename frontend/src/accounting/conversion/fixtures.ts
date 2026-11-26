/** Conversion API answers for the C-05 component tests and the Playwright specs. */
import type { Difference, Overview, Session, StepKey } from "./api";

export const ORG = "acme";

export function difference(over: Partial<Difference> = {}): Difference {
  return {
    debits: "0.00",
    credits: "0.00",
    difference: "0.00",
    balanced: true,
    lines: 0,
    controls: [],
    accounts: [],
    warnings: [],
    opening_equity_missing: true,
    reasons: [{ code: "conversion.empty", message: "Enter at least one opening balance." }],
    can_finalise: false,
    ...over,
  };
}

export function session(over: Partial<Session> = {}): Session {
  return {
    id: "s1",
    conversion_date: "2026-01-01",
    status: "draft",
    lock_balances: false,
    step: "bank",
    completed_steps: ["date"],
    finalised_by: null,
    finalised_at: null,
    opening_entry: null,
    corrections: [],
    ...over,
  };
}

const STEP_LABELS: Record<StepKey, string> = {
  date: "Conversion date",
  bank: "Bank and cash",
  invoices: "Open invoices",
  bills: "Open bills",
  other: "Other balances",
  review: "Review",
};

export function overview(over: Partial<Overview> = {}): Overview {
  return {
    session: session(),
    difference: difference(),
    steps: (Object.keys(STEP_LABELS) as StepKey[]).map((key) => ({
      key,
      label: STEP_LABELS[key],
    })),
    is_adviser: false,
    ...over,
  };
}

export const ACCOUNTS = [
  {
    id: "a-1010",
    code: "1010",
    name: "Chequing account",
    description: "",
    type: "asset",
    type_label: "Asset",
    subtype: "bank",
    subtype_label: "Bank",
    parent: null,
    depth: 1,
    has_children: false,
    system_role: "",
    system_role_label: "",
    is_bank: true,
    gifi: null,
    require_contact: false,
    require_tracking: false,
    require_attachment: false,
    default_tax_key: "",
    status: "active",
    archived_at: null,
    balance: { accounting: "0.00", tax: "0.00" },
  },
  {
    id: "a-3000",
    code: "3000",
    name: "Common shares",
    description: "",
    type: "equity",
    type_label: "Equity",
    subtype: "share_capital",
    subtype_label: "Share capital",
    parent: null,
    depth: 1,
    has_children: false,
    system_role: "",
    system_role_label: "",
    is_bank: false,
    gifi: null,
    require_contact: false,
    require_tracking: false,
    require_attachment: false,
    default_tax_key: "",
    status: "active",
    archived_at: null,
    balance: { accounting: "0.00", tax: "0.00" },
  },
];

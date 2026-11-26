import type { CategoryList, ExpenseClaim } from "./api";

/** An expense claim awaiting approval (shapes of numo9/purchases/expense_api.py). */
export const CLAIM_ID = "e1e1e1e1-0000-4000-8000-000000000001";

export function claimFixture(over: Partial<ExpenseClaim> = {}): ExpenseClaim {
  return {
    id: CLAIM_ID,
    number: "EXP-0001",
    title: "Kingston client visit",
    status: "submitted",
    status_label: "Awaiting approval",
    claimant: { id: "u-clerk", name: "Clerk" },
    submitted_by: { id: "u-clerk", name: "Clerk" },
    submitted_at: "2026-06-15T14:00:00Z",
    decided_by: null,
    decided_at: null,
    rejection_reason: "",
    currency: "CAD",
    total: "129.50",
    notes: "",
    lines: [
      {
        id: "l1",
        kind: "receipt",
        date: "2026-06-15",
        description: "",
        account: { id: "a1", code: "6100", name: "Meals and entertainment" },
        amount: "56.50",
        merchant: "Bistro 21",
        tax_code: { id: "t1", code: "purchase.ON.standard" },
        receipt: { id: "d1", name: "bistro.jpg" },
        split: {
          gross: "56.50",
          net: "50.00",
          tax: "6.50",
          claimable: "3.25",
          cost: "3.25",
          expense: "53.25",
        },
      },
      {
        id: "l2",
        kind: "mileage",
        date: "2026-06-15",
        description: "",
        account: null,
        amount: "73.00",
        from_place: "Office",
        to_place: "Kingston",
        distance_km: "100.0",
        rate_detail: [{ tier: "first", km: "100.0", rate: "0.73", amount: "73.00" }],
      },
    ],
    warnings: [],
    can_approve: true,
    blocked: null,
    ...over,
  };
}

/** The form's categories (most used first) and tax codes (`GET expense-claims/categories`). */
export function categoriesFixture(): CategoryList {
  const names: [string, string, string, number][] = [
    ["c-travel", "6200", "Travel", 4],
    ["c-meals", "6010", "Meals and entertainment", 2],
    ["c-office", "6080", "Office supplies", 0],
    ["c-phone", "6110", "Telephone and internet", 0],
    ["c-software", "6100", "Computer and software", 0],
    ["c-vehicle", "6210", "Vehicle expenses", 0],
    ["c-training", "6190", "Training and education", 0],
    ["c-post", "6090", "Postage and courier", 0],
  ];
  return {
    categories: names.map(([id, code, name, used]) => ({
      id,
      code,
      name,
      used,
      itc_restriction_pct: code === "6010" ? "50" : null,
    })),
    tax_codes: [
      { id: "t-on", code: "purchase.ON.standard", name: "HST 13% (ON)" },
      { id: "t-qc", code: "purchase.QC.standard", name: "GST 5% + QST 9.975% (QC)" },
    ],
    default_tax_code: "t-on",
  };
}

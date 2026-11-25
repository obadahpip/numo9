import type { ExpenseClaim } from "./api";

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

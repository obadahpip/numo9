import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * E-04-T11 — expense claim approver view: an approver approves; for the person who submitted the
 * claim Approve and Reject are hidden, with the reason. Rules on the server:
 * backend/tests/test_expense_claim_workflow.py and test_expense_claim_approver.py.
 */
const ORG = "acme";
const ID = "e1e1e1e1-0000-4000-8000-000000000001";

const claim = (over: Record<string, unknown> = {}) => ({
  id: ID,
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
});

test("an approver approves the claim", async ({ page }) => {
  await mockCsrf(page);
  let approved = false;
  await page.route(`**/api/v1/o/${ORG}/expense-claims/${ID}/approve`, (r) => {
    approved = true;
    return r.fulfill({
      json: claim({
        status: "approved",
        status_label: "Approved",
        can_approve: false,
        blocked: "status",
      }),
    });
  });
  await page.route(`**/api/v1/o/${ORG}/expense-claims/${ID}`, (r) => r.fulfill({ json: claim() }));
  await page.goto(`/o/${ORG}/purchases/expense-claims/${ID}`);
  await expect(page.getByRole("heading", { name: "Expense claim EXP-0001" })).toBeVisible();
  await expect(page.getByText("Office → Kingston, 100.0 km")).toBeVisible();
  await expectAccessible(page);
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Claim approved." })).toBeVisible();
  expect(approved).toBe(true);
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
});

test("Approve is hidden for the submitter", async ({ page }) => {
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/expense-claims/${ID}`, (r) =>
    r.fulfill({ json: claim({ can_approve: false, blocked: "self" }) }),
  );
  await page.goto(`/o/${ORG}/purchases/expense-claims/${ID}`);
  await expect(page.getByRole("heading", { name: "Expense claim EXP-0001" })).toBeVisible();
  await expect(page.getByText(/This is your claim/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Reject" })).toHaveCount(0);
});

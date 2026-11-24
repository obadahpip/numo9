import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * C-04-T12 — approvals inbox: approve from the keyboard (A); self-created items say "You created
 * this" with no Approve button; limit indicator; axe clean. Rules on the server:
 * backend/tests/test_approvals_inbox.py and test_journal_workflow_api.py.
 */
const ORG = "acme";
const row = (id: string, title: string, over: Record<string, unknown> = {}) => ({
  kind: "journal",
  id,
  title,
  subtitle: "",
  amount: "2400.00",
  date: "2026-06-30",
  url: `/o/${ORG}/accounting/journals/${id}`,
  submitted_by: { id: "u1", name: "Ava" },
  submitted_at: `2026-06-30T12:00:0${id.length % 9}Z`,
  created_by: { id: "u1", name: "Ava" },
  can_approve: true,
  blocked: null,
  limit: "5000.00",
  ...over,
});

test.use({ viewport: { width: 1440, height: 900 } });

test("approve with A; own items can't be approved", async ({ page }) => {
  await mockCsrf(page);
  let items = [
    row("j1", "Kingsway lease"),
    row("j22", "My own accrual", { can_approve: false, blocked: "self" }),
  ];
  const approved: string[] = [];
  await page.route(`**/api/v1/o/${ORG}/approvals`, (r) =>
    r.fulfill({
      json: {
        results: items,
        kinds: [],
        counts: { total: items.length, can_approve: items.filter((i) => i.can_approve).length },
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/journals/*/approve`, (r) => {
    const id = r.request().url().split("/").at(-2)!;
    approved.push(id);
    items = items.filter((i) => i.id !== id);
    return r.fulfill({ json: { id, status: "posted" } });
  });
  await page.route(`**/api/v1/o/${ORG}/journals/j*`, (r) =>
    r.fulfill({
      json: {
        id: "j1",
        lines: [
          {
            line: 1,
            account: { id: "a", code: "5400", name: "Rent" },
            debit: "2400.00",
            credit: "0.00",
          },
          {
            line: 2,
            account: { id: "b", code: "1000", name: "Chequing" },
            debit: "0.00",
            credit: "2400.00",
          },
        ],
      },
    }),
  );
  await page.goto(`/o/${ORG}/approvals`);
  await expect(page.getByText("Your limit $5,000.00")).toBeVisible();
  const own = page.locator("[data-item='j22']");
  await expect(own).toContainText("You created this");
  await own.click();
  await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
  await expectAccessible(page);

  await page.locator("[data-item='j1']").click();
  await expect(page.getByRole("button", { name: "Approve" })).toBeVisible();
  await page.getByRole("listbox", { name: "Waiting for approval" }).focus();
  await page.keyboard.press("a");
  await expect(page.getByText("Approved and posted.")).toBeVisible();
  expect(approved).toEqual(["j1"]);
  await expect(page.locator("[data-item='j1']")).toHaveCount(0);
});

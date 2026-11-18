import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";
import { entitlements, mockEntitlements } from "./entitlements-fixtures";

/**
 * U-07-T12 demo bar: visible on every page of a demo (never elsewhere), the watermark tag, reset
 * with its progress, start my free trial (and the sign-up-first answer), the demo outbox.
 * Rules are tested on the real API in backend/tests/test_demo_*.py.
 */
const ORG = "acme";
const NEW_ORG = "99999999-9999-4999-8999-999999999999";

async function mockPage(page: Page, reason: string) {
  // The guided tour (U-07-T13, e2e/demo-tour.spec.ts) was already dismissed in this browser.
  await page.addInitScript(() => localStorage.setItem("numo9.demoTour.dismissed", "1"));
  await mockCsrf(page);
  await mockEntitlements(page, ORG, entitlements({ reason, status: reason }));
  await page.route("**/api/v1/o/acme/contacts?*", (r) =>
    r.fulfill({
      json: {
        results: [],
        count: 0,
        next_offset: null,
        role_counts: { customer: 0, supplier: 0, contractor: 0, government_agency: 0, employee: 0 },
      },
    }),
  );
}

test("no demo bar outside a demo", async ({ page }) => {
  await mockPage(page, "active");
  await page.goto(`/o/${ORG}/contacts`);
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.locator("[data-demo-bar]")).toHaveCount(0);
});

test("demo bar: watermark, reset with progress, outbox", async ({ page }) => {
  await mockPage(page, "demo");
  let release: () => void = () => {};
  const resetDone = new Promise<void>((resolve) => (release = resolve));
  let resets = 0;
  await page.route("**/api/v1/o/acme/demo/reset", async (r) => {
    resets += 1;
    await resetDone;
    await r.fulfill({ json: { seed_version: 1 } });
  });
  await page.route("**/api/v1/o/acme/demo/outbox", (r) =>
    r.fulfill({
      json: {
        results: [
          {
            id: 1,
            to_email: "priya@lakeshorehw.example",
            subject: "Statement from Maple & Pine Supply Co.",
            text_body: "Your statement is attached.",
            kind: "statement",
            created_at: "2026-11-19T14:00:00Z",
          },
        ],
      },
    }),
  );
  await page.goto(`/o/${ORG}/contacts`);
  const bar = page.getByRole("region", { name: "Demo organisation" });
  await expect(bar).toBeVisible();
  await expect(bar.locator("[data-demo-watermark]")).toHaveText("Demo");
  await expectAccessible(page);

  await bar.getByRole("button", { name: "Demo outbox" }).click();
  const drawer = page.getByRole("dialog", { name: "Demo outbox" });
  await expect(drawer.getByText("Statement from Maple & Pine Supply Co.")).toBeVisible();
  await expect(drawer.getByText(/To priya@lakeshorehw\.example/)).toBeVisible();
  await drawer.getByRole("button", { name: "Close" }).click();

  await bar.getByRole("button", { name: "Reset demo" }).click();
  const dialog = page.getByRole("dialog", { name: "Reset the demo?" });
  await dialog.getByRole("button", { name: "Reset", exact: true }).click();
  await expect(dialog.getByRole("progressbar", { name: "Resetting the demo…" })).toBeVisible();
  release();
  await expect.poll(() => resets).toBe(1);
  await expect(page.locator("[data-demo-bar]")).toBeVisible();
});

test("start my free trial: sign up first, then the new organisation", async ({ page }) => {
  await mockPage(page, "demo");
  let anonymous = true;
  let body: Record<string, unknown> = {};
  await page.route("**/api/v1/o/acme/demo/convert", async (r) => {
    body = jsonBody(r);
    if (anonymous) {
      await r.fulfill({
        status: 409,
        json: { code: "demo.sign_up_first", detail: "Create your free Numo9 account first." },
      });
    } else {
      await r.fulfill({ status: 201, json: { id: NEW_ORG, name: "Maple & Pine" } });
    }
  });
  await page.route(`**/o/${NEW_ORG}/**`, (r) =>
    r.request().resourceType() === "document" ? r.fulfill({ body: "new org" }) : r.continue(),
  );
  await page.goto(`/o/${ORG}/contacts`);
  await page.getByRole("button", { name: "Start my free trial" }).click();
  const dialog = page.getByRole("dialog", { name: "Start your free trial" });
  await dialog.getByRole("textbox", { name: "Your organisation's name" }).fill("Maple & Pine");
  await dialog.getByRole("button", { name: "Start the trial" }).click();
  await expect(dialog.getByRole("link", { name: "Create your free account first." })).toBeVisible();
  expect(body).toEqual({ name: "Maple & Pine" });
  anonymous = false;
  await dialog.getByRole("button", { name: "Start the trial" }).click();
  await expect(page).toHaveURL(new RegExp(`/o/${NEW_ORG}/`));
});

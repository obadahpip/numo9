import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, jsonBody, mockCsrf } from "./auth-helpers";

/**
 * G-06 tax settings on one page. T08 — every tax setting is edited here (registrations with
 * their filing link, basis with reason and mid-year warning, default codes and rounding, quick
 * method, restricted ITCs) and the history drawer attributes every change. T09 — deep links
 * land on their card. The rules are tested on the real API in
 * backend/tests/test_tax_settings_api.py.
 */
const ORG = "acme";
const API = `**/api/v1/o/${ORG}`;
const PAGE = `/o/${ORG}/settings/registrations`;
const RT = {
  id: "aaaaaaaa-0000-4000-8000-0000000000aa",
  type: "rt",
  type_label: "GST/HST program account (RT)",
  number: "123456782RT0001",
  display_number: "123456782 RT 0001",
  effective_from: "2026-01-01",
  effective_to: null,
  status: "active",
  status_label: "Registered",
  cra_approval_ref: "",
  files_returns: true,
  filing: {
    frequency: "quarterly",
    periods: 12,
    next_due: { start: "2026-01-01", end: "2026-03-31", due_date: "2026-04-30", attention: "" },
    overdue: 0,
  },
};

interface Model {
  settings: Record<string, unknown>;
  changes: Record<string, unknown>[];
}

async function mockTax(page: Page, over: Record<string, unknown> = {}): Promise<Model> {
  const model: Model = {
    settings: {
      basis: "accrual",
      rounding_mode: "line",
      quick_method: false,
      quick_method_from: null,
      default_codes: {},
      restricted_itc_accounts: [{ id: "a-meals", code: "6400", name: "Meals", pct: "50" }],
      registered: true,
      ...over,
    },
    changes: [],
  };
  await mockCsrf(page);
  await page.route(`${API}/tax/registrations`, (r) => r.fulfill({ json: { results: [RT] } }));
  await page.route(`${API}/tax/settings`, (r) => {
    if (r.request().method() === "GET") return r.fulfill({ json: model.settings });
    const body = jsonBody(r);
    model.changes.push(body);
    if (body.basis && String(body.basis_reason ?? "").length < 10) {
      return r.fulfill({
        status: 400,
        json: { reason: ["Say why the tax basis changes (at least 10 characters)."] },
      });
    }
    const change = { ...body };
    delete change.basis_reason;
    model.settings = { ...model.settings, ...change };
    return r.fulfill({ json: { ...model.settings, basis_warning: "" } });
  });
  await page.route(`${API}/tax/settings/basis-check*`, (r) =>
    r.fulfill({
      json: {
        changes: true,
        mid_year: true,
        warning:
          "The fiscal year started on 2026-01-01: changing to the cash basis during the year leaves the returns already filed on the accrual basis.",
      },
    }),
  );
  await page.route(`${API}/tax/settings/restricted-itc/*`, (r) => {
    const body = jsonBody(r);
    model.changes.push({ restricted: r.request().url().split("/").pop(), ...body });
    const list =
      body.pct === null
        ? []
        : [
            { id: "a-meals", code: "6400", name: "Meals", pct: "50" },
            { id: "a-ent", code: "6500", name: "Entertainment", pct: String(body.pct) },
          ];
    model.settings = { ...model.settings, restricted_itc_accounts: list };
    return r.fulfill({ json: { restricted_itc_accounts: list } });
  });
  await page.route(`${API}/tax/codes*`, (r) =>
    r.fulfill({
      json: {
        results: r.request().url().includes("side=sales")
          ? [{ id: "c1", code: "sales.ON.standard", name: "HST 13 % (Ontario) on sales" }]
          : [{ id: "c2", code: "purchase.ON.standard", name: "HST 13 % (Ontario) on purchases" }],
      },
    }),
  );
  await page.route(`${API}/accounts*`, (r) =>
    r.fulfill({
      json: {
        count: 2,
        results: [
          { id: "a-meals", code: "6400", name: "Meals", type: "expense" },
          { id: "a-ent", code: "6500", name: "Entertainment", type: "expense" },
        ],
      },
    }),
  );
  const viewer = { time_format: "12h", time_zone: "America/Toronto", locale: "en-ca" };
  const event = (over2: Record<string, unknown>) => ({
    id: "e1",
    at: "2026-06-01T15:00:00Z",
    action: "tax.taxsettings.basis_changed",
    action_label: "Tax basis changed",
    verb: "updated",
    actor: {
      kind: "user",
      label: "Dana Lee",
      user: { id: "u1", name: "Dana Lee", email: "dana@refined.ca" },
      impersonator: null,
    },
    record: { type: "tax.TaxSettings", type_label: "Tax settings", id: "1", label: "Tax settings" },
    changes: [{ field: "basis", label: "Basis", old: "accrual", new: "cash", masked: false }],
    meta: { reason: "CRA approved the cash method" },
    ip: null,
    device: "",
    request_id: "",
    batch_id: null,
    is_batch_summary: false,
    ...over2,
  });
  await page.route(`${API}/audit/events*`, (r) =>
    r.fulfill({
      json: {
        results: [
          event({}),
          event({
            id: "e2",
            action_label: "Tax code created",
            actor: { kind: "system", label: "Tax table seed", user: null, impersonator: null },
            record: { type: "tax.TaxCode", type_label: "Tax code", id: "9", label: "HST 13 %" },
            changes: [],
            meta: { job: { id: "7f3c2a10-aaaa-4bbb-8ccc-000000000000", task: "seed" } },
          }),
        ],
        next: null,
        range: {
          from: "2026-01-01",
          to: "2026-12-31",
          default: true,
          time_zone: "America/Toronto",
        },
        viewer,
      },
    }),
  );
  return model;
}

const card = (page: Page, anchor: string) => page.locator(`[data-card="${anchor}"]`);

test.use({ viewport: { width: 1280, height: 1000 } });

test("T08 every tax setting is editable on the one page", async ({ page }) => {
  const model = await mockTax(page);
  await page.goto(PAGE);
  await expect(
    page.getByRole("heading", { level: 1, name: "Tax registrations and settings" }),
  ).toBeVisible();
  await expect(card(page, "registrations")).toContainText("Files quarterly");
  await expect(
    page.getByRole("link", { name: "Filing periods of GST/HST program account (RT)" }),
  ).toHaveAttribute("href", `/o/${ORG}/settings/tax/registrations/${RT.id}/filing`);
  await expectAccessible(page);

  // Tax basis: a reason is required; the mid-year warning shows before saving.
  await page.getByRole("button", { name: "Edit Tax basis" }).click();
  await card(page, "tax-basis").getByRole("radio", { name: /^Cash/ }).click();
  await expect(card(page, "tax-basis").locator("[data-basis-warning]")).toContainText(
    "during the year",
  );
  await card(page, "tax-basis").getByRole("button", { name: "Save" }).click();
  await expect(card(page, "tax-basis").getByRole("alert")).toContainText("Say why");
  await card(page, "tax-basis")
    .getByLabel(/Why the basis changes/)
    .fill("CRA approved cash");
  await card(page, "tax-basis").getByRole("button", { name: "Save" }).click();
  await expect(card(page, "tax-basis").locator("[data-value='basis']")).toHaveText("Cash");

  // Default codes and rounding.
  await page.getByRole("button", { name: "Edit Default codes" }).click();
  await card(page, "default-codes")
    .getByRole("combobox", { name: "Sales on revenue accounts" })
    .click();
  await page.getByRole("option", { name: "HST 13 % (Ontario) on sales" }).click();
  await card(page, "default-codes").getByRole("combobox", { name: "Rounding" }).click();
  await page.getByRole("option", { name: "Per document" }).click();
  await expectAccessible(page);
  await card(page, "default-codes").getByRole("button", { name: "Save" }).click();
  await expect(card(page, "default-codes")).toContainText("sales.ON.standard");
  await expect(card(page, "default-codes")).toContainText("Per document");

  // Quick method.
  await page.getByRole("button", { name: "Edit Quick method" }).click();
  await card(page, "quick-method").getByRole("switch", { name: "Quick method elected" }).click();
  await card(page, "quick-method").getByLabel("In effect from").fill("2026-01-01");
  await card(page, "quick-method").getByRole("button", { name: "Save" }).click();
  await expect(card(page, "quick-method")).toContainText("Elected from 2026-01-01");

  // Restricted ITCs.
  await page.getByRole("button", { name: "Edit Restricted input tax credits" }).click();
  await card(page, "restricted-itc").getByRole("combobox", { name: "Restrict an account" }).click();
  await page.getByRole("option", { name: "6500 Entertainment" }).click();
  await card(page, "restricted-itc").getByRole("button", { name: "Add" }).click();
  await expect(card(page, "restricted-itc").locator("[data-itc='6500']")).toBeVisible();

  expect(model.changes).toEqual([
    { basis: "cash", basis_reason: "" },
    { basis: "cash", basis_reason: "CRA approved cash" },
    { default_codes: { sales: { revenue: "sales.ON.standard" } }, rounding_mode: "document" },
    { quick_method: true, quick_method_from: "2026-01-01" },
    { restricted: "a-ent", pct: "50" },
  ]);
});

test("T08 history drawer: who (a person or a job with its id), old → new, the reason", async ({
  page,
}) => {
  await mockTax(page);
  await page.goto(PAGE);
  await page.getByRole("button", { name: "History" }).first().click();
  const drawer = page.getByRole("dialog", { name: "Tax settings history" });
  const rows = drawer.locator("[data-tax-history-list] > li");
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText("Tax basis changed · Tax settings");
  await expect(rows.nth(0).locator("[data-who]")).toHaveText("Dana Lee");
  await expect(rows.nth(0)).toContainText("Reason: CRA approved the cash method");
  await expect(rows.nth(1).locator("[data-who]")).toHaveText("Tax table seed (job 7f3c2a10)");
  await expectAccessible(page);
});

test("T08 not registered: the small-supplier explanation", async ({ page }) => {
  await mockTax(page, { registered: false });
  await page.goto(PAGE);
  await expect(page.getByRole("heading", { name: "Not registered for GST/HST?" })).toBeVisible();
  await expect(page.getByText(/small supplier/)).toBeVisible();
});

test("T09 deep links land on the card they name", async ({ page }) => {
  await mockTax(page);
  // From Settings → Tax codes: default codes and rounding.
  await page.route(`${API}/tax/codes*`, (r) => r.fulfill({ json: { results: [] } }));
  await page.goto(`/o/${ORG}/settings/tax-codes`);
  const defaults = page.locator("[data-tax-settings-link='default-codes']");
  await expect(defaults).toHaveAttribute("href", `${PAGE}#default-codes`);
  await defaults.click();
  await expect(page).toHaveURL(`${PAGE}#default-codes`);
  await expect(card(page, "default-codes")).toBeInViewport();

  // From a registration's filing periods: back to the registrations card.
  await page.route(`${API}/tax/registrations/${RT.id}/periods`, (r) =>
    r.fulfill({
      json: {
        registration: {
          id: RT.id,
          type: "rt",
          number: RT.display_number,
          start_date: "2026-01-01",
          stop_date: null,
        },
        today: "2026-06-01",
        results: [],
      },
    }),
  );
  await page.route(`${API}/tax/registrations/${RT.id}/cycles`, (r) =>
    r.fulfill({ json: { results: [] } }),
  );
  await page.goto(`/o/${ORG}/settings/tax/registrations/${RT.id}/filing`);
  const back = page.locator("[data-tax-settings-link='registrations']");
  await expect(back).toHaveAttribute("href", `${PAGE}#registrations`);
  await back.click();
  await expect(page).toHaveURL(`${PAGE}#registrations`);
  await expect(card(page, "registrations")).toBeInViewport();

  // Every anchor of the page is a card, and landing on it shows the card (short viewport).
  await page.setViewportSize({ width: 1280, height: 500 });
  for (const anchor of ["tax-basis", "quick-method", "restricted-itc"]) {
    await page.goto(`${PAGE}#${anchor}`);
    await expect(card(page, anchor)).toBeInViewport();
  }
  // The old entry points redirect to the one page.
  for (const alias of ["settings/tax", "tax-settings"]) {
    await page.goto(`/o/${ORG}/${alias}`);
    await expect(page).toHaveURL(new RegExp(`${PAGE}$`)); // the redirect may change the host name
  }
});

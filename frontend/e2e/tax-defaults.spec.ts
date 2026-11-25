import { expect, test, type Page } from "@playwright/test";

import { mockBillEditor, SUPPLIER } from "./bills-fixtures";

/**
 * G-02-T07 — the bill editor's tax cell auto-fills from the resolver (auto chip), a code picked
 * by hand is an override (the dot) that a supplier change doesn't touch; G-02-T08 — inline PST
 * and missing-province warnings that don't block saving (bill editor and receive money). The
 * resolver itself: backend/tests/test_tax_resolve_api.py.
 */
const ORG = "acme";
const QUEBEC = "5a5a5a5a-0000-4000-8000-000000000002";
const code = (id: string, key: string, name: string, side = "purchase") => ({
  id,
  code: key,
  version: 1,
  name,
  side,
  type: "taxable",
  province: "ON",
  effective_from: "2016-07-01",
  effective_to: null,
  expired: false,
  archived_at: null,
  rate: "13",
  components: [
    { id: `${id}c`, key: "hst_on", name: "HST", kind: "hst", rate: "13", recoverable_pct: null },
  ],
});
const ON = code("cccc0001-0000-4000-8000-000000000001", "purchase.ON.standard", "HST on purchases");
const QC = code(
  "cccc0002-0000-4000-8000-000000000002",
  "purchase.QC.standard",
  "GST and QST on purchases",
);
const EXEMPT = {
  ...code("cccc0003-0000-4000-8000-000000000003", "purchase.exempt", "Exempt purchases"),
  components: [],
};

function resolved(tax: typeof ON, extra: Record<string, unknown> = {}) {
  return {
    key: tax.code,
    tax_code: { id: tax.id, code: tax.code, name: tax.name, version: 1 },
    source: "place_of_supply",
    auto: true,
    explanation: "tax.pos.supplier_province",
    params: { province: "ON" },
    province: "ON",
    flags: [],
    warnings: [],
    ...extra,
  };
}

async function mockResolve(
  page: Page,
  answer: (body: { contact: string | null; lines: unknown[] }) => unknown[],
) {
  await page.route(`**/api/v1/o/${ORG}/tax/resolve`, (r) => {
    const body = r.request().postDataJSON() as { contact: string | null; lines: unknown[] };
    return r.fulfill({ json: { lines: answer(body) } });
  });
}

test("auto chip, override kept when the supplier changes, missing-province note", async ({
  page,
}) => {
  await mockBillEditor(page);
  await page.route(`**/api/v1/o/${ORG}/contacts?*`, (r) =>
    r.fulfill({
      json: {
        count: 2,
        next_offset: null,
        role_counts: {},
        results: [
          { id: SUPPLIER, display_name: "Cedar Supply Co.", roles: ["supplier"] },
          { id: QUEBEC, display_name: "Fournitures Laval", roles: ["supplier"] },
        ],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/codes*`, (r) =>
    r.fulfill({ json: { results: [ON, QC, EXEMPT] } }),
  );
  await mockResolve(page, (body) =>
    body.lines.map(() =>
      body.contact === QUEBEC
        ? resolved(QC, { params: { province: "QC" }, province: "QC" })
        : resolved(ON, { flags: ["missing_province"] }),
    ),
  );
  await page.goto(`/o/${ORG}/purchases/bills/new`);
  const form = page.getByRole("form", { name: "New bill" });
  await form.getByRole("combobox", { name: "Supplier" }).selectOption(SUPPLIER);
  const tax = (n: number) => page.getByRole("combobox", { name: `Tax code, line ${n}` });
  await expect(tax(1)).toHaveValue("HST on purchases");
  await expect(page.locator("[data-tax-auto]")).toHaveCount(1);
  await expect(page.locator('[data-tax-notice="missing_province"]')).toContainText(
    "no province on file",
  );
  await page.getByRole("button", { name: "Add a line" }).click();
  await expect(tax(2)).toHaveValue("HST on purchases");
  await tax(2).click();
  await page.getByRole("option", { name: /Exempt purchases/ }).click();
  await expect(
    page.getByRole("button", { name: /Changed from the default, line 2/ }),
  ).toBeVisible();
  await form.getByRole("combobox", { name: "Supplier" }).selectOption(QUEBEC);
  await expect(tax(1)).toHaveValue("GST and QST on purchases");
  await expect(tax(2)).toHaveValue("Exempt purchases");
  await expect(page.locator("[data-tax-notices]")).toHaveCount(0);
  await expect(form.getByRole("button", { name: "Save draft" })).toBeEnabled(); // never blocks
});

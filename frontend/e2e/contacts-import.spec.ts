import { expect, test } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * B-03-T12 import wizard (upload → match columns → review → import) and B-03-T13 template link
 * and help text. The engine and API are tested in backend/tests/test_imports_api.py and the
 * B-03 engine tests.
 */
const RUN = "33333333-3333-4333-8333-333333333333";
const FIELDS = [
  { key: "external_id", label: "External ID", required: false, match_key: true },
  { key: "display_name", label: "Display name", required: true, match_key: false },
  { key: "email", label: "Email", required: false, match_key: false },
];
const run = (over: Record<string, unknown> = {}) => ({
  id: RUN,
  entity: "contacts.contact",
  filename: "contacts.csv",
  status: "uploaded",
  rows: 2,
  headers: ["Identifiant externe", "Nom", "Notes"],
  columns: { "Identifiant externe": "external_id", Nom: "display_name", Notes: "" },
  options: {},
  counts: {},
  job: null,
  fields: FIELDS,
  samples: {
    "Identifiant externe": ["X-1", "X-2"],
    Nom: ["Maple Leaf Supply Ltd.", "Birch"],
    Notes: [""],
  },
  ...over,
});

test("upload, map, review and import", async ({ page }) => {
  await mockCsrf(page);
  let mapped: Record<string, unknown> = {};
  await page.route("**/api/v1/o/acme/imports", (r) => r.fulfill({ status: 201, json: run() }));
  await page.route(`**/api/v1/o/acme/imports/${RUN}/dry-run`, async (r) => {
    mapped = r.request().postDataJSON() as Record<string, unknown>;
    await r.fulfill({
      json: {
        ...run({ status: "reviewed", counts: { create: 1, update: 0, unchanged: 0, error: 1 } }),
        results: [],
      },
    });
  });
  await page.route(`**/api/v1/o/acme/imports/${RUN}/rows*`, (r) =>
    r.fulfill({
      json: {
        count: 2,
        results: [
          {
            row: 2,
            key: "X-1",
            label: "Maple Leaf Supply Ltd.",
            action: "create",
            changes: { display_name: ["", "Maple Leaf Supply Ltd."] },
            errors: [],
          },
          {
            row: 3,
            key: "X-2",
            label: "",
            action: "error",
            changes: {},
            errors: [
              {
                field: "billing_province",
                code: "contacts.import.province",
                message: "'Ontar' isn't a province or territory.",
              },
            ],
          },
        ],
      },
    }),
  );
  await page.route(`**/api/v1/o/acme/imports/${RUN}/apply`, (r) =>
    r.fulfill({ status: 202, json: run({ status: "applied", counts: { create: 1, error: 1 } }) }),
  );
  await page.goto("/o/acme/contacts/import");
  await expect(page.getByRole("heading", { name: "Import contacts", level: 1 })).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download a template with the right columns" }),
  ).toHaveAttribute("href", /imports\/template\?entity=contacts\.contact/);
  await expect(page.getByText(/never by its name/)).toBeVisible();
  await page.getByLabel("CSV or Excel file (25 MB at most)").setInputFiles({
    name: "contacts.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("Identifiant externe,Nom,Notes\nX-1,Maple Leaf Supply Ltd.,\n"),
  });
  await expectAccessible(page);
  await page.getByRole("button", { name: "Upload file" }).click();

  await expect(page.getByRole("heading", { name: "Step 2 of 4: Match columns" })).toBeVisible();
  await expect(page.getByText("e.g. Maple Leaf Supply Ltd., Birch")).toBeVisible();
  await page.getByRole("combobox", { name: "Field for the column Notes" }).click();
  await page.getByRole("option", { name: "Email" }).click();
  await page.getByLabel("Save this mapping as (optional)").fill("From Xero");
  await page.getByRole("button", { name: "Review the file" }).click();

  await expect(page.getByRole("heading", { name: "Step 3 of 4: Review" })).toBeVisible();
  await expect(page.getByText("1 new, 0 to update, 0 unchanged, 1 with errors.")).toBeVisible();
  await expect(page.getByText("'Ontar' isn't a province or territory.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Download the errors (CSV)" })).toBeVisible();
  expect(mapped).toMatchObject({ columns: { Notes: "email" }, save_mapping_as: "From Xero" });
  await expectAccessible(page);
  await page.getByRole("button", { name: "Import 1 row" }).click();
  await expect(page.getByRole("heading", { name: "Step 4 of 4: Import" })).toBeVisible();
  await expect(page.getByText("Import finished.")).toBeVisible();
});

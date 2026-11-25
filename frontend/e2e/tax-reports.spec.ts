import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * G-05-T10 — tax reports in the runner: the tax period presets, the tie-out card (green on the
 * fixture; red with the offending journal named), the audit flags as chips, a summary figure
 * drilling to the tax detail of its code. Server side: backend/tests/test_tax_report_*.py.
 */
const ORG = "acme";
const TAX_PARAMS = [
  { name: "date_from", kind: "date", default: null, choices: [], required: false },
  { name: "date_to", kind: "date", default: null, choices: [], required: false },
  { name: "period", kind: "text", default: "", choices: [], required: false },
  { name: "basis", kind: "choice", default: "", choices: ["", "accrual", "cash"], required: false },
  { name: "kind", kind: "choice", default: "all", choices: ["all", "gst_hst"], required: false },
  { name: "side", kind: "choice", default: "all", choices: ["all", "sales"], required: false },
];
const taxReport = (id: string, name: string) => ({
  id,
  slug: id.replace(/_/g, "-"),
  name,
  description: "",
  category: "tax",
  feature: "tax.reports.read",
  product: "tax",
  product_name: "Tax",
  params: TAX_PARAMS,
  available: true,
  favourite: false,
});
const CATALOGUE = {
  categories: [
    {
      key: "tax",
      reports: [
        taxReport("tax_summary", "Tax summary"),
        taxReport("tax_detail", "Tax detail by document"),
        taxReport("tax_audit", "Tax audit report"),
        taxReport("tax_tie_out", "Tax-to-GL tie-out"),
      ],
    },
  ],
  favourites: [],
  drafts: [],
  published: [],
  custom: [],
};
const HEADER = {
  title: "Tax-to-GL tie-out",
  display_name: "Refined Interiors",
  legal_name: "Refined Interiors Inc.",
  period_label: "1 Apr 2026 to 30 Jun 2026",
  status_label: "",
  basis_label: "Basis: Accrual (organisation default)",
  book_label: "Accounting book",
};
const COLUMNS = [
  { key: "gl", label: "GL movement" },
  { key: "report", label: "Tax report" },
  { key: "difference", label: "Difference" },
];

function tieOut(difference: string) {
  return {
    report: "tax_tie_out",
    params: {},
    columns: COLUMNS,
    rows: [
      {
        key: "control:gst_hst_payable",
        label: "2200 · GST/HST payable",
        kind: "row",
        level: 0,
        values: [(195 + Number(difference)).toFixed(2), "195.00", difference],
        drill: {
          account: "2200",
          ties: difference === "0.00",
          journals:
            difference === "0.00"
              ? []
              : [
                  {
                    journal: "JE-000007",
                    entry: "e-7",
                    date: "2026-05-31",
                    narration: "GST correction",
                    amount: difference,
                    url: `/o/${ORG}/accounting/journals/e-7`,
                  },
                ],
        },
      },
      {
        key: "control:itc_receivable",
        label: "1150 · GST/HST receivable (ITCs)",
        kind: "row",
        level: 0,
        values: ["143.00", "143.00", "0.00"],
        drill: { account: "1150", ties: true, journals: [] },
      },
    ],
    totals: [
      {
        key: "total",
        label: "Total difference",
        kind: "total",
        level: 0,
        values: [null, null, difference],
        drill: null,
      },
    ],
    alerts:
      difference === "0.00"
        ? [{ code: "tax.tie_out.ties", level: "info", message: "Ties to GL" }]
        : [{ code: "tax.tie_out.difference", level: "error", message: "Doesn't tie" }],
    header: HEADER,
    notes: "",
  };
}

async function mock(page: Page) {
  const runs: string[] = [];
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/reports`, (r) => r.fulfill({ json: CATALOGUE }));
  await page.route(`**/api/v1/o/${ORG}/reports/*/run*`, (r) => {
    const url = new URL(r.request().url());
    runs.push(url.pathname.split("/").at(-2) + url.search);
    const slug = url.pathname.split("/").at(-2);
    if (slug === "tax-tie-out") {
      return r.fulfill({
        json: tieOut(url.searchParams.get("period") === "last_filed" ? "10.00" : "0.00"),
      });
    }
    if (slug === "tax-audit") {
      return r.fulfill({
        json: {
          ...tieOut("0.00"),
          report: "tax_audit",
          columns: [
            { key: "rate", label: "Rate %" },
            { key: "basis", label: "Basis" },
            { key: "tax", label: "Tax" },
            { key: "recoverable", label: "Recoverable" },
          ],
          rows: [
            {
              key: "line:1",
              label: "2026-04-20 · JE-000003 · 1 · 6010 · Meals · purchase.ON.standard",
              kind: "row",
              level: 0,
              values: ["13.0000", "200.00", "26.00", "13.00"],
              drill: {
                flags: ["restricted_itc"],
                number: "BILL-0001",
                url: `/o/${ORG}/purchases/bills/b-1`,
              },
            },
            {
              key: "line:2",
              label: "2026-05-05 · JE-000004 · 1 · 6080 · Supplies · purchase.ON.standard",
              kind: "row",
              level: 0,
              values: ["13.0000", "1000.00", "130.00", "130.00"],
              drill: { flags: [], number: "BILL-0002", url: `/o/${ORG}/purchases/bills/b-2` },
            },
          ],
          totals: [],
          alerts: [],
          header: { ...HEADER, title: "Tax audit report" },
        },
      });
    }
    return r.fulfill({
      json: {
        report: slug === "tax-detail" ? "tax_detail" : "tax_summary",
        params: {},
        columns: [
          { key: "basis", label: "Basis" },
          { key: "tax", label: "Tax" },
          { key: "recoverable", label: "Recoverable" },
          { key: "non_recoverable", label: "Non-recoverable" },
        ],
        rows: [
          {
            key: "side:sales",
            label: "Sales — tax collected",
            kind: "section",
            level: 0,
            values: [null, null, null, null],
            drill: null,
          },
          {
            key: "code:sales:hst_on:sales.ON.standard",
            label: "sales.ON.standard",
            kind: "row",
            level: 2,
            values: ["1500.00", "195.00", "0.00", "0.00"],
            drill: {
              report: "tax_detail",
              from: "2026-04-01",
              to: "2026-06-30",
              basis: "accrual",
              side: "sales",
              component: "hst_on",
              code: "sales.ON.standard",
            },
          },
        ],
        totals: [],
        alerts: [],
        header: { ...HEADER, title: "Tax summary" },
        notes: "",
      },
    });
  });
  return runs;
}

test.use({ viewport: { width: 1440, height: 900 } });

test("tie-out card green on the fixture; red with the journal named", async ({ page }) => {
  const runs = await mock(page);
  await page.goto(`/o/${ORG}/reports/tax-tie-out?period=current`);
  const card = page.locator("[data-tie-out]");
  await expect(card).toHaveAttribute("data-tie-out", "ties");
  await expect(card).toContainText("✓ Ties to GL");
  expect(runs[0]).toContain("period=current");
  await expectAccessible(page);

  await page.getByRole("combobox", { name: "Tax period" }).click();
  await page.getByRole("option", { name: "Last filed period" }).click();
  await page.getByRole("button", { name: "Update" }).click();
  await expect(card).toHaveAttribute("data-tie-out", "difference");
  await expect(card).toContainText("Doesn't tie to GL: difference $10.00");
  const link = card.getByRole("link", { name: /JE-000007 · 2026-05-31 · GST correction/ });
  await expect(link).toHaveAttribute("href", `/o/${ORG}/accounting/journals/e-7`);
  expect(runs.at(-1)).toContain("period=last_filed");
});

test("audit flags as chips with the document link", async ({ page }) => {
  await mock(page);
  await page.goto(`/o/${ORG}/reports/tax-audit?period=current`);
  const flags = page.locator("[data-tax-flags]");
  await expect(flags.locator('[data-flag="restricted_itc"]')).toHaveText("Restricted ITC");
  await expect(flags.locator("[data-flag-row]")).toHaveCount(1);
  await expect(flags.getByRole("link", { name: "Open BILL-0001" })).toHaveAttribute(
    "href",
    `/o/${ORG}/purchases/bills/b-1`,
  );
  await expectAccessible(page);
});

test("a summary figure drills to the tax detail of its code", async ({ page }) => {
  const runs = await mock(page);
  await page.goto(`/o/${ORG}/reports/tax-summary?period=current`);
  const row = page.getByRole("row", { name: /sales\.ON\.standard/ });
  await row.hover();
  await row.getByRole("button").first().click();
  await expect(page).toHaveURL(/\/o\/acme\/reports\/tax-detail\?/);
  await expect(page).toHaveURL(/code=sales\.ON\.standard/);
  await expect.poll(() => runs.some((r) => r.startsWith("tax-detail"))).toBe(true);
});

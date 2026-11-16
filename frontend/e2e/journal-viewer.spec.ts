import { expect, test, type Page } from "@playwright/test";

import { expectAccessible, mockCsrf } from "./auth-helpers";

/**
 * C-02-T16 — Journal viewer: read-only detail with book badges and the reversal link.
 * Acceptance: renders the lines and the books — every line (account, contact, tax code, book
 * badge, debit/credit), a total row per book the entry touches, the entry's book badges; the
 * reversal link opens the reversing journal (and back); no edit control; a missing journal shows
 * the not-found state; French; axe clean.
 */
const ORG = "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6";
const FIRST = "aaaaaaaa-0000-4000-8000-000000000001";
const REVERSAL = "aaaaaaaa-0000-4000-8000-000000000003";
const MISSING = "aaaaaaaa-0000-4000-8000-0000000000ff";

const line = (
  n: number,
  code: string,
  name: string,
  side: { debit?: string; credit?: string },
  book: "both" | "accounting" | "tax" = "both",
  extra: Record<string, unknown> = {},
) => ({
  line: n,
  account: { id: `acc-${code}`, code, name },
  debit: side.debit ?? "0.00",
  credit: side.credit ?? "0.00",
  book,
  contact: null,
  description: "",
  tax_code: "",
  tracking: {},
  ...extra,
});

const first = {
  id: FIRST,
  number: "JE-000001",
  date: "2026-03-01",
  type: "sales",
  status: "reversed",
  narration: "Invoice INV-0042",
  source: { type: "sales.Invoice", id: "inv-42" },
  book_scope: "both",
  total: "1170.00",
  lines: [
    line(1, "1100", "Accounts receivable", { debit: "1130.00" }, "both", {
      contact: { id: "c1", name: "Érable Distribution inc." },
    }),
    line(2, "4000", "Sales", { credit: "1000.00" }),
    line(3, "2200", "GST/HST payable", { credit: "130.00" }, "both", { tax_code: "HST-ON" }),
    line(4, "6400", "Amortization", { debit: "40.00" }, "tax"),
    line(5, "1810", "Accumulated amortization", { credit: "40.00" }, "tax"),
  ],
  books: {
    accounting: { debit: "1130.00", credit: "1130.00" },
    tax: { debit: "1170.00", credit: "1170.00" },
  },
  reversal_of: null,
  reversed_by: { id: REVERSAL, number: "JE-000003" },
  posted_by: { id: "u1", name: "Olivia Tremblay" },
  posted_at: "2026-03-01T15:12:00Z",
  audit: [
    { action: "ledger.journalentry.posted", by: "Olivia Tremblay", at: "2026-03-01T15:12:00Z" },
    { action: "ledger.journalentry.reversed", by: "Olivia Tremblay", at: "2026-04-02T13:00:00Z" },
  ],
};

const reversal = {
  ...first,
  id: REVERSAL,
  number: "JE-000003",
  date: "2026-04-02",
  type: "reversal",
  status: "posted",
  narration: "Reversal of JE-000001",
  lines: first.lines.map((l) => ({ ...l, debit: l.credit, credit: l.debit })),
  reversal_of: { id: FIRST, number: "JE-000001" },
  reversed_by: null,
  audit: [first.audit[0]],
};

async function mock(page: Page) {
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/journals/*`, (route) => {
    const id = route.request().url().split("/").pop();
    if (id === FIRST) return route.fulfill({ json: first });
    if (id === REVERSAL) return route.fulfill({ json: reversal });
    return route.fulfill({ status: 404, json: { detail: "Not found." } });
  });
}

test.use({ viewport: { width: 1280, height: 1000 } });

test("renders lines and books, read-only, reversal link both ways", async ({ page }) => {
  await mock(page);
  await page.goto(`/o/${ORG}/accounting/journals/${FIRST}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Journal JE-000001");
  const header = page.locator("header", { has: page.locator("#journal-title") });
  await expect(header.getByText("Reversed", { exact: true })).toBeVisible();
  await expect(header.getByText("Accounting book", { exact: true })).toBeVisible();
  await expect(header.getByText("Tax book", { exact: true })).toBeVisible();

  const rows = page.locator("tbody tr");
  await expect(rows).toHaveCount(5);
  await expect(rows.nth(0)).toContainText("1100 Accounts receivable");
  await expect(rows.nth(0)).toContainText("Érable Distribution inc.");
  await expect(rows.nth(0)).toContainText("Both books");
  await expect(rows.nth(0)).toContainText("$1,130.00");
  await expect(rows.nth(2)).toContainText("HST-ON");
  await expect(rows.nth(3)).toContainText("Tax book");
  await expect(page.locator('[data-total="accounting"]')).toContainText("Total, accounting book");
  await expect(page.locator('[data-total="accounting"]')).toContainText("$1,130.00");
  await expect(page.locator('[data-total="tax"]')).toContainText("$1,170.00");
  await expect(page.getByText("sales.Invoice · inv-42")).toBeVisible();
  await expect(page.getByText(/by Olivia Tremblay/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Activity" })).toBeVisible();

  // Read-only: nothing to edit or save.
  await expect(page.getByRole("textbox")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /save|edit|delete/i })).toHaveCount(0);
  await expectAccessible(page);

  await page.getByRole("link", { name: "JE-000003" }).click();
  await expect(page).toHaveURL(new RegExp(`/accounting/journals/${REVERSAL}$`));
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Journal JE-000003");
  await expect(page.locator("[data-reverses]")).toHaveText("This journal reverses JE-000001.");
  await page.getByRole("link", { name: "JE-000001" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Journal JE-000001");
});

test("a missing journal shows the not-found state", async ({ page }) => {
  await mock(page);
  await page.goto(`/o/${ORG}/accounting/journals/${MISSING}`);
  await expect(
    page.getByText("There's no journal with this link in this organisation"),
  ).toBeVisible();
});

test("French", async ({ page, context, baseURL }) => {
  await context.addCookies([{ name: "numo9_locale", value: "fr-CA", url: baseURL! }]);
  await mock(page);
  await page.goto(`/o/${ORG}/accounting/journals/${FIRST}`);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Écriture JE-000001");
  await expect(page.locator('[data-total="tax"]')).toContainText("Total, livre fiscal");
  await expect(page.locator("[data-reversed-by]")).toHaveText("Contrepassée par JE-000003.");
  await expectAccessible(page);
});

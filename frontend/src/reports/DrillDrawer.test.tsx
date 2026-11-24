import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import type { DrillResult } from "./api";
import { drillQuery, linesCsv } from "./DrillDrawer";
import { BODY, CATALOGUE, ORG, row, serveJson } from "./fixtures";
import { ReportScreen } from "./ReportScreen";

/** K-01-T14 — drill drawer: the figure's lines, total = figure, Open invoice, pages. */
afterEach(() => vi.unstubAllGlobals());

const LINES: DrillResult = {
  account: { id: "a", code: "4000", name: "Sales" },
  total: "-6200.00",
  count: 1,
  page: 1,
  pages: 1,
  lines: [
    {
      date: "2026-05-03",
      journal: "JE-0007",
      narration: "Invoice INV-0001",
      description: "Design consultation",
      contact: "Maple & Pine",
      debit: "0.00",
      credit: "6200.00",
      amount: "-6200.00",
      status: "posted",
      source: {
        type: "sales.invoice",
        url: `/o/${ORG}/sales/invoices/i1`,
        journal_url: `/o/${ORG}/accounting/journals/j1`,
      },
    },
  ],
};

it("opens from a figure and links the line to its invoice (2 clicks)", async () => {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        if (url.endsWith("/reports")) return { body: CATALOGUE };
        if (url.includes("/drill")) return { body: LINES };
        return { body: BODY };
      }),
    ),
  );
  renderWithIntl(<ReportScreen org={ORG} slug="account-activity" />);
  await userEvent.click(
    await screen.findByRole("button", { name: "Show the lines of 4000 · Sales, Net movement" }),
  );
  const drawer = await screen.findByRole("dialog", { name: "4000 · Sales" });
  expect(await within(drawer).findByText("1 line · total -$6,200.00")).toBeVisible();
  expect(within(drawer).getByRole("link", { name: "Open invoice" })).toHaveAttribute(
    "href",
    `/o/${ORG}/sales/invoices/i1`,
  );
  expect(within(drawer).getByText("Journal JE-0007")).toBeVisible();
  expect(urls.at(-1)).toBe(
    `/api/v1/o/${ORG}/reports/account-activity/drill?account=4000&book=accounting&from=2026-05-01&to=2026-07-31&page=1`,
  );
});

it("takes per-column drill keys when the report gives them", () => {
  const target = {
    row: row({
      drill: {
        account: "4000",
        book: "accounting",
        columns: [
          { from: "2026-01-01", to: "2026-01-31" },
          { from: "2025-01-01", to: "2025-01-31" },
        ],
      } as unknown as Record<string, string>,
    }),
    column: 1,
  };
  expect(drillQuery(target)).toEqual({
    account: "4000",
    book: "accounting",
    from: "2025-01-01",
    to: "2025-01-31",
  });
});

it("exports the lines as CSV", () => {
  expect(linesCsv(LINES)).toBe(
    'date,journal,description,amount\r\n"2026-05-03","JE-0007","Design consultation","-6200.00"',
  );
});

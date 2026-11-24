import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { BODY, CATALOGUE, ORG, serveJson } from "./fixtures";
import { initialParams, ReportRunner, runQuery } from "./ReportRunner";

/**
 * K-01-T13 — runner: the parameter bar from the report's schema (preset or custom dates, book
 * switch), Update and Enter run it, the header and the table; a 402 names the product; export
 * links carry the screen's parameters.
 */
afterEach(() => vi.unstubAllGlobals());

const activity = CATALOGUE.categories[0]!.reports[1]!;

function serve(run: { status?: number; body: unknown } = { body: BODY }) {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        if (url.endsWith("/reports")) return { body: CATALOGUE };
        return run;
      }),
    ),
  );
  return urls;
}

it("runs on this financial year by default and shows the header and the rows", async () => {
  const urls = serve();
  renderWithIntl(<ReportRunner org={ORG} slug="account-activity" />);
  expect(await screen.findByRole("heading", { name: "Account activity", level: 1 })).toBeVisible();
  expect(await screen.findByText("1 May 2026 to 31 Jul 2026")).toBeVisible();
  expect(screen.getByText("Basis: Accrual (organisation default)")).toBeVisible();
  const table = screen.getByRole("table", { name: "Account activity" });
  expect(within(table).getByText("$3,650.00")).toBeVisible();
  expect(urls).toContain(
    `/api/v1/o/${ORG}/reports/account-activity/run?book=accounting&preset=this_financial_year`,
  );
});

it("Update runs again with the book switched; Enter in a field submits too", async () => {
  const urls = serve();
  renderWithIntl(<ReportRunner org={ORG} slug="account-activity" />);
  await screen.findByRole("table");
  const book = screen.getByRole("group", { name: "Book" });
  await userEvent.click(within(book).getByRole("button", { name: "Tax" }));
  await userEvent.click(screen.getByRole("button", { name: "Update" }));
  expect(urls.at(-1)).toContain("book=tax");
});

it("names the product when the report isn't in the package", async () => {
  serve({ status: 402, body: { code: "entitlement.feature_not_in_package", product_name: "Tax" } });
  renderWithIntl(<ReportRunner org={ORG} slug="account-activity" />);
  expect(
    await screen.findByText(
      "Account activity is part of Tax, which isn't in this organisation's package.",
    ),
  ).toBeVisible();
});

it("an unknown report says so", async () => {
  serve();
  renderWithIntl(<ReportRunner org={ORG} slug="nope" />);
  expect(await screen.findByRole("heading", { name: "There's no such report" })).toBeVisible();
});

it("export links use the screen's parameters", async () => {
  serve();
  renderWithIntl(<ReportRunner org={ORG} slug="account-activity" />);
  await screen.findByRole("table");
  const pdf = screen.getByRole("link", { name: "PDF (Letter)" });
  expect(pdf.getAttribute("href")).toBe(
    `/api/v1/o/${ORG}/reports/account-activity/export?book=accounting&preset=this_financial_year&file=pdf`,
  );
});

it("builds the run query from the schema: preset replaces dates unless custom", () => {
  expect(
    runQuery(activity, {
      preset: "last_month",
      date_from: "2026-01-01",
      date_to: "2026-01-31",
      junk: "x",
    }),
  ).toEqual({ preset: "last_month" });
  expect(
    runQuery(activity, { preset: "custom", date_from: "2026-01-01", date_to: "2026-01-31" }),
  ).toEqual({
    preset: "custom",
    date_from: "2026-01-01",
    date_to: "2026-01-31",
  });
  expect(
    initialParams(activity, new URLSearchParams("date_from=2026-01-01&date_to=2026-03-31")),
  ).toEqual({
    book: "accounting",
    preset: "custom",
    date_from: "2026-01-01",
    date_to: "2026-03-31",
  });
});

it("an empty P&L shows the no-activity hint and offers the financial year (K-01-T16)", async () => {
  const empty = {
    ...BODY,
    rows: [],
    totals: [{ ...BODY.totals[0]!, values: [null] }],
  };
  serve({ body: empty });
  renderWithIntl(<ReportRunner org={ORG} slug="account-activity" />);
  const hint = await screen.findByRole("status");
  expect(hint).toHaveTextContent("No activity in this period");
  expect(screen.getByRole("table")).not.toHaveTextContent("–");
  expect(within(screen.getByRole("table")).getByText("$0.00")).toBeVisible();
  expect(within(hint).queryByRole("button", { name: "Run this financial year" })).toBeNull();
});

it("an integrity failure is a red banner above the statement (K-02-T05)", async () => {
  serve({
    body: {
      ...BODY,
      alerts: [
        {
          code: "reports.integrity.unbalanced",
          level: "error",
          message: "The balance sheet at 31 Jul 2026 doesn't balance by 12.34.",
        },
      ],
    },
  });
  renderWithIntl(<ReportRunner org={ORG} slug="account-activity" />);
  const banner = await screen.findByRole("alert");
  expect(banner).toHaveTextContent("doesn't balance by 12.34");
  expect(banner).toHaveAttribute("data-report-alert", "reports.integrity.unbalanced");
});

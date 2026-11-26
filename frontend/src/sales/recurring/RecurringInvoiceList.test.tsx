import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { ORG, TEMPLATE_ID, recurringHandler, row, serveJson } from "./fixtures";
import { RecurringHistory, RecurringInvoiceList } from "./RecurringInvoiceList";

/**
 * D-04-T10 — the recurring invoices list (next and last run, status, the tabs with the server's
 * counts, the generated and skipped counts) and the generated history tab (the invoice or the
 * reason, the counts match the rows).
 */
afterEach(() => vi.unstubAllGlobals());

function serve(extra?: Parameters<typeof recurringHandler>[1]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(serveJson(recurringHandler(calls, extra))));
  return calls;
}

it("lists the templates with next and last run, status and counts", async () => {
  const calls = serve((url) =>
    url.includes("status=paused")
      ? {
          body: {
            count: 1,
            page: 1,
            pages: 1,
            counts: { active: 1, paused: 1, ended: 0 },
            results: [row({ id: "p1", name: "Rent", status: "paused", paused: true })],
          },
        }
      : undefined,
  );
  renderWithIntl(<RecurringInvoiceList org={ORG} />);
  const link = await screen.findByRole("link", { name: "Monthly bookkeeping" });
  expect(link).toHaveAttribute("href", `/o/${ORG}/sales/recurring-invoices/${TEMPLATE_ID}`);
  const cells = within(link.closest("tr")!);
  expect(cells.getByText("15 Jul 2026")).toBeVisible();
  expect(cells.getByText("15 Jun 2026")).toBeVisible();
  expect(cells.getByText("Every month")).toBeVisible();
  expect(cells.getByText("Active")).toBeVisible();
  expect(cells.getByText("1 invoice")).toBeVisible();
  expect(screen.getByRole("tab", { name: "All (1)" })).toHaveAttribute("aria-selected", "true");
  await userEvent.click(screen.getByRole("tab", { name: "Paused (0)" }));
  expect(await screen.findByRole("link", { name: "Rent" })).toBeVisible();
  expect(screen.getByRole("tab", { name: "Paused (1)" })).toHaveAttribute("aria-selected", "true");
  await waitFor(() => expect(calls.some((c) => c.url.includes("status=paused"))).toBe(true));
});

it("the history tab lists generated invoices and skipped dates", async () => {
  serve();
  renderWithIntl(<RecurringHistory org={ORG} id={TEMPLATE_ID} />);
  expect(
    await screen.findByRole("heading", { name: "Generated invoices and skipped dates" }),
  ).toBeVisible();
  expect(screen.getByText("1 invoice, 1 skipped")).toBeVisible();
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows).toHaveLength(2); // the counts match the rows
  expect(within(rows[0]!).getByRole("link", { name: "INV-0007" })).toBeVisible();
  expect(within(rows[0]!).getByText("$339.00")).toBeVisible();
  expect(within(rows[1]!).getByText("Skipped")).toBeVisible();
  expect(within(rows[1]!).getByText("The AR lock date is 31 May 2026.")).toBeVisible();
});

it("an empty list explains what recurring invoices are", async () => {
  serve((url) =>
    url.includes("/recurring-invoices?") || url.endsWith("/recurring-invoices")
      ? {
          body: {
            count: 0,
            page: 1,
            pages: 1,
            counts: { active: 0, paused: 0, ended: 0 },
            results: [],
          },
        }
      : undefined,
  );
  renderWithIntl(<RecurringInvoiceList org={ORG} />);
  expect(await screen.findByText("No recurring invoices here")).toBeVisible();
});

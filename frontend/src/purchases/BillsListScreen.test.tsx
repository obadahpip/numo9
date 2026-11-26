import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { BillsListScreen } from "./BillsListScreen";
import { ORG, serveJson } from "./fixtures";

/** E-02-T15 — bills list tabs with the overview's counts; `?tab=` opens a tab; server search. */
const TABS = [
  ["all", 8],
  ["draft", 2],
  ["awaiting_approval", 1],
  ["awaiting_payment", 4],
  ["overdue", 3],
  ["paid", 1],
  ["void", 0],
] as const;

const row = (over: Record<string, unknown>) => ({
  id: "b1",
  number: "BILL-0007",
  status: "awaiting_payment",
  status_label: "Awaiting payment",
  supplier: { id: "s1", name: "Cedar Supply Co." },
  supplier_invoice_no: "CS-1001",
  reference: "",
  date: "2026-08-01",
  due_date: "2026-08-31",
  total: "2500.00",
  amount_due: "2000.00",
  url: `/o/${ORG}/purchases/bills/b1`,
  ...over,
});

function serve() {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        const query = new URL(url, "http://x").searchParams;
        const tab = query.get("tab") ?? "all";
        const results =
          tab === "draft"
            ? [row({ id: "d1", number: "", status: "draft", status_label: "Draft" })]
            : [row({})];
        return {
          body: {
            count: results.length,
            page: 1,
            pages: 1,
            tab,
            counts: {},
            tabs: TABS.map(([key, count]) => ({ key, label: key, count, amount: "0.00" })),
            results,
          },
        };
      }),
    ),
  );
  return urls;
}

afterEach(() => vi.unstubAllGlobals());

describe("BillsListScreen (E-02-T15)", () => {
  it("opens the tab from the URL and shows every tab with its count", async () => {
    const urls = serve();
    renderWithIntl(<BillsListScreen org={ORG} initialTab="overdue" />);
    const tabs = screen.getByRole("tablist", { name: "Bills by status" });
    await waitFor(() =>
      expect(within(tabs).getByRole("tab", { name: /Overdue/ })).toHaveTextContent("3"),
    );
    expect(
      within(tabs)
        .getAllByRole("tab")
        .map((t) => t.textContent),
    ).toEqual([
      "All8",
      "Draft2",
      "Awaiting approval1",
      "Awaiting payment4",
      "Overdue3",
      "Paid1",
      "Void0",
    ]);
    expect(within(tabs).getByRole("tab", { name: /Overdue/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    expect(urls[0]).toContain("tab=overdue");
    expect(await screen.findByRole("link", { name: "BILL-0007" })).toHaveAttribute(
      "href",
      `/o/${ORG}/purchases/bills/b1`,
    );
    expect(screen.getByText("$2,000.00")).toBeInTheDocument();
  });

  it("switching tab asks the server for that tab; drafts show as Draft", async () => {
    const urls = serve();
    renderWithIntl(<BillsListScreen org={ORG} />);
    await screen.findByRole("link", { name: "BILL-0007" });
    await userEvent.click(screen.getByRole("tab", { name: /Draft/ }));
    expect(await screen.findByRole("link", { name: "Draft" })).toBeInTheDocument();
    expect(urls.at(-1)).toContain("tab=draft");
  });

  it("searches on the server", async () => {
    const urls = serve();
    renderWithIntl(<BillsListScreen org={ORG} />);
    await screen.findByRole("link", { name: "BILL-0007" });
    await userEvent.type(screen.getByRole("searchbox"), "CS-1001");
    await waitFor(() => expect(urls.at(-1)).toContain("q=CS-1001"));
  });
});

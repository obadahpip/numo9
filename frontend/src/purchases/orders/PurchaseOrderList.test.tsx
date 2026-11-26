import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import type { PurchaseOrderRow } from "./api";
import { LIST, order, orderHandler, ORG, PO_ID, serveJson } from "./fixtures";
import { allCount, PurchaseOrderList } from "./PurchaseOrderList";

/**
 * E-01-T13 — PO list: tabs per status with the server's counts (Partially received and
 * Received included; All = the sum), the tab asks the server for its status, "Create bill"
 * makes the draft bill of what was received and opens it.
 */
afterEach(() => vi.unstubAllGlobals());

const row = (over: Partial<PurchaseOrderRow>): PurchaseOrderRow => {
  const { id, number, status, status_label, supplier, reference, date, delivery_date, total, url } =
    order(over);
  return { id, number, status, status_label, supplier, reference, date, delivery_date, total, url };
};
const PARTIAL = row({ number: "PO-0002", status: "partially_received" });
const RECEIVED = row({
  id: "90909090-0000-4000-8000-000000000003",
  number: "PO-0003",
  status: "received",
});
const DRAFT = row({ id: "90909090-0000-4000-8000-000000000004" });

function serve() {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson(
        orderHandler(calls, (url, method) => {
          if (url.includes("/bills/from-po") && method === "POST")
            return { status: 201, body: { id: "b1b1b1b1-0000-4000-8000-000000000001" } };
          if (!url.includes("/purchase-orders") || url.includes(`/${PO_ID}`)) return undefined;
          const status = new URL(url, "http://x").searchParams.get("status");
          const all = [DRAFT, PARTIAL, RECEIVED];
          return {
            body: { ...LIST, results: status ? all.filter((r) => r.status === status) : all },
          };
        }),
      ),
    ),
  );
  return calls;
}

it("shows the status tabs with their counts and filters on the server", async () => {
  const calls = serve();
  renderWithIntl(<PurchaseOrderList org={ORG} />);
  const tabs = await screen.findByRole("tablist", { name: "Purchase orders by status" });
  await waitFor(() =>
    expect(within(tabs).getByRole("tab", { name: /All/ })).toHaveTextContent("3"),
  );
  expect(within(tabs).getByRole("tab", { name: /Partially received/ })).toHaveTextContent("1");
  expect(within(tabs).getByRole("tab", { name: /^Received/ })).toHaveTextContent("1");
  expect(within(tabs).getByRole("tab", { name: /Billed/ })).toHaveTextContent("0");
  expect(screen.getAllByRole("row")).toHaveLength(4);
  await userEvent.click(within(tabs).getByRole("tab", { name: /Partially received/ }));
  await waitFor(() => expect(screen.getAllByRole("row")).toHaveLength(2));
  expect(calls.some((c) => c.url.includes("status=partially_received"))).toBe(true);
  expect(screen.getByRole("link", { name: "Receive PO-0002" })).toHaveAttribute(
    "href",
    `/o/${ORG}/purchases/orders/${PO_ID}/receive`,
  );
});

it("creates a bill from a received PO and opens it", async () => {
  const calls = serve();
  const navigate = vi.fn();
  renderWithIntl(<PurchaseOrderList org={ORG} navigate={navigate} />);
  await userEvent.click(await screen.findByRole("button", { name: "Create bill from PO-0003" }));
  await waitFor(() =>
    expect(navigate).toHaveBeenCalledWith(
      `/o/${ORG}/purchases/bills/b1b1b1b1-0000-4000-8000-000000000001`,
    ),
  );
  expect(calls.find((c) => c.url.includes("/bills/from-po"))?.body).toEqual({
    purchase_order: RECEIVED.id,
  });
  expect(screen.queryByRole("button", { name: /Create bill from Draft/ })).toBeNull();
});

it("adds every status into All", () => {
  expect(allCount(LIST.counts)).toBe(3);
  expect(allCount({})).toBe(0);
});

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { order, orderHandler, ORG, PO_ID, serveJson, SUPPLIER, EXPENSE } from "./fixtures";
import { gridLine, limitVerdict, orderLines, PurchaseOrderEditor } from "./PurchaseOrderEditor";

/**
 * E-01-T11 — purchase order editor: the shared grid in purchase mode, the delivery block, the
 * limit indicator (within → Approve; above or no limit → Submit for approval); an approved PO
 * keeps its line ids when edited; a billed PO is read-only.
 */
afterEach(() => vi.unstubAllGlobals());

function serve(extra?: Parameters<typeof orderHandler>[1]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(serveJson(orderHandler(calls, extra))));
  return calls;
}

it("creates a purchase order with its delivery block and approves it within the limit", async () => {
  const calls = serve();
  const navigate = vi.fn();
  renderWithIntl(<PurchaseOrderEditor org={ORG} navigate={navigate} />);
  const form = await screen.findByRole("form", { name: "New purchase order" });
  await userEvent.selectOptions(
    await within(form).findByRole("combobox", { name: "Supplier" }),
    SUPPLIER,
  );
  await userEvent.type(screen.getByRole("textbox", { name: "Description, line 1" }), "Tiles");
  await userEvent.click(screen.getByRole("combobox", { name: "Account, line 1" }));
  await userEvent.click(await screen.findByRole("option", { name: /6100/ }));
  await userEvent.type(within(form).getByRole("textbox", { name: "Deliver to" }), "12 King St W");
  await userEvent.type(within(form).getByRole("textbox", { name: "Attention" }), "Site office");
  expect(await screen.findByRole("status", { name: "Approval limit" })).toHaveTextContent(
    /Within your approval limit of \$5,000\.00/,
  );
  await userEvent.click(within(form).getByRole("button", { name: "Approve" }));
  expect(await screen.findByText("PO-0001 is approved. Send it to the supplier.")).toBeVisible();
  await waitFor(() => expect(navigate).toHaveBeenCalledWith(`/o/${ORG}/purchases/orders/${PO_ID}`));
  const created = calls.find((c) => c.method === "POST" && c.url.endsWith("/purchase-orders"))!;
  expect(created.body).toMatchObject({
    supplier: SUPPLIER,
    delivery_address: "12 King St W",
    delivery_attention: "Site office",
    lines: [{ id: null, description: "Tiles", account: EXPENSE }],
  });
  expect(calls.some((c) => c.url.endsWith(`/${PO_ID}/approve`))).toBe(true);
}, 20_000); // a long keyboard flow: slow under a loaded CI runner

it("submits for approval when the total is above the limit", async () => {
  serve((url) =>
    url.endsWith(`/purchase-orders/${PO_ID}`)
      ? {
          body: order({ total: "6000.00", approval: { limit: null, within: false } }),
        }
      : undefined,
  );
  renderWithIntl(<PurchaseOrderEditor org={ORG} id={PO_ID} />);
  expect(await screen.findByRole("status", { name: "Approval limit" })).toHaveTextContent(
    "You have no purchase order approval limit: it goes to an approver.",
  );
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
  expect(await screen.findByText("Submitted: it is waiting for approval.")).toBeVisible();
});

it("edits an approved PO keeping its line ids, and says when it needs approval again", async () => {
  const approved = order({ number: "PO-0001", status: "approved", status_label: "Approved" });
  const calls = serve((url, method) => {
    if (url.endsWith(`/purchase-orders/${PO_ID}`) && method === "PATCH")
      return { body: order({ ...approved, status: "awaiting_approval", version: 2 }) };
    if (url.endsWith(`/purchase-orders/${PO_ID}`)) return { body: approved };
    return undefined;
  });
  renderWithIntl(<PurchaseOrderEditor org={ORG} id={PO_ID} />);
  expect(await screen.findByRole("link", { name: "Receive goods" })).toHaveAttribute(
    "href",
    `/o/${ORG}/purchases/orders/${PO_ID}/receive`,
  );
  await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
  expect(
    await screen.findByText("The total went up: the purchase order is waiting for approval again."),
  ).toBeVisible();
  const patched = calls.find((c) => c.method === "PATCH")!;
  expect(patched.body).toMatchObject({ version: 1, lines: [{ id: order().lines[0]!.id }] });
});

it("opens a billed PO read-only", async () => {
  serve((url) =>
    url.endsWith(`/purchase-orders/${PO_ID}`)
      ? { body: order({ number: "PO-0001", status: "billed", status_label: "Billed" }) }
      : undefined,
  );
  renderWithIntl(<PurchaseOrderEditor org={ORG} id={PO_ID} />);
  expect(
    await screen.findByText("Billed: this purchase order can't be edited any more."),
  ).toBeVisible();
  expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Cancel order" })).toBeNull();
});

it("converts lines and judges the limit", () => {
  const grid = gridLine(order().lines[0]!);
  expect(orderLines([grid], new Set([grid.id]))[0]).toMatchObject({ id: grid.id, quantity: "10" });
  expect(orderLines([grid], new Set())[0]?.id).toBeNull();
  expect(limitVerdict("5000.00", "5000.00")).toBe("within");
  expect(limitVerdict("5001.00", "5000.00")).toBe("above");
  expect(limitVerdict("1.00", null)).toBe("none");
});

it("creates the bill of what was received and opens it", async () => {
  const navigate = vi.fn();
  serve((url, method) => {
    if (url.endsWith(`/purchase-orders/${PO_ID}`))
      return { body: order({ number: "PO-0001", status: "received", status_label: "Received" }) };
    if (url.includes("/bills/from-po") && method === "POST")
      return { status: 201, body: { id: "b1b1b1b1-0000-4000-8000-000000000001" } };
    return undefined;
  });
  renderWithIntl(<PurchaseOrderEditor org={ORG} id={PO_ID} navigate={navigate} />);
  await userEvent.click(await screen.findByRole("button", { name: "Create bill" }));
  await waitFor(() =>
    expect(navigate).toHaveBeenCalledWith(
      `/o/${ORG}/purchases/bills/b1b1b1b1-0000-4000-8000-000000000001`,
    ),
  );
  expect(screen.getByRole("button", { name: "Close order" })).toBeVisible();
});

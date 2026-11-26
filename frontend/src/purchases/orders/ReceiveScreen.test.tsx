import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { LINE_1, order, orderHandler, ORG, partlyReceived, PO_ID, serveJson } from "./fixtures";
import { overBy, ReceiveScreen } from "./ReceiveScreen";

/**
 * E-01-T12 — receive screen: ordered / received / outstanding per line, Enter moves to the next
 * line and records on the last, an over-receipt warns as typed and needs "Receive anyway".
 */
afterEach(() => vi.unstubAllGlobals());

function serve(extra?: Parameters<typeof orderHandler>[1]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(serveJson(orderHandler(calls, extra))));
  return calls;
}

const approved = () => {
  const two = partlyReceived();
  return order({
    ...two,
    status: "approved",
    lines: two.lines.map((l) => ({ ...l, quantity_received: "0.0000", outstanding: l.quantity })),
  });
};

it("receives 6 of 10 with Enter-to-next and shows what is still outstanding", async () => {
  let current = approved();
  const calls = serve((url, method) => {
    if (url.endsWith("/receipts") && method === "POST") {
      current = partlyReceived();
      return {
        status: 201,
        body: { id: "r1", warnings: [], purchase_order_status: "partially_received" },
      };
    }
    if (url.endsWith(`/purchase-orders/${PO_ID}`)) return { body: current };
    return undefined;
  });
  renderWithIntl(<ReceiveScreen org={ORG} id={PO_ID} />);
  const tiles = await screen.findByRole("textbox", { name: "Receiving now: Tiles" });
  expect(screen.getByRole("row", { name: /Tiles/ })).toHaveTextContent("Tiles10010");
  await userEvent.type(tiles, "6{Enter}");
  expect(screen.getByRole("textbox", { name: "Receiving now: Grout" })).toHaveFocus();
  await userEvent.keyboard("{Enter}"); // last line: records the receipt
  expect(await screen.findByText("Receipt recorded. 8 still outstanding.")).toBeVisible();
  const posted = calls.find((c) => c.url.endsWith("/receipts"))!;
  expect(posted.body).toMatchObject({
    purchase_order: PO_ID,
    lines: [{ po_line: LINE_1, quantity: "6" }],
    confirm_over: false,
  });
  await waitFor(() =>
    expect(screen.getByRole("row", { name: /Tiles/ })).toHaveTextContent("Tiles1064"),
  );
});

it("warns as typed and confirms an over-receipt", async () => {
  const calls = serve((url, method) => {
    if (url.endsWith("/receipts") && method === "POST") {
      const body = (calls.at(-1)?.body ?? {}) as { confirm_over?: boolean };
      if (!body.confirm_over)
        return {
          status: 400,
          body: {
            code: "purchases.receipt.over_tolerance_confirm",
            detail: "This receives more than ordered: confirm to receive it anyway.",
            over: [{ line: "Tiles", ordered: "10.0000", received: "12.0000", allowed: "10.0000" }],
          },
        };
      return { status: 201, body: { id: "r1", warnings: [], purchase_order_status: "received" } };
    }
    if (url.endsWith(`/purchase-orders/${PO_ID}`)) return { body: approved() };
    return undefined;
  });
  renderWithIntl(<ReceiveScreen org={ORG} id={PO_ID} />);
  await userEvent.type(await screen.findByRole("textbox", { name: "Receiving now: Tiles" }), "12");
  expect(screen.getByText("2 more than ordered")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Record receipt" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Tiles: 12 received of 10 ordered (tolerance up to 10)",
  );
  await userEvent.click(screen.getByRole("button", { name: "Receive anyway" }));
  await waitFor(() =>
    expect(calls.filter((c) => c.url.endsWith("/receipts")).at(-1)?.body).toMatchObject({
      confirm_over: true,
      lines: [{ po_line: LINE_1, quantity: "12" }],
    }),
  );
  expect(calls.filter((c) => c.url.endsWith("/receipts"))).toHaveLength(2);
});

it("fills every outstanding quantity and refuses an empty receipt", async () => {
  const calls = serve((url) =>
    url.endsWith(`/purchase-orders/${PO_ID}`) ? { body: approved() } : undefined,
  );
  renderWithIntl(<ReceiveScreen org={ORG} id={PO_ID} />);
  await userEvent.click(await screen.findByRole("button", { name: "Record receipt" }));
  expect(screen.getByRole("alert")).toHaveTextContent(
    "Enter the quantity received on at least one line.",
  );
  await userEvent.click(screen.getByRole("button", { name: "Receive everything outstanding" }));
  expect(screen.getByRole("textbox", { name: "Receiving now: Grout" })).toHaveValue("4");
  expect(calls.some((c) => c.url.endsWith("/receipts"))).toBe(false);
});

it("computes the quantity over what was ordered", () => {
  expect(overBy("10", "6", "4")).toBe(0);
  expect(overBy("10", "6", "5")).toBe(1);
  expect(overBy("10", "0", "")).toBe(0);
});

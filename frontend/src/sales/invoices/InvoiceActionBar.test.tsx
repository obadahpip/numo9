import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { invoiceActions } from "./actionMatrix";
import { INVOICE_ID, ORG, PREVIEW, invoice, invoiceHandler, serveJson } from "./fixtures";
import { InvoiceScreen } from "./InvoiceScreen";

/**
 * D-03a-T14 — the action bar's state matrix, the posting preview drawer (its totals balance and
 * it lists each tax control account) and the period ribbon (open, AR-locked, GST/HST filed).
 */
const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: replace }) }));
afterEach(() => vi.unstubAllGlobals());

function serve(extra?: Parameters<typeof invoiceHandler>[1]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(serveJson(invoiceHandler(calls, extra))));
  return calls;
}

it("offers each status its actions", () => {
  expect(invoiceActions("new")).toEqual(["save", "approve", "preview"]);
  expect(invoiceActions("draft", { needsApproval: true })).toEqual([
    "save",
    "submit",
    "preview",
    "delete",
  ]);
  expect(invoiceActions("awaiting_approval")).toEqual(["approve_waiting", "preview"]);
  expect(invoiceActions("approved")).toContain("void");
  expect(invoiceActions("partially_paid")).not.toContain("void");
  expect(invoiceActions("void")).toEqual(["pdf", "copy", "preview"]);
});

it("previews the posting and approves", async () => {
  const calls = serve();
  renderWithIntl(<InvoiceScreen org={ORG} id={INVOICE_ID} />);
  const bar = await screen.findByRole("toolbar", { name: "Invoice actions" });
  expect(within(bar).getByRole("button", { name: "Delete draft" })).toBeVisible();
  await userEvent.click(within(bar).getByRole("button", { name: "Preview posting" }));
  const drawer = await screen.findByRole("dialog", { name: "What approval posts" });
  const table = await within(drawer).findByRole("table");
  expect(within(table).getByText("2200 · GST/HST payable")).toBeVisible();
  expect(within(table).getAllByText("$565.00")).toHaveLength(3); // AR debit, both totals
  await userEvent.keyboard("{Escape}");
  await userEvent.click(within(bar).getByRole("button", { name: "Approve" }));
  expect(await screen.findByText("Invoice INV-0001 approved and posted.")).toBeVisible();
  expect(calls.map((c) => `${c.method} ${c.url.split("/invoices")[1] ?? ""}`)).toEqual(
    expect.arrayContaining([`PATCH /${INVOICE_ID}`, `POST /${INVOICE_ID}/approve`]),
  );
  const posted = await screen.findByRole("toolbar", { name: "Invoice actions" });
  expect(within(posted).getByRole("button", { name: "Void" })).toBeVisible();
  expect(within(posted).queryByRole("button", { name: "Approve" })).toBeNull();
});

it("the ribbon names a filed GST/HST period", async () => {
  serve((url) =>
    url.endsWith("/preview")
      ? {
          body: {
            ...PREVIEW,
            period: {
              ...PREVIEW.period,
              tax_period: { ...PREVIEW.period.tax_period!, filed: true, status: "filed" },
            },
          },
        }
      : url.endsWith(`/invoices/${INVOICE_ID}`)
        ? { body: invoice() }
        : undefined,
  );
  renderWithIntl(<InvoiceScreen org={ORG} id={INVOICE_ID} />);
  const ribbon = await screen.findByRole("group", { name: "Period" });
  await waitFor(() => expect(ribbon).toHaveAttribute("data-period-ribbon", "blocked"));
  expect(ribbon).toHaveTextContent("GST/HST period 1 Apr 2026 – 30 Jun 2026 is filed");
});

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { InvoiceEditor, invoiceLines } from "./InvoiceEditor";
import { CUSTOMER, INVOICE_ID, ORG, REVENUE, invoice, invoiceHandler, serveJson } from "./fixtures";

/**
 * D-03a-T13 — the invoice editor: header, grid and totals; a new invoice's first line starts on
 * the revenue account, so a first invoice is a customer, a description, a price and Save; a
 * saved draft opens with its lines and attachments; a posted invoice is read-only.
 */
afterEach(() => vi.unstubAllGlobals());

function serve(extra?: Parameters<typeof invoiceHandler>[1]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(serveJson(invoiceHandler(calls, extra))));
  return calls;
}

it("creates a first invoice from a customer and one line", async () => {
  const calls = serve();
  const navigate = vi.fn();
  renderWithIntl(<InvoiceEditor org={ORG} navigate={navigate} />);
  const form = await screen.findByRole("form", { name: "New invoice" });
  const customer = within(form).getByRole("combobox", { name: "Customer" });
  await waitFor(() => expect(within(customer).getAllByRole("option")).toHaveLength(2));
  await userEvent.selectOptions(customer, CUSTOMER);
  await userEvent.type(screen.getByRole("textbox", { name: "Description, line 1" }), "Design");
  await userEvent.type(screen.getByRole("textbox", { name: "Unit price, line 1" }), "250");
  await userEvent.click(within(form).getByRole("button", { name: "Save draft" }));
  await waitFor(() =>
    expect(navigate).toHaveBeenCalledWith(`/o/${ORG}/sales/invoices/${INVOICE_ID}`),
  );
  const created = calls.find((c) => c.method === "POST" && c.url.endsWith("/invoices"))!;
  expect(created.body).toMatchObject({
    customer: CUSTOMER,
    tax_mode: "exclusive",
    lines: [{ description: "Design", unit_price: "250.00", account: REVENUE }],
    attachments: [],
  });
  expect(await screen.findByText("Draft saved.")).toBeVisible();
});

it("opens a saved draft with its lines and attachments", async () => {
  serve((url) =>
    url.endsWith(`/invoices/${INVOICE_ID}`)
      ? { body: invoice({ attachments: [{ id: "d1", name: "signed-po.pdf" }] }) }
      : undefined,
  );
  renderWithIntl(<InvoiceEditor org={ORG} id={INVOICE_ID} />);
  expect(await screen.findByRole("heading", { name: "Draft invoice" })).toBeVisible();
  expect(screen.getByRole("textbox", { name: "Description, line 1" })).toHaveValue(
    "Design consultation",
  );
  expect(screen.getByRole("textbox", { name: "Reference" })).toHaveValue("PO-778");
  expect(screen.getByText("signed-po.pdf")).toBeVisible();
});

it("a posted invoice is read-only", async () => {
  serve((url) =>
    url.endsWith(`/invoices/${INVOICE_ID}`)
      ? { body: invoice({ status: "approved", status_label: "Approved", number: "INV-0007" }) }
      : undefined,
  );
  renderWithIntl(<InvoiceEditor org={ORG} id={INVOICE_ID} />);
  expect(await screen.findByRole("heading", { name: "Invoice INV-0007" })).toBeVisible();
  expect(screen.getByRole("note")).toHaveTextContent("This invoice is approved");
  expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
  expect(screen.getByRole("group", { name: "Invoice details" })).toBeDisabled();
});

it("sends only the lines with something on them", () => {
  const empty = { id: "x", description: "", unitPrice: "", quantity: "1", discount: "" };
  const full = { id: "y", description: "Design", unitPrice: "10", quantity: "2", discount: "" };
  expect(
    invoiceLines([empty, full] as never, (id) => id === "y").map((l) => l.tax_overridden),
  ).toEqual([true]);
});

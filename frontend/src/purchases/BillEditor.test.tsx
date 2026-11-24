import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { BillEditor, billLines, gridLine } from "./BillEditor";
import { bill, billHandler, DOC_ID, EXPENSE, HST_P, ORG, serveJson, SUPPLIER } from "./fixtures";

/**
 * E-02-T11 — bill editor split view: the inbox document beside the form, a bill entered from it
 * without leaving the page (created with the document attached), save, approve; a posted bill is
 * read-only.
 */
beforeEach(() => {
  // jsdom has no object URLs: the document pane shows the fetched file from one.
  URL.createObjectURL = vi.fn(() => "blob:bill-document");
  URL.revokeObjectURL = vi.fn();
});
afterEach(() => vi.unstubAllGlobals());

function serve(extra?: Parameters<typeof billHandler>[1]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(serveJson(billHandler(calls, extra))));
  return calls;
}

async function chooseAccount() {
  await userEvent.click(screen.getByRole("combobox", { name: "Account, line 1" }));
  await userEvent.click(await screen.findByRole("option", { name: /6100/ }));
}

it("enters a bill from its document without leaving the page", async () => {
  const calls = serve();
  const navigate = vi.fn();
  renderWithIntl(<BillEditor org={ORG} documentId={DOC_ID} navigate={navigate} />);
  expect(await screen.findByTitle("Preview of cedar-invoice-1001.pdf")).toBeInTheDocument();
  const form = screen.getByRole("form", { name: "New bill" });
  await userEvent.selectOptions(within(form).getByRole("combobox", { name: "Supplier" }), SUPPLIER);
  await userEvent.type(
    within(form).getByRole("textbox", { name: "Supplier invoice number" }),
    "CS-1001",
  );
  await userEvent.type(screen.getByRole("textbox", { name: "Description, line 1" }), "Tiles");
  await chooseAccount();
  await userEvent.click(within(form).getByRole("button", { name: "Save draft" }));
  await waitFor(() =>
    expect(navigate).toHaveBeenCalledWith(
      `/o/${ORG}/purchases/bills/b1b1b1b1-0000-4000-8000-000000000001`,
    ),
  );
  const created = calls.find((c) => c.method === "POST" && c.url.endsWith("/bills"))!;
  expect(created.body).toMatchObject({
    supplier: SUPPLIER,
    supplier_invoice_no: "CS-1001",
    document: DOC_ID,
    lines: [{ description: "Tiles", account: EXPENSE }],
  });
  expect(await screen.findByText("Saved as a draft.")).toBeVisible();
  expect(screen.getByTitle("Preview of cedar-invoice-1001.pdf")).toBeInTheDocument(); // same page
});

it("approves: saves, then approves and shows the number", async () => {
  const calls = serve();
  renderWithIntl(<BillEditor org={ORG} id="b1b1b1b1-0000-4000-8000-000000000001" />);
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
  expect(await screen.findByText("BILL-0001 is approved and awaiting payment.")).toBeVisible();
  expect(calls.map((c) => `${c.method} ${c.url.split("/bills")[1] ?? ""}`)).toEqual(
    expect.arrayContaining([
      "PATCH /b1b1b1b1-0000-4000-8000-000000000001",
      "POST /b1b1b1b1-0000-4000-8000-000000000001/approve",
    ]),
  );
  expect(screen.getByText(/a posted bill isn't edited/)).toBeVisible();
  expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
});

it("shows the server's refusal", async () => {
  serve((url, method) =>
    url.endsWith("/approve") && method === "POST"
      ? {
          status: 400,
          body: {
            code: "purchases.bill.supplier_invoice_required",
            detail: "Enter the supplier's invoice number before approving the bill.",
          },
        }
      : undefined,
  );
  renderWithIntl(<BillEditor org={ORG} id="b1b1b1b1-0000-4000-8000-000000000001" />);
  await userEvent.click(await screen.findByRole("button", { name: "Approve" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Enter the supplier's invoice number");
});

it("converts lines both ways", () => {
  const [line] = bill().lines;
  const grid = gridLine({ ...line!, discount_type: "percent", discount_value: "10.0000" });
  expect(grid).toMatchObject({
    quantity: "10",
    unitPrice: "45.00",
    discount: "10%",
    account: EXPENSE,
    taxCode: HST_P,
  });
  expect(billLines([grid], { [grid.id]: "po-1" })).toEqual([
    {
      description: "Tiles",
      quantity: "10",
      unit_price: "45.00",
      discount_type: "percent",
      discount_value: "10",
      account: EXPENSE,
      tax_code: HST_P,
      po_line: "po-1",
    },
  ]);
});

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { quoteActions } from "./actionMatrix";
import { CUSTOMER, ORG, QUOTE_ID, REVENUE, quote, quoteHandler, serveJson } from "./fixtures";
import { QuoteEditor, depositAt, plusDays } from "./QuoteEditor";
import { countedLines, normaliseQuoteLines, quoteLines, type QuoteGridLine } from "./lines";

/**
 * D-02-T12 — the quote editor: header with expiry (30 days by default) and deposit, the shared
 * grid with Optional, Alternative group and Included; the totals count the lines that count; a
 * quote with two options is a customer, three lines and Save; a sent quote is read-only.
 */
afterEach(() => vi.unstubAllGlobals());

function serve(extra?: Parameters<typeof quoteHandler>[1]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal("fetch", vi.fn(serveJson(quoteHandler(calls, extra))));
  return calls;
}

const line = (over: Partial<QuoteGridLine>): QuoteGridLine => ({
  id: "x",
  item: "",
  description: "Line",
  quantity: "1",
  unitPrice: "10",
  discount: "",
  account: null,
  taxCode: null,
  isOptional: false,
  alternativeGroup: "",
  selected: true,
  ...over,
});

it("creates a quote with an optional line and an alternative group", async () => {
  const calls = serve();
  const navigate = vi.fn();
  const user = userEvent.setup({ delay: null });
  renderWithIntl(<QuoteEditor org={ORG} navigate={navigate} />);
  const form = await screen.findByRole("form", { name: "New quote" });
  const customer = within(form).getByRole("combobox", { name: "Customer" });
  await waitFor(() => expect(within(customer).getAllByRole("option")).toHaveLength(2));
  await user.selectOptions(customer, CUSTOMER);
  const expiry = within(form).getByLabelText(/^Expiry date/);
  expect(expiry).toHaveValue(
    plusDays((within(form).getByLabelText("Quote date") as HTMLInputElement).value, 30),
  );
  const expiryDate = (expiry as HTMLInputElement).value;
  await user.type(screen.getByRole("textbox", { name: "Description, line 1" }), "Cabinets");
  await user.type(screen.getByRole("textbox", { name: "Unit price, line 1" }), "1000");
  await user.click(screen.getByRole("button", { name: "Add a line" }));
  await user.type(screen.getByRole("textbox", { name: "Description, line 2" }), "Install");
  await user.type(screen.getByRole("textbox", { name: "Unit price, line 2" }), "200");
  await user.click(screen.getByRole("checkbox", { name: "Optional, line 2" }));
  expect(screen.getByRole("checkbox", { name: "Included, line 2" })).not.toBeChecked();
  await user.click(screen.getByRole("button", { name: "Add a line" }));
  await user.type(screen.getByRole("textbox", { name: "Description, line 3" }), "Oak");
  await user.type(screen.getByRole("textbox", { name: "Unit price, line 3" }), "500");
  await user.type(screen.getByRole("combobox", { name: "Alternative group, line 3" }), "Wood");
  expect(screen.getByRole("checkbox", { name: "Optional, line 3" })).toBeDisabled();
  await user.selectOptions(
    within(form).getByRole("combobox", { name: "Deposit on acceptance" }),
    "percent",
  );
  await user.type(within(form).getByRole("textbox", { name: "Deposit %" }), "20");
  await user.click(within(form).getByRole("button", { name: "Save draft" }));
  await waitFor(() => expect(navigate).toHaveBeenCalledWith(`/o/${ORG}/sales/quotes/${QUOTE_ID}`));
  const created = calls.find((c) => c.method === "POST" && c.url.endsWith("/quotes"))!;
  expect(created.body).toMatchObject({
    customer: CUSTOMER,
    deposit_type: "percent",
    deposit_value: "20",
    expiry_date: expiryDate,
    lines: [
      { description: "Cabinets", account: REVENUE, is_optional: false, selected: true },
      { description: "Install", is_optional: true, selected: false, alternative_group: "" },
      { description: "Oak", is_optional: false, alternative_group: "Wood", selected: true },
    ],
  });
  expect(await screen.findByText("Draft saved.")).toBeVisible();
}, 30_000);

it("a sent quote is read-only and offers the sent actions", async () => {
  serve((url) =>
    url.endsWith(`/quotes/${QUOTE_ID}`)
      ? { body: quote({ status: "sent", status_label: "Sent" }) }
      : undefined,
  );
  renderWithIntl(<QuoteEditor org={ORG} id={QUOTE_ID} />);
  expect(await screen.findByRole("heading", { name: "Quote QU-0001" })).toBeVisible();
  expect(screen.getByRole("note")).toHaveTextContent("This quote is sent");
  expect(screen.getByRole("group", { name: "Quote details" })).toBeDisabled();
  expect(screen.getByRole("checkbox", { name: "Optional, line 2" })).toBeDisabled();
  expect(quoteActions("sent")).toContain("accept");
  expect(quoteActions("accepted")).toEqual(["convert", "revise", "pdf", "copy"]);
  expect(quoteActions("invoiced")).not.toContain("revise");
});

it("counts lines like the server and keeps one alternative per group", () => {
  const lines = [
    line({ id: "a" }),
    line({ id: "b", isOptional: true, selected: false }),
    line({ id: "c", alternativeGroup: "W" }),
    line({ id: "d", alternativeGroup: "W", selected: false }),
  ];
  expect(countedLines(lines)).toEqual([true, false, true, false]);
  const swapped = normaliseQuoteLines(
    lines.map((l) => (l.id === "d" ? { ...l, selected: true } : l)),
    lines,
  );
  expect(swapped.map((l) => l.selected)).toEqual([true, false, false, true]);
  const optional = normaliseQuoteLines(
    lines.map((l) => (l.id === "a" ? { ...l, isOptional: true } : l)),
    lines,
  );
  expect(optional[0]).toMatchObject({ isOptional: true, selected: false });
  expect(quoteLines(lines).map((l) => [l.is_optional, l.alternative_group, l.selected])).toEqual([
    [false, "", true],
    [true, "", false],
    [false, "W", true],
    [false, "W", false],
  ]);
  expect(depositAt("percent", "20", "1695.00")).toBe(339);
  expect(depositAt("amount", "5000", "1695.00")).toBe(1695);
});

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { BillEditor } from "@/purchases/BillEditor";
import { billHandler, serveJson, SUPPLIER, TAX } from "@/purchases/fixtures";
import { renderWithIntl } from "@/test/intl";

/**
 * G-02-T07 — default tax codes in the editor: the resolver fills the tax cell (auto chip, the
 * reason as its tooltip); a code the person picks is an override (the dot) and isn't
 * re-resolved when the supplier changes; the dot resets the line to its default.
 */
const QUEBEC = "5a5a5a5a-0000-4000-8000-000000000002";
const QC_TAX = {
  ...TAX,
  id: "cccc0002-0000-4000-8000-000000000002",
  code: "purchase.QC.standard",
  name: "GST and QST on purchases",
};
const EXEMPT = {
  ...TAX,
  id: "cccc0003-0000-4000-8000-000000000003",
  code: "purchase.exempt",
  name: "Exempt purchases",
  type: "exempt",
  components: [],
};
const resolved = (code: typeof TAX, province: string) => ({
  key: code.code,
  tax_code: { id: code.id, code: code.code, name: code.name, version: 1 },
  source: "place_of_supply",
  auto: true,
  explanation: "tax.pos.supplier_province",
  params: { province },
  province,
  flags: [],
  warnings: [],
});

afterEach(() => vi.unstubAllGlobals());

function serve() {
  const asked: unknown[] = [];
  const calls: { url: string; method: string; body: unknown }[] = [];
  const handler = billHandler(calls, (url) => {
    if (url.includes("/contacts?"))
      return {
        body: {
          count: 2,
          next_offset: null,
          role_counts: {},
          results: [
            { id: SUPPLIER, display_name: "Cedar Supply Co.", roles: ["supplier"] },
            { id: QUEBEC, display_name: "Fournitures Laval", roles: ["supplier"] },
          ],
        },
      };
    if (url.includes("/tax/codes")) return { body: { results: [TAX, QC_TAX, EXEMPT] } };
    if (url.includes("/tax/resolve")) {
      const body = JSON.parse(
        String(calls.at(-1)?.body ? JSON.stringify(calls.at(-1)!.body) : "{}"),
      );
      asked.push(body);
      const code = body.contact === QUEBEC ? QC_TAX : TAX;
      const province = body.contact === QUEBEC ? "QC" : "ON";
      return { body: { lines: body.lines.map(() => resolved(code, province)) } };
    }
    return undefined;
  });
  vi.stubGlobal("fetch", vi.fn(serveJson(handler)));
  return asked;
}

const cell = (n: number) => screen.getByRole("combobox", { name: `Tax code, line ${n}` });

test("auto-fills, keeps overrides when the supplier changes, and resets", async () => {
  const asked = serve();
  const user = userEvent.setup();
  renderWithIntl(<BillEditor org="acme" navigate={() => undefined} />);
  const form = await screen.findByRole("form", { name: "New bill" });
  await user.selectOptions(within(form).getByRole("combobox", { name: "Supplier" }), SUPPLIER);
  await waitFor(() => expect(cell(1)).toHaveValue("HST on purchases"));
  const row1 = cell(1).closest("[role='row']") as HTMLElement;
  expect(within(row1).getByText("auto")).toBeVisible();
  expect(
    within(row1).getByRole("button", { name: "Why this tax code, line 1" }),
  ).toHaveAccessibleDescription("Supplier in ON: its standard rate");

  await user.click(screen.getByRole("button", { name: "Add a line" }));
  await waitFor(() => expect(cell(2)).toHaveValue("HST on purchases"));
  await user.click(cell(2));
  await user.click(await screen.findByRole("option", { name: /Exempt purchases/ }));
  await waitFor(() => expect(cell(2)).toHaveValue("Exempt purchases"));
  expect(screen.getByRole("button", { name: /Changed from the default, line 2/ })).toBeVisible();

  await user.selectOptions(within(form).getByRole("combobox", { name: "Supplier" }), QUEBEC);
  await waitFor(() => expect(cell(1)).toHaveValue("GST and QST on purchases"));
  expect(cell(2)).toHaveValue("Exempt purchases"); // the override stays
  expect(asked.length).toBeGreaterThanOrEqual(2);

  await user.click(screen.getByRole("button", { name: /Changed from the default, line 2/ }));
  await waitFor(() => expect(cell(2)).toHaveValue("GST and QST on purchases"));
  expect(screen.queryByRole("button", { name: /Changed from the default/ })).toBeNull();
});

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import type { TaxComponent } from "./api";
import { ORG, taxCode } from "./fixtures";
import { TaxCodeEditor } from "./TaxCodeEditor";

/**
 * G-01-T13 — tax code editor: component builder, recoverable %, live example equal to the API's
 * calculation (POST /tax/calculate gives 100.00 → GST 5.00 + PST 7.00 = 112.00, recoverable
 * 5.00, cost 7.00), effective-date picker; a new code posts version 1, an edit a new version.
 */
afterEach(() => vi.unstubAllGlobals());

const comp = (over: Partial<TaxComponent>): TaxComponent => ({
  id: "x",
  key: "x",
  name: "X",
  kind: "gst",
  authority: "CRA",
  rate: "5",
  effective_from: "2008-01-01",
  effective_to: null,
  recoverable: true,
  side: "both",
  control_account_sales: "2100",
  control_account_purchase: "1160",
  ...over,
});
const COMPONENTS = [
  comp({ id: "gst", key: "gst", name: "GST", rate: "5" }),
  comp({
    id: "pst",
    key: "pst_bc",
    name: "PST (BC)",
    kind: "pst",
    rate: "7",
    authority: "BC",
    recoverable: false,
  }),
  comp({ id: "hst", key: "hst_on", name: "HST (ON)", kind: "hst", rate: "13" }),
];
/** What the server's POST /tax/calculate answers for these cases (backend test_tax_calculator). */
const API = {
  bc: { net: "100.00", tax: "12.00", gross: "112.00", claimable: "5.00", cost: "7.00" },
  meals: { net: "100.00", tax: "13.00", gross: "113.00", claimable: "6.50", cost: "6.50" },
};

function serve(posted: { url: string; body: unknown }[]) {
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url, init) => {
        if (init?.method === "POST") {
          const body = JSON.parse(String(init.body));
          posted.push({ url, body });
          return {
            status: 201,
            body: taxCode({
              name: body.name ?? "HST meals",
              version: url.endsWith("/versions") ? 2 : 1,
            }),
          };
        }
        return { body: { results: COMPONENTS } };
      }),
    ),
  );
}

it("builds a BC purchase code; the live example equals the API calculation", async () => {
  const posted: { url: string; body: unknown }[] = [];
  serve(posted);
  const user = userEvent.setup();
  renderWithIntl(<TaxCodeEditor org={ORG} side="purchase" today="2026-01-01" />);
  await user.type(screen.getByLabelText("Code"), "purchase.BC.custom");
  await user.type(screen.getByLabelText("Name"), "GST + PST on purchases");
  await user.selectOptions(screen.getByLabelText("Province or territory"), "BC");
  await user.click(screen.getByRole("button", { name: "Add component" }));
  await screen.findByRole("option", { name: /GST 5 %/ });
  await user.selectOptions(screen.getByLabelText("Component 1"), "gst");
  await user.click(screen.getByRole("button", { name: "Add component" }));
  await user.selectOptions(screen.getByLabelText("Component 2"), "pst");
  const panel = screen.getByRole("region", { name: "Live example" });
  expect(within(panel).getByText("GST 5 %").nextSibling).toHaveTextContent("$5.00");
  expect(within(panel).getByText("PST (BC) 7 %").nextSibling).toHaveTextContent("$7.00");
  expect(panel.querySelector("[data-total]")).toHaveTextContent(`$${API.bc.gross}`);
  expect(panel.querySelector("[data-claimable]")).toHaveTextContent(`$${API.bc.claimable}`);
  expect(panel.querySelector("[data-cost]")).toHaveTextContent(`$${API.bc.cost}`);
  expect(screen.queryByLabelText("Recoverable % for component 2")).toBeNull(); // PST: never
  await user.click(screen.getByRole("button", { name: "Save" }));
  expect(await screen.findByText(/saved \(version 1\)/)).toBeVisible();
  expect(posted[0]).toEqual({
    url: `/api/v1/o/${ORG}/tax/codes`,
    body: {
      code: "purchase.BC.custom",
      name: "GST + PST on purchases",
      side: "purchase",
      type: "taxable",
      province: "BC",
      effective_from: "2026-01-01",
      itc_restriction_pct: null,
      components: [
        { component: "gst", recoverable_pct: null },
        { component: "pst", recoverable_pct: null },
      ],
    },
  });
});

it("recoverable % and inclusive example match the API; editing saves a new version", async () => {
  const posted: { url: string; body: unknown }[] = [];
  serve(posted);
  const user = userEvent.setup();
  const existing = taxCode({
    id: "p1",
    code: "purchase.ON.meals",
    name: "HST meals",
    side: "purchase",
    components: [
      {
        id: "hst",
        key: "hst_on",
        name: "HST (ON)",
        kind: "hst",
        rate: "13",
        recoverable_pct: null,
      },
    ],
  });
  renderWithIntl(<TaxCodeEditor org={ORG} code={existing} today="2027-01-01" />);
  const recoverable = await screen.findByLabelText("Recoverable % for component 1");
  await user.type(recoverable, "50");
  const panel = screen.getByRole("region", { name: "Live example" });
  await user.click(within(panel).getByRole("switch", { name: "Amount includes tax" }));
  await user.clear(within(panel).getByLabelText("Amount"));
  await user.type(within(panel).getByLabelText("Amount"), "113.00");
  expect(panel.querySelector("[data-total]")).toHaveTextContent(`$${API.meals.gross}`);
  expect(panel.querySelector("[data-claimable]")).toHaveTextContent(`$${API.meals.claimable}`);
  expect(panel.querySelector("[data-cost]")).toHaveTextContent(`$${API.meals.cost}`);
  expect(screen.getByText(/creates version 2 from this date/)).toBeVisible();
  expect(screen.getByLabelText("Code")).toBeDisabled();
  await user.click(screen.getByRole("button", { name: "Save as a new version" }));
  expect(await screen.findByText(/saved \(version 2\)/)).toBeVisible();
  expect(posted[0]).toEqual({
    url: `/api/v1/o/${ORG}/tax/codes/p1/versions`,
    body: {
      effective_from: "2027-01-01",
      name: "HST meals",
      components: [{ component: "hst", recoverable_pct: "50" }],
    },
  });
});

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { serveJson } from "@/banking/fixtures";
import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { CODES, EXPIRED_MB, ORG } from "./fixtures";
import { TaxCodesScreen } from "./TaxCodesScreen";

/**
 * G-01-T12 — tax code list: Sales / Purchases tabs with counts, type badges, components, the
 * effective timeline, usage count; expired codes hidden by default and shown with the toggle.
 */
afterEach(() => vi.unstubAllGlobals());

function serve() {
  const urls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(
      serveJson((url) => {
        urls.push(url);
        const withExpired = url.includes("expired=1");
        return { body: { results: withExpired ? [...CODES, EXPIRED_MB] : CODES } };
      }),
    ),
  );
  return urls;
}

it("lists sales codes with badges, components, timeline and usage; expired hidden", async () => {
  const urls = serve();
  const { container } = renderWithIntl(<TaxCodesScreen org={ORG} canManage />);
  const table = await screen.findByRole("table", { name: "Sales tax codes" });
  expect(screen.getByRole("tab", { name: /Sales/ })).toHaveTextContent("4");
  expect(screen.getByRole("tab", { name: /Purchases/ })).toHaveTextContent("1");
  const on = within(table)
    .getByRole("link", { name: "Edit HST 13 % (Ontario) on sales" })
    .closest("tr")!;
  expect(within(on).getByText("Taxable")).toBeVisible();
  expect(within(on).getByText("HST (ON) 13 %")).toBeVisible();
  expect(within(on).getByText("412 lines")).toBeVisible();
  expect(within(on).getByText(/From/)).toBeVisible();
  expect(on.querySelector("[data-timeline]")).not.toBeNull();
  expect(within(table).getByText("Zero-rated")).toBeVisible();
  expect(within(table).getByText("Exempt")).toBeVisible();
  expect(within(table).getByText("No tax")).toBeVisible();
  expect(within(table).getByText("Not used")).toBeVisible();
  expect(container.querySelector('[data-code="sales.MB.standard"]')).toBeNull();
  expect(urls[0]).toBe(`/api/v1/o/${ORG}/tax/codes`);
  expect(screen.getByRole("link", { name: "New tax code" })).toHaveAttribute(
    "href",
    `/o/${ORG}/settings/tax-codes/new?side=sales`,
  );
  await expectNoAxeViolations(container);
});

it("shows expired versions with the toggle, greyed with an Expired badge", async () => {
  const urls = serve();
  const user = userEvent.setup();
  const { container } = renderWithIntl(<TaxCodesScreen org={ORG} />);
  await screen.findByRole("table", { name: "Sales tax codes" });
  await user.click(screen.getByRole("switch", { name: "Show expired rates" }));
  const row = await screen.findByText("GST 5 % + RST 8 % (Manitoba) on sales");
  const tr = row.closest("tr")!;
  expect(within(tr).getByText("Expired")).toBeVisible();
  expect(within(tr).getByText(/2019/)).toBeVisible();
  expect(tr).toHaveAttribute("data-expired", "true");
  expect(urls[urls.length - 1]).toBe(`/api/v1/o/${ORG}/tax/codes?expired=1`);
  expect(container.querySelectorAll("[data-expired]")).toHaveLength(1);
  expect(screen.queryByRole("link", { name: "New tax code" })).toBeNull();
});

it("switches to purchases and searches", async () => {
  serve();
  const user = userEvent.setup();
  renderWithIntl(<TaxCodesScreen org={ORG} />);
  await screen.findByRole("table", { name: "Sales tax codes" });
  await user.click(screen.getByRole("tab", { name: /Purchases/ }));
  const table = screen.getByRole("table", { name: "Purchases tax codes" });
  expect(within(table).getByText("50 % claimable")).toBeVisible();
  await user.click(screen.getByRole("tab", { name: /Sales/ }));
  await user.type(screen.getByLabelText("Search codes"), "british");
  expect(screen.getAllByRole("row")).toHaveLength(2);
});

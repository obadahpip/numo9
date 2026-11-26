import { screen, within } from "@testing-library/react";

import { renderWithIntl } from "@/test/intl";

import type { MatchRow } from "./api";
import { MatchPanel } from "./MatchPanel";

/** E-02-T13 — match panel: one row per PO line, the result in colour and in words. */
const row = (over: Partial<MatchRow>): MatchRow => ({
  line: "l1",
  po_line: "p1",
  po: "PO-0007",
  description: "Tiles",
  ordered: "10.0000",
  received: "10.0000",
  billed_elsewhere: "0.0000",
  quantity: "10.0000",
  po_price: "45.0000",
  price: "45.0000",
  quantity_over: "0.0000",
  price_difference_pct: "0.00",
  status: "green",
  ...over,
});

it("shows each line's result in words", () => {
  renderWithIntl(
    <MatchPanel
      rows={[
        row({}),
        row({
          line: "l2",
          description: "Grout",
          quantity: "12.0000",
          quantity_over: "2.0000",
          status: "red",
        }),
        row({
          line: "l3",
          description: "Caulk",
          price: "46.0000",
          price_difference_pct: "2.22",
          status: "amber",
        }),
      ]}
    />,
  );
  const table = screen.getByRole("table");
  expect(within(screen.getByRole("row", { name: /Tiles/ })).getByText("Matches")).toBeVisible();
  expect(
    within(screen.getByRole("row", { name: /Grout/ })).getByText("2 more than received"),
  ).toBeVisible();
  expect(
    within(screen.getByRole("row", { name: /Caulk/ })).getByText("price 2.22 % off"),
  ).toBeVisible();
  expect(within(table).getByText("Within tolerance")).toBeVisible();
  expect(screen.getByRole("heading", { name: "Match with purchase order PO-0007" })).toBeVisible();
});

it("says more than ordered, and a bill before receipt waits for it (E-01-T07)", () => {
  renderWithIntl(
    <MatchPanel
      rows={[
        row({
          received: "12.0000",
          quantity: "12.0000",
          quantity_over: "2.0000",
          flags: ["over_ordered"],
          status: "red",
        }),
        row({
          line: "l2",
          description: "Install",
          received: "0.0000",
          flags: ["received_later"],
          received_later: true,
        }),
      ]}
    />,
  );
  expect(screen.getByRole("row", { name: /Tiles/ })).toHaveTextContent("2 more than ordered");
  expect(screen.getByRole("row", { name: /Install/ })).toHaveTextContent(
    "nothing received yet: match pending the receipt",
  );
});

it("renders nothing for a bill without a PO", () => {
  const { container } = renderWithIntl(<MatchPanel rows={[]} />);
  expect(container).toBeEmptyDOMElement();
});

import { screen, within } from "@testing-library/react";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { CycleHistory } from "./CycleHistory";
import { MONTHLY, QUARTERLY } from "./fixtures";

/** G-03a-T21 — the history shows every switch: who, when, the approval reference. */
it("lists every switch newest first with who, when and the approval", async () => {
  const { container } = renderWithIntl(
    <CycleHistory cycles={[QUARTERLY, MONTHLY]} today="2026-10-20" />,
  );
  const table = screen.getByRole("table", { name: "Filing frequency changes" });
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows).toHaveLength(2);
  expect(rows[0]).toHaveTextContent("1 Oct 2026");
  expect(rows[0]).toHaveTextContent("Monthly");
  expect(rows[0]).toHaveTextContent("Current");
  expect(rows[0]).toHaveTextContent("2026-GST-48812 (10 Sep 2026)");
  expect(rows[0]).toHaveTextContent("CRA letter");
  expect(rows[0]).toHaveTextContent("Sam Patel");
  expect(rows[0]).toHaveTextContent("12 Sep 2026");
  expect(rows[1]).toHaveTextContent("Quarterly");
  expect(rows[1]).toHaveTextContent("Dana Lee");
  expect(rows[1]).not.toHaveTextContent("Current");
  await expectNoAxeViolations(container);
});

it("marks a future switch as not yet current and handles no history", () => {
  const { rerender } = renderWithIntl(
    <CycleHistory cycles={[QUARTERLY, MONTHLY]} today="2026-06-01" />,
  );
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows[0]).not.toHaveTextContent("Current");
  expect(rows[1]).toHaveTextContent("Current");
  rerender(<CycleHistory cycles={[]} today="2026-06-01" />);
  expect(screen.getByText("No frequency chosen yet.")).toBeVisible();
});

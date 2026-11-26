import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../../packages/ui/src/test/axe";
import { AssuranceFindings, ScoreCard } from "./AssuranceFindings";
import { TEARDOWN_FINDINGS, TEARDOWN_SUMMARY } from "./fixtures";
import { groupFindings } from "./grouping";

/**
 * K-09-T21 — Assurance page: score card with counts by severity, findings grouped by rule with
 * their plain-language explanation and amount, and the actions (View source, Propose fix only
 * where the rule has one, Acknowledge, Mark false positive). The teardown fixture shows at least
 * seven rule groups.
 */
describe("AssuranceFindings", () => {
  it("shows the teardown's rule groups with explanations and actions", async () => {
    const onAction = vi.fn();
    const { container } = renderWithIntl(
      <>
        <ScoreCard summary={TEARDOWN_SUMMARY} />
        <AssuranceFindings
          org="refined"
          locale="en-CA"
          groups={groupFindings(TEARDOWN_FINDINGS)}
          onAction={onAction}
        />
      </>,
    );
    expect(screen.getByText("20 out of 100")).toBeInTheDocument();
    expect(screen.getByText("Critical: 3")).toBeInTheDocument();
    const groups = container.querySelectorAll("[data-rule-group]");
    expect(groups.length).toBeGreaterThanOrEqual(7);
    const neg = container.querySelector('[data-rule-group="NEG_CASH"]') as HTMLElement;
    expect(within(neg).getByText(/Petty Cash went below zero/)).toBeInTheDocument();
    expect(within(neg).getByText("-$994.17")).toBeInTheDocument();
    expect(within(neg).getByRole("link", { name: "View source" })).toHaveAttribute(
      "href",
      "/o/refined/accounting/chart-of-accounts?account=acc-1000",
    );
    await userEvent.click(within(neg).getByRole("button", { name: "Propose fix" }));
    expect(onAction).toHaveBeenCalledWith("fix", expect.objectContaining({ id: "neg-cash" }));
    const backdated = container.querySelector('[data-rule-group="BACKDATED"]') as HTMLElement;
    expect(within(backdated).queryByRole("button", { name: "Propose fix" })).toBeNull();
    await userEvent.click(within(backdated).getByRole("button", { name: "Mark false positive" }));
    expect(onAction).toHaveBeenLastCalledWith("falsePositive", expect.anything());
    await expectNoAxeViolations(container);
  });

  it("collapses a group", async () => {
    const { container } = renderWithIntl(
      <AssuranceFindings
        org="refined"
        locale="en-CA"
        groups={groupFindings(TEARDOWN_FINDINGS)}
        onAction={vi.fn()}
      />,
    );
    const group = container.querySelector('[data-rule-group="JOURNAL_TO_CASH"]') as HTMLElement;
    const toggle = within(group).getByRole("button", { expanded: true });
    expect(within(group).getAllByRole("listitem")).toHaveLength(2);
    await userEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(within(group).queryAllByRole("listitem")).toHaveLength(0);
  });
});

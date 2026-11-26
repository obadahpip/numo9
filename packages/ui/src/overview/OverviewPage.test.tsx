import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { expectNoAxeViolations } from "../test/axe";
import {
  agingBuckets,
  agingLabels,
  cardLabels,
  emptyTiles,
  salesTiles,
  tileLabel,
} from "./fixtures";
import {
  AgingBar,
  agingTotal,
  OVERVIEW_COMPONENT_ID,
  OverviewCard,
  OverviewPage,
  OverviewTiles,
} from "./OverviewPage";

/** D-09-T06 — shared OverviewPage: tiles, cards with retry, aging bar (used by sales and E-02). */
function page(kind: string, failing = false, onRetry = vi.fn()) {
  return render(
    <OverviewPage
      kind={kind}
      title="Sales overview"
      tiles={<OverviewTiles tiles={salesTiles} locale="en-CA" tileLabel={tileLabel} />}
    >
      <OverviewCard
        cardKey="aging"
        title="Money coming in"
        status={failing ? "error" : "ready"}
        labels={cardLabels}
        error={{ title: "Money coming in couldn't be loaded" }}
        onRetry={onRetry}
      >
        <AgingBar buckets={agingBuckets} locale="en-CA" labels={agingLabels} />
      </OverviewCard>
      <OverviewCard
        cardKey="top"
        title="Customers owing the most"
        status="ready"
        labels={cardLabels}
      >
        <p>Lakeshore Hardware Ltd.</p>
      </OverviewCard>
    </OverviewPage>,
  );
}

describe("OverviewPage (D-09-T06)", () => {
  it("carries the shared component id and its kind", () => {
    const { container, unmount } = page("sales");
    const root = container.querySelector(`[data-component=${OVERVIEW_COMPONENT_ID}]`);
    expect(root).toHaveAttribute("data-overview", "sales");
    unmount();
    const purchases = page("purchases").container;
    expect(purchases.querySelector("[data-component=overview-page]")).toHaveAttribute(
      "data-overview",
      "purchases",
    );
  });

  it("shows each tile's count and amount as a link to the filtered list", () => {
    page("sales");
    const overdue = screen.getByRole("link", { name: "Overdue: 3 invoices, $4,275.25" });
    expect(overdue).toHaveAttribute("href", "#overdue");
    expect(overdue).toHaveClass("border-border-danger");
    expect(within(overdue).getByText("3")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /invoices/ })).toHaveLength(4);
  });

  it("renders zero tiles as 0 and $0.00, never blank, without the attention accent", () => {
    render(<OverviewTiles tiles={emptyTiles} locale="en-CA" tileLabel={tileLabel} />);
    const overdue = screen.getByRole("link", { name: "Overdue: 0 invoices, $0.00" });
    expect(overdue).not.toHaveClass("border-border-danger");
    expect(screen.getAllByText("$0.00")).toHaveLength(4);
  });

  it("formats tiles in French Canadian", () => {
    render(<OverviewTiles tiles={salesTiles} locale="fr-CA" tileLabel={tileLabel} />);
    expect(screen.getByText("18 400,00 $")).toBeInTheDocument();
  });

  it("keeps the other cards when one fails, and its Try again retries", async () => {
    const onRetry = vi.fn();
    page("sales", true, onRetry);
    const failed = document.querySelector("[data-card=aging]") as HTMLElement;
    expect(failed).toHaveAttribute("data-card-status", "error");
    expect(within(failed).getByRole("alert")).toHaveTextContent(
      "Money coming in couldn't be loaded",
    );
    expect(screen.getByText("Lakeshore Hardware Ltd.")).toBeInTheDocument();
    await userEvent.click(within(failed).getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows a skeleton while a card loads and hides its action", () => {
    render(
      <OverviewCard
        cardKey="quotes"
        title="Quotes"
        status="loading"
        labels={{ ...cardLabels, loading: "Loading quotes…" }}
        action={<a href="#q">View all</a>}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading quotes…");
    expect(screen.queryByRole("link", { name: "View all" })).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Quotes" })).toHaveAttribute("aria-busy", "true");
  });

  it("has no axe violations", async () => {
    page("sales", true);
    await expectNoAxeViolations();
  });
});

describe("AgingBar (D-09-T06)", () => {
  it("sizes segments by amount, skips empty buckets and names every bucket", () => {
    render(<AgingBar buckets={agingBuckets} locale="en-CA" labels={agingLabels} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Money coming in by age: $18,400.00 owed");
    const segments = document.querySelectorAll("[data-bucket]");
    expect([...segments].map((s) => s.getAttribute("data-bucket"))).toEqual([
      "current",
      "1_30",
      "31_60",
      "over_90",
    ]);
    expect((segments[1] as HTMLElement).style.width).toBe(`${(2400 / 18400) * 100}%`);
    expect(screen.getAllByRole("listitem")).toHaveLength(5);
    expect(screen.getByRole("link", { name: /Over 90 days/ })).toHaveAttribute("href", "#over_90");
    expect(screen.getByText("61–90 days").closest("li")).toHaveTextContent("$0.00");
  });

  it("says nothing is owed when every bucket is zero", () => {
    render(
      <AgingBar
        buckets={agingBuckets.map((b) => ({ ...b, amount: "0.00" }))}
        locale="en-CA"
        labels={agingLabels}
      />,
    );
    expect(document.querySelectorAll("[data-bucket]")).toHaveLength(0);
    expect(screen.getByText("Nothing owed — every invoice is paid.")).toBeInTheDocument();
    expect(screen.getByRole("img")).toHaveAccessibleName("Money coming in by age: $0.00 owed");
  });

  it("totals exactly to the cent", () => {
    expect(
      agingTotal([
        { key: "a", label: "a", amount: "0.10" },
        { key: "b", label: "b", amount: "0.2" },
      ]),
    ).toBe("0.30");
    expect(
      agingTotal([
        { key: "a", label: "a", amount: "-5.05" },
        { key: "b", label: "b", amount: "1" },
      ]),
    ).toBe("-4.05");
  });
});

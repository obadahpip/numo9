import { OVERVIEW_COMPONENT_ID } from "@numo9/ui";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { renderWithIntl } from "@/test/intl";

import { expectNoAxeViolations } from "../../../packages/ui/src/test/axe";
import { ORG, serveJson } from "./fixtures";
import { PurchasesOverviewScreen } from "./PurchasesOverviewScreen";

/**
 * E-02-T15 — purchases overview on the shared OverviewPage (gap-22: the same component id as the
 * sales overview); tiles open the bills list on the same tab; one failing card keeps the others
 * and recovers on Try again (gap-05).
 */
const tiles = [
  { key: "draft", label: "Draft", count: 2, amount: "400.00", href: "" },
  { key: "awaiting_approval", label: "Awaiting approval", count: 1, amount: "700.00", href: "" },
  { key: "awaiting_payment", label: "Awaiting payment", count: 4, amount: "3700.00", href: "" },
  { key: "overdue", label: "Overdue", count: 3, amount: "2700.00", href: "" },
];
const aging = [
  { key: "current", label: "Current", count: 1, amount: "1000.00" },
  { key: "1_30", label: "1–30 days", count: 1, amount: "400.00" },
  { key: "31_60", label: "31–60 days", count: 1, amount: "2000.00" },
  { key: "61_90", label: "61–90 days", count: 0, amount: "0.00" },
  { key: "over_90", label: "Over 90 days", count: 1, amount: "300.00" },
];
const suppliers = [
  { id: "s1", name: "Cedar Supply Co.", owed: "3000.00", overdue: "2000.00", bills: 2 },
  { id: "s2", name: "Maple Hardware Ltd", owed: "700.00", overdue: "0.00", bills: 1 },
];

function serve(failAging = { times: 0 }) {
  const fetcher = vi.fn(
    serveJson((url) => {
      const section = new URL(url, "http://x").searchParams.get("section");
      if (section === "tiles") return { body: { as_of: "2026-09-30", tiles } };
      if (section === "aging") {
        if (failAging.times > 0) {
          failAging.times -= 1;
          return { status: 500, body: { detail: "boom" } };
        }
        return { body: { as_of: "2026-09-30", aging } };
      }
      return { body: { as_of: "2026-09-30", top_suppliers: suppliers } };
    }),
  );
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}

afterEach(() => vi.unstubAllGlobals());

describe("PurchasesOverviewScreen (E-02-T15)", () => {
  it("is the shared OverviewPage, kind purchases (gap-22)", async () => {
    serve();
    const { container } = renderWithIntl(<PurchasesOverviewScreen org={ORG} />);
    await screen.findByRole("link", { name: /Overdue: 3 bills/ });
    const root = container.querySelector(`[data-component=${OVERVIEW_COMPONENT_ID}]`);
    expect(root).toHaveAttribute("data-overview", "purchases");
    expect(screen.getByRole("heading", { level: 1, name: "Purchases overview" })).toBeVisible();
  });

  it("tiles show count and amount and open the bills list on the same tab", async () => {
    serve();
    renderWithIntl(<PurchasesOverviewScreen org={ORG} />);
    const overdue = await screen.findByRole("link", { name: "Overdue: 3 bills, $2,700.00" });
    expect(overdue).toHaveAttribute("href", `/o/${ORG}/purchases/bills?tab=overdue`);
    expect(
      screen.getByRole("link", { name: "Awaiting payment: 4 bills, $3,700.00" }),
    ).toHaveAttribute("href", `/o/${ORG}/purchases/bills?tab=awaiting_payment`);
    expect(screen.getByText("Overdue means due before 30 Sep 2026.")).toBeInTheDocument();
  });

  it("shows the aging bar and the suppliers owed the most", async () => {
    serve();
    renderWithIntl(<PurchasesOverviewScreen org={ORG} />);
    expect(
      await screen.findByRole("img", { name: "Money going out by age: $3,700.00 owed" }),
    ).toBeInTheDocument();
    const top = screen.getByRole("region", { name: "Suppliers you owe the most" });
    await within(top).findByRole("link", { name: "Cedar Supply Co." });
    expect(top).toHaveTextContent("$3,000.00");
    expect(top).toHaveTextContent("$2,000.00 overdue");
    expect(top).toHaveTextContent("2 open bills");
  });

  it("a failing card keeps the others and recovers on Try again (gap-05)", async () => {
    serve({ times: 1 });
    renderWithIntl(<PurchasesOverviewScreen org={ORG} />);
    const card = await screen.findByRole("region", { name: "Money going out" });
    const alert = await within(card).findByRole("alert");
    expect(alert).toHaveTextContent("Money going out couldn't be loaded");
    expect(alert).toHaveTextContent(/Reference: web-/);
    expect(await screen.findByRole("link", { name: /Overdue: 3 bills/ })).toBeVisible();
    await userEvent.click(within(alert).getByRole("button", { name: "Try again" }));
    expect(
      await screen.findByRole("img", { name: "Money going out by age: $3,700.00 owed" }),
    ).toBeInTheDocument();
    expect(within(card).queryByRole("alert")).not.toBeInTheDocument();
  });

  it("an empty organisation shows zeros and how to start", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        serveJson((url) => {
          const section = new URL(url, "http://x").searchParams.get("section");
          if (section === "tiles")
            return {
              body: {
                as_of: "2026-09-30",
                tiles: tiles.map((t) => ({ ...t, count: 0, amount: "0.00" })),
              },
            };
          if (section === "aging")
            return { body: { aging: aging.map((b) => ({ ...b, count: 0, amount: "0.00" })) } };
          return { body: { top_suppliers: [] } };
        }),
      ),
    );
    renderWithIntl(<PurchasesOverviewScreen org={ORG} />);
    expect(await screen.findByRole("link", { name: "Overdue: 0 bills, $0.00" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "No bills yet" })).toBeVisible();
    expect(await screen.findByText("You don't owe any supplier right now.")).toBeVisible();
    expect(screen.getByText("Nothing owed — every approved bill is paid.")).toBeVisible();
  });

  it("has no axe violations", async () => {
    serve();
    renderWithIntl(<PurchasesOverviewScreen org={ORG} />);
    await screen.findByRole("link", { name: "Cedar Supply Co." });
    await waitFor(() => expect(document.querySelector("[aria-busy=true]")).toBeNull());
    await expectNoAxeViolations();
  });
});

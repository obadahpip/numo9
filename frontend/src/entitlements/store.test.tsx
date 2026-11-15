import { QueryClient } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { Gated, useFeature } from "@/catalogue/Gated";
import { entitlementsBody, entitlementsFetch } from "@/test/entitlements";
import { renderWithIntl } from "@/test/intl";

import { decide, EntitlementsProvider, productOf, useEntitlements } from "./store";

/**
 * U-03-T10 — the entitlement store (React Query) and the locked panel.
 * Acceptance: the locked panel shows the product name and the CTA per role.
 */
function client() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function Probe({ feature }: { feature: string }) {
  const decision = useFeature(feature);
  return (
    <p data-testid={feature}>
      {decision.state}
      {decision.productName ? ` ${decision.productName}` : ""}
    </p>
  );
}

function Mode() {
  const { status, data } = useEntitlements();
  return <p data-testid="mode">{`${status} ${data?.mode ?? ""}`}</p>;
}

function renderStore(ui: React.ReactNode) {
  return renderWithIntl(
    <EntitlementsProvider org="acme" client={client()}>
      {ui}
    </EntitlementsProvider>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("decide (U-03-T10)", () => {
  const ready = { org: "acme", status: "ready" as const, data: entitlementsBody() };

  it("allows a key in the features, CORE always, and gates the others naming product and packages", () => {
    expect(decide(ready, "accounting.sales_invoices.write").state).toBe("allowed");
    expect(decide(ready, "@core").state).toBe("allowed");
    expect(decide(ready, "payroll.pay_runs.write")).toEqual({
      feature: "payroll.pay_runs.write",
      state: "gated",
      product: "payroll",
      productName: "Payroll",
      packages: ["Complete"],
    });
  });

  it("is loading until the first answer and allows everything after a failed call", () => {
    expect(decide({ status: "loading" }, "payroll.pay_runs.write").state).toBe("loading");
    expect(decide({ status: "error" }, "payroll.pay_runs.write").state).toBe("allowed");
  });

  it("reads the product of companion-app keys", () => {
    expect(productOf("payroll.pay_runs.write")).toBe("payroll");
    expect(productOf("app.bank.feeds.read")).toBe("app.bank");
  });
});

describe("EntitlementsProvider (U-03-T10)", () => {
  it("loads the organisation's entitlements once and decides from them", async () => {
    const fetchMock = entitlementsFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderStore(
      <>
        <Mode />
        <Probe feature="accounting.sales_invoices.write" />
        <Probe feature="payroll.pay_runs.write" />
      </>,
    );
    expect(screen.getByTestId("mode")).toHaveTextContent("loading");
    expect(await screen.findByText("ready full")).toBeInTheDocument();
    expect(screen.getByTestId("accounting.sales_invoices.write")).toHaveTextContent("allowed");
    expect(screen.getByTestId("payroll.pay_runs.write")).toHaveTextContent("gated Payroll");
    const calls = fetchMock.mock.calls.filter(([url]) => String(url).includes("/entitlements"));
    expect(calls).toHaveLength(1);
    expect(String(calls[0]![0])).toBe("/api/v1/o/acme/entitlements");
  });

  it("allows everything when the bootstrap call fails (the API still answers 402)", async () => {
    vi.stubGlobal("fetch", entitlementsFetch(null, 500));
    renderStore(
      <>
        <Mode />
        <Probe feature="payroll.pay_runs.write" />
      </>,
    );
    expect(await screen.findByText(/^error/)).toBeInTheDocument();
    expect(screen.getByTestId("payroll.pay_runs.write")).toHaveTextContent("allowed");
  });
});

describe("locked panel per role (U-03-T10)", () => {
  it("owner: names the product and the packages, See packages + Change the package", async () => {
    vi.stubGlobal("fetch", entitlementsFetch(entitlementsBody()));
    renderStore(
      <Gated feature="payroll.pay_runs.write">
        <p>Pay runs</p>
      </Gated>,
    );
    expect(
      await screen.findByRole("heading", { name: "Payroll isn't in this organisation's package" }),
    ).toBeVisible();
    expect(
      screen.getByText(/It's part of the Payroll product, included in Complete/),
    ).toBeVisible();
    expect(screen.queryByText("Pay runs")).toBeNull();
    expect(screen.getByRole("link", { name: "See what's in each package" })).toHaveAttribute(
      "href",
      "/o/acme/settings/package-features",
    );
    expect(screen.getByRole("link", { name: "Change the package" })).toHaveAttribute(
      "href",
      "/o/acme/settings/subscription",
    );
    expect(screen.queryByRole("button", { name: "Ask the owner" })).toBeNull();
  });

  it("staff and accountants: See packages + Ask the owner (they can't buy)", async () => {
    vi.stubGlobal(
      "fetch",
      entitlementsFetch(entitlementsBody({ viewer: { can_change_package: false } })),
    );
    renderStore(
      <Gated feature="payroll.pay_runs.write">
        <p>Pay runs</p>
      </Gated>,
    );
    const ask = await screen.findByRole("button", { name: "Ask the owner" });
    expect(screen.queryByRole("link", { name: "Change the package" })).toBeNull();
    expect(screen.getByRole("link", { name: "See what's in each package" })).toBeVisible();
    expect(ask).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(ask);
    expect(ask).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("status")).toHaveTextContent(
      "Only the organisation's owner can change the package. Ask them to add Payroll.",
    );
  });
});

import { screen } from "@testing-library/react";

import { renderWithIntl } from "@/test/intl";

import { FeatureProvider, Gated, useFeatureAllowed } from "./Gated";

function Probe({ feature }: { feature: string }) {
  return <p>{useFeatureAllowed(feature) ? "allowed" : "not allowed"}</p>;
}

describe("Gated (U-01-T06)", () => {
  it("renders the children with the allow-all stub (no provider until U-03)", () => {
    renderWithIntl(
      <Gated feature="accounting.sales_invoices.write">
        <p>Invoice editor</p>
      </Gated>,
    );
    expect(screen.getByText("Invoice editor")).toBeInTheDocument();
  });

  it("renders the translated locked panel in place when gated", () => {
    renderWithIntl(
      <FeatureProvider
        source={(feature) => ({
          feature,
          state: "gated",
          product: "payroll",
          productName: "Payroll",
          packages: ["Growth", "Complete"],
        })}
      >
        <Gated feature="payroll.pay_runs.write" packagesHref="/o/acme/settings/package">
          <p>Pay runs</p>
        </Gated>
        <Probe feature="payroll.pay_runs.write" />
      </FeatureProvider>,
    );
    expect(screen.queryByText("Pay runs")).not.toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Payroll isn't in this organisation's package" }),
    ).toBeVisible();
    expect(screen.getByText(/included in Growth, Complete/)).toBeVisible();
    expect(screen.getByRole("link", { name: "See what's in each package" })).toHaveAttribute(
      "href",
      "/o/acme/settings/package",
    );
    expect(screen.getByText("not allowed")).toBeInTheDocument();
  });
});

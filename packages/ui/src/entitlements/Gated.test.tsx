import { render, renderHook, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { expectNoAxeViolations } from "../test/axe";
import {
  allowAllFeatures,
  FeatureProvider,
  Gated,
  useFeature,
  type EntitlementSource,
} from "./Gated";

const source: EntitlementSource = (feature) => {
  if (feature.startsWith("payroll.")) {
    return { feature, state: "gated", product: "payroll", productName: "Payroll" };
  }
  if (feature.startsWith("tax.")) return { feature, state: "loading" };
  return { feature, state: "allowed" };
};

const wrapper = ({ children }: { children: ReactNode }) => (
  <FeatureProvider source={source}>{children}</FeatureProvider>
);

describe("useFeature (U-01-T06)", () => {
  it("allows every feature without a provider (stub until U-03)", () => {
    const { result } = renderHook(() => useFeature("payroll.pay_runs.write"));
    expect(result.current).toEqual({ feature: "payroll.pay_runs.write", state: "allowed" });
    expect(allowAllFeatures("x.y.read").state).toBe("allowed");
  });

  it("returns the provider's decision", () => {
    const { result } = renderHook(() => useFeature("payroll.pay_runs.write"), { wrapper });
    expect(result.current).toMatchObject({ state: "gated", productName: "Payroll" });
  });
});

describe("<Gated> (U-01-T06)", () => {
  it("renders the children when allowed", () => {
    render(
      <Gated feature="accounting.sales_invoices.write" locked={<p>Locked</p>}>
        <p>Invoice editor</p>
      </Gated>,
      { wrapper },
    );
    expect(screen.getByText("Invoice editor")).toBeInTheDocument();
    expect(screen.queryByText("Locked")).not.toBeInTheDocument();
    const box = document.querySelector("[data-feature='accounting.sales_invoices.write']");
    expect(box).toHaveAttribute("data-feature-state", "allowed");
  });

  it("renders the locked state in place when gated, with the decision", async () => {
    const { container } = render(
      <Gated
        feature="payroll.pay_runs.write"
        locked={(d) => <h2>{`${d.productName} isn't in your package`}</h2>}
      >
        <p>Pay run editor</p>
      </Gated>,
      { wrapper },
    );
    expect(screen.queryByText("Pay run editor")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Payroll isn't in your package" })).toBeVisible();
    expect(container.firstChild).toHaveAttribute("data-feature-state", "gated");
    await expectNoAxeViolations(container);
  });

  it("never shows the children while loading", () => {
    render(
      <Gated feature="tax.returns.write" locked={<p>Locked</p>} loading={<p>Checking…</p>}>
        <p>Return</p>
      </Gated>,
      { wrapper },
    );
    expect(screen.getByText("Checking…")).toBeInTheDocument();
    expect(screen.queryByText("Return")).not.toBeInTheDocument();
    expect(screen.queryByText("Locked")).not.toBeInTheDocument();
  });
});

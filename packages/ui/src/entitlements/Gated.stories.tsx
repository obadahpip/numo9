import type { Meta, StoryObj } from "@storybook/react";

import { Button } from "../primitives/Button";
import { ExplainPanel } from "../states/ExplainPanel";
import { FeatureProvider, Gated, type EntitlementSource, type FeatureDecision } from "./Gated";

/**
 * Feature gating (U-01-T06, U-03-T10): `<Gated feature=…>` renders its content when the
 * organisation's package includes the feature key, else the locked panel in place — never hidden,
 * never a redirect. Decisions come from the entitlement source (the U-03 store in the app).
 *
 * Locked panel design (U-03-T10): icon, one sentence naming the product and the packages that
 * include it, and buttons per role — the owner: "See packages" + "Change the package"; staff and
 * accountants (they can't buy): "See packages" + "Ask the owner".
 */
const meta: Meta = { title: "Entitlements/Gated" };
export default meta;
type Story = StoryObj;

const payroll: EntitlementSource = (feature) =>
  feature.startsWith("payroll.")
    ? {
        feature,
        state: "gated",
        product: "payroll",
        productName: "Payroll",
        packages: ["Growth", "Complete"],
      }
    : { feature, state: "allowed" };

function lockedFor(role: "owner" | "staff") {
  return function Locked(decision: FeatureDecision) {
    return (
      <ExplainPanel
        kind="gated"
        title={`${decision.productName} isn't in this organisation's package`}
        body={`It's part of the ${decision.productName} product, included in ${decision.packages?.join(", ")}. Everything you already have stays here and keeps working.`}
        actions={[
          <Button key="packages" variant="primary">
            See what's in each package
          </Button>,
          role === "owner" ? (
            <Button key="change">Change the package</Button>
          ) : (
            <Button key="ask">Ask the owner</Button>
          ),
        ]}
      />
    );
  };
}

const Locked = lockedFor("staff");

function PayRuns() {
  return (
    <div className="rounded-lg border border-border bg-surface p-6 text-sm text-fg">
      Pay run · Nov 1–15, 2026 · 12 employees
    </div>
  );
}

export const Allowed: Story = {
  render: () => (
    <FeatureProvider source={payroll}>
      <Gated feature="accounting.sales_invoices.write" locked={Locked}>
        <div className="rounded-lg border border-border bg-surface p-6 text-sm text-fg">
          Invoice INV-0042 · Maple Leaf Supply Ltd. · $1,250.00
        </div>
      </Gated>
    </FeatureProvider>
  ),
};

export const GatedFeature: Story = {
  name: "Gated",
  render: () => (
    <FeatureProvider source={payroll}>
      <Gated feature="payroll.pay_runs.write" locked={Locked}>
        <PayRuns />
      </Gated>
    </FeatureProvider>
  ),
};

export const LockedPanelOwner: Story = {
  name: "Locked panel — owner",
  render: () => (
    <FeatureProvider source={payroll}>
      <Gated feature="payroll.pay_runs.write" locked={lockedFor("owner")}>
        <PayRuns />
      </Gated>
    </FeatureProvider>
  ),
};

export const LockedPanelStaff: Story = {
  name: "Locked panel — staff and accountants",
  render: () => (
    <FeatureProvider source={payroll}>
      <Gated feature="payroll.pay_runs.write" locked={lockedFor("staff")}>
        <PayRuns />
      </Gated>
    </FeatureProvider>
  ),
};

"use client";

import { createContext, useContext, useMemo, type ReactNode } from "react";

/**
 * Feature gating (U-01-T06). Every gated screen or control declares the feature key it needs
 * (`<product>.<area>.<action>`, docs/architecture/feature-keys.md) and asks the entitlement
 * source — the U-03 entitlement store; until then a source that allows every key:
 *
 *   const invoices = useFeature("accounting.sales_invoices.write");
 *   <Gated feature="payroll.pay_runs.write" locked={(d) => <ExplainPanel kind="gated" … />}>
 *     <PayRunEditor />
 *   </Gated>
 *
 * Gating is explicit (Phase 0 UX principle 3): a gated feature renders the locked state in place
 * — never hidden, never a redirect — and `data-feature` / `data-feature-state` mark it for tests.
 */
export type FeatureState = "allowed" | "gated" | "loading";

export interface FeatureDecision {
  feature: string;
  state: FeatureState;
  /** Product that includes the feature (`accounting`), when known. */
  product?: string;
  /** The product's display name in the viewer's language ("Payroll"), when known. */
  productName?: string;
  /** Display names of the packages that include it (U-02/U-03), when known. */
  packages?: readonly string[];
}

/** Where decisions come from: the U-03 entitlement store implements this. */
export type EntitlementSource = (feature: string) => FeatureDecision;

/** Interface stub until U-03: every feature is allowed. */
export const allowAllFeatures: EntitlementSource = (feature) => ({ feature, state: "allowed" });

const EntitlementContext = createContext<EntitlementSource>(allowAllFeatures);

export interface FeatureProviderProps {
  source: EntitlementSource;
  children: ReactNode;
}

export function FeatureProvider({ source, children }: FeatureProviderProps) {
  return <EntitlementContext.Provider value={source}>{children}</EntitlementContext.Provider>;
}

/** The decision for one feature key from the nearest `FeatureProvider` (allow-all without one). */
export function useFeature(feature: string): FeatureDecision {
  const source = useContext(EntitlementContext);
  return useMemo(() => source(feature), [source, feature]);
}

export interface GatedProps {
  feature: string;
  /** Rendered when the feature is allowed. */
  children: ReactNode;
  /** Locked state in place of the children (ExplainPanel kind="gated", U-03-T10 design). */
  locked: ReactNode | ((decision: FeatureDecision) => ReactNode);
  /** While the decision is loading (default: nothing — never the children). */
  loading?: ReactNode;
  className?: string;
}

/** Renders the children when the feature is allowed, else the locked state — in place. */
export function Gated({ feature, children, locked, loading = null, className }: GatedProps) {
  const decision = useFeature(feature);
  const content =
    decision.state === "allowed"
      ? children
      : decision.state === "loading"
        ? loading
        : typeof locked === "function"
          ? locked(decision)
          : locked;
  return (
    <div data-feature={feature} data-feature-state={decision.state} className={className}>
      {content}
    </div>
  );
}

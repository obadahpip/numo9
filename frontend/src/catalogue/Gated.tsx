"use client";

/**
 * Feature gating in the web app (U-01-T06): `useFeature(key)` and `<Gated feature=…>` from
 * `@numo9/ui`, with the translated locked panel. Decisions come from the nearest
 * `FeatureProvider` — the U-03 entitlement store (React Query) provides it; until then every
 * feature is allowed, so declaring keys never hides a Phase 0 screen.
 *
 *   <Gated feature="accounting.sales_invoices.write"><InvoiceEditor /></Gated>
 *
 * A gated feature shows the panel in place, the URL unchanged — never a redirect (gap-14).
 */
import { Gated as UiGated, ExplainPanel, useFeature, type FeatureDecision } from "@numo9/ui";
import type { ReactNode } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

export { FeatureProvider, useFeature, type FeatureDecision } from "@numo9/ui";

export const gatedMessages = defineMessages({
  title: {
    id: "catalogue.gated.title",
    defaultMessage: "{product} isn't in this organisation's package",
    description: "Locked panel heading: the product that includes the feature",
  },
  titleUnknown: {
    id: "catalogue.gated.titleUnknown",
    defaultMessage: "This isn't in this organisation's package",
    description: "Locked panel heading when the product is not known",
  },
  body: {
    id: "catalogue.gated.body",
    defaultMessage:
      "It's part of the {product} product. Everything you already have stays here and keeps working.",
    description: "Locked panel text",
  },
  bodyPackages: {
    id: "catalogue.gated.bodyPackages",
    defaultMessage:
      "It's part of the {product} product, included in {packages}. Everything you already have stays here and keeps working.",
    description: "Locked panel text naming the packages that include the product",
  },
  bodyUnknown: {
    id: "catalogue.gated.bodyUnknown",
    defaultMessage: "Everything you already have stays here and keeps working.",
    description: "Locked panel text when the product is not known",
  },
  seePackages: {
    id: "catalogue.gated.seePackages",
    defaultMessage: "See what's in each package",
    description: "Locked panel action: open the Package and features page",
  },
});

export function GatedPanel({
  decision,
  packagesHref,
  headingLevel = 2,
}: {
  decision: FeatureDecision;
  /** Link to the in-app Package and features page (U-01-T12). */
  packagesHref?: string;
  headingLevel?: 1 | 2;
}) {
  const fm = useFormatMessage();
  const product = decision.productName ?? decision.product;
  const packages = decision.packages?.join(", ");
  return (
    <ExplainPanel
      kind="gated"
      headingLevel={headingLevel}
      title={product ? fm(gatedMessages.title, { product }) : fm(gatedMessages.titleUnknown)}
      body={
        product
          ? packages
            ? fm(gatedMessages.bodyPackages, { product, packages })
            : fm(gatedMessages.body, { product })
          : fm(gatedMessages.bodyUnknown)
      }
      actions={
        packagesHref
          ? [
              <a
                key="packages"
                href={packagesHref}
                className="inline-flex items-center rounded-md border border-border px-3 py-2 text-sm font-medium text-fg underline-offset-2 hover:underline"
              >
                {fm(gatedMessages.seePackages)}
              </a>,
            ]
          : []
      }
    />
  );
}

export function Gated({
  feature,
  children,
  packagesHref,
  headingLevel,
  loading,
}: {
  feature: string;
  children: ReactNode;
  packagesHref?: string;
  headingLevel?: 1 | 2;
  loading?: ReactNode;
}) {
  return (
    <UiGated
      feature={feature}
      loading={loading}
      locked={(decision) => (
        <GatedPanel decision={decision} packagesHref={packagesHref} headingLevel={headingLevel} />
      )}
    >
      {children}
    </UiGated>
  );
}

/** Whether a feature is allowed right now (allowed only once known — never while loading). */
export function useFeatureAllowed(feature: string): boolean {
  return useFeature(feature).state === "allowed";
}

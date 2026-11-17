"use client";

/**
 * Feature gating in the web app (U-01-T06, U-03-T10): `useFeature(key)` and `<Gated feature=…>`
 * from `@numo9/ui`, with the translated locked panel. Decisions come from the nearest
 * `FeatureProvider` — the entitlement store (`@/entitlements/store`, React Query) that the app
 * shell mounts; without one every feature is allowed.
 *
 *   <Gated feature="accounting.sales_invoices.write"><InvoiceEditor /></Gated>
 *
 * A gated feature shows the locked panel in place, the URL unchanged — never a redirect (gap-14):
 * an icon, one sentence naming the product and the packages that include it (gap-41), and buttons
 * per role — the organisation's owner gets "See packages" and "Change the package"; everyone else
 * (staff, accountants: they can't buy) "See packages" and "Ask the owner". A 402 from the API
 * shows the same panel (`decisionFromError`).
 */
import { Gated as UiGated, ExplainPanel, useFeature, type FeatureDecision } from "@numo9/ui";
import { useId, useState, type ReactNode } from "react";

import { useEntitlements } from "@/entitlements/store";
import { defineMessages, useFormatMessage } from "@/i18n";
import { orgModuleUrl } from "@/routing/routes";

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
  changePackage: {
    id: "catalogue.gated.changePackage",
    defaultMessage: "Change the package",
    description: "Locked panel action for the organisation owner: open Settings → Subscription",
  },
  askOwner: {
    id: "catalogue.gated.askOwner",
    defaultMessage: "Ask the owner",
    description: "Locked panel action for everyone but the owner: shows how to get the product",
  },
  askOwnerText: {
    id: "catalogue.gated.askOwnerText",
    defaultMessage:
      "Only the organisation's owner can change the package. Ask them to add {product}.",
    description: "Shown after Ask the owner: accountants and staff can't buy products",
  },
  readOnlyTitle: {
    id: "catalogue.gated.readOnlyTitle",
    defaultMessage: "This organisation is read-only",
    description: "Locked panel heading on a change while the organisation is read-only",
  },
  readOnlyTrial: {
    id: "catalogue.gated.readOnlyTrial",
    defaultMessage:
      "The free trial ended. You can still see and export everything; choose a package to make changes again.",
    description: "Locked panel text after the free trial (U-05-T11)",
  },
  readOnlyOther: {
    id: "catalogue.gated.readOnlyOther",
    defaultMessage:
      "You can still see and export everything; reactivate the subscription to make changes again.",
    description: "Locked panel text while read-only for any other reason",
  },
  choosePackage: {
    id: "catalogue.gated.choosePackage",
    defaultMessage: "Choose a package",
    description: "Locked panel action for the owner while read-only: Settings → Subscription",
  },
  askOwnerTextUnknown: {
    id: "catalogue.gated.askOwnerTextUnknown",
    defaultMessage: "Only the organisation's owner can change the package.",
    description: "Shown after Ask the owner when the product is not known",
  },
});

const ACTION =
  "inline-flex items-center rounded-md border border-border px-3 py-2 text-sm font-medium text-fg underline-offset-2 hover:underline";

export function GatedPanel({
  decision,
  packagesHref,
  headingLevel = 2,
}: {
  decision: FeatureDecision;
  /** Link to the in-app Package and features page (U-01-T12); default: the organisation's. */
  packagesHref?: string;
  headingLevel?: 1 | 2;
}) {
  const fm = useFormatMessage();
  const { org, data } = useEntitlements();
  const [asked, setAsked] = useState(false);
  const askId = useId();
  const product = decision.productName ?? decision.product;
  const packages = decision.packages?.join(", ");
  const seeHref =
    packagesHref ?? (org ? orgModuleUrl(org, "settings/package-features") : undefined);
  const owner = data?.viewer.can_change_package ?? false;
  const actions: ReactNode[] = [];
  if (seeHref) {
    actions.push(
      <a key="packages" href={seeHref} className={ACTION}>
        {fm(gatedMessages.seePackages)}
      </a>,
    );
  }
  if (owner && org) {
    actions.push(
      <a key="change" href={orgModuleUrl(org, "settings/subscription")} className={ACTION}>
        {fm(gatedMessages.changePackage)}
      </a>,
    );
  } else if (data) {
    actions.push(
      <button
        key="ask"
        type="button"
        className={ACTION}
        aria-expanded={asked}
        aria-controls={askId}
        onClick={() => setAsked(true)}
      >
        {fm(gatedMessages.askOwner)}
      </button>,
    );
  }
  if (data?.mode === "read_only") {
    // U-05-T11: a change while read-only (trial ended, payment failed…) — say why, not "package".
    const trial = data.reason === "trial_ended";
    return (
      <ExplainPanel
        kind="gated"
        headingLevel={headingLevel}
        title={fm(gatedMessages.readOnlyTitle)}
        body={fm(trial ? gatedMessages.readOnlyTrial : gatedMessages.readOnlyOther)}
        actions={
          owner && org
            ? [
                <a
                  key="choose"
                  href={orgModuleUrl(org, "settings/subscription")}
                  className={ACTION}
                >
                  {fm(gatedMessages.choosePackage)}
                </a>,
              ]
            : []
        }
      />
    );
  }
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
      actions={actions}
    >
      {data && !owner ? (
        <p id={askId} role="status" className="text-sm text-fg-muted">
          {asked
            ? product
              ? fm(gatedMessages.askOwnerText, { product })
              : fm(gatedMessages.askOwnerTextUnknown)
            : null}
        </p>
      ) : null}
    </ExplainPanel>
  );
}

/**
 * The locked panel's decision from a 402 `entitlement.feature_not_in_package` body (U-03-T07):
 * forms show the same panel as screens. Null for any other body.
 */
export function decisionFromError(body: unknown): FeatureDecision | null {
  if (typeof body !== "object" || body === null) return null;
  const error = body as {
    code?: unknown;
    feature?: unknown;
    product?: unknown;
    product_name?: unknown;
    packages?: unknown;
  };
  if (error.code !== "entitlement.feature_not_in_package" || typeof error.feature !== "string") {
    return null;
  }
  const packages = Array.isArray(error.packages)
    ? error.packages
        .map((p: unknown) => (p as { name?: unknown }).name)
        .filter((name): name is string => typeof name === "string")
    : undefined;
  return {
    feature: error.feature,
    state: "gated",
    product: typeof error.product === "string" ? error.product : undefined,
    productName: typeof error.product_name === "string" ? error.product_name : undefined,
    packages,
  };
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

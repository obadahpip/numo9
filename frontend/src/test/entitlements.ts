/**
 * Entitlements bootstrap bodies for component tests (U-03): `entitlementsBody({...})` and a fetch
 * stub that answers `GET /api/v1/o/<org>/entitlements` (anything else never resolves).
 */
import { vi } from "vitest";

import type { Entitlements } from "@/entitlements/api";

/** Phase 0 Accounting keys (the seed), enough for the screens under test. */
export const ACCOUNTING_FEATURES = [
  "accounting.contacts.read",
  "accounting.contacts.write",
  "accounting.chart_of_accounts.read",
  "accounting.chart_of_accounts.write",
  "accounting.journals.read",
  "accounting.journals.write",
  "accounting.journals.approve",
  "accounting.documents.read",
  "accounting.documents.write",
  "accounting.sales_invoices.read",
  "accounting.sales_invoices.write",
  "accounting.sales_invoices.approve",
  "accounting.credit_notes.read",
  "accounting.credit_notes.write",
];

export function entitlementsBody(overrides: Partial<Entitlements> = {}): Entitlements {
  return {
    organisation: "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6",
    mode: "full",
    reason: "active",
    since: null,
    package: "growth",
    package_name: "Growth",
    status: "active",
    founding: false,
    products: ["accounting", "practice", "portal"],
    read_products: [],
    features: ACCOUNTING_FEATURES,
    version: "1.1",
    product_names: {
      accounting: "Accounting",
      tax: "Tax",
      payroll: "Payroll",
      practice: "Practice",
      portal: "Client portal",
    },
    packages_by_product: {
      accounting: [{ code: "growth", name: "Growth" }],
      payroll: [{ code: "complete", name: "Complete" }],
    },
    time_zone: "America/Toronto",
    viewer: { can_change_package: true },
    ...overrides,
  };
}

/** A `fetch` stub: the entitlements URL answers `body`; every other request stays pending. */
export function entitlementsFetch(body: Entitlements | null = entitlementsBody(), status = 200) {
  return vi.fn((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.includes("/entitlements")) {
      return Promise.resolve(
        new Response(JSON.stringify(body ?? {}), {
          status,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    return new Promise<Response>(() => undefined);
  });
}

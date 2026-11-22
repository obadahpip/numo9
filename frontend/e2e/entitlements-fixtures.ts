import type { Page } from "@playwright/test";

/**
 * Entitlements bootstrap bodies for the Playwright suites (U-03), in the shape of
 * `GET /api/v1/o/<org>/entitlements` (backend/numo9/entitlements/presenter.py + api.py).
 */
export const ACCOUNTING_FEATURES = [
  "accounting.contacts.read",
  "accounting.contacts.write",
  "accounting.chart_of_accounts.read",
  "accounting.chart_of_accounts.write",
  "accounting.journals.read",
  "accounting.journals.write",
  "accounting.journals.approve",
  "accounting.documents.read",
  "accounting.banking.read",
  "accounting.banking.write",
  "accounting.documents.write",
  "accounting.sales_invoices.read",
  "accounting.sales_invoices.write",
  "accounting.sales_invoices.approve",
  "accounting.credit_notes.read",
  "accounting.credit_notes.write",
  "accounting.bills.approve",
  "accounting.purchase_orders.approve",
  "accounting.expense_claims.approve",
];

export function entitlements(overrides: Record<string, unknown> = {}) {
  return {
    organisation: "7f3c2a10-1b2c-4d5e-8f90-a1b2c3d4e5f6",
    mode: "full",
    reason: "active",
    since: null,
    grace_until: null,
    package: "starter",
    package_name: "Starter",
    status: "active",
    founding: false,
    products: ["accounting", "practice", "portal"],
    read_products: [],
    features: ACCOUNTING_FEATURES,
    version: "3.7",
    product_names: {
      accounting: "Accounting",
      tax: "Tax",
      payroll: "Payroll",
      inventory: "Inventory",
      finance: "Finance",
      practice: "Practice",
      portal: "Client portal",
    },
    packages_by_product: {
      accounting: [
        { code: "starter", name: "Starter" },
        { code: "growth", name: "Growth" },
      ],
      payroll: [{ code: "complete", name: "Complete" }],
    },
    time_zone: "America/Toronto",
    viewer: { can_change_package: true },
    ...overrides,
  };
}

/** No Accounting at all: what a package without Accounting resolves to. */
export const WITHOUT_ACCOUNTING = {
  products: ["tax", "practice", "portal"],
  features: ["tax.codes.read", "tax.codes.write", "tax.returns.read"],
};

export async function mockEntitlements(page: Page, org: string, body: unknown): Promise<string[]> {
  const requests: string[] = [];
  await page.route(`**/api/v1/o/${org}/entitlements`, (route) => {
    requests.push(route.request().url());
    return route.fulfill({ json: body });
  });
  return requests;
}

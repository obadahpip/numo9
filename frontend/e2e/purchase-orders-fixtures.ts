import { type Page } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";

/** Purchase order API answers for the E-01 Playwright suites (shapes of numo9/purchases/po_api.py). */
export const ORG = "acme";
export const SUPPLIER = "5a5a5a5a-0000-4000-8000-000000000001";
export const EXPENSE = "61006100-0000-4000-8000-000000000002";
export const PO = "90909090-0000-4000-8000-000000000001";
export const LINE_1 = "11111111-0000-4000-8000-000000000001";
export const LINE_2 = "11111111-0000-4000-8000-000000000002";
export const BILL = "b1b1b1b1-0000-4000-8000-000000000001";

const account = {
  id: EXPENSE,
  code: "6100",
  name: "Office supplies",
  type: "expense",
  subtype: "operating_expense",
  subtype_label: "",
  system_role: "",
  is_bank: false,
  depth: 1,
  has_children: false,
  require_contact: false,
  require_tracking: false,
  require_attachment: false,
  default_tax_key: "",
};

function line(over: Record<string, unknown> = {}) {
  return {
    id: LINE_1,
    position: 0,
    description: "Tiles",
    quantity: "10.0000",
    unit_price: "25.0000",
    discount_type: "none",
    discount_value: "0",
    account: { id: EXPENSE, code: "6100", name: "Office supplies" },
    tax_code: null,
    tracking: {},
    quantity_received: "0.0000",
    quantity_billed: "0.0000",
    outstanding: "10.0000",
    net: "250.00",
    tax_amount: "0.00",
    amount: "250.00",
    ...over,
  };
}

export function savedOrder(over: Record<string, unknown> = {}) {
  return {
    id: PO,
    number: "",
    status: "draft",
    status_label: "Draft",
    supplier: { id: SUPPLIER, name: "Cedar Supply Co." },
    reference: "",
    date: "2026-06-15",
    delivery_date: "2026-06-30",
    total: "250.00",
    url: `/o/${ORG}/purchases/orders/${PO}`,
    terms: null,
    currency: "CAD",
    tax_mode: "no_tax",
    discount_type: "none",
    discount_value: "0",
    notes: "",
    delivery_attention: "Site office",
    delivery_address: "12 King St W, Toronto ON",
    delivery_instructions: "",
    subtotal: "250.00",
    discount_total: "0.00",
    tax_total: "0.00",
    approved_total: null,
    version: 1,
    submitted_at: null,
    approved_at: null,
    approved_by: "",
    sent_at: null,
    approval: { limit: "5000.00", within: true },
    lines: [line()],
    receipts: [],
    ...over,
  };
}

/** An approved PO, 10 tiles and 4 grout, nothing received yet. */
export function approvedOrder(over: Record<string, unknown> = {}) {
  return savedOrder({
    number: "PO-0001",
    status: "approved",
    status_label: "Approved",
    total: "330.00",
    lines: [
      line(),
      line({
        id: LINE_2,
        position: 1,
        description: "Grout",
        quantity: "4.0000",
        unit_price: "20.0000",
        outstanding: "4.0000",
        net: "80.00",
        amount: "80.00",
      }),
    ],
    ...over,
  });
}

/** The editor's reference data (accounts, suppliers, tax codes, the calculator). */
export async function mockReferenceData(page: Page) {
  await mockCsrf(page);
  await page.route(`**/api/v1/o/${ORG}/accounts?*`, (r) =>
    r.fulfill({ json: { count: 1, results: [account] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/contacts?*`, (r) =>
    r.fulfill({
      json: {
        count: 1,
        next_offset: null,
        role_counts: {},
        results: [{ id: SUPPLIER, display_name: "Cedar Supply Co.", roles: ["supplier"] }],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/codes*`, (r) => r.fulfill({ json: { results: [] } }));
  await page.route(`**/api/v1/o/${ORG}/documents/**`, (r) => r.fulfill({ status: 503, json: {} }));
}

export async function mockOrderEditor(page: Page) {
  await mockReferenceData(page);
  const posted: Record<string, unknown>[] = [];
  await page.route(`**/api/v1/o/${ORG}/purchase-orders/approval-limit`, (r) =>
    r.fulfill({ json: { limit: "5000.00" } }),
  );
  await page.route(`**/api/v1/o/${ORG}/purchase-orders`, async (r) => {
    posted.push(r.request().postDataJSON() as Record<string, unknown>);
    await r.fulfill({ status: 201, json: savedOrder() });
  });
  await page.route(`**/api/v1/o/${ORG}/purchase-orders/${PO}`, (r) =>
    r.fulfill({ json: savedOrder() }),
  );
  await page.route(`**/api/v1/o/${ORG}/purchase-orders/${PO}/approve`, (r) =>
    r.fulfill({ json: approvedOrder() }),
  );
  return posted;
}

import type { Page } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";

/** Mocks of the quote suites (D-02-T12…T14): the API shapes of quotes_api.py. */
export const ORG = "acme";
export const CUSTOMER = "c0c0c0c0-0000-4000-8000-000000000001";
export const REVENUE = "40004000-0000-4000-8000-000000000002";
export const QUOTE = "2a2a2a2a-0000-4000-8000-000000000001";
export const TOKEN = "eyJxIjoiMSJ9:1tok:sig";

const account = {
  id: REVENUE,
  code: "4000",
  name: "Sales",
  type: "revenue",
  subtype: "revenue",
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

function line(id: string, description: string, price: string, over: Record<string, unknown> = {}) {
  return {
    id,
    position: 0,
    item: null,
    description,
    quantity: "1.0000",
    unit_price: `${price}.0000`,
    discount_type: "none",
    discount_value: "0.0000",
    account: { id: REVENUE, code: "4000", name: "Sales" },
    tax_code: null,
    tax_overridden: false,
    tracking: {},
    net: `${price}.00`,
    tax_amount: "0.00",
    amount: `${price}.00`,
    is_optional: false,
    alternative_group: "",
    selected: true,
    counted: true,
    ...over,
  };
}

export function savedQuote(over: Record<string, unknown> = {}) {
  return {
    id: QUOTE,
    number: "QU-0001",
    status: "draft",
    status_label: "Draft",
    title: "Kitchen renovation",
    customer: { id: CUSTOMER, name: "Maple Leaf Supply Ltd." },
    reference: "",
    date: "2026-06-15",
    expiry_date: "2026-07-15",
    total: "1500.00",
    url: `/o/${ORG}/sales/quotes/${QUOTE}`,
    summary: "",
    currency: "CAD",
    tax_mode: "exclusive",
    ship_to_country: "",
    ship_to_province: "",
    discount_type: "none",
    discount_value: "0.0000",
    deposit_type: "none",
    deposit_value: "0.0000",
    deposit_amount: "0.00",
    notes: "",
    subtotal: "1500.00",
    discount_total: "0.00",
    tax_total: "0.00",
    version: 1,
    sent_at: null,
    viewed_at: null,
    accepted_at: null,
    declined_at: null,
    decline_reason: "",
    expired_at: null,
    invoiced_at: null,
    invoice: null,
    deposit_invoice: null,
    revises: null,
    superseded_by: null,
    link: null,
    acceptance: null,
    pdf: `/api/v1/o/${ORG}/quotes/${QUOTE}/pdf`,
    lines: [
      line("l1", "Cabinets", "1000"),
      line("l2", "Install", "200", { is_optional: true, selected: false, counted: false }),
      line("l3", "Oak doors", "500", { alternative_group: "Wood" }),
      line("l4", "Walnut doors", "800", {
        alternative_group: "Wood",
        selected: false,
        counted: false,
      }),
    ],
    ...over,
  };
}

export async function mockQuoteEditor(page: Page, initial = savedQuote()) {
  await mockCsrf(page);
  const state = { current: initial, posts: [] as { path: string; body: unknown }[] };
  await page.route(`**/api/v1/o/${ORG}/accounts?*`, (r) =>
    r.fulfill({ json: { count: 1, results: [account] } }),
  );
  await page.route(`**/api/v1/o/${ORG}/contacts?*`, (r) =>
    r.fulfill({
      json: {
        count: 1,
        next_offset: null,
        role_counts: {},
        results: [{ id: CUSTOMER, display_name: "Maple Leaf Supply Ltd.", roles: ["customer"] }],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/tax/**`, (r) => r.fulfill({ json: { results: [] } }));
  await page.route(`**/api/v1/o/${ORG}/documents/**`, (r) => r.fulfill({ status: 503, json: {} }));
  await page.route(`**/api/v1/o/${ORG}/quotes**`, async (r) => {
    const url = new URL(r.request().url());
    const path = url.pathname.replace(`/api/v1/o/${ORG}/quotes`, "");
    const method = r.request().method();
    if (method === "POST" || method === "PATCH") {
      state.posts.push({ path: `${method} ${path}`, body: r.request().postDataJSON() ?? {} });
      if (path === "") return r.fulfill({ status: 201, json: state.current });
      return r.fulfill({ json: state.current });
    }
    return r.fulfill({ json: state.current });
  });
  return state;
}

export function publicQuote(over: Record<string, unknown> = {}) {
  const lines = savedQuote().lines.map((l) => ({
    id: l.id,
    description: l.description,
    quantity: "1",
    unit_price: l.unit_price.slice(0, -2),
    amount: l.amount,
    tax: "0.00",
    is_optional: l.is_optional,
    alternative_group: l.alternative_group,
    selected: l.selected,
    counted: l.counted,
  }));
  return {
    number: "QU-0001",
    title: "Kitchen renovation",
    summary: "Supply and install of the kitchen.",
    organisation: "Refined Interiors Inc.",
    customer: "Maple Leaf Supply Ltd.",
    date: "2026-06-15",
    expiry_date: "2026-07-15",
    currency: "CAD",
    status: "viewed",
    lines,
    subtotal: "1500.00",
    discount_total: "0.00",
    tax_total: "0.00",
    total: "1500.00",
    deposit_type: "none",
    deposit_value: "0",
    deposit: "0.00",
    accepted_by: null,
    can_accept: true,
    reason: null,
    ...over,
  };
}

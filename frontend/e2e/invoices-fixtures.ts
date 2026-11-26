import type { Page } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";

/** Mocks of the invoice editor suites (D-03a-T13, T14): the API shapes of invoices_api.py. */
export const ORG = "acme";
export const CUSTOMER = "c0c0c0c0-0000-4000-8000-000000000001";
export const REVENUE = "40004000-0000-4000-8000-000000000002";
export const INVOICE = "1a1a1a1a-0000-4000-8000-000000000001";

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

export function savedInvoice(over: Record<string, unknown> = {}) {
  return {
    id: INVOICE,
    number: "",
    status: "draft",
    status_label: "Draft",
    customer: { id: CUSTOMER, name: "Maple Leaf Supply Ltd." },
    reference: "",
    date: "2026-06-15",
    due_date: "2026-07-15",
    total: "250.00",
    amount_paid: "0.00",
    amount_due: "250.00",
    url: `/o/${ORG}/sales/invoices/${INVOICE}`,
    terms: null,
    currency: "CAD",
    tax_mode: "exclusive",
    ship_to_country: "",
    ship_to_province: "",
    discount_type: "none",
    discount_value: "0.0000",
    notes: "",
    subtotal: "250.00",
    discount_total: "0.00",
    tax_total: "0.00",
    version: 1,
    journal: null,
    submitted_at: null,
    approved_at: null,
    approved_by: "",
    sent_at: null,
    voided_at: null,
    pdf: `/api/v1/o/${ORG}/invoices/${INVOICE}/pdf`,
    attachments: [],
    lines: [
      {
        id: "l1",
        position: 0,
        item: null,
        description: "Design consultation",
        quantity: "1.0000",
        unit_price: "250.0000",
        discount_type: "none",
        discount_value: "0.0000",
        account: { id: REVENUE, code: "4000", name: "Sales" },
        tax_code: null,
        tax_overridden: false,
        tracking: {},
        net: "250.00",
        tax_amount: "0.00",
        amount: "250.00",
      },
    ],
    ...over,
  };
}

export const JOURNAL = [
  {
    account: "1200",
    name: "Accounts receivable",
    debit: "250.00",
    credit: "0.00",
    description: "",
  },
  { account: "4000", name: "Sales", debit: "0.00", credit: "250.00", description: "" },
];

export function preview(over: Record<string, unknown> = {}) {
  return {
    journal: { posted: false, complete: true, lines: JOURNAL },
    period: {
      date: "2026-06-15",
      ar_lock: "2026-03-31",
      locked: false,
      lock: null,
      tax_period: {
        start: "2026-04-01",
        end: "2026-06-30",
        status: "open",
        filed: false,
        due_date: "2026-07-31",
      },
    },
    approval: null,
    credit: { outcome: "no_limit", message: "" },
    duplicates: [],
    ...over,
  };
}

export interface InvoiceState {
  current: Record<string, unknown>;
  preview: Record<string, unknown>;
  posts: { path: string; body: Record<string, unknown> }[];
}

export async function mockInvoiceEditor(page: Page, initial = savedInvoice()) {
  await mockCsrf(page);
  const state: InvoiceState = { current: initial, preview: preview(), posts: [] };
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
  await page.route(`**/api/v1/o/${ORG}/tax/codes*`, (r) => r.fulfill({ json: { results: [] } }));
  await page.route(`**/api/v1/o/${ORG}/documents/**`, (r) => r.fulfill({ status: 503, json: {} }));
  await page.route(`**/api/v1/o/${ORG}/invoices**`, async (r) => {
    const url = new URL(r.request().url());
    const path = url.pathname.replace(`/api/v1/o/${ORG}/invoices`, "");
    const method = r.request().method();
    if (path.endsWith("/credit")) return r.fulfill({ json: { outcome: "no_limit" } });
    if (path.endsWith("/preview")) return r.fulfill({ json: state.preview });
    if (method === "POST" || method === "PATCH") {
      const body = (r.request().postDataJSON() ?? {}) as Record<string, unknown>;
      state.posts.push({ path: `${method} ${path}`, body });
      if (path === "") return r.fulfill({ status: 201, json: state.current });
      if (path.endsWith("/approve")) {
        state.current = savedInvoice({
          status: "approved",
          status_label: "Approved",
          number: "INV-0001",
          journal: `/o/${ORG}/accounting/journals/j1`,
        });
        state.preview = preview({ journal: { posted: true, complete: true, lines: JOURNAL } });
      }
      if (path.endsWith("/void")) {
        state.current = { ...state.current, status: "void", status_label: "Void" };
      }
      if (path.endsWith("/copy")) {
        return r.fulfill({
          status: 201,
          json: savedInvoice({ id: "2b2b2b2b-0000-4000-8000-000000000002" }),
        });
      }
      return r.fulfill({ json: state.current });
    }
    return r.fulfill({ json: state.current });
  });
  return state;
}

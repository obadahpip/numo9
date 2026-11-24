import { type Page } from "@playwright/test";

import { mockCsrf } from "./auth-helpers";

/** Bill editor API answers for the E-02 Playwright suites (shapes of numo9/purchases/api.py). */
const ORG = "acme";
export const SUPPLIER = "5a5a5a5a-0000-4000-8000-000000000001";
export const EXPENSE = "61006100-0000-4000-8000-000000000002";
export const DOC = "d0c0d0c0-0000-4000-8000-000000000001";
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
const doc = {
  id: DOC,
  name: "cedar-invoice-1001.pdf",
  mime: "application/pdf",
  size: 4821,
  sha256: "x",
  status: "clean",
  status_label: "Clean",
  source: "upload",
  sender: "",
  sender_known: false,
  period: "",
  tax_year: null,
  tags: [],
  folder: "inbox",
  preview_status: "ready",
  password_protected: false,
  uploaded_by: "Owner",
  created_at: "2026-06-15T12:00:00Z",
};
const PDF =
  "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF";

export function savedBill(over: Record<string, unknown> = {}) {
  return {
    id: BILL,
    number: "",
    status: "draft",
    status_label: "Draft",
    supplier: { id: SUPPLIER, name: "Cedar Supply Co." },
    supplier_invoice_no: "CS-1001",
    reference: "",
    date: "2026-06-15",
    due_date: "2026-07-15",
    total: "450.00",
    amount_due: "450.00",
    url: `/o/${ORG}/purchases/bills/${BILL}`,
    terms: null,
    currency: "CAD",
    tax_mode: "no_tax",
    discount_type: "none",
    discount_value: "0",
    department: "",
    notes: "",
    holdback_type: "none",
    holdback_value: "0",
    holdback_amount: "0.00",
    holdback_released: "0.00",
    holdback_outstanding: "0.00",
    subtotal: "450.00",
    discount_total: "0.00",
    tax_total: "0.00",
    amount_paid: "0.00",
    version: 1,
    purchase_order: null,
    journal: null,
    lines: [
      {
        id: "l1",
        position: 0,
        description: "Tiles",
        quantity: "10.0000",
        unit_price: "45.0000",
        discount_type: "none",
        discount_value: "0",
        account: { id: EXPENSE, code: "6100", name: "Office supplies" },
        tax_code: null,
        tracking: {},
        po_line: null,
        net: "450.00",
        tax_amount: "0.00",
        amount: "450.00",
      },
    ],
    ...over,
  };
}

export async function mockBillEditor(page: Page) {
  await mockCsrf(page);
  const posted: Record<string, unknown>[] = [];
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
  await page.route(`**/api/v1/o/${ORG}/files/${DOC}`, (r) => r.fulfill({ json: doc }));
  await page.route(`**/api/v1/o/${ORG}/files/${DOC}/url*`, (r) =>
    r.fulfill({ json: { url: `/__test/${DOC}.pdf`, expires_at: "" } }),
  );
  await page.route(`**/__test/${DOC}.pdf`, (r) =>
    r.fulfill({ body: PDF, contentType: "application/pdf" }),
  );
  await page.route(`**/api/v1/o/${ORG}/files/attachments*`, (r) =>
    r.fulfill({
      json: {
        results: [
          {
            id: "a1",
            record_type: "purchases.Bill",
            record_id: BILL,
            document: doc,
            attached_at: "",
            attached_by: "",
          },
        ],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/bills`, async (r) => {
    posted.push(r.request().postDataJSON() as Record<string, unknown>);
    await r.fulfill({ status: 201, json: savedBill() });
  });
  await page.route(`**/api/v1/o/${ORG}/bills/${BILL}`, (r) => r.fulfill({ json: savedBill() }));
  await page.route(`**/api/v1/o/${ORG}/bills/${BILL}/preview`, (r) =>
    r.fulfill({
      json: {
        journal: { lines: [], complete: true },
        itc: [],
        routing: { rule: null, role: null, role_name: null, explanation: "" },
        duplicates: [],
        match: [],
      },
    }),
  );
  await page.route(`**/api/v1/o/${ORG}/bills/check-number*`, (r) =>
    r.fulfill({ json: { number: "", available: true, conflict: null } }),
  );
  return posted;
}

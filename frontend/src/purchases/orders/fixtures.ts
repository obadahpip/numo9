/** Fixtures of the purchase order suites (E-01-T11…T14). */
import { ACCOUNT, EXPENSE, ORG, SUPPLIER, TAX } from "../fixtures";

import type { CommitmentReport, OrderMatch, PurchaseOrder, PurchaseOrderList } from "./api";

export { serveJson } from "@/banking/fixtures";
export { EXPENSE, ORG, SUPPLIER } from "../fixtures";

export const PO_ID = "90909090-0000-4000-8000-000000000001";
export const LINE_1 = "11111111-0000-4000-8000-000000000001";
export const LINE_2 = "11111111-0000-4000-8000-000000000002";

export const order = (over: Partial<PurchaseOrder> = {}): PurchaseOrder => ({
  id: PO_ID,
  number: "",
  status: "draft",
  status_label: "Draft",
  supplier: { id: SUPPLIER, name: "Cedar Supply Co." },
  reference: "",
  date: "2026-06-15",
  delivery_date: "2026-06-30",
  total: "250.00",
  url: `/o/${ORG}/purchases/orders/${PO_ID}`,
  terms: null,
  currency: "CAD",
  tax_mode: "no_tax",
  discount_type: "none",
  discount_value: "0.0000",
  notes: "",
  delivery_attention: "Site office",
  delivery_address: "12 King St W, Toronto ON",
  delivery_instructions: "Loading dock at the back",
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
  lines: [
    {
      id: LINE_1,
      position: 0,
      description: "Tiles",
      quantity: "10.0000",
      unit_price: "25.0000",
      discount_type: "none",
      discount_value: "0.0000",
      account: { id: EXPENSE, code: "6100", name: "Office supplies" },
      tax_code: null,
      tracking: {},
      quantity_received: "0.0000",
      quantity_billed: "0.0000",
      outstanding: "10.0000",
      net: "250.00",
      tax_amount: "0.00",
      amount: "250.00",
    },
  ],
  receipts: [],
  ...over,
});

/** An approved PO with two lines: 6 of 10 tiles received, nothing of the grout. */
export const partlyReceived = (): PurchaseOrder => {
  const base = order();
  return order({
    number: "PO-0001",
    status: "partially_received",
    status_label: "Partially received",
    total: "330.00",
    lines: [
      {
        ...base.lines[0]!,
        quantity_received: "6.0000",
        outstanding: "4.0000",
      },
      {
        ...base.lines[0]!,
        id: LINE_2,
        position: 1,
        description: "Grout",
        quantity: "4.0000",
        unit_price: "20.0000",
        net: "80.00",
        amount: "80.00",
      },
    ],
  });
};

export const LIST: PurchaseOrderList = {
  count: 3,
  page: 1,
  pages: 1,
  counts: {
    draft: 1,
    awaiting_approval: 0,
    approved: 0,
    partially_received: 1,
    received: 1,
    billed: 0,
    closed: 0,
    cancelled: 0,
  },
  results: [],
};

export const MATCH: OrderMatch = {
  purchase_order: { id: PO_ID, number: "PO-0001", status: "partially_received" },
  tolerance: { quantity: "0.00", price: "0.00" },
  status: "green",
  lines: [],
};

export const COMMITMENTS: CommitmentReport = {
  by: "supplier",
  rows: [
    {
      key: SUPPLIER,
      label: "Cedar Supply Co.",
      amount: "570.00",
      lines: 2,
      orders: 1,
      budget: null,
    },
    { key: "m", label: "Maple Hardware Ltd", amount: "200.00", lines: 1, orders: 1, budget: null },
  ],
  total: "770.00",
  from: null,
  to: null,
};

/** Reference data of the editor and the PO endpoints; `extra` answers first. */
export function orderHandler(
  calls: { url: string; method: string; body: unknown }[],
  extra?: (url: string, method: string) => { status?: number; body: unknown } | undefined,
) {
  return (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : null });
    const special = extra?.(url, method);
    if (special) return special;
    if (url.includes("/accounts?")) return { body: { count: 1, results: [ACCOUNT] } };
    if (url.includes("/contacts?"))
      return {
        body: {
          count: 1,
          next_offset: null,
          role_counts: {},
          results: [{ id: SUPPLIER, display_name: "Cedar Supply Co.", roles: ["supplier"] }],
        },
      };
    if (url.includes("/tax/codes")) return { body: { results: [TAX] } };
    if (url.includes("/calculate")) return { status: 503, body: {} };
    if (url.endsWith("/purchase-orders/approval-limit")) return { body: { limit: "5000.00" } };
    if (url.endsWith("/purchase-orders") && method === "POST")
      return { status: 201, body: order() };
    if (url.endsWith(`/purchase-orders/${PO_ID}`) && method === "PATCH")
      return { body: order({ version: 2 }) };
    if (url.endsWith(`/purchase-orders/${PO_ID}`)) return { body: order() };
    if (url.endsWith("/approve"))
      return { body: order({ status: "approved", status_label: "Approved", number: "PO-0001" }) };
    if (url.endsWith("/submit"))
      return { body: order({ status: "awaiting_approval", status_label: "Awaiting approval" }) };
    return { status: 404, body: {} };
  };
}

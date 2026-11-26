/** Fixtures of the quote suites (D-02-T12…T14). */
import { ACCOUNT, CUSTOMER, HST_S, ORG, REVENUE, TAX } from "../invoices/fixtures";
import type { PublicQuote, Quote, QuoteLine } from "./api";

export { serveJson } from "@/banking/fixtures";
export { CUSTOMER, ORG, REVENUE };

export const QUOTE_ID = "2a2a2a2a-0000-4000-8000-000000000001";
export const TOKEN = "eyJxIjoiMSJ9:1tok:sig";

export const quoteLine = (over: Partial<QuoteLine> = {}): QuoteLine => ({
  id: "q1",
  position: 0,
  item: null,
  description: "Cabinets",
  quantity: "1.0000",
  unit_price: "1000.0000",
  discount_type: "none",
  discount_value: "0.0000",
  account: { id: REVENUE, code: "4000", name: "Sales" },
  tax_code: { id: HST_S, code: "sales.ON.standard" },
  tax_overridden: false,
  tracking: {},
  net: "1000.00",
  tax_amount: "130.00",
  amount: "1000.00",
  is_optional: false,
  alternative_group: "",
  selected: true,
  counted: true,
  ...over,
});

export const quote = (over: Partial<Quote> = {}): Quote => ({
  id: QUOTE_ID,
  number: "QU-0001",
  status: "draft",
  status_label: "Draft",
  title: "Kitchen renovation",
  customer: { id: CUSTOMER, name: "Maple Leaf Supply Ltd." },
  reference: "",
  date: "2026-06-15",
  expiry_date: "2026-07-15",
  total: "1130.00",
  url: `/o/${ORG}/sales/quotes/${QUOTE_ID}`,
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
  subtotal: "1000.00",
  discount_total: "0.00",
  tax_total: "130.00",
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
  pdf: `/api/v1/o/${ORG}/quotes/${QUOTE_ID}/pdf`,
  lines: [
    quoteLine(),
    quoteLine({
      id: "q2",
      position: 1,
      description: "Install",
      unit_price: "200.0000",
      net: "200.00",
      tax_amount: "26.00",
      amount: "200.00",
      is_optional: true,
      selected: false,
      counted: false,
    }),
  ],
  ...over,
});

export const publicQuote = (over: Partial<PublicQuote> = {}): PublicQuote => ({
  number: "QU-0001",
  title: "Kitchen renovation",
  summary: "Supply and install.",
  organisation: "Refined Interiors Inc.",
  customer: "Maple Leaf Supply Ltd.",
  date: "2026-06-15",
  expiry_date: "2026-07-15",
  currency: "CAD",
  status: "viewed",
  lines: [
    {
      id: "p1",
      description: "Cabinets",
      quantity: "1",
      unit_price: "1000.00",
      amount: "1000.00",
      tax: "130.00",
      is_optional: false,
      alternative_group: "",
      selected: true,
      counted: true,
    },
    {
      id: "p2",
      description: "Install",
      quantity: "1",
      unit_price: "200.00",
      amount: "200.00",
      tax: "26.00",
      is_optional: true,
      alternative_group: "",
      selected: false,
      counted: false,
    },
    {
      id: "p3",
      description: "Oak doors",
      quantity: "1",
      unit_price: "500.00",
      amount: "500.00",
      tax: "65.00",
      is_optional: false,
      alternative_group: "Wood",
      selected: true,
      counted: true,
    },
    {
      id: "p4",
      description: "Walnut doors",
      quantity: "1",
      unit_price: "800.00",
      amount: "800.00",
      tax: "104.00",
      is_optional: false,
      alternative_group: "Wood",
      selected: false,
      counted: false,
    },
  ],
  subtotal: "1500.00",
  discount_total: "0.00",
  tax_total: "195.00",
  total: "1695.00",
  deposit_type: "percent",
  deposit_value: "20",
  deposit: "339.00",
  accepted_by: null,
  can_accept: true,
  reason: null,
  ...over,
});

/** The editor's reference data and the quote endpoints; `extra` answers first. */
export function quoteHandler(
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
          results: [{ id: CUSTOMER, display_name: "Maple Leaf Supply Ltd.", roles: ["customer"] }],
        },
      };
    if (url.includes("/tax/codes")) return { body: { results: [TAX] } };
    if (url.includes("/calculate")) return { status: 503, body: {} };
    if (url.includes("/tax/defaults") || url.includes("/tax/resolve"))
      return { status: 503, body: {} };
    if (url.endsWith("/quotes") && method === "POST") return { status: 201, body: quote() };
    if (url.endsWith(`/quotes/${QUOTE_ID}`) && method === "PATCH")
      return { body: quote({ version: 2 }) };
    if (url.endsWith(`/quotes/${QUOTE_ID}`)) return { body: quote() };
    return { status: 404, body: {} };
  };
}

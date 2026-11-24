/** Invoice email API client (D-03a-T12/T15): the composer's defaults, send, PDF preview. */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface InvoiceSend {
  id: string;
  recipients: string[];
  subject: string;
  language: string;
  file_name: string;
  sent_at: string;
  sent_by: string;
  viewed_at: string | null;
}

export interface InvoiceEmailDefaults {
  to: string[];
  subject: string;
  message: string;
  language: string;
  file_name: string;
  sendable: boolean;
  sent_at: string | null;
  viewed_at: string | null;
  sends: InvoiceSend[];
}

export interface SendInvoiceInput {
  to: string[];
  subject: string;
  message: string;
}

const base = (org: string, id: string) =>
  `/api/v1/o/${encodeURIComponent(org)}/invoices/${encodeURIComponent(id)}`;

export const invoiceEmailApi = {
  defaults: (org: string, id: string): Promise<ApiResult<InvoiceEmailDefaults>> =>
    apiRequest(`${base(org, id)}/email`),
  send: (
    org: string,
    id: string,
    input: SendInvoiceInput,
  ): Promise<ApiResult<InvoiceSend | { code?: string; detail?: string }>> =>
    apiRequest(`${base(org, id)}/email`, { method: "POST", body: input }),
  pdfUrl: (org: string, id: string): string => `${base(org, id)}/pdf`,
  /** The PDF as a blob URL for the preview frame (the API's responses can't be framed); `null`
   * when it can't be fetched. Revoke it with `URL.revokeObjectURL` when done. */
  pdfBlobUrl: async (org: string, id: string): Promise<string | null> => {
    try {
      const response = await fetch(`${base(org, id)}/pdf`, { credentials: "same-origin" });
      if (!response.ok) return null;
      return URL.createObjectURL(await response.blob());
    } catch {
      return null;
    }
  },
};

const EMAIL = /^[^\s@,;]+@[^\s@,;]+\.[^\s@,;]+$/;

/** The addresses typed in the To field (comma, semicolon or space separated), and the bad ones. */
export function parseRecipients(text: string): { valid: string[]; invalid: string[] } {
  const parts = text
    .split(/[\s,;]+/)
    .map((part) => part.trim())
    .filter(Boolean);
  const unique = [...new Set(parts)];
  return {
    valid: unique.filter((part) => EMAIL.test(part)),
    invalid: unique.filter((part) => !EMAIL.test(part)),
  };
}

export type CreditOutcome = "no_limit" | "within" | "warn" | "block" | "override";

export interface InvoiceCredit {
  outcome: CreditOutcome;
  mode: "warn" | "block";
  limit: string | null;
  exposure: string;
  amount: string;
  projected: string;
  over_by: string;
  message: string;
  contact: { id: string; name: string };
  pending_override: { id: string; amount: string; requested_at: string } | null;
}

export const invoiceCreditApi = {
  check: (org: string, id: string): Promise<ApiResult<InvoiceCredit>> =>
    apiRequest(`${base(org, id)}/credit`),
  requestOverride: (
    org: string,
    id: string,
    reason: string,
  ): Promise<ApiResult<InvoiceCredit | { code?: string; detail?: string; reason?: string[] }>> =>
    apiRequest(`${base(org, id)}/credit/override`, { method: "POST", body: { reason } }),
};

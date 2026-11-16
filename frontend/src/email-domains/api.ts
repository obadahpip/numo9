/** Client for the sending-domain API (A-07-T05, T06): `/api/v1/o/<org>/email-domains`. */
import { apiRequest, type ApiResult, type Numo9Error } from "@/auth/client";

export type DomainStatus = "pending" | "partial" | "verified" | "failed";
export type RecordStatus = "unchecked" | "ok" | "missing" | "wrong";

export interface DnsRecord {
  kind: "spf" | "dkim" | "dmarc" | "return_path";
  kind_label: string;
  record_type: string;
  host: string;
  value: string;
  status: RecordStatus;
  status_label: string;
  found: string;
  checked_at: string | null;
}

export interface SendingDomain {
  id: string;
  domain: string;
  from_local_part: string;
  from_address: string;
  provider: string;
  status: DomainStatus;
  status_label: string;
  verified_at: string | null;
  last_checked_at: string | null;
  records: DnsRecord[];
  created_at: string;
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/email-domains`;

export const listDomains = (org: string): Promise<ApiResult<{ results: SendingDomain[] }>> =>
  apiRequest<{ results: SendingDomain[] }>(base(org));

export const addDomain = (
  org: string,
  domain: string,
  from_local_part: string,
): Promise<ApiResult<SendingDomain | Numo9Error>> =>
  apiRequest<SendingDomain | Numo9Error>(base(org), {
    method: "POST",
    body: { domain, from_local_part },
  });

export const checkDomain = (org: string, id: string): Promise<ApiResult<SendingDomain>> =>
  apiRequest<SendingDomain>(`${base(org)}/${encodeURIComponent(id)}/check`, { method: "POST" });

export const removeDomain = (org: string, id: string): Promise<ApiResult<unknown>> =>
  apiRequest<unknown>(`${base(org)}/${encodeURIComponent(id)}`, { method: "DELETE" });

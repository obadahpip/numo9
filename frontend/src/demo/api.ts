/** Demo organisation API client (U-07-T10…T12). */
import { apiRequest } from "@/auth/client";

export interface DemoOutboxItem {
  id: number;
  to_email: string;
  subject: string;
  text_body: string;
  kind: string;
  created_at: string;
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/demo`;

export const demoApi = {
  reset: (org: string) =>
    apiRequest<{ seed_version: number }>(`${base(org)}/reset`, { method: "POST" }),
  convert: (org: string, name: string) =>
    apiRequest<{ id: string; name: string }>(`${base(org)}/convert`, {
      method: "POST",
      body: { name },
    }),
  outbox: (org: string) => apiRequest<{ results: DemoOutboxItem[] }>(`${base(org)}/outbox`),
};

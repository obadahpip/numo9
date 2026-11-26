/**
 * The organisation's GST/HST registrations, read only, for the returns list (G-03-T11). They are
 * edited on the tax settings page alone (G-06-T10).
 */
import { apiRequest, type ApiResult } from "@/auth/client";
import type { Registration } from "@/settings/general/registrations";

export async function returnRegistrations(org: string): Promise<ApiResult<Registration[]>> {
  const answer = await apiRequest<{ results: Registration[] }>(
    `/api/v1/o/${encodeURIComponent(org)}/tax/registrations`,
  );
  return { ...answer, body: answer.body?.results };
}

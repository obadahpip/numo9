/** Console organisations (U-06-T03/T04): list with filters and one organisation's detail. */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface PlatformOrganisationRow {
  id: string;
  name: string;
  status: string;
  is_demo: boolean;
  package: string;
  subscription_status: string;
  province: string;
  created_at: string;
}

export interface PlatformOrganisationPage {
  count: number;
  page: number;
  page_size: number;
  pages: number;
  results: PlatformOrganisationRow[];
}

export interface TimelineItem {
  at: string;
  kind: "trial_started" | "subscribed" | "status" | "converted";
  detail: string;
}

export interface PlatformOrganisationDetail {
  id: string;
  name: string;
  status: string;
  is_demo: boolean;
  province: string;
  time_zone: string;
  created_at: string;
  subscription: {
    status: string;
    reason: string;
    package: string;
    interval: string;
    current_period_end: string | null;
    founding: boolean;
  } | null;
  timeline: TimelineItem[];
  users: { id: string; name: string; email: string; role: string; last_login: string | null }[];
  practices: { id: string; name: string; role: string; active: boolean; staff_count: number }[];
  recent_events: { at: string; action: string; actor: string; record: string }[];
}

export interface OrganisationFilters {
  q?: string;
  status?: string;
  package?: string;
  province?: string;
  created_from?: string;
  created_to?: string;
  page?: number;
}

export function listOrganisations(
  filters: OrganisationFilters,
): Promise<ApiResult<PlatformOrganisationPage>> {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  return apiRequest<PlatformOrganisationPage>(`/api/v1/platform/organisations?${params}`);
}

export const getOrganisation = (id: string): Promise<ApiResult<PlatformOrganisationDetail>> =>
  apiRequest<PlatformOrganisationDetail>(
    `/api/v1/platform/organisations/${encodeURIComponent(id)}`,
  );

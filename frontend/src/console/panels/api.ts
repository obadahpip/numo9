/** Console home panels (U-06-T13): founding counter (U-08) and demo manager (U-07). */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface DemoRow {
  id: string;
  name: string;
  seed_version: number | null;
  created_at: string;
  last_active_at: string | null;
  purge_on: string;
  members: number;
}

export interface DemoOverview {
  seed_version: number;
  idle_days: number;
  open: number;
  purge_soon: number;
  templates: { seed_version: number; built_at: string }[];
  demos: DemoRow[];
}

export const getDemos = (): Promise<ApiResult<DemoOverview>> =>
  apiRequest<DemoOverview>("/api/v1/platform/demos");

export const purgeDemo = (id: string): Promise<ApiResult<unknown>> =>
  apiRequest<unknown>(`/api/v1/platform/demos/${encodeURIComponent(id)}/purge`, {
    method: "POST",
  });

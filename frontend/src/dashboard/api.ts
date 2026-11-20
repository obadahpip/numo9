/** Practice home (V-04): `GET /api/v1/practice/dashboard`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type WidgetKind = "count" | "list" | "workload";
export type DashboardScope = "mine" | "all";

export interface DashboardWidget {
  key: string;
  title: string;
  description: string;
  kind: WidgetKind;
  status: "ok" | "error";
  count: number | null;
  filters: Record<string, string[]> | null;
  href: string;
  items: Record<string, unknown>[];
  /** Hidden by the user (V-04-T09): shown only while customising. */
  hidden?: boolean;
}

export interface DashboardLayout {
  order: string[];
  hidden: string[];
}

export interface Dashboard {
  practice: { id: string; name: string };
  scope: DashboardScope;
  scopes: DashboardScope[];
  layout?: DashboardLayout;
  widgets: DashboardWidget[];
}

export interface DeadlineItem {
  date: string;
  kind: string;
  label: string;
  organisation_id: string;
  organisation_name: string;
}

export interface WorkloadItem {
  id: string;
  name: string;
  role: string;
  organisations: number;
  open_tasks: number;
}

export const DASHBOARD_URL = "/api/v1/practice/dashboard";

export const dashboardApi = {
  get: (practice: string, scope?: DashboardScope): Promise<ApiResult<Dashboard>> => {
    const params = new URLSearchParams({ practice });
    if (scope) params.set("scope", scope);
    return apiRequest<Dashboard>(`${DASHBOARD_URL}?${params.toString()}`);
  },
  saveLayout: (practice: string, layout: DashboardLayout): Promise<ApiResult<DashboardLayout>> =>
    apiRequest<DashboardLayout>(
      `${DASHBOARD_URL}/layout?practice=${encodeURIComponent(practice)}`,
      { method: "PUT", body: layout },
    ),
};

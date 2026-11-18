/** Console metrics (U-06-T05/T06): KPI figures, their daily history and each tile's drill-down. */
import { apiRequest, type ApiResult } from "@/auth/client";

import type { PlatformOrganisationPage } from "../organisations/api";

export interface MetricPoint {
  date: string;
  mrr_cents: number;
  active: number;
  trials: number;
  conversion_rate: string | null;
  churn_rate: string | null;
}

export interface PlatformMetrics {
  current: MetricPoint & {
    converted: number;
    trials_ended: number;
    cancelled: number;
    active_at_start: number;
  };
  history: MetricPoint[];
}

/** Tiles with a list of the organisations they count. */
export type DrillMetric = "mrr" | "active" | "trials";

export const getMetrics = (days = 90): Promise<ApiResult<PlatformMetrics>> =>
  apiRequest<PlatformMetrics>(`/api/v1/platform/metrics?days=${days}`);

export const drillDown = (
  metric: DrillMetric,
  page = 1,
): Promise<ApiResult<PlatformOrganisationPage>> =>
  apiRequest<PlatformOrganisationPage>(
    `/api/v1/platform/metrics/${metric}/organisations?page=${page}`,
  );

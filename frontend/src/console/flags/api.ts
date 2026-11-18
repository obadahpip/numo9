/** Console feature flags (U-06-T12) and the app's `/me/flags`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type FlagMode = "on" | "off" | "rules";

export interface FlagTarget {
  id: string;
  name: string;
}

export interface FeatureFlag {
  name: string;
  note: string;
  mode: FlagMode;
  percent: string | null;
  organisations: FlagTarget[];
  practices: FlagTarget[];
  users: { id: string; name: string; email: string }[];
  updated_at: string;
}

export interface FlagUpdate {
  mode?: FlagMode;
  percent?: string | null;
  note?: string;
  organisations?: string[];
  practices?: string[];
}

export interface ApiErrorBody {
  code?: string;
  detail?: string;
}

const API = "/api/v1/platform/flags";

export const listFlags = (): Promise<ApiResult<{ flags: FeatureFlag[] }>> =>
  apiRequest<{ flags: FeatureFlag[] }>(API);

export const createFlag = (
  name: string,
  note: string,
): Promise<ApiResult<FeatureFlag | ApiErrorBody>> =>
  apiRequest(API, { method: "POST", body: { name, note } });

export const updateFlag = (
  name: string,
  update: FlagUpdate,
): Promise<ApiResult<FeatureFlag | ApiErrorBody>> =>
  apiRequest(`${API}/${encodeURIComponent(name)}`, { method: "PATCH", body: update });

export const deleteFlag = (name: string): Promise<ApiResult<unknown>> =>
  apiRequest(`${API}/${encodeURIComponent(name)}`, { method: "DELETE" });

/** Organisations or practices matching a name, for the pickers. */
export const searchTargets = (
  kind: "organisations" | "practices",
  q: string,
): Promise<ApiResult<{ results: FlagTarget[] }>> =>
  apiRequest<{ results: FlagTarget[] }>(
    `/api/v1/platform/${kind}?page_size=10&q=${encodeURIComponent(q)}`,
  );

/** The flags on for the signed-in user (and the organisation, when given). */
export const myFlags = (org?: string): Promise<ApiResult<{ flags: Record<string, boolean> }>> =>
  apiRequest<{ flags: Record<string, boolean> }>("/api/v1/me/flags", {
    headers: org ? { "X-Numo9-Org": org } : {},
  });

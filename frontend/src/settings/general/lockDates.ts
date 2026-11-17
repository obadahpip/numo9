/** Lock dates API client (A-05-T07, T09): `/api/v1/o/<org>/settings/lock-dates…`. */
import { apiRequest, type ApiResult } from "@/auth/client";

import { settingsUrl, type FieldErrors } from "./api";

export type Level = "advisers_only" | "everyone";

export interface LockCell {
  date: string | null;
  reason: string;
  updated_at: string | null;
}

export interface LockRow {
  module: string;
  module_label: string;
  advisers_only: LockCell;
  everyone: LockCell;
}

export interface Impact {
  module: string;
  date: string;
  items: { module: string; kind: string; label: string; count: number }[];
  total: number;
}

export const getLockDates = (org: string): Promise<ApiResult<LockRow[]>> =>
  apiRequest<LockRow[]>(settingsUrl(org, "/lock-dates"));

export const setLockDate = (
  org: string,
  body: { module: string; level: Level; date: string | null; reason: string },
): Promise<ApiResult<LockRow[] | FieldErrors>> =>
  apiRequest<LockRow[] | FieldErrors>(settingsUrl(org, "/lock-dates"), { method: "PATCH", body });

export const getImpact = (org: string, module: string, date: string): Promise<ApiResult<Impact>> =>
  apiRequest<Impact>(
    settingsUrl(
      org,
      `/lock-dates/impact?module=${encodeURIComponent(module)}&date=${encodeURIComponent(date)}`,
    ),
  );

/** Console founding offer (U-08-T11): `/api/v1/platform/founding`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export type SlotState = "active" | "cancelled" | "released";

export interface FoundingSlotRow {
  slot_no: number;
  organisation_id: string;
  organisation_name: string;
  allocated_at: string;
  payment_ref: string;
  lapsed_at: string | null;
  released_at: string | null;
  release_reason: string;
  state: SlotState;
}

export interface FoundingOverview {
  cap: number;
  allocated: number;
  remaining: number;
  active: number;
  churn_rule: "keep_on_return" | "lose_on_cancel" | "keep_if_returns_within_days";
  return_window_days: number;
  refund_release_hours: number;
  slots: FoundingSlotRow[];
}

const API = "/api/v1/platform/founding";

export const FOUNDING_EXPORT_URL = `${API}/export`;

export const getFounding = (): Promise<ApiResult<FoundingOverview>> =>
  apiRequest<FoundingOverview>(API);

export const releaseSlot = (
  slot: number,
  reason: string,
): Promise<ApiResult<FoundingSlotRow | Record<string, string[]>>> =>
  apiRequest<FoundingSlotRow | Record<string, string[]>>(`${API}/slots/${slot}/release`, {
    method: "POST",
    body: { reason },
  });

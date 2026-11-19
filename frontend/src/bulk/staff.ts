/** The practice's staff (V-05-T02 `GET /api/v1/practice/staff`), for the staff bulk action. */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface StaffMember {
  id: string;
  name: string;
  email: string;
  role: string;
  role_label: string;
  status: "active" | "suspended" | "pending";
  joined_at?: string | null;
  suspended_at?: string | null;
  invitation_expires_at?: string | null;
  organisation_count: number;
  last_login: string | null;
  dormant: boolean;
}

export const STAFF_URL = "/api/v1/practice/staff";

export const staffApi = {
  list: (practice: string): Promise<ApiResult<{ practice: string; staff: StaffMember[] }>> =>
    apiRequest(`${STAFF_URL}?practice=${encodeURIComponent(practice)}`),
};

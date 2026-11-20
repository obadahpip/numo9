/** Staff invitations (V-05-T03): the A-02 invitation API with a practice role. */
import { apiRequest, type ApiResult } from "@/auth/client";

export const PRACTICE_ROLES = [
  "accountant",
  "reviewer",
  "payroll_specialist",
  "practice_admin",
] as const;
export type PracticeRole = (typeof PRACTICE_ROLES)[number];

export interface StaffInvitation {
  id: string;
  kind: "practice_staff";
  email: string;
  role: PracticeRole;
  status: string;
  expires_at: string;
  target_name: string;
  target_id: string;
  inviter_name: string;
}

export type InviteError = { detail?: string; code?: string } & Record<string, unknown>;

export const invitationsApi = {
  invite: (
    practice: string,
    email: string,
    role: PracticeRole,
  ): Promise<ApiResult<StaffInvitation | InviteError>> =>
    apiRequest<StaffInvitation | InviteError>("/api/v1/invitations", {
      method: "POST",
      body: { kind: "practice_staff", practice, email, role },
    }),
  resend: (id: string): Promise<ApiResult<StaffInvitation | InviteError>> =>
    apiRequest<StaffInvitation | InviteError>(
      `/api/v1/invitations/${encodeURIComponent(id)}/resend`,
      { method: "POST" },
    ),
  revoke: (id: string): Promise<ApiResult<StaffInvitation | InviteError>> =>
    apiRequest<StaffInvitation | InviteError>(
      `/api/v1/invitations/${encodeURIComponent(id)}/revoke`,
      { method: "POST" },
    ),
};

/** The first readable message of a 400/403/409 answer (field errors or `detail`). */
export function inviteErrorText(body: unknown): string {
  if (!body || typeof body !== "object") return "";
  const value = body as Record<string, unknown>;
  if (typeof value.detail === "string") return value.detail;
  for (const field of ["email", "role", "non_field_errors"]) {
    const list = value[field];
    if (Array.isArray(list) && list.length) {
      const first = list[0] as unknown;
      if (typeof first === "string") return first;
      if (first && typeof first === "object" && "message" in first)
        return String((first as { message: unknown }).message);
    }
  }
  return "";
}

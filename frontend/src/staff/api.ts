/** Practice staff API (V-05): list, assignments. */
import { apiRequest, type ApiResult } from "@/auth/client";
import type { StaffMember } from "@/bulk/staff";

export { staffApi, STAFF_URL, type StaffMember } from "@/bulk/staff";

export interface Assignments {
  organisations: { id: string; name: string }[];
  groups: { id: string; name: string; role: string; depth: number }[];
}

const base = (user: string) => `/api/v1/practice/staff/${encodeURIComponent(user)}`;
const q = (practice: string) => `?practice=${encodeURIComponent(practice)}`;

export const assignmentsApi = {
  get: (practice: string, user: string): Promise<ApiResult<Assignments>> =>
    apiRequest<Assignments>(`${base(user)}/assignments${q(practice)}`),
  assignOrganisation: (practice: string, user: string, org: string) =>
    apiRequest<Assignments>(`${base(user)}/organisations/${org}${q(practice)}`, { method: "PUT" }),
  unassignOrganisation: (practice: string, user: string, org: string) =>
    apiRequest<Assignments>(`${base(user)}/organisations/${org}${q(practice)}`, {
      method: "DELETE",
    }),
  assignGroup: (practice: string, user: string, group: string, role: string) =>
    apiRequest<Assignments>(`${base(user)}/groups/${group}${q(practice)}`, {
      method: "PUT",
      body: { role },
    }),
  unassignGroup: (practice: string, user: string, group: string) =>
    apiRequest<Assignments>(`${base(user)}/groups/${group}${q(practice)}`, { method: "DELETE" }),
};

export interface DormantMember {
  id: string;
  name: string;
  email: string;
  role: string;
  last_login: string | null;
  days: number;
}

export const dormantApi = {
  list: (practice: string): Promise<ApiResult<{ dormant_days: number; staff: DormantMember[] }>> =>
    apiRequest(`/api/v1/practice/staff/dormant${q(practice)}`),
  suspend: (practice: string, user: string) =>
    apiRequest<unknown>(`${base(user)}/suspend${q(practice)}`, { method: "POST" }),
};

export interface Activity {
  from: string;
  to: string;
  total: number;
  days: { date: string; count: number }[];
}

export const activityApi = {
  get: (practice: string, user: string): Promise<ApiResult<Activity>> =>
    apiRequest<Activity>(`${base(user)}/activity${q(practice)}`),
};

/** Suspend, lift the suspension or remove a member (V-05-T05; the last admin is refused). */
export const memberApi = {
  suspend: (practice: string, user: string): Promise<ApiResult<StaffMember>> =>
    apiRequest<StaffMember>(`${base(user)}/suspend${q(practice)}`, { method: "POST" }),
  reinstate: (practice: string, user: string): Promise<ApiResult<StaffMember>> =>
    apiRequest<StaffMember>(`${base(user)}/reinstate${q(practice)}`, { method: "POST" }),
  remove: (practice: string, user: string): Promise<ApiResult<unknown>> =>
    apiRequest<unknown>(`${base(user)}${q(practice)}`, { method: "DELETE" }),
};

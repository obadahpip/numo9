/** Practice staff API (V-05): list, assignments. */
import { apiRequest, type ApiResult } from "@/auth/client";

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

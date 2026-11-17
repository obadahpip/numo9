/** Impersonation (U-06-T09/T11): start a session, the browser's current one, end it. */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface ImpersonationPerson {
  id: string;
  name: string;
  email: string;
}

export interface ImpersonationSession {
  id: string;
  actor: ImpersonationPerson;
  user: ImpersonationPerson;
  organisation: { id: string; name: string };
  reason: string;
  started_at: string;
  expires_at: string;
  ended_at: string | null;
  end_reason: "" | "ended" | "expired" | "revoked";
}

export interface ImpersonationState {
  session: ImpersonationSession | null;
  ended: ImpersonationSession | null;
}

const API = "/api/v1/platform/impersonation";

export const DURATIONS = [15, 30, 60, 120] as const;
export const DEFAULT_DURATION = 30;

export const startImpersonation = (input: {
  organisation: string;
  user: string;
  reason: string;
  minutes: number;
}): Promise<ApiResult<ImpersonationSession | { code?: string; detail?: string }>> =>
  apiRequest(API, { method: "POST", body: input });

export const currentImpersonation = (): Promise<ApiResult<ImpersonationState>> =>
  apiRequest<ImpersonationState>(`${API}/current`);

export const endImpersonation = (): Promise<ApiResult<ImpersonationState>> =>
  apiRequest<ImpersonationState>(`${API}/end`, { method: "POST" });

/** Where the console sends the staff member once a session ends. */
export const consoleOrganisationUrl = (organisation: string) =>
  `/console/organisations/${encodeURIComponent(organisation)}`;

/** The organisation's home, where a session starts. */
export const impersonationLandingUrl = (organisation: string) =>
  `/o/${encodeURIComponent(organisation)}/home`;

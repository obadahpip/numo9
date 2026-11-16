/**
 * Security settings API (A-02-T13): django-allauth headless endpoints under `/_allauth/browser/v1`
 * — authenticators (TOTP, recovery codes), re-authentication, sessions (A-02-T07).
 */
import { apiRequest, authRequest, type ApiResult, type AuthBody } from "@/auth/client";

export interface Session {
  id: number;
  device: string;
  ip: string;
  user_agent: string;
  created_at: number;
  last_seen_at?: number;
  is_current: boolean;
}

export interface Authenticator {
  type: "totp" | "recovery_codes" | "webauthn";
  created_at: number;
  last_used_at: number | null;
  total_code_count?: number;
  unused_code_count?: number;
  unused_codes?: string[];
}

export const listSessions = () =>
  apiRequest<{ data: Session[] }>("/_allauth/browser/v1/auth/sessions");

export const endSessions = (ids: number[]) =>
  apiRequest<{ data?: Session[] } & AuthBody>("/_allauth/browser/v1/auth/sessions", {
    method: "DELETE",
    body: { sessions: ids },
  });

export const listAuthenticators = () =>
  apiRequest<{ data: Authenticator[] }>("/_allauth/browser/v1/account/authenticators");

export const totpSetup = () => authRequest("/account/authenticators/totp");
export const totpActivate = (code: string) =>
  authRequest("/account/authenticators/totp", { method: "POST", body: { code } });
export const totpDeactivate = () =>
  authRequest("/account/authenticators/totp", { method: "DELETE" });
export const regenerateRecoveryCodes = () =>
  apiRequest<{ data?: Authenticator } & AuthBody>(
    "/_allauth/browser/v1/account/authenticators/recovery-codes",
    { method: "POST" },
  );
export const reauthenticate = (password: string) =>
  authRequest("/auth/reauthenticate", { method: "POST", body: { password } });

/** allauth asks for the password again (401 with the `reauthenticate` flow). */
export function needsReauthentication(answer: ApiResult<AuthBody>): boolean {
  return (
    answer.status === 401 &&
    (answer.body.data?.flows ?? []).some((flow) => flow.id === "reauthenticate")
  );
}

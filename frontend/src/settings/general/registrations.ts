/** Tax registrations API client (A-05-T09): `/api/v1/o/<org>/settings/registrations`. */
import { apiRequest, type ApiResult } from "@/auth/client";

import { settingsUrl, type FieldErrors } from "./api";

export interface Registration {
  id: string;
  type: string;
  type_label: string;
  number: string;
  display_number: string;
  effective_from: string | null;
  effective_to: string | null;
  status: string;
  status_label: string;
  cra_approval_ref: string;
}

export type RegistrationInput = Pick<
  Registration,
  "type" | "number" | "effective_from" | "effective_to" | "status" | "cra_approval_ref"
>;

export const listRegistrations = (org: string): Promise<ApiResult<Registration[]>> =>
  apiRequest<Registration[]>(settingsUrl(org, "/registrations"));

export const addRegistration = (
  org: string,
  body: RegistrationInput,
): Promise<ApiResult<Registration | FieldErrors>> =>
  apiRequest<Registration | FieldErrors>(settingsUrl(org, "/registrations"), {
    method: "POST",
    body,
  });

export const updateRegistration = (
  org: string,
  id: string,
  body: Partial<RegistrationInput>,
): Promise<ApiResult<Registration | FieldErrors>> =>
  apiRequest<Registration | FieldErrors>(
    settingsUrl(org, `/registrations/${encodeURIComponent(id)}`),
    {
      method: "PATCH",
      body,
    },
  );

export const removeRegistration = (org: string, id: string): Promise<ApiResult<unknown>> =>
  apiRequest<unknown>(settingsUrl(org, `/registrations/${encodeURIComponent(id)}`), {
    method: "DELETE",
  });

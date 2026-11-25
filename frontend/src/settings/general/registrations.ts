/**
 * Tax registrations API client: `/api/v1/o/<org>/tax/registrations` (G-06-T07) — the tax
 * settings page's registrations, each with its filing summary; adding a GST/HST or QST
 * registration creates its first filing cycle and periods (G-06-T04).
 */
import { apiRequest, type ApiResult } from "@/auth/client";

import type { FieldErrors } from "./api";

const taxUrl = (org: string, suffix = "") =>
  `/api/v1/o/${encodeURIComponent(org)}/tax/registrations${suffix}`;

export interface FilingSummary {
  frequency: "monthly" | "quarterly" | "annual" | "";
  periods: number;
  next_due: { start: string; end: string; due_date: string; attention: string } | null;
  overdue: number;
}

/** 422: a change the filed periods forbid. */
export interface RegistrationRefusal {
  code?: string;
  detail?: string;
}

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
  /** GST/HST (RT) and QST registrations file returns: they have filing periods. */
  files_returns?: boolean;
  filing?: FilingSummary | null;
}

export type RegistrationInput = Pick<
  Registration,
  "type" | "number" | "effective_from" | "effective_to" | "status" | "cra_approval_ref"
> & {
  /** Filing frequency of a new GST/HST or QST registration (annual when not given). */
  frequency?: string;
};

export const listRegistrations = async (org: string): Promise<ApiResult<Registration[]>> => {
  const answer = await apiRequest<{ results: Registration[] }>(taxUrl(org));
  return { ...answer, body: answer.body?.results };
};

export const addRegistration = (
  org: string,
  body: RegistrationInput,
): Promise<ApiResult<Registration | FieldErrors>> =>
  apiRequest<Registration | FieldErrors>(taxUrl(org), {
    method: "POST",
    body,
  });

export const updateRegistration = (
  org: string,
  id: string,
  body: Partial<RegistrationInput>,
): Promise<ApiResult<Registration | FieldErrors>> =>
  apiRequest<Registration | FieldErrors>(taxUrl(org, `/${encodeURIComponent(id)}`), {
    method: "PATCH",
    body,
  });

export const removeRegistration = (org: string, id: string): Promise<ApiResult<unknown>> =>
  apiRequest<unknown>(taxUrl(org, `/${encodeURIComponent(id)}`), {
    method: "DELETE",
  });

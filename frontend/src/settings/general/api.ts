/** Organisation settings API client (A-05-T09): `/api/v1/o/<org>/settings…`. */
import { apiRequest, type ApiResult } from "@/auth/client";

export interface OrganisationSettings {
  legal_name: string;
  display_name: string;
  industry: string;
  structure: string;
  mailing_line1: string;
  mailing_line2: string;
  mailing_city: string;
  mailing_province: string;
  mailing_postal_code: string;
  phone: string;
  email: string;
  website: string;
  fye_month: number;
  fye_day: number;
  base_currency: string;
  time_zone: string;
  /** Founding organisation number (U-08-T09), read-only; null when not founding. */
  founding_slot?: number | null;
  [field: string]: unknown;
}

/** 400 body: field → messages (model rules), or `{detail, code}`. */
export type FieldErrors = Record<string, string[]>;

export const settingsUrl = (org: string, suffix = "") =>
  `/api/v1/o/${encodeURIComponent(org)}/settings${suffix}`;

export const getSettings = (org: string): Promise<ApiResult<OrganisationSettings>> =>
  apiRequest<OrganisationSettings>(settingsUrl(org));

export const saveSettings = (
  org: string,
  change: Partial<OrganisationSettings>,
): Promise<ApiResult<OrganisationSettings | FieldErrors>> =>
  apiRequest<OrganisationSettings | FieldErrors>(settingsUrl(org), {
    method: "PATCH",
    body: change,
  });

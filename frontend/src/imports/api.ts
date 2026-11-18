/** Imports API client (B-03-T11): `/api/v1/o/<org>/imports…`. */
import { apiRequest } from "@/auth/client";

export type ImportEntity = "contacts.contact" | "contacts.person";
export type RowAction = "create" | "update" | "unchanged" | "error";

export interface ImportField {
  key: string;
  label: string;
  required: boolean;
  match_key: boolean;
}

export interface ImportRun {
  id: string;
  entity: ImportEntity;
  filename: string;
  status: "uploaded" | "reviewed" | "applying" | "applied" | "failed";
  rows: number;
  headers: string[];
  columns: Record<string, string>;
  options: { match_bn?: boolean };
  counts: Partial<Record<RowAction, number>>;
  job: string | null;
  fields?: ImportField[];
  samples?: Record<string, string[]>;
}

export interface ImportRow {
  row: number;
  key: string;
  label: string;
  action: RowAction;
  changes: Record<string, [unknown, unknown]>;
  errors: { field: string; code: string; message: string }[];
}

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/imports`;

export const importsApi = {
  upload: (org: string, entity: ImportEntity, file: File) => {
    const form = new FormData();
    form.set("entity", entity);
    form.set("file", file);
    return apiRequest<ImportRun>(base(org), { method: "POST", body: form });
  },
  dryRun: (
    org: string,
    id: string,
    columns: Record<string, string>,
    matchBn: boolean,
    saveAs: string,
  ) =>
    apiRequest<ImportRun & { results: ImportRow[] }>(`${base(org)}/${id}/dry-run`, {
      method: "POST",
      body: { columns, options: { match_bn: matchBn }, save_mapping_as: saveAs },
    }),
  rows: (org: string, id: string, action?: RowAction) =>
    apiRequest<{ results: ImportRow[]; count: number }>(
      `${base(org)}/${id}/rows${action ? `?action=${action}` : ""}`,
    ),
  apply: (org: string, id: string) =>
    apiRequest<ImportRun>(`${base(org)}/${id}/apply`, { method: "POST" }),
  get: (org: string, id: string) => apiRequest<ImportRun>(`${base(org)}/${id}`),
};

export const errorsCsvUrl = (org: string, id: string) => `${base(org)}/${id}/errors.csv`;
export const templateUrl = (org: string, entity: ImportEntity) =>
  `${base(org)}/template?entity=${entity}`;

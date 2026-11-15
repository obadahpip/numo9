/**
 * Client for the documents API (A-06, docs/architecture/files.md): `/api/v1/o/<org>/files…`.
 * Every call resolves (never throws on an HTTP error): screens branch on `status` and `code`.
 */
import { apiRequest, type ApiResult, type Numo9Error } from "@/auth/client";

export type DocumentStatus = "uploading" | "scanning" | "clean" | "infected";
export type PreviewStatus = "pending" | "ready" | "unsupported" | "password" | "failed";
export type Folder = "inbox" | "archived";

export interface FileDocument {
  id: string;
  name: string;
  mime: string;
  size: number;
  sha256: string;
  status: DocumentStatus;
  status_label: string;
  source: "upload" | "email";
  sender: string;
  sender_known: boolean;
  period: string;
  tax_year: number | null;
  tags: string[];
  folder: Folder;
  preview_status: PreviewStatus;
  password_protected: boolean;
  uploaded_by: string;
  created_at: string;
}

export interface DocumentPage {
  results: FileDocument[];
  next: string | null;
  total: number;
}

export interface DocumentFilters {
  folder?: Folder;
  status?: string;
  source?: string;
  period?: string;
  taxYear?: string;
  tags?: string[];
  q?: string;
  limit?: number;
  cursor?: string | null;
}

export interface FileAction {
  key: string;
  label: string;
  module: string;
  available: boolean;
  reason: string;
  url: string;
}

export interface Attachment {
  id: string;
  record_type: string;
  record_id: string;
  document: FileDocument;
  attached_at: string;
  attached_by: string;
}

export interface UploadStart {
  document: FileDocument;
  upload: { url: string; fields: Record<string, string> };
  max_size: number;
}

export interface InboundAddress {
  address: string;
  created_at: string;
  previous: { address: string; accepted_until: string } | null;
}

export const MAX_FILE_SIZE = 25 * 1024 * 1024;
export const ACCEPTED_EXTENSIONS = [
  "pdf",
  "png",
  "jpg",
  "jpeg",
  "tif",
  "tiff",
  "heic",
  "heif",
  "xlsx",
  "docx",
  "csv",
  "ofx",
  "qfx",
  "qbo",
];

const base = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/files`;

export function documentsUrl(org: string, filters: DocumentFilters = {}): string {
  const params = new URLSearchParams();
  const set = (key: string, value: string | number | undefined | null) => {
    if (value !== undefined && value !== null && String(value) !== "")
      params.set(key, String(value));
  };
  set("folder", filters.folder);
  set("status", filters.status);
  set("source", filters.source);
  set("period", filters.period);
  set("tax_year", filters.taxYear);
  set("q", filters.q?.trim());
  set("limit", filters.limit);
  set("cursor", filters.cursor);
  for (const tag of filters.tags ?? []) params.append("tag", tag);
  const query = params.toString();
  return query ? `${base(org)}?${query}` : base(org);
}

type Result<T> = Promise<ApiResult<T & Numo9Error>>;

export const filesApi = {
  list: (org: string, filters?: DocumentFilters): Result<DocumentPage> =>
    apiRequest(documentsUrl(org, filters)),
  tags: (org: string): Result<{ results: { tag: string; count: number }[] }> =>
    apiRequest(`${base(org)}/tags`),
  startUpload: (org: string, name: string, size: number): Result<UploadStart> =>
    apiRequest(`${base(org)}/uploads`, { method: "POST", body: { name, size } }),
  finalize: (org: string, id: string): Result<FileDocument & { duplicate: boolean }> =>
    apiRequest(`${base(org)}/${id}/finalize`, { method: "POST" }),
  signedUrl: (
    org: string,
    id: string,
    variant: "file" | "preview" | "thumbnail" = "file",
    download = false,
  ): Result<{ url: string; expires_at: string }> =>
    apiRequest(`${base(org)}/${id}/url?variant=${variant}${download ? "&download=1" : ""}`),
  update: (
    org: string,
    id: string,
    body: Partial<Pick<FileDocument, "name" | "period" | "tax_year" | "tags" | "folder">>,
  ): Result<FileDocument> => apiRequest(`${base(org)}/${id}`, { method: "PATCH", body }),
  bulk: (
    org: string,
    body: {
      ids: string[];
      action: string;
      tags?: string[];
      period?: string;
      tax_year?: number | null;
    },
  ): Result<{ updated: number }> => apiRequest(`${base(org)}/bulk`, { method: "POST", body }),
  actions: (org: string, id: string): Result<{ results: FileAction[] }> =>
    apiRequest(`${base(org)}/${id}/actions`),
  inboundAddress: (org: string): Result<InboundAddress> =>
    apiRequest(`${base(org)}/inbound-address`),
  rotateAddress: (org: string): Result<InboundAddress> =>
    apiRequest(`${base(org)}/inbound-address/rotate`, { method: "POST" }),
  attachments: (
    org: string,
    recordType: string,
    recordId: string,
  ): Result<{ results: Attachment[] }> =>
    apiRequest(
      `${base(org)}/attachments?record_type=${encodeURIComponent(recordType)}&record_id=${encodeURIComponent(recordId)}`,
    ),
  attach: (
    org: string,
    document: string,
    recordType: string,
    recordId: string,
  ): Result<Attachment> =>
    apiRequest(`${base(org)}/attachments`, {
      method: "POST",
      body: { document, record_type: recordType, record_id: recordId },
    }),
  detach: (org: string, attachmentId: string): Result<Record<string, never>> =>
    apiRequest(`${base(org)}/attachments/${attachmentId}`, { method: "DELETE" }),
};

/** "26.2 MB", "740 KB", "12 bytes" — like the API's messages. */
export function humanSize(size: number): string {
  if (size >= 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  if (size >= 1024) return `${Math.round(size / 1024)} KB`;
  return `${size} bytes`;
}

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

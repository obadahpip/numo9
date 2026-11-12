/**
 * Client for the platform console's job dashboard API (A-08-T08, docs/architecture/jobs.md
 * § Job dashboard): `/api/v1/platform/jobs…`, platform.jobs.view to look and
 * platform.jobs.manage to retry or purge. Every call resolves (never throws on an HTTP error).
 */
import { apiRequest, type ApiResult, type Numo9Error } from "@/auth/client";
import type { Job, JobStatus } from "@/jobs/api";

export const CONSOLE_JOBS_API = "/api/v1/platform/jobs";
export const QUEUES = ["high", "default", "io", "reports"] as const;

export interface QueueRow {
  name: string;
  /** Messages waiting in the broker; null when the broker could not be reached. */
  waiting_messages: number | null;
  queued: number;
  running: number;
  retrying: number;
}

export interface Overview {
  queues: QueueRow[];
  counts: {
    queued: number;
    running: number;
    retrying: number;
    succeeded_24h: number;
    failed_24h: number;
    dead: number;
  };
}

export interface ConsoleJob extends Job {
  organisation: { id: string; name: string } | null;
  created_by: { id: string; name: string; email: string } | null;
  queue: string;
  /** Scrubbed arguments. */
  payload: Record<string, unknown>;
  error_detail: string;
  worker: string;
  celery_task_id: string;
  idempotency_key: string;
  max_retries: number;
}

export interface JobPage {
  count: number;
  results: ConsoleJob[];
}

export interface JobFilters {
  status?: JobStatus | "";
  queue?: string;
  q?: string;
}

export type ConsoleError = Numo9Error;

export function getOverview(): Promise<ApiResult<Overview | ConsoleError>> {
  return apiRequest<Overview | ConsoleError>(`${CONSOLE_JOBS_API}/overview`);
}

export function listConsoleJobs(filters: JobFilters): Promise<ApiResult<JobPage | ConsoleError>> {
  const params = new URLSearchParams({ limit: "50" });
  for (const [key, value] of Object.entries(filters)) if (value) params.set(key, String(value));
  return apiRequest<JobPage | ConsoleError>(`${CONSOLE_JOBS_API}?${params.toString()}`);
}

export function retryConsoleJob(id: string): Promise<ApiResult<ConsoleJob | ConsoleError>> {
  return apiRequest<ConsoleJob | ConsoleError>(
    `${CONSOLE_JOBS_API}/${encodeURIComponent(id)}/retry`,
    { method: "POST" },
  );
}

export function purgeJobs(body: {
  ids?: string[];
  status?: "dead" | "failed";
  older_than_days?: number;
}): Promise<ApiResult<{ deleted: number } | ConsoleError>> {
  return apiRequest<{ deleted: number } | ConsoleError>(`${CONSOLE_JOBS_API}/purge`, {
    method: "POST",
    body,
  });
}

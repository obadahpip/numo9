/**
 * Client for the job tray API (A-08-T06, docs/architecture/jobs.md § Progress API): the signed-in
 * person's own jobs in an organisation, under `/api/v1/o/<org>/jobs…`.
 *
 * Every call resolves (never throws on an HTTP error): the tray branches on `status`.
 */
import { apiRequest, type ApiResult, type Numo9Error } from "@/auth/client";

export type JobStatus = "queued" | "running" | "retrying" | "succeeded" | "failed" | "dead";

export const ACTIVE_STATUSES: readonly JobStatus[] = ["queued", "running", "retrying"];

export interface JobProgress {
  done: number;
  total: number | null;
  /** 0–100; null while the number of steps is unknown. */
  percent: number | null;
  message: string;
}

export interface Job {
  id: string;
  type: string;
  /** The job type's name, translated by the server. */
  label: string;
  status: JobStatus;
  status_label: string;
  progress: JobProgress;
  result_url: string;
  /** Message in the language of the person who started the job. */
  error: { code: string; message: string } | null;
  can_retry: boolean;
  attempts: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  next_retry_at: string | null;
}

export const jobsUrl = (org: string) => `/api/v1/o/${encodeURIComponent(org)}/jobs`;
export const jobEventsUrl = (org: string) => `${jobsUrl(org)}/events`;

export function isActive(job: Job): boolean {
  return ACTIVE_STATUSES.includes(job.status);
}

export function listJobs(org: string): Promise<ApiResult<Job[]>> {
  return apiRequest<Job[]>(jobsUrl(org));
}

export function retryJob(org: string, id: string): Promise<ApiResult<Job | Numo9Error>> {
  return apiRequest<Job | Numo9Error>(`${jobsUrl(org)}/${encodeURIComponent(id)}/retry`, {
    method: "POST",
  });
}

/** Tell the job tray that a screen just started a job, so it shows and follows it at once. */
export const JOBS_CHANGED_EVENT = "numo9:jobs-changed";

export function notifyJobsChanged(): void {
  window.dispatchEvent(new Event(JOBS_CHANGED_EVENT));
}

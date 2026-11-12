"use client";

/**
 * Live list of the signed-in person's jobs in an organisation (job tray, A-08-T07).
 *
 * 1. Loads `GET jobs` when mounted, when a screen calls `notifyJobsChanged()` and on `refresh()`.
 * 2. While a job is going, follows `GET jobs/events` (Server-Sent Events): every `jobs` event
 *    replaces the list; `idle` (nothing going any more) closes the stream.
 * 3. Without EventSource, or when the stream fails, polls `GET jobs` every `POLL_ACTIVE_MS`
 *    while a job is going.
 * 4. When nothing is going, checks every `POLL_IDLE_MS` (jobs started in another tab).
 *
 * `jobs` is null until the first answer; a failed load keeps the last list.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { isActive, jobEventsUrl, JOBS_CHANGED_EVENT, listJobs, type Job } from "./api";

export const POLL_ACTIVE_MS = 3_000;
export const POLL_IDLE_MS = 30_000;

export interface JobsState {
  jobs: Job[] | null;
  refresh: () => Promise<void>;
  /** Replace one job in the list (after a retry answered). */
  update: (job: Job) => void;
}

export function useJobs(org: string): JobsState {
  const [jobs, setJobs] = useState<Job[] | null>(null);
  const stream = useRef<EventSource | null>(null);
  const streamFailed = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const alive = useRef(true);

  const closeStream = useCallback(() => {
    stream.current?.close();
    stream.current = null;
  }, []);

  const refresh = useCallback(async () => {
    const answer = await listJobs(org);
    if (alive.current && answer.status === 200 && Array.isArray(answer.body)) {
      setJobs(answer.body);
    }
  }, [org]);

  const openStream = useCallback(() => {
    if (stream.current || streamFailed.current || typeof EventSource === "undefined") return;
    const source = new EventSource(jobEventsUrl(org));
    stream.current = source;
    source.addEventListener("jobs", (event) => {
      try {
        const list = JSON.parse((event as MessageEvent<string>).data) as unknown;
        if (alive.current && Array.isArray(list)) setJobs(list as Job[]);
      } catch {
        // A malformed event is ignored; the next one replaces the list.
      }
    });
    source.addEventListener("idle", () => closeStream());
    source.onerror = () => {
      // The server ends the stream every 25 s and EventSource reconnects by itself; a stream
      // that cannot be opened at all (CLOSED) falls back to polling.
      if (source.readyState === EventSource.CLOSED) {
        streamFailed.current = true;
        closeStream();
        if (alive.current) setJobs((current) => (current ? [...current] : current));
      }
    };
  }, [org, closeStream]);

  // Follow the list: stream (or poll) while something is going, slow check otherwise.
  const anyActive = jobs?.some(isActive) ?? false;
  useEffect(() => {
    if (timer.current) clearTimeout(timer.current);
    if (anyActive) {
      openStream();
      if (!stream.current) timer.current = setTimeout(() => void refresh(), POLL_ACTIVE_MS);
    } else {
      closeStream();
      timer.current = setTimeout(() => void refresh(), POLL_IDLE_MS);
    }
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [jobs, anyActive, openStream, closeStream, refresh]);

  useEffect(() => {
    alive.current = true;
    void refresh();
    const onChanged = () => void refresh();
    window.addEventListener(JOBS_CHANGED_EVENT, onChanged);
    return () => {
      alive.current = false;
      window.removeEventListener(JOBS_CHANGED_EVENT, onChanged);
      closeStream();
    };
  }, [refresh, closeStream]);

  const update = useCallback((job: Job) => {
    setJobs((current) => current?.map((item) => (item.id === job.id ? job : item)) ?? [job]);
  }, []);

  return { jobs, refresh, update };
}

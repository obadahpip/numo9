"use client";

import { Button, Drawer, formatDateTime, IconButton, StatusBadge } from "@numo9/ui";
import { useLocale } from "next-intl";
import { useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";

import { isActive, retryJob, type Job } from "./api";
import { useJobs } from "./useJobs";

const messages = defineMessages({
  button: {
    id: "jobs.tray.button",
    defaultMessage:
      "{active, plural, =0 {Background jobs} one {Background jobs: # running} other {Background jobs: # running}}",
    description: "Top-bar button that opens the job tray; names how many jobs are still going",
  },
  title: {
    id: "jobs.tray.title",
    defaultMessage: "Background jobs",
    description: "Title of the job tray drawer",
  },
  description: {
    id: "jobs.tray.description",
    defaultMessage: "Jobs you started in this organisation. Finished jobs stay here for a day.",
    description: "Text under the job tray title",
  },
  close: {
    id: "jobs.tray.close",
    defaultMessage: "Close background jobs",
    description: "Accessible name of the job tray's close button",
  },
  empty: {
    id: "jobs.tray.empty",
    defaultMessage: "You have no background jobs right now.",
    description: "Job tray when the person has no recent jobs",
  },
  progress: {
    id: "jobs.tray.progress",
    defaultMessage: "{percent}% done",
    description: "Progress bar text of a running job",
  },
  working: {
    id: "jobs.tray.working",
    defaultMessage: "Working…",
    description: "Progress bar text while the number of steps is not known yet",
  },
  waiting: {
    id: "jobs.tray.waiting",
    defaultMessage: "Waiting for a free server…",
    description: "A job that is queued and has not started yet",
  },
  nextTry: {
    id: "jobs.tray.nextTry",
    defaultMessage: "Numo9 will try again at {time}.",
    description: "A job that failed once and will be tried again automatically",
  },
  finishedAt: {
    id: "jobs.tray.finishedAt",
    defaultMessage: "Finished {time}",
    description: "When a job finished",
  },
  openResult: {
    id: "jobs.tray.openResult",
    defaultMessage: "Open the result",
    description: "Link to what a finished job produced (a download, a report, the records)",
  },
  retry: {
    id: "jobs.tray.retry",
    defaultMessage: "Try again",
    description: "Button that starts a failed job again",
  },
  retryFailed: {
    id: "jobs.tray.retryFailed",
    defaultMessage: "The job couldn't be started again. Try again in a few minutes.",
    description: "Shown when the Try again request itself failed",
  },
  reference: {
    id: "jobs.tray.reference",
    defaultMessage: "Reference: {reference}",
    description: "Short job reference to give support when a job fails",
  },
});

interface JobTrayProps {
  /** Active organisation (its public id, as in the app URL). */
  org: string;
}

/**
 * Job tray (A-08-T07): a top-bar button that appears once the person has a recent job, opening a
 * drawer with each job's progress, its result link when done, and its error with "Try again" when
 * it failed. Live through the job event stream (`useJobs`).
 */
export function JobTray({ org }: Readonly<JobTrayProps>) {
  const fm = useFormatMessage();
  const { jobs, update } = useJobs(org);
  const [open, setOpen] = useState(false);
  if (!jobs || jobs.length === 0) return null;
  const active = jobs.filter(isActive).length;

  return (
    <Drawer
      open={open}
      onOpenChange={setOpen}
      size="sm"
      title={fm(messages.title)}
      description={fm(messages.description)}
      closeLabel={fm(messages.close)}
      trigger={
        <span className="relative inline-flex" data-job-tray>
          <IconButton
            variant="inverse"
            label={fm(messages.button, { active })}
            tooltip={false}
            icon={<JobsIcon spinning={active > 0} />}
          />
          {active > 0 ? (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute end-1 top-1 inline-flex min-w-5 items-center justify-center rounded-full bg-surface-accent px-1 text-xs font-semibold text-fg-on-accent"
            >
              {active}
            </span>
          ) : null}
        </span>
      }
    >
      {jobs.length === 0 ? (
        <p className="text-fg-muted">{fm(messages.empty)}</p>
      ) : (
        <ul className="flex flex-col divide-y divide-border" aria-label={fm(messages.title)}>
          {jobs.map((job) => (
            <JobItem key={job.id} org={org} job={job} onChange={update} />
          ))}
        </ul>
      )}
    </Drawer>
  );
}

function JobItem({
  org,
  job,
  onChange,
}: Readonly<{ org: string; job: Job; onChange: (job: Job) => void }>) {
  const fm = useFormatMessage();
  const locale = useLocale() as "en-CA" | "fr-CA";
  const [busy, setBusy] = useState(false);
  const [retryError, setRetryError] = useState(false);
  const when = (value: string) => formatDateTime(value, { locale });

  const retry = async () => {
    setBusy(true);
    setRetryError(false);
    const answer = await retryJob(org, job.id);
    setBusy(false);
    if (answer.status === 202 && "id" in answer.body) onChange(answer.body as Job);
    else setRetryError(true);
  };

  return (
    <li className="flex flex-col gap-2 py-4" data-job={job.id} data-job-status={job.status}>
      <div className="flex items-start justify-between gap-3">
        <span className="font-semibold">{job.label}</span>
        <StatusBadge status={job.status} label={job.status_label} />
      </div>
      {job.status === "running" ? <ProgressBar job={job} /> : null}
      {job.status === "queued" ? <p className="text-fg-muted">{fm(messages.waiting)}</p> : null}
      {job.progress.message && isActive(job) ? (
        <p className="text-fg-muted">{job.progress.message}</p>
      ) : null}
      {job.error ? <p className="text-fg">{job.error.message}</p> : null}
      {job.status === "retrying" && job.next_retry_at ? (
        <p className="text-fg-muted">{fm(messages.nextTry, { time: when(job.next_retry_at) })}</p>
      ) : null}
      {job.status === "succeeded" && job.finished_at ? (
        <p className="text-fg-muted">{fm(messages.finishedAt, { time: when(job.finished_at) })}</p>
      ) : null}
      <div className="flex flex-wrap items-center gap-3">
        {job.status === "succeeded" && job.result_url ? (
          <a className="text-fg-link underline" href={job.result_url}>
            {fm(messages.openResult)}
          </a>
        ) : null}
        {job.can_retry ? (
          <Button size="sm" onClick={() => void retry()} loading={busy}>
            {fm(messages.retry)}
          </Button>
        ) : null}
        {job.error ? (
          <span className="text-xs text-fg-muted">
            {fm(messages.reference, { reference: job.id.slice(0, 8) })}
          </span>
        ) : null}
      </div>
      {retryError ? (
        <p role="alert" className="text-fg-danger">
          {fm(messages.retryFailed)}
        </p>
      ) : null}
    </li>
  );
}

function ProgressBar({ job }: Readonly<{ job: Job }>) {
  const fm = useFormatMessage();
  const percent = job.progress.percent;
  const text = percent === null ? fm(messages.working) : fm(messages.progress, { percent });
  return (
    <div className="flex flex-col gap-1">
      <div
        role="progressbar"
        aria-label={job.label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent ?? undefined}
        aria-valuetext={text}
        className="h-2 w-full overflow-hidden rounded-full bg-surface-muted"
      >
        <div
          className={
            percent === null
              ? "h-full w-1/3 animate-pulse rounded-full bg-surface-accent"
              : "h-full rounded-full bg-surface-accent transition-[width]"
          }
          style={percent === null ? undefined : { width: `${percent}%` }}
        />
      </div>
      <span className="text-xs text-fg-muted">{text}</span>
    </div>
  );
}

function JobsIcon({ spinning }: Readonly<{ spinning: boolean }>) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={spinning ? "size-5 motion-safe:animate-spin" : "size-5"}
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
    >
      {spinning ? (
        <path d="M21 12a9 9 0 1 1-6.2-8.56" />
      ) : (
        <>
          <path d="M4 6h16M4 12h16M4 18h10" />
          <path d="m17 17 2 2 3-4" />
        </>
      )}
    </svg>
  );
}

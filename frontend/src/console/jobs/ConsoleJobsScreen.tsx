"use client";

import {
  Button,
  Checkbox,
  ExplainPanel,
  formatDateTime,
  Input,
  Select,
  StatusBadge,
} from "@numo9/ui";
import { useLocale } from "next-intl";
import { useCallback, useEffect, useId, useState } from "react";

import { defineMessages, useFormatMessage } from "@/i18n";
import type { JobStatus } from "@/jobs/api";

import {
  getOverview,
  listConsoleJobs,
  purgeJobs,
  QUEUES,
  retryConsoleJob,
  type ConsoleError,
  type ConsoleJob,
  type JobFilters,
  type JobPage,
  type Overview,
} from "./api";

const m = defineMessages({
  title: {
    id: "console.jobs.title",
    defaultMessage: "Background jobs",
    description: "Heading of the platform console's job dashboard",
  },
  intro: {
    id: "console.jobs.intro",
    defaultMessage:
      "Every organisation's and the platform's background jobs. Dead jobs used up their tries and wait here to be tried again or purged.",
    description: "Text under the job dashboard heading",
  },
  queues: {
    id: "console.jobs.queues",
    defaultMessage: "Queues",
    description: "Heading of the queue table",
  },
  queue: { id: "console.jobs.queue", defaultMessage: "Queue", description: "Column: queue name" },
  waiting: {
    id: "console.jobs.waitingMessages",
    defaultMessage: "Messages waiting",
    description: "Column: messages waiting in the broker for a worker",
  },
  queued: { id: "console.jobs.queued", defaultMessage: "Queued", description: "Column/count" },
  running: { id: "console.jobs.running", defaultMessage: "Running", description: "Column/count" },
  retrying: {
    id: "console.jobs.retrying",
    defaultMessage: "Waiting to try again",
    description: "Column/count: jobs between two tries",
  },
  failed24h: {
    id: "console.jobs.failed24h",
    defaultMessage: "Failed (24 h)",
    description: "Count of jobs that failed in the last 24 hours",
  },
  succeeded24h: {
    id: "console.jobs.succeeded24h",
    defaultMessage: "Done (24 h)",
    description: "Count of jobs that finished in the last 24 hours",
  },
  dead: {
    id: "console.jobs.dead",
    defaultMessage: "Dead",
    description: "Count of dead jobs (retries used up — the dead-letter queue)",
  },
  brokerDown: {
    id: "console.jobs.brokerDown",
    defaultMessage: "Unknown",
    description: "Messages waiting when the broker could not be reached",
  },
  jobs: { id: "console.jobs.list", defaultMessage: "Jobs", description: "Heading of the job list" },
  filterStatus: {
    id: "console.jobs.filterStatus",
    defaultMessage: "Status",
    description: "Filter: job status",
  },
  filterQueue: {
    id: "console.jobs.filterQueue",
    defaultMessage: "Queue",
    description: "Filter: queue",
  },
  any: { id: "console.jobs.any", defaultMessage: "Any", description: "Filter option: no filter" },
  search: {
    id: "console.jobs.search",
    defaultMessage: "Search",
    description: "Search box: job reference, type, error code or organisation",
  },
  searchHint: {
    id: "console.jobs.searchHint",
    defaultMessage: "Reference, job type, error code or organisation",
    description: "Placeholder of the job search box",
  },
  apply: { id: "console.jobs.apply", defaultMessage: "Show", description: "Apply the filters" },
  platform: {
    id: "console.jobs.platformJob",
    defaultMessage: "Platform",
    description: "Organisation column of a platform job",
  },
  tries: {
    id: "console.jobs.tries",
    defaultMessage: "{attempts} of {max}",
    description: "Tries made of tries allowed",
  },
  error: { id: "console.jobs.error", defaultMessage: "Error", description: "Column" },
  select: {
    id: "console.jobs.select",
    defaultMessage: "Select {reference}",
    description: "Checkbox that selects a job for purging",
  },
  details: {
    id: "console.jobs.details",
    defaultMessage: "Details",
    description: "Opens a job's technical details",
  },
  detailsOf: {
    id: "console.jobs.detailsOf",
    defaultMessage: "Technical details of {reference}",
    description: "Accessible name of a job's detail section",
  },
  arguments: { id: "console.jobs.arguments", defaultMessage: "Arguments", description: "Detail" },
  worker: { id: "console.jobs.worker", defaultMessage: "Worker", description: "Detail" },
  taskId: { id: "console.jobs.taskId", defaultMessage: "Celery task id", description: "Detail" },
  key: { id: "console.jobs.key", defaultMessage: "Idempotency key", description: "Detail" },
  retry: { id: "console.jobs.retry", defaultMessage: "Try again", description: "Retry a job" },
  purgeSelected: {
    id: "console.jobs.purgeSelected",
    defaultMessage: "{count, plural, one {Purge # selected job} other {Purge # selected jobs}}",
    description: "Deletes the selected failed or dead jobs",
  },
  purgeOld: {
    id: "console.jobs.purgeOld",
    defaultMessage: "Purge dead jobs older than 7 days",
    description: "Deletes dead jobs that finished over a week ago",
  },
  purged: {
    id: "console.jobs.purged",
    defaultMessage:
      "{count, plural, =0 {No jobs were purged.} one {# job purged.} other {# jobs purged.}}",
    description: "Result of a purge",
  },
  retried: {
    id: "console.jobs.retried",
    defaultMessage: "{reference} is queued again.",
    description: "Result of Try again",
  },
  count: {
    id: "console.jobs.count",
    defaultMessage: "{shown, plural, one {# job} other {# jobs}} of {total}",
    description: "How many jobs the list shows",
  },
  none: {
    id: "console.jobs.none",
    defaultMessage: "No jobs match these filters.",
    description: "Empty job list",
  },
  loadFailed: {
    id: "console.jobs.loadFailed",
    defaultMessage: "The job dashboard couldn't be loaded. Refresh the page to try again.",
    description: "The dashboard request failed",
  },
  refusedTitle: {
    id: "console.jobs.refusedTitle",
    defaultMessage: "You can't open the job dashboard",
    description: "Title when the person lacks platform.jobs.view",
  },
});

const statusNames = defineMessages({
  queued: {
    id: "console.jobs.statusQueued",
    defaultMessage: "Waiting to start",
    description: "Status filter option",
  },
  running: {
    id: "console.jobs.statusRunning",
    defaultMessage: "Running",
    description: "Status filter option",
  },
  retrying: {
    id: "console.jobs.statusRetrying",
    defaultMessage: "Waiting to try again",
    description: "Status filter option",
  },
  succeeded: {
    id: "console.jobs.statusSucceeded",
    defaultMessage: "Done",
    description: "Status filter option",
  },
  failed: {
    id: "console.jobs.statusFailed",
    defaultMessage: "Failed",
    description: "Status filter option",
  },
  dead: {
    id: "console.jobs.statusDead",
    defaultMessage: "Failed after several tries (dead)",
    description: "Status filter option: the dead-letter queue",
  },
});

const STATUSES: JobStatus[] = ["queued", "running", "retrying", "succeeded", "failed", "dead"];

const isError = (body: unknown): body is ConsoleError =>
  typeof body === "object" && body !== null && "code" in body && !("results" in body);

const reference = (id: string) => id.slice(0, 8);

/**
 * Platform console → Background jobs (A-08-T08): queues and counts, every organisation's job
 * runs with filters, technical details, Try again and purge of failed / dead jobs.
 */
export function ConsoleJobsScreen() {
  const fm = useFormatMessage();
  const [overview, setOverview] = useState<Overview | null>(null);
  const [page, setPage] = useState<JobPage | null>(null);
  const [refusal, setRefusal] = useState<ConsoleError | null>(null);
  const [failed, setFailed] = useState(false);
  const [filters, setFilters] = useState<JobFilters>({ status: "dead" });
  const [draft, setDraft] = useState<JobFilters>({ status: "dead" });
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async (current: JobFilters) => {
    const [head, list] = await Promise.all([getOverview(), listConsoleJobs(current)]);
    if (head.status === 403 || head.status === 401) {
      setRefusal(isError(head.body) ? head.body : { detail: "" });
      return;
    }
    if (head.status !== 200 || list.status !== 200 || isError(head.body) || isError(list.body)) {
      setFailed(true);
      return;
    }
    setFailed(false);
    setOverview(head.body);
    setPage(list.body);
    setSelected(new Set());
  }, []);

  useEffect(() => {
    void load(filters);
  }, [load, filters]);

  const act = async (
    request: Promise<{ status: number; body: unknown }>,
    ok: (body: unknown) => string,
  ) => {
    const answer = await request;
    if (answer.status >= 200 && answer.status < 300) {
      setNotice({ tone: "ok", text: ok(answer.body) });
      await load(filters);
    } else {
      const detail = isError(answer.body) ? answer.body.detail : undefined;
      setNotice({ tone: "error", text: detail ?? fm(m.loadFailed) });
    }
  };

  if (refusal) {
    return (
      <ExplainPanel
        kind="permission"
        headingLevel={1}
        title={fm(m.refusedTitle)}
        body={<p>{refusal.detail}</p>}
      />
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">{fm(m.title)}</h1>
        <p className="text-fg-muted">{fm(m.intro)}</p>
      </header>
      {failed ? (
        <p role="alert" className="text-fg-danger">
          {fm(m.loadFailed)}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className={notice.tone === "ok" ? "text-fg" : "text-fg-danger"}>
          {notice.text}
        </p>
      ) : null}
      {overview ? <OverviewPanel overview={overview} /> : null}
      <section aria-labelledby="console-jobs-list" className="flex flex-col gap-4">
        <h2 id="console-jobs-list" className="text-lg font-semibold">
          {fm(m.jobs)}
        </h2>
        <FilterBar
          draft={draft}
          onChange={setDraft}
          onApply={() => {
            setNotice(null);
            setFilters(draft);
          }}
        />
        <div className="flex flex-wrap gap-3">
          <Button
            variant="danger"
            disabled={selected.size === 0}
            onClick={() =>
              void act(purgeJobs({ ids: [...selected] }), (body) =>
                fm(m.purged, { count: (body as { deleted: number }).deleted }),
              )
            }
          >
            {fm(m.purgeSelected, { count: selected.size })}
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              void act(purgeJobs({ status: "dead", older_than_days: 7 }), (body) =>
                fm(m.purged, { count: (body as { deleted: number }).deleted }),
              )
            }
          >
            {fm(m.purgeOld)}
          </Button>
        </div>
        {page ? (
          <JobTable
            page={page}
            selected={selected}
            onSelect={(id, on) =>
              setSelected((current) => {
                const next = new Set(current);
                if (on) next.add(id);
                else next.delete(id);
                return next;
              })
            }
            onRetry={(job) =>
              void act(retryConsoleJob(job.id), () =>
                fm(m.retried, { reference: reference(job.id) }),
              )
            }
          />
        ) : null}
      </section>
    </div>
  );
}

function OverviewPanel({ overview }: Readonly<{ overview: Overview }>) {
  const fm = useFormatMessage();
  const counts = overview.counts;
  const tiles = [
    { label: fm(m.running), value: counts.running },
    { label: fm(m.queued), value: counts.queued },
    { label: fm(m.retrying), value: counts.retrying },
    { label: fm(m.failed24h), value: counts.failed_24h },
    { label: fm(m.dead), value: counts.dead },
    { label: fm(m.succeeded24h), value: counts.succeeded_24h },
  ];
  return (
    <section aria-labelledby="console-jobs-queues" className="flex flex-col gap-4">
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
        {tiles.map((tile) => (
          <div key={tile.label} className="rounded-md border border-border p-3">
            <dt className="text-sm text-fg-muted">{tile.label}</dt>
            <dd className="text-2xl font-semibold">{tile.value}</dd>
          </div>
        ))}
      </dl>
      <h2 id="console-jobs-queues" className="text-lg font-semibold">
        {fm(m.queues)}
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full text-start text-sm">
          <thead>
            <tr className="border-b border-border text-fg-muted">
              <th scope="col" className="py-2 text-start">
                {fm(m.queue)}
              </th>
              <th scope="col" className="py-2 text-end">
                {fm(m.waiting)}
              </th>
              <th scope="col" className="py-2 text-end">
                {fm(m.queued)}
              </th>
              <th scope="col" className="py-2 text-end">
                {fm(m.running)}
              </th>
              <th scope="col" className="py-2 text-end">
                {fm(m.retrying)}
              </th>
            </tr>
          </thead>
          <tbody>
            {overview.queues.map((queue) => (
              <tr key={queue.name} className="border-b border-border" data-queue={queue.name}>
                <th scope="row" className="py-2 text-start font-mono font-normal">
                  {queue.name}
                </th>
                <td className="py-2 text-end">{queue.waiting_messages ?? fm(m.brokerDown)}</td>
                <td className="py-2 text-end">{queue.queued}</td>
                <td className="py-2 text-end">{queue.running}</td>
                <td className="py-2 text-end">{queue.retrying}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function FilterBar({
  draft,
  onChange,
  onApply,
}: Readonly<{ draft: JobFilters; onChange: (f: JobFilters) => void; onApply: () => void }>) {
  const fm = useFormatMessage();
  const statusId = useId();
  const queueId = useId();
  const searchId = useId();
  const ANY = "any";
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        onApply();
      }}
    >
      <div className="flex flex-col gap-1">
        <label htmlFor={statusId} className="text-sm font-medium">
          {fm(m.filterStatus)}
        </label>
        <Select
          id={statusId}
          value={draft.status || ANY}
          onValueChange={(value) =>
            onChange({ ...draft, status: value === ANY ? "" : (value as JobStatus) })
          }
          options={[
            { value: ANY, label: fm(m.any) },
            ...STATUSES.map((status) => ({ value: status, label: fm(statusNames[status]) })),
          ]}
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={queueId} className="text-sm font-medium">
          {fm(m.filterQueue)}
        </label>
        <Select
          id={queueId}
          value={draft.queue || ANY}
          onValueChange={(value) => onChange({ ...draft, queue: value === ANY ? "" : value })}
          options={[
            { value: ANY, label: fm(m.any) },
            ...QUEUES.map((queue) => ({ value: queue, label: queue })),
          ]}
        />
      </div>
      <div className="flex min-w-60 flex-1 flex-col gap-1">
        <label htmlFor={searchId} className="text-sm font-medium">
          {fm(m.search)}
        </label>
        <Input
          id={searchId}
          type="search"
          value={draft.q ?? ""}
          placeholder={fm(m.searchHint)}
          onChange={(event) => onChange({ ...draft, q: event.target.value })}
        />
      </div>
      <Button type="submit">{fm(m.apply)}</Button>
    </form>
  );
}

function JobTable({
  page,
  selected,
  onSelect,
  onRetry,
}: Readonly<{
  page: JobPage;
  selected: Set<string>;
  onSelect: (id: string, on: boolean) => void;
  onRetry: (job: ConsoleJob) => void;
}>) {
  const fm = useFormatMessage();
  const locale = useLocale() as "en-CA" | "fr-CA";
  const [open, setOpen] = useState<string | null>(null);
  if (page.results.length === 0) return <p className="text-fg-muted">{fm(m.none)}</p>;
  return (
    <div className="flex flex-col gap-2">
      <p className="text-sm text-fg-muted">
        {fm(m.count, { shown: page.results.length, total: page.count })}
      </p>
      <ul className="flex flex-col divide-y divide-border border-y border-border">
        {page.results.map((job) => {
          const ref = reference(job.id);
          return (
            <li key={job.id} className="flex flex-col gap-2 py-3" data-console-job={job.id}>
              <div className="flex flex-wrap items-start gap-3">
                {job.can_retry ? (
                  <Checkbox
                    aria-label={fm(m.select, { reference: ref })}
                    checked={selected.has(job.id)}
                    onCheckedChange={(on) => onSelect(job.id, on === true)}
                  />
                ) : (
                  <span className="inline-block size-5" aria-hidden="true" />
                )}
                <div className="flex min-w-48 flex-1 flex-col">
                  <span className="font-semibold">{job.label}</span>
                  <span className="font-mono text-xs text-fg-muted">
                    {[ref, job.type, job.queue].join(" · ")}
                  </span>
                </div>
                <span className="min-w-40">{job.organisation?.name ?? fm(m.platform)}</span>
                <StatusBadge status={job.status} label={job.status_label} />
                <span className="text-sm text-fg-muted">
                  {fm(m.tries, { attempts: job.attempts, max: job.max_retries + 1 })}
                </span>
                <span className="text-sm text-fg-muted">
                  {formatDateTime(job.created_at, { locale })}
                </span>
              </div>
              {job.error ? (
                <p className="ps-8">
                  <span className="font-mono text-xs">{job.error.code}</span> {job.error.message}
                </p>
              ) : null}
              <div className="flex flex-wrap gap-3 ps-8">
                {job.can_retry ? (
                  <Button size="sm" onClick={() => onRetry(job)}>
                    {fm(m.retry)}
                  </Button>
                ) : null}
                <Button
                  size="sm"
                  variant="ghost"
                  aria-expanded={open === job.id}
                  aria-controls={`details-${job.id}`}
                  onClick={() => setOpen(open === job.id ? null : job.id)}
                >
                  {fm(m.details)}
                </Button>
              </div>
              {open === job.id ? (
                <dl
                  id={`details-${job.id}`}
                  aria-label={fm(m.detailsOf, { reference: ref })}
                  className="ms-8 grid grid-cols-1 gap-2 rounded-md bg-surface-muted p-3 text-sm md:grid-cols-[12rem_1fr]"
                >
                  <dt className="font-medium">{fm(m.error)}</dt>
                  <dd className="font-mono break-all whitespace-pre-wrap">{job.error_detail}</dd>
                  <dt className="font-medium">{fm(m.arguments)}</dt>
                  <dd className="font-mono break-all whitespace-pre-wrap">
                    {JSON.stringify(job.payload, null, 2)}
                  </dd>
                  <dt className="font-medium">{fm(m.worker)}</dt>
                  <dd className="font-mono break-all">{job.worker}</dd>
                  <dt className="font-medium">{fm(m.taskId)}</dt>
                  <dd className="font-mono break-all">{job.celery_task_id}</dd>
                  <dt className="font-medium">{fm(m.key)}</dt>
                  <dd className="font-mono break-all">{job.idempotency_key}</dd>
                </dl>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

# Background jobs (A-08)

| | |
|---|---|
| **Deliverable** | A-08 · Background jobs & scheduling (Phase 0) |
| **Code** | `backend/numo9/celery.py`, `backend/numo9/jobs/`, settings in `backend/numo9/settings/base.py` § Background jobs |
| **Library** | Celery 5.6, Redis 7 (broker and result backend) |

## Celery app (A-08-T01)

`numo9/celery.py` builds the app from Django settings (`CELERY_*`) and discovers each installed
app's `tasks` module. Start a worker for every queue:

```
celery -A numo9 worker -Q high,default,io,reports --loglevel INFO
```

`make up` starts one as the `worker` service (health check: `manage.py celery_ping`).
`manage.py celery_ping [--queue reports] [--timeout 10]` sends the `numo9.jobs.ping` task and
fails (exit 1) when no worker answers — used after a deploy.

| Setting | Value | Why |
|---|---|---|
| Broker / results | Redis of `REDIS_URL`, database 2 / 3 (`CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` override) | The cache keeps database 0 |
| Serialisation | JSON only (`accept_content = ["json"]`) | No pickle: a message cannot run code in a worker |
| `task_acks_late` + `task_reject_on_worker_lost` | on | A task is acknowledged after it finishes; a worker that dies mid-task leaves it to be delivered again (A-08-T03 idempotency keys make that safe) |
| `worker_prefetch_multiplier` | 1 | Each worker process reserves one message: no short job waits behind a long one |
| Time limits | soft 25 min (`SoftTimeLimitExceeded` in the task), hard 30 min (process killed); env `CELERY_TASK_SOFT_TIME_LIMIT`, `CELERY_TASK_TIME_LIMIT`; per task overrides for long reports | Runaway jobs end |
| `visibility_timeout` | 2 h | Must exceed the hard limit, or Redis would redeliver a task that is still running |
| Results | kept 1 day, extended (name, args, queue) | What users see is kept in `JobRun` (A-08-T02, 30 days) |
| Queues | `high`, `default`, `io`, `reports`; unnamed tasks → `default`; unknown queue names are refused (`task_create_missing_queues = False`) | See below |
| Events | task events on | Job dashboard (A-08-T08) |
| Time zone | UTC | Organisation-local schedules convert explicitly |

### Queues

| Queue | For | Examples |
|---|---|---|
| `high` | short jobs a person is waiting for | an email the user just triggered, new-device notice, webhooks to acknowledge |
| `default` | ordinary background work | trial reminders, recurring documents, usage metering |
| `io` | slow network or file work | virus scans, inbound email, OCR, bank feeds, exports to storage |
| `reports` | long CPU / database work | report packs, bulk edits, imports, period-end runs |

Production runs separate workers per queue group (e.g. `high,default` and `io,reports`) so a
long report never delays a high-priority job.

Tests: `backend/tests/test_celery.py` (configuration; a worker thread on the in-memory broker
consumes the test task on every queue; `celery_ping`), `backend/tests/test_celery_redis.py`
(the same against Redis — CI backend job has a Redis 7 service).

## Job runs (A-08-T02)

`numo9.jobs.models.JobRun` is the record of every background job: written before the Celery
message is sent, updated by the job base class as the job runs, read by the job tray and the
platform console. Celery's result backend keeps outcomes one day; job runs are kept 30 days
after they finish (`RETENTION`).

| Field | Meaning |
|---|---|
| `organisation` | The organisation the job works for; empty for platform jobs (retention purge, nightly rebuilds) |
| `task_name`, `queue` | Job type (the Celery task name) and the queue it was sent to |
| `status` | `queued` → `running` → `succeeded`; `retrying` between tries; `failed` (an error retrying cannot fix); `dead` (retries used up — the dead-letter state) |
| `progress_done` / `progress_total` / `progress_message` | Progress in steps (total may be unknown); `progress_percent` 0–100 |
| `payload` | The task's keyword arguments (JSON), kept so a failed run can be sent again |
| `result`, `result_url` | What the job returned; a link to its output (download, report) |
| `error_code`, `error_message` | A stable code and a message the person who started the job may read |
| `error_detail` | Exception type and text (scrubbed) — platform console only |
| `idempotency_key` | **Unique** across the table: a second start with the same key gets the existing run |
| `attempts`, `max_retries`, `next_retry_at` | Tries made, tries allowed, when the next try is due |
| `celery_task_id`, `worker`, `started_at`, `finished_at` | Where and when it ran |
| `created_by`, `created_at`, `public_id` | From `OrgOwnedModel`: who started it (empty for scheduled jobs), when, public id for the API |

Database rules: unique `idempotency_key` (`jobs_jobrun_idempotency_key_unique`, never empty),
`status` one of the six, `progress_done ≤ progress_total` when the total is known. Indexes for
the tray (organisation, starter, newest first), the console (status, newest first) and the purge
(`finished_at`).

**Tenancy.** `JobRun` is an `OrgOwnedModel` whose organisation may be empty. `JobRun.objects`
(the default manager) is organisation-scoped like every business record, so API views only ever
see the active organisation's jobs and never platform jobs. `JobRun.platform_runs` (plain
manager) is reserved for the job machinery, which loads a run before any tenant context exists,
and for the platform console.

Tests: `backend/tests/test_job_run_model.py` (duplicate key rejected by the database, also across
organisations; status and progress constraints; scoping).

## Job base class (A-08-T03)

`numo9/jobs/runtime.py`. A *job* is a Celery task built on `JobTask` (organisation jobs, on top
of `OrgTask` from A-01-T07) or `PlatformJobTask` (no organisation), declared with `@org_job` /
`@platform_job` and **started with `start_job()`** — `delay()` / `apply_async()` without a run
raise `JobRunRequired`.

```python
@org_job(name="numo9.contacts.bulk_archive", queue=queues.REPORTS)
def bulk_archive(*, org_id: str, contact_ids: list[str]) -> dict[str, int]:
    for done, cid in enumerate(contact_ids, 1):
        ...
        report_progress(done, len(contact_ids))
    set_result_url(f"/o/{org_id}/contacts?archived=1")
    return {"archived": len(contact_ids)}

run = start_job(bulk_archive, organisation=org, key=f"archive:{batch_id}",
                created_by=request.user, contact_ids=ids)
```

**Starting (`start_job`).** The idempotency key is `<task>:<organisation public id | platform>:<key>`
(random when no key is given; keys over 255 characters are hashed). The run is created with that
key; if one exists — also one another process inserted a moment earlier (the unique constraint
decides) — it is returned with `run.started_now = False` and nothing is sent. Otherwise the message
(`job_run_id` added to the keyword arguments, Celery task id = `run.celery_task_id`) is sent when
the surrounding transaction commits; if the broker refuses, the run becomes `failed` with
`job.not_queued` and the error reaches the caller. Arguments and results are JSON only.

**Running.** For each delivery the base class:

| Step | What happens |
|---|---|
| Check the message | No `job_run_id` → `JobRunRequired`; unknown run, other task or other organisation than the run's → `JobRunMismatch` (both in `throws`: logged, never retried) |
| Lock | PostgreSQL session advisory lock on the run (`0xA08 << 40 \| run id`) for the whole run. Held by another worker → the delivery is skipped (`job.skipped_locked`). A killed worker's connection closes and releases it, so the redelivered message can take over |
| Already finished? | A redelivered message of a finished run returns the stored result; the body does not run (`job.skipped_finished`) |
| Mark running | `attempts + 1`, `worker` (`host:pid`), `started_at` (first try), Celery task id |
| Run the body | Organisation jobs inside `org_context` (scoped managers, RLS setting). `atomic = True` (default): the body and the `succeeded` mark are one transaction — a job that dies half-way leaves nothing, and its rerun applies the effect once. `atomic=False` for long jobs that commit as they go (each step must be safe to repeat) |
| Finish | `succeeded` with the result and finish time (progress set to its total), or `failed` with the error |

Inside the body: `current_job()` (the run), `report_progress(done, total, note)` (written at once;
in an atomic job visible at commit), `set_result_url(url)`. `JobError(errors.X, retry=False,
**params)` fails the run with that catalogue message; any other exception stores the generic
`job.failed` message. Messages are stored in the language of the person who started the job
(else the organisation's); `error_detail` keeps the exception type and text, scrubbed of SINs,
card and bank numbers (S-03-T06), for the console only.

**Logs.** One `numo9.jobs` record per step — `job.queued`, `job.duplicate`, `job.started`,
`job.succeeded`, `job.failed`, `job.skipped_locked`, `job.skipped_finished` — with a `job` field
(`id`, `task`, `org_id`, `queue`, `status`, `attempt`, `duration_ms`, `error`). Lines the body logs
carry `job_id`, `job_task` and `org_id` (structlog context variables).

Tests: `backend/tests/test_job_runtime.py` — same key runs once (duplicate start sends nothing, a
redelivered finished run does not rerun), keys per organisation, the race path, commit-time
sending, broker failure, the lifecycle fields and log events, rollback of an atomic job, scrubbed
detail in the starter's language, refused messages, skip while another connection holds the lock,
and a real worker thread running a started job.

## Retry policy and dead letters (A-08-T04)

`numo9/jobs/retry.py`, applied by the base class when a body raises.

| Outcome of a try | Run status | What the person sees |
|---|---|---|
| Error retrying can help (any unexpected exception, `JobError(..., retry=True)`, soft time limit) and tries left | `retrying`, `next_retry_at` set | The error message with "Waiting to try again" |
| Same, no tries left | `dead` (dead letter) | "Failed after several tries" + the error, **Retry** |
| `JobError(...)` (retry=False), result not JSON (`JobResultNotJSON`), `throws` errors | `failed` at once | The error, **Retry** |
| The worker died mid-run (OOM, hard time limit) | redelivered, counted as a try; after the last try `dead` with `job.worker_lost` | as dead |

**Backoff.** Retry *n* waits `d = min(backoff_max, backoff_base × 2^(n-1))` with equal jitter —
a random delay in `[d/2, d]` — so jobs that failed together do not return together. Defaults
`max_retries = 5` (6 tries), `backoff_base = 30` s, `backoff_max = 1` h: 15–30 s, 30–60 s,
1–2 min, 2–4 min, 4–8 min. Per task: `@org_job(max_retries=…, backoff_base=…, backoff_max=…)`.
Retries are Celery retries (`task.retry(countdown=…)`, state `RETRY`; the same Celery task id).

**Dead letters.** A `dead` run keeps its task, `payload` and last error; nothing retries it by
itself. The dead-letter list is the console's failures view (A-08-T08: retry, purge); the person
who started a job retries it from the job tray (A-08-T07).

**Retry by hand** — `retry_run(run, by=user)`: only `failed` / `dead` runs (else `409
job.not_retryable`); the same run (same idempotency key) goes back to `queued` with its error,
result and progress cleared, a new Celery task id and a fresh retry budget, and is sent after
commit. The status change is a conditional update, so two clicks send it once.

Log events: `job.retrying` (with `retry` number and `delay_s`, WARNING), `job.dead` (ERROR),
`job.retried_by_hand`.

Tests: `backend/tests/test_job_retry.py` — backoff growth, cap and jitter range; the retrying run
shows its error and next try; retried until it succeeds; dead after the last try with its
arguments kept; errors that fail at once; worker-lost poison message dead-lettered; retry by hand
(fresh budget, only failed runs, two clicks send once); a real worker retrying with backoff.

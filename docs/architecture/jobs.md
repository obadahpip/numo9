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

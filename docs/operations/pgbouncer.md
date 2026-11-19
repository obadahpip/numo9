# Connection pooling with PgBouncer (S-06-T01)

Django and Celery workers don't talk to PostgreSQL directly in staging and production: they
connect to **PgBouncer in transaction pooling mode**, which lends one of a small set of server
connections to a client for the length of one transaction.

| Setting | Value | Where |
|---|---|---|
| Pool mode | `transaction` | `infra/staging/docker-compose.staging.yml` service `pgbouncer` |
| Client connections | up to 1,000 (`MAX_CLIENT_CONN`) | idem |
| Server connections | 40 per database/user (`DEFAULT_POOL_SIZE`), + 10 reserve, 60 at most | idem |
| PostgreSQL `max_connections` | 100 (pool + maintenance + migrations) | service `postgres` |
| Django `DATABASE_URL` | `…@pgbouncer:6432/numo9` | service `backend` |
| Django `NUMO9_DB_POOL` | `pgbouncer` | idem |
| Django `CONN_MAX_AGE` | `DJANGO_CONN_MAX_AGE`, 300 s in staging (60 s default), with `CONN_HEALTH_CHECKS` | `numo9/settings/database.py` |

## What transaction pooling forbids, and how Numo9 complies

A server connection belongs to the client only until `COMMIT`/`ROLLBACK`; the next transaction
may run on another one. Anything that lives on the server connection beyond a transaction breaks:

| Feature | Numo9 |
|---|---|
| Server-side cursors (`QuerySet.iterator()` declares one) | `DISABLE_SERVER_SIDE_CURSORS = True` with `NUMO9_DB_POOL=pgbouncer`; Django fetches in chunks client-side |
| Prepared statements (psycopg 3 prepares after 5 executions) | `OPTIONS["prepare_threshold"] = None` |
| Session settings (`SET`, `set_config(…, false)`) | none; the tenancy GUC `app.current_org` is `set_config(…, true)`, transaction-local (`numo9.tenancy.rls`) |
| Session advisory locks (`pg_advisory_lock`) | none; the audit chain and files use `pg_advisory_xact_lock` |
| `LISTEN`/`NOTIFY`, temporary tables across transactions | not used |

`CONN_MAX_AGE` keeps a worker's *client* connection to PgBouncer between requests (cheap); the
health check replaces one PgBouncer or the network closed.

Migrations run through the pool too: each Django migration is one transaction.

## Measurement (acceptance: 500 concurrent connections served by the pool)

`pgbench` on a developer machine (PostgreSQL 16, PgBouncer 1.22, transaction mode, pool 40),
read-only workload, 500 clients for 20 s through PgBouncer:

```
pgbench -h 127.0.0.1 -p 6432 -U numo9 -c 500 -j 4 -T 20 -S numo9
number of clients: 500
number of transactions actually processed: 467559
number of failed transactions: 0 (0.000%)
latency average = 21.098 ms
tps = 23483.731293
```

During the run `pg_stat_activity` showed **40** server connections for 500 clients. The same
command straight to PostgreSQL fails above `max_connections`.

The backend suite runs through the pool with
`NUMO9_DB_POOL=pgbouncer DATABASE_URL=postgres://…@127.0.0.1:6432/numo9 pytest …` — RLS
(`test_tenancy_rls.py`), the audit hash chain, tenant revocation, files isolation, the journal
sequence and the posting storm passed that way; `test_settings_database.py` pins the settings.

The production-scale check (500 organisations × 100k lines) is part of Phase 5.

## Read replica (S-06-T10)

`DATABASE_REPLICA_URL` adds the `replica` alias. Reporting code wraps its reads in
`numo9.replica.using_replica()`; `ReplicaRouter` sends them to the replica when the alias exists
and to the primary otherwise (the stub until the replica server exists, Phase 5). Writes and
migrations always use the primary; reads inside an open transaction stay on the primary. A replica
behind PgBouncer gets its own `[databases]` entry and the same `NUMO9_DB_POOL` settings.

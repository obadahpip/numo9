"""Database connection settings shared by every environment (S-06-T01).

``database(url)`` turns ``DATABASE_URL`` into Django's ``DATABASES["default"]``:

- ``CONN_MAX_AGE`` (``DJANGO_CONN_MAX_AGE``, default 60 s) keeps a worker's connection between
  requests, with ``CONN_HEALTH_CHECKS`` so a connection the pool or the server closed is replaced
  instead of failing the next request.
- ``NUMO9_DB_POOL=pgbouncer`` — ``DATABASE_URL`` points at PgBouncer in **transaction** pooling
  mode (infra/staging/docker-compose.staging.yml, docs/operations/pgbouncer.md). A server
  connection then belongs to a client only for one transaction, so nothing may outlive a
  transaction on the server:

  * ``DISABLE_SERVER_SIDE_CURSORS`` — ``QuerySet.iterator()`` would declare a cursor that the next
    transaction (another client) can't see; Django fetches in chunks client-side instead;
  * ``prepare_threshold=None`` — psycopg 3 prepares a statement after 5 runs, and a prepared
    statement lives on the server connection, which the next transaction may not get;
  * session settings are never used: the tenancy GUC is ``set_config(..., true)``
    (transaction-local, numo9.tenancy.rls) and locks are ``pg_advisory_xact_lock``.

  ``CONN_MAX_AGE`` then keeps the cheap client connection to PgBouncer, not a server connection.
"""

from __future__ import annotations

from typing import Any

import dj_database_url

from .env import env_int, env_str

#: PgBouncer in transaction pooling mode.
PGBOUNCER = "pgbouncer"


def database(
    url: str, *, pool: str | None = None, conn_max_age: int | None = None
) -> dict[str, Any]:
    """``DATABASES["default"]`` for ``url``; ``pool`` and ``conn_max_age`` default to the env."""
    pool = env_str("NUMO9_DB_POOL", "") if pool is None else pool
    if pool not in ("", PGBOUNCER):
        raise ValueError(f"NUMO9_DB_POOL must be empty or {PGBOUNCER!r}, not {pool!r}")
    age = env_int("DJANGO_CONN_MAX_AGE", 60) if conn_max_age is None else conn_max_age
    config: dict[str, Any] = dict(
        dj_database_url.parse(url, conn_max_age=age, conn_health_checks=age > 0)
    )
    if pool == PGBOUNCER:
        config["DISABLE_SERVER_SIDE_CURSORS"] = True
        config["OPTIONS"] = {**config.get("OPTIONS", {}), "prepare_threshold": None}
    return config

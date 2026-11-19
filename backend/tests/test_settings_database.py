"""S-06-T01 — database settings for PgBouncer transaction pooling.

Acceptance: 500 concurrent connections are served by the pool (pgbench through PgBouncer,
docs/operations/pgbouncer.md). These tests pin the Django side: with ``NUMO9_DB_POOL=pgbouncer``
nothing outlives a transaction on the server connection — no server-side cursors, no prepared
statements — and persistent client connections are health-checked; without a pool the
configuration is unchanged. The suite itself runs through PgBouncer with
``NUMO9_DB_POOL=pgbouncer`` (``test_through_the_pool`` below only runs then).
"""

from __future__ import annotations

import os

import pytest
from django.db import connection

from numo9.settings.database import PGBOUNCER, database

URL = "postgres://numo9:secret@pgbouncer:6432/numo9"


def test_pgbouncer_disables_server_side_cursors_and_prepared_statements() -> None:
    config = database(URL, pool=PGBOUNCER, conn_max_age=300)
    assert config["DISABLE_SERVER_SIDE_CURSORS"] is True
    assert config["OPTIONS"]["prepare_threshold"] is None
    assert config["CONN_MAX_AGE"] == 300
    assert config["CONN_HEALTH_CHECKS"] is True
    assert (config["HOST"], config["PORT"]) == ("pgbouncer", 6432)


def test_direct_connection_keeps_the_defaults() -> None:
    config = database(URL, pool="", conn_max_age=60)
    assert not config.get("DISABLE_SERVER_SIDE_CURSORS")
    assert "prepare_threshold" not in config.get("OPTIONS", {})
    assert config["CONN_MAX_AGE"] == 60


def test_no_persistent_connection_means_no_health_check() -> None:
    assert database(URL, pool="", conn_max_age=0)["CONN_HEALTH_CHECKS"] is False


def test_conn_max_age_and_pool_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DJANGO_CONN_MAX_AGE", "120")
    monkeypatch.setenv("NUMO9_DB_POOL", "pgbouncer")
    config = database(URL)
    assert config["CONN_MAX_AGE"] == 120
    assert config["DISABLE_SERVER_SIDE_CURSORS"] is True


def test_unknown_pool_is_refused() -> None:
    with pytest.raises(ValueError, match="NUMO9_DB_POOL"):
        database(URL, pool="pgpool")


@pytest.mark.skipif(os.environ.get("NUMO9_DB_POOL") != PGBOUNCER, reason="suite not pooled")
@pytest.mark.django_db
def test_through_the_pool() -> None:
    from django.contrib.auth import get_user_model

    assert connection.settings_dict["DISABLE_SERVER_SIDE_CURSORS"] is True
    users = get_user_model().objects.all()
    assert list(users.iterator(chunk_size=10)) == list(users)  # no server-side cursor needed

"""S-06-T10 — read-replica routing stub.

Acceptance: the router selects the alias by ``using_replica()``. Reads go to ``replica`` only
inside ``using_replica()`` and only when a replica is configured; without one they stay on
``default`` (the stub points to the primary until the replica exists); writes and migrations
always use ``default``; a read inside an open transaction stays on the primary. In the test
settings ``replica`` mirrors the primary, so a real query through it returns committed rows.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.db import connections, transaction

from numo9.replica import DEFAULT, REPLICA, ReplicaRouter, read_alias, using_replica
from numo9.settings.database import databases

router = ReplicaRouter()


def test_reads_use_the_replica_only_inside_using_replica() -> None:
    User = get_user_model()
    assert router.db_for_read(User) == DEFAULT
    with using_replica() as alias:
        assert alias == REPLICA
        assert router.db_for_read(User) == REPLICA
        assert router.db_for_write(User) == DEFAULT
    assert router.db_for_read(User) == DEFAULT


def test_without_a_replica_everything_stays_on_the_primary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("numo9.replica.replica_configured", lambda: False)
    with using_replica() as alias:
        assert alias == DEFAULT
        assert router.db_for_read(get_user_model()) == DEFAULT


def test_migrations_only_on_the_primary() -> None:
    assert router.allow_migrate(DEFAULT, "ledger") is True
    assert router.allow_migrate(REPLICA, "ledger") is False


@pytest.mark.django_db(transaction=True, databases=[DEFAULT, REPLICA])
def test_a_reporting_read_goes_through_the_replica_connection() -> None:
    User = get_user_model()
    User.objects.create_user(email="report@cpa.ca", password="x" * 12)
    replica = connections[REPLICA]
    with using_replica():
        assert list(User.objects.values_list("email", flat=True)) == ["report@cpa.ca"]
    assert replica.connection is not None  # the query opened the replica's connection
    assert User.objects.db == DEFAULT


@pytest.mark.django_db(transaction=True, databases=[DEFAULT, REPLICA])
def test_reads_inside_a_transaction_stay_on_the_primary() -> None:
    with transaction.atomic(), using_replica():
        assert read_alias() == DEFAULT


def test_settings_build_the_replica_alias_from_its_url() -> None:
    assert list(databases("postgres://a:b@primary/numo9")) == [DEFAULT]
    found = databases("postgres://a:b@primary/numo9", "postgres://a:b@replica/numo9")
    assert found[REPLICA]["HOST"] == "replica"

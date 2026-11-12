"""Hash chain per organisation + ``audit_verify`` (A-04-T05).

Acceptance: a tampered row is detected. A row changed in the database (the append-only trigger
switched off, as only a superuser could), a row removed and a row inserted are each reported by
``audit_verify``, which fails; untouched chains pass. Concurrent writers in one organisation still
produce one unbroken chain.
"""

from __future__ import annotations

import threading
import uuid
from io import StringIO
from typing import Any

import pytest
from django.core.management import CommandError, call_command
from django.db import connection, connections

from numo9.audit.chain import GENESIS, compute_hash, payload, verify
from numo9.audit.models import AuditEvent
from numo9.audit.service import record
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


def chain_of(org: Organisation | None) -> list[AuditEvent]:
    rows = AuditEvent.platform_events.order_by("id")
    return list(rows.filter(organisation=org) if org else rows.filter(organisation__isnull=True))


def write(org: Organisation | None, n: int) -> list[AuditEvent]:
    return [record(f"tests.step{i}", organisation=org, changes={"n": [i, i + 1]}) for i in range(n)]


def sql(statement: str, params: list[Any] | None = None) -> None:
    with connection.cursor() as cursor:
        cursor.execute(statement, params)


def run_verify(*args: str) -> str:
    out = StringIO()
    call_command("audit_verify", *args, stdout=out)
    return out.getvalue()


def tamper(statement: str, params: list[Any]) -> None:
    """Change the table behind the application's back (superuser only: trigger off, then on)."""
    sql("SET CONSTRAINTS ALL IMMEDIATE")  # no deferred foreign-key checks pending
    sql("ALTER TABLE audit_event DISABLE TRIGGER audit_event_append_only")
    try:
        sql(statement, params)
    finally:
        sql("ALTER TABLE audit_event ENABLE TRIGGER audit_event_append_only")


# ---- the chain ---------------------------------------------------------------------------------


def test_events_link_to_the_previous_one(org: Organisation) -> None:
    write(org, 3)
    first, second, third = chain_of(org)
    assert first.prev_hash == GENESIS
    assert second.prev_hash == first.hash and third.prev_hash == second.hash
    for event in (first, second, third):
        assert event.hash == compute_hash(event.prev_hash, payload(event))
        assert len(event.hash) == 64


def test_each_organisation_and_the_platform_have_their_own_chain(org: Organisation) -> None:
    other = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    write(org, 2)
    write(other, 1)
    write(None, 1)
    assert chain_of(other)[0].prev_hash == GENESIS
    assert chain_of(None)[0].prev_hash == GENESIS
    assert chain_of(org)[1].prev_hash == chain_of(org)[0].hash


def test_verify_passes_untouched_chains(org: Organisation) -> None:
    write(org, 4)
    write(None, 2)
    output = run_verify()
    assert f"OK     {org.public_id}" in output and "4 events" in output
    assert "0 broken" in output
    assert all(report.ok for report in verify())


def test_hash_survives_reload_of_every_field_type(org: Organisation) -> None:
    event = record(
        "tests.rich",
        organisation=org,
        changes={"amount": ["1.00", "2.50"], "note": [None, "Café — été"]},
        meta={"nested": {"b": [1, 2], "a": True}},
        ip="2001:DB8:0:0::1",
        user_agent="UA",
    )
    stored = AuditEvent.platform_events.get(public_id=event.public_id)
    assert stored.hash == compute_hash(stored.prev_hash, payload(stored)) == event.hash


# ---- acceptance: tampering is detected ---------------------------------------------------------


def test_changed_row_is_detected(org: Organisation) -> None:
    events = write(org, 3)
    tamper(
        "UPDATE audit_event SET changes = '{\"n\": [1, 99]}'::jsonb WHERE public_id = %s",
        [events[1].public_id],
    )
    (report,) = verify(str(org.public_id))
    assert [(p.public_id, p.reason) for p in report.problems] == [
        (str(events[1].public_id), "hash")
    ]
    with pytest.raises(CommandError, match="1 broken"):
        run_verify("--organisation", str(org.public_id))


def test_rewritten_hash_breaks_the_next_link(org: Organisation) -> None:
    events = write(org, 3)
    tamper(
        "UPDATE audit_event SET action = 'tests.forged', hash = %s WHERE public_id = %s",
        ["f" * 64, events[1].public_id],
    )
    (report,) = verify(str(org.public_id))
    reasons = {(p.public_id, p.reason) for p in report.problems}
    assert (str(events[1].public_id), "hash") in reasons
    assert (str(events[2].public_id), "link") in reasons


def test_removed_row_is_detected(org: Organisation) -> None:
    events = write(org, 3)
    tamper("DELETE FROM audit_event WHERE public_id = %s", [events[1].public_id])
    (report,) = verify(str(org.public_id))
    assert [(p.public_id, p.reason) for p in report.problems] == [
        (str(events[2].public_id), "link")
    ]


def test_inserted_row_is_detected(org: Organisation) -> None:
    events = write(org, 2)
    sql(
        "INSERT INTO audit_event (id, created_at, public_id, organisation_id, actor_kind, "
        "actor_label, action, object_type, object_id, object_label, changes, meta, user_agent, "
        "request_id, prev_hash, hash) VALUES (%s, now(), %s, %s, 'system', 'System', "
        "'tests.inserted', '', '', '', '{}', '{}', '', '', %s, %s)",
        [events[0].id, uuid.uuid4(), org.pk, events[0].hash, "e" * 64],
    )
    (report,) = verify(str(org.public_id))
    assert not report.ok


def test_quiet_output_lists_only_broken_chains(org: Organisation) -> None:
    other = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    events = write(org, 2)
    write(other, 1)
    tamper("DELETE FROM audit_event WHERE public_id = %s", [events[0].public_id])
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("audit_verify", "--quiet", stdout=out)
    assert str(org.public_id) in out.getvalue() and str(other.public_id) not in out.getvalue()


# ---- concurrency -------------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_writers_in_one_organisation_keep_one_chain() -> None:
    org = Organisation.objects.create(name="Busy Ltd.")
    errors: list[BaseException] = []

    def writer(n: int) -> None:
        try:
            for i in range(10):
                record(f"tests.thread{n}", organisation=org, changes={"i": [i, i + 1]})
        except BaseException as error:  # noqa: BLE001 — reported by the test
            errors.append(error)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=writer, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    (report,) = verify(str(org.public_id))
    assert report.ok and report.events == 80

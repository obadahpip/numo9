"""Internal job dashboard of the platform console — API (A-08-T08).

Acceptance (manual in the plan, automated here and in frontend/e2e/job-console.spec.ts): the
platform owner sees failures — queues, counts, every organisation's failed and dead runs with
their technical detail — and can retry or purge them; platform support may look, not act; an
organisation's people may do neither.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.test import Client
from django.utils import timezone

from numo9.accounts.models import User
from numo9.jobs import console
from numo9.jobs.models import JobRun, JobStatus
from numo9.jobs.queues import QUEUE_NAMES
from numo9.jobs.runtime import JOB_RUN_ID, platform_job, start_job
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.job_helpers import deliver

pytestmark = pytest.mark.django_db

BASE = "/api/v1/platform/jobs"


@platform_job(name="tests.console.sync_rates", label="Exchange rates", max_retries=0)
def sync_rates(*, account: str) -> None:
    raise ConnectionError(f"rates provider refused card 4111 1111 1111 1111 for {account}")


def _user(email: str) -> User:
    return User.objects.create_user(email=email, password="x" * 12, name=email.split("@")[0])


def _platform(role_key: str) -> Client:
    user = _user(f"{role_key}@numo9.ca")
    role = Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key=role_key)
    RoleAssignment.objects.create(role=role, user=user)
    client = Client()
    client.force_login(user)
    return client


def _run(key: str, status: str, org: Organisation | None = None, **fields: Any) -> JobRun:
    run: JobRun = JobRun.platform_runs.create(
        organisation=org, task_name="tests.console.x", idempotency_key=key, status=status, **fields
    )
    return run


@pytest.fixture
def no_broker() -> Any:
    with mock.patch.object(console, "queue_depths", return_value=dict.fromkeys(QUEUE_NAMES, 3)):
        yield


# ---- the platform owner sees failures ----------------------------------------------------------


def test_owner_sees_failures_with_their_detail(sent: list[dict[str, Any]]) -> None:
    owner = _platform("platform_owner")
    run = start_job(sync_rates, key="nightly", account="4111111111111111")
    with pytest.raises(ConnectionError):
        deliver(sync_rates, sent[0])
    listing = owner.get(BASE, {"status": "dead"}).json()
    assert listing["count"] == 1
    [row] = listing["results"]
    assert row["id"] == str(run.public_id)
    assert (row["label"], row["status"], row["queue"]) == ("Exchange rates", "dead", "default")
    assert row["error"]["code"] == "job.failed"
    assert row["error_detail"].startswith("builtins.ConnectionError: rates provider refused")
    assert "4111 1111 1111 1111" not in row["error_detail"]  # scrubbed
    assert row["payload"] == {"account": "[REDACTED]"}  # arguments scrubbed too
    assert row["organisation"] is None and row["created_by"] is None
    assert row["idempotency_key"] == "tests.console.sync_rates:platform:nightly"
    assert row["worker"] and row["celery_task_id"]
    assert owner.get(f"{BASE}/{run.public_id}").json()["id"] == str(run.public_id)


def test_overview_counts_queues_and_failures(no_broker: Any) -> None:
    owner = _platform("platform_owner")
    org = Organisation.objects.create(name="Maple Ltd.")
    _run("q", JobStatus.QUEUED, org, queue="reports")
    _run("r", JobStatus.RUNNING, org, queue="reports")
    _run("t", JobStatus.RETRYING, org, queue="io")
    now = timezone.now()
    _run("ok", JobStatus.SUCCEEDED, finished_at=now)
    _run("fail", JobStatus.FAILED, org, finished_at=now)
    _run("old-fail", JobStatus.FAILED, finished_at=now - timedelta(days=3))
    _run("dead-1", JobStatus.DEAD, finished_at=now - timedelta(days=3))
    _run("dead-2", JobStatus.DEAD, org, finished_at=now)
    body = owner.get(f"{BASE}/overview").json()
    assert body["counts"] == {
        "queued": 1,
        "running": 1,
        "retrying": 1,
        "succeeded_24h": 1,
        "failed_24h": 1,
        "dead": 2,
    }
    queues = {q["name"]: q for q in body["queues"]}
    assert list(queues) == ["high", "default", "io", "reports"]
    assert queues["reports"] == {
        "name": "reports",
        "waiting_messages": 3,
        "queued": 1,
        "running": 1,
        "retrying": 0,
    }
    assert queues["io"]["retrying"] == 1


def test_queue_depths_come_from_the_broker() -> None:
    from numo9.celery import app

    with app.connection_for_write() as connection:
        channel = connection.default_channel
        for queue in QUEUE_NAMES:
            channel.queue_declare(queue)  # as a worker does
        channel.queue_purge("io")
        connection.SimpleQueue("io").put({"x": 1})  # one message waiting on io
    try:
        depths = console.queue_depths()  # the in-memory broker of the tests
    finally:
        with app.connection_for_write() as connection:
            connection.default_channel.queue_purge("io")  # no stray message for later workers
    assert set(depths) == {"high", "default", "io", "reports"}
    assert depths["io"] == 1
    assert all(isinstance(n, int) for n in depths.values())
    with mock.patch("numo9.celery.app.connection_for_read", side_effect=OSError("down")):
        assert set(console.queue_depths().values()) == {None}  # the page still answers


def test_list_filters_and_search() -> None:
    owner = _platform("platform_owner")
    maple = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    other = Organisation.objects.create(name="Refined Interiors Inc.")
    a = _run("a", JobStatus.FAILED, maple, queue="io", error_code="job.not_queued")
    b = _run("b", JobStatus.DEAD, other, queue="reports")
    c = _run("c", JobStatus.SUCCEEDED)

    def ids(**params: Any) -> list[str]:
        return [r["id"] for r in owner.get(BASE, params).json()["results"]]

    assert ids() == [str(c.public_id), str(b.public_id), str(a.public_id)]
    assert ids(status="failed") == [str(a.public_id)]
    assert ids(queue="reports") == [str(b.public_id)]
    assert ids(organisation=str(maple.public_id)) == [str(a.public_id)]
    assert ids(q="refined") == [str(b.public_id)]
    assert ids(q="not_queued") == [str(a.public_id)]
    assert ids(q=str(b.public_id)[:8]) == [str(b.public_id)]  # the tray's short reference
    assert ids(type="tests.console.x", limit=1, offset=1) == [str(b.public_id)]
    bad = owner.get(BASE, {"organisation": "nope"})
    assert (bad.status_code, bad.json()["organisation"][0]) == (400, bad.json()["organisation"][0])
    assert owner.get(BASE, {"limit": "500"}).status_code == 200
    row = owner.get(BASE, {"status": "failed"}).json()["results"][0]
    assert row["organisation"] == {"id": str(maple.public_id), "name": "Maple Leaf Supply Ltd."}


# ---- retry and purge ---------------------------------------------------------------------------


def test_owner_retries_a_dead_run(sent: list[dict[str, Any]]) -> None:
    owner = _platform("platform_owner")
    run = start_job(sync_rates, key="again", account="x")
    with pytest.raises(ConnectionError):
        deliver(sync_rates, sent[0])
    response = owner.post(f"{BASE}/{run.public_id}/retry")
    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert sent[-1]["kwargs"][JOB_RUN_ID] == str(run.public_id)
    again = owner.post(f"{BASE}/{run.public_id}/retry")
    assert (again.status_code, again.json()["code"]) == (409, "job.not_retryable")
    assert owner.post(f"{BASE}/{uuid.uuid4()}/retry").status_code == 404


def test_purge_removes_dead_letters_only() -> None:
    owner = _platform("platform_owner")
    old = timezone.now() - timedelta(days=10)
    dead_old = _run("dead-old", JobStatus.DEAD, finished_at=old)
    dead_new = _run("dead-new", JobStatus.DEAD, finished_at=timezone.now())
    failed = _run("failed", JobStatus.FAILED, finished_at=old)
    done = _run("done", JobStatus.SUCCEEDED, finished_at=old)
    going = _run("going", JobStatus.RUNNING)

    def purge(body: dict[str, Any]) -> Any:
        return owner.post(f"{BASE}/purge", body, content_type="application/json")

    assert purge({"status": "dead", "older_than_days": 7}).json() == {"deleted": 1}
    assert not JobRun.platform_runs.filter(pk=dead_old.pk).exists()
    # Chosen runs: only failed / dead ones go, whatever else is listed.
    ids = [str(r.public_id) for r in (dead_new, done, going)]
    assert purge({"ids": ids}).json() == {"deleted": 1}
    left = set(JobRun.platform_runs.values_list("idempotency_key", flat=True))
    assert left == {"failed", "done", "going"}
    refused = purge({})
    assert (refused.status_code, refused.json()["code"]) == (400, "job.purge_filter")
    assert purge({"status": "succeeded"}).status_code == 400
    assert failed.pk in JobRun.platform_runs.values_list("pk", flat=True)


# ---- who may look and act ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/overview"),
        ("get", ""),
        ("get", "/{id}"),
        ("post", "/{id}/retry"),
        ("post", "/purge"),
    ],
)
def test_support_may_look_but_not_act(no_broker: Any, method: str, path: str) -> None:
    run = _run("x", JobStatus.DEAD, finished_at=timezone.now())
    support = _platform("platform_support")
    response = getattr(support, method)(
        BASE + path.format(id=run.public_id),
        {"status": "dead"} if method == "post" else None,
        content_type="application/json",
    )
    if method == "get":
        assert response.status_code == 200
    else:
        assert (response.status_code, response.json()["code"]) == (403, "permission.denied")


def test_organisation_people_and_visitors_are_refused(no_broker: Any) -> None:
    org = Organisation.objects.create(name="Maple Ltd.")
    owner = _user("owner@maple.ca")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    client = Client()
    client.force_login(owner)
    for path in ("/overview", ""):
        response = client.get(BASE + path)
        assert (response.status_code, response.json()["code"]) == (403, "permission.denied")
        assert Client().get(BASE + path).status_code in {401, 403}

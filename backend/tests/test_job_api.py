"""Job progress API + Server-Sent Events for the job tray (A-08-T06).

Acceptance: progress updates — a job's progress written by the running job reaches the person who
started it through the list, the detail and the event stream.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import timedelta
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.utils import timezone

from numo9.accounts.models import User
from numo9.jobs.models import JobRun, JobStatus
from numo9.jobs.runtime import JOB_RUN_ID, org_job, report_progress, start_job
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.job_helpers import deliver

pytestmark = pytest.mark.django_db


@org_job(name="tests.api.import_rows", label="Import contacts", max_retries=0)
def import_rows(*, org_id: str, rows: int, fail: bool = False) -> dict[str, int]:
    for done in range(1, rows + 1):
        report_progress(done, rows, f"Row {done} of {rows}")
    if fail:
        raise RuntimeError("bad row 3")
    return {"rows": rows}


def _user(name: str = "Dana Lee", locale: str = "en-ca") -> User:
    email = f"{name.split()[0].lower()}@{name.split()[1].lower()}.ca"
    return User.objects.create_user(email=email, password="x" * 12, name=name, locale=locale)


def _setup() -> tuple[Organisation, User, Client]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    user = _user()
    OrganisationMember.objects.create(organisation=org, user=user, role="employee")
    client = Client()
    client.force_login(user)
    return org, user, client


def _url(org: Organisation, tail: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/jobs{tail}"


def _run(org: Organisation, user: User | None, key: str, **fields: Any) -> JobRun:
    run: JobRun = JobRun.platform_runs.create(
        organisation=org,
        task_name=import_rows.name,
        idempotency_key=key,
        created_by=user,
        **fields,
    )
    return run


# ---- list and detail ---------------------------------------------------------------------------


def test_list_shows_my_jobs_with_progress(sent: list[dict[str, Any]]) -> None:
    org, user, client = _setup()
    run = start_job(import_rows, organisation=org, created_by=user, rows=4)
    JobRun.platform_runs.filter(pk=run.pk).update(
        status=JobStatus.RUNNING, progress_done=1, progress_total=4, progress_message="Row 1 of 4"
    )
    response = client.get(_url(org))
    assert response.status_code == 200
    [job] = response.json()
    assert job["id"] == str(run.public_id)
    assert (job["type"], job["label"]) == ("tests.api.import_rows", "Import contacts")
    assert (job["status"], job["status_label"]) == ("running", "Running")
    assert job["progress"] == {"done": 1, "total": 4, "percent": 25, "message": "Row 1 of 4"}
    assert job["error"] is None and job["can_retry"] is False
    assert "payload" not in job and "error_detail" not in job  # never shown in the tray


def test_progress_updates_reach_the_tray(sent: list[dict[str, Any]]) -> None:
    org, user, client = _setup()
    run = start_job(import_rows, organisation=org, created_by=user, rows=3)
    assert client.get(_url(org, f"/{run.public_id}")).json()["progress"]["percent"] is None
    deliver(import_rows, sent[0])
    job = client.get(_url(org, f"/{run.public_id}")).json()
    assert job["status"] == "succeeded"
    assert job["progress"] == {"done": 3, "total": 3, "percent": 100, "message": "Row 3 of 3"}
    assert job["finished_at"] is not None


def test_failed_job_shows_its_error_and_can_be_retried(sent: list[dict[str, Any]]) -> None:
    org, user, client = _setup()
    run = start_job(import_rows, organisation=org, created_by=user, rows=3, fail=True)
    with pytest.raises(RuntimeError):
        deliver(import_rows, sent[0])
    job = client.get(_url(org, f"/{run.public_id}")).json()
    assert job["status"] == "dead"
    assert job["status_label"] == "Failed after several tries"
    assert job["error"]["code"] == "job.failed"
    assert job["error"]["message"].startswith("Something went wrong")
    assert job["can_retry"] is True
    response = client.post(_url(org, f"/{run.public_id}/retry"))
    assert response.status_code == 202
    assert response.json()["status"] == "queued" and response.json()["error"] is None
    assert len(sent) == 2 and sent[1]["kwargs"][JOB_RUN_ID] == str(run.public_id)
    again = client.post(_url(org, f"/{run.public_id}/retry"))
    assert (again.status_code, again.json()["code"]) == (409, "job.not_retryable")


def test_only_my_jobs_in_this_organisation() -> None:
    org, user, client = _setup()
    colleague = _user("Sam Patel")
    OrganisationMember.objects.create(organisation=org, user=colleague, role="employee")
    other_org = Organisation.objects.create(name="Other Ltd.")
    OrganisationMember.objects.create(organisation=other_org, user=user, role="owner")
    mine = _run(org, user, "mine")
    theirs = _run(org, colleague, "theirs")
    elsewhere = _run(other_org, user, "elsewhere")
    platform = JobRun.platform_runs.create(task_name="x", idempotency_key="platform")
    assert [j["id"] for j in client.get(_url(org)).json()] == [str(mine.public_id)]
    for run in (theirs, elsewhere, platform):
        assert client.get(_url(org, f"/{run.public_id}")).status_code == 404
        assert client.post(_url(org, f"/{run.public_id}/retry")).status_code == 404
    assert client.get(_url(other_org)).json()[0]["id"] == str(elsewhere.public_id)


def test_recent_window_and_active_filter() -> None:
    org, user, client = _setup()
    old = timezone.now() - timedelta(days=2)
    still_going = _run(org, user, "going", status=JobStatus.RETRYING)
    old_done = _run(org, user, "old", status=JobStatus.SUCCEEDED)
    recent = _run(org, user, "recent", status=JobStatus.FAILED)
    JobRun.platform_runs.filter(pk__in=[still_going.pk, old_done.pk]).update(created_at=old)
    ids = [j["id"] for j in client.get(_url(org)).json()]
    assert ids == [str(recent.public_id), str(still_going.public_id)]  # old finished one gone
    active = [j["id"] for j in client.get(_url(org) + "?active=1").json()]
    assert active == [str(still_going.public_id)]
    # An old job is still reachable by its id (a link from an email).
    assert client.get(_url(org, f"/{old_done.public_id}")).status_code == 200


def test_recent_finished_jobs_are_capped() -> None:
    org, user, client = _setup()
    for i in range(25):
        _run(org, user, f"done-{i}", status=JobStatus.SUCCEEDED)
    _run(org, user, "going", status=JobStatus.RUNNING)
    jobs = client.get(_url(org)).json()
    assert len(jobs) == 21  # every job still going + the last 20 finished
    assert sum(j["status"] == "running" for j in jobs) == 1


def test_polling_with_etag_answers_304_until_something_changes() -> None:
    org, user, client = _setup()
    run = _run(org, user, "etag", status=JobStatus.RUNNING)
    first = client.get(_url(org))
    tag = first["ETag"]
    assert client.get(_url(org), HTTP_IF_NONE_MATCH=tag).status_code == 304
    JobRun.platform_runs.filter(pk=run.pk).update(progress_done=1, progress_total=2)
    changed = client.get(_url(org), HTTP_IF_NONE_MATCH=tag)
    assert changed.status_code == 200 and changed["ETag"] != tag


def test_signed_out_and_strangers_are_refused() -> None:
    org, user, _ = _setup()
    run = _run(org, user, "x")
    assert Client().get(_url(org)).status_code in {401, 403}
    stranger = Client()
    stranger.force_login(_user("Lee Stranger"))
    assert stranger.get(_url(org)).status_code == 404
    assert stranger.get(_url(org, f"/{run.public_id}")).status_code == 404
    assert stranger.get(_url(org, "/events")).status_code == 404


def test_error_message_is_in_the_starters_language(sent: list[dict[str, Any]]) -> None:
    org, _, _ = _setup()
    francophone = _user("Luc Tremblay", locale="fr-ca")
    OrganisationMember.objects.create(organisation=org, user=francophone, role="employee")
    run = start_job(import_rows, organisation=org, created_by=francophone, rows=1, fail=True)
    with pytest.raises(RuntimeError):
        deliver(import_rows, sent[0])
    client = Client()
    client.force_login(francophone)
    job = client.get(_url(org, f"/{run.public_id}"), HTTP_ACCEPT_LANGUAGE="fr-CA").json()
    assert job["error"]["message"].startswith("Une erreur")
    assert job["status_label"] == "Échec après plusieurs essais"


# ---- Server-Sent Events ------------------------------------------------------------------------


def _events(body: bytes) -> list[dict[str, Any]]:
    events = []
    for block in body.decode().split("\n\n"):
        fields: dict[str, Any] = {}
        for line in block.splitlines():
            key, _, value = line.partition(": ")
            fields[key] = value
        if "event" in fields:
            fields["data"] = json.loads(fields["data"])
            events.append(fields)
    return events


def test_event_stream_ends_at_once_when_nothing_is_going() -> None:
    org, user, client = _setup()
    _run(org, user, "done", status=JobStatus.SUCCEEDED)
    response = client.get(_url(org, "/events"), HTTP_ACCEPT="text/event-stream")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/event-stream")
    assert response["Cache-Control"] == "no-cache"
    body = b"".join(response.streaming_content)  # type: ignore[attr-defined]
    assert body.startswith(b"retry: 2000\n\n")
    events = _events(body)
    assert [e["event"] for e in events] == ["jobs", "idle"]
    assert events[0]["data"][0]["status"] == "succeeded"
    assert events[0]["id"].startswith('"')


@pytest.mark.django_db(transaction=True)  # another thread's connection writes the progress
def test_event_stream_sends_progress_as_it_changes() -> None:
    org, user, client = _setup()
    run = _run(org, user, "live", status=JobStatus.RUNNING, progress_total=3)

    def work() -> None:  # another worker reporting progress, then finishing
        for done in (1, 2, 3):
            time.sleep(0.08)
            JobRun.platform_runs.filter(pk=run.pk).update(progress_done=done)
        time.sleep(0.08)
        JobRun.platform_runs.filter(pk=run.pk).update(status=JobStatus.SUCCEEDED)
        connection.close()  # this thread's own connection

    response = client.get(_url(org, "/events"), HTTP_ACCEPT="text/event-stream")
    worker = threading.Thread(target=work)
    worker.start()
    body = b"".join(response.streaming_content)  # type: ignore[attr-defined]
    worker.join()
    jobs = [e for e in _events(body) if e["event"] == "jobs"]
    seen = [e["data"][0]["progress"]["done"] for e in jobs]
    assert seen == sorted(seen) and seen[0] == 0 and seen[-1] == 3
    assert len(seen) >= 3  # progress arrived while the job ran, not only at the end
    assert jobs[-1]["data"][0]["status"] == "succeeded"
    assert _events(body)[-1]["event"] == "idle"


def test_event_stream_stops_after_its_time_and_skips_a_known_list() -> None:
    org, user, client = _setup()
    _run(org, user, "stuck", status=JobStatus.RUNNING)
    first = client.get(_url(org, "/events"))
    started = time.monotonic()
    body = b"".join(first.streaming_content)  # type: ignore[attr-defined]
    assert 0.9 <= time.monotonic() - started < 5  # JOBS_SSE_MAX_SECONDS = 1 in tests
    events = _events(body)
    assert [e["event"] for e in events] == ["jobs"]  # one list; unchanged since
    reconnect = client.get(_url(org, "/events"), HTTP_LAST_EVENT_ID=events[0]["id"])
    again = b"".join(reconnect.streaming_content)  # type: ignore[attr-defined]
    assert _events(again) == []  # nothing new to send


def test_openapi_documents_the_job_endpoints() -> None:
    from drf_spectacular.generators import SchemaGenerator

    generator = SchemaGenerator()  # type: ignore[no-untyped-call]
    schema = generator.get_schema(request=None, public=True)  # type: ignore[no-untyped-call]
    paths = schema["paths"]
    assert "/api/v1/o/{org}/jobs" in paths
    assert (
        "text/event-stream"
        in (paths["/api/v1/o/{org}/jobs/events"]["get"]["responses"]["200"]["content"])
    )

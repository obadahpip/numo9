"""V-03-T07 — bulk API: create preview, confirm, cancel, status (polling), results CSV.

Contract tests: the shapes of each answer, the status codes, who may do what.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest
from django.test import Client

from numo9.bulk import service
from numo9.bulk.models import BulkJob
from numo9.workspace.tags import create_tag
from tests.bulk_helpers import bulk_world
from tests.job_helpers import deliver
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db
API = "/api/v1/practice/bulk"


@pytest.fixture
def world() -> dict[str, Any]:
    world = bulk_world(3)
    world["tag"] = create_tag(world["practice"], "Retail")
    return world


def create(world: dict[str, Any], browser: Client | None = None, **body: Any) -> Any:
    payload = {
        "practice": str(world["practice"].public_id),
        "action": "tags",
        "params": {"add": [str(world["tag"].public_id)]},
        "selection": {"ids": [str(org.public_id) for org in world["orgs"]]},
        **body,
    }
    return (browser or world["browser"]).post(API, payload, content_type="application/json")


def test_create_preview_contract(world: dict[str, Any]) -> None:
    response = create(world)
    assert response.status_code == 201, response.content
    body = response.json()
    assert set(body) == {"job", "preview"}
    job = body["job"]
    assert job["status"] == "preview" and job["total"] == 3 and job["done"] == 0
    assert job["action"] == "tags" and job["action_label"] == "Add or remove tags"
    assert set(job["counts"]) == {"pending", "succeeded", "skipped", "failed", "cancelled"}
    assert body["preview"]["counts"] == {"change": 3, "no_change": 0, "skipped": 0}
    line = body["preview"]["lines"][0]
    assert set(line) == {"organisation", "status", "reason", "message", "before", "after"}
    assert line["after"] == {"tags": ["Retail"]}


def test_confirm_status_rows_and_csv(world: dict[str, Any], sent: list[dict[str, Any]]) -> None:
    job_id = create(world).json()["job"]["id"]
    browser = world["browser"]
    confirmed = browser.post(f"{API}/{job_id}/confirm")
    assert confirmed.status_code == 202 and confirmed.json()["status"] == "queued"
    assert confirmed.json()["counts"]["pending"] == 3
    deliver(service.run_bulk_job, sent[0])
    status = browser.get(f"{API}/{job_id}").json()
    assert (status["status"], status["done"], status["percent"]) == ("completed", 3, 100)
    assert status["counts"]["succeeded"] == 3
    rows = browser.get(f"{API}/{job_id}/rows?outcome=succeeded").json()
    assert rows["count"] == 3 and rows["results"][0]["outcome"] == "succeeded"
    assert browser.get(f"{API}/{job_id}/rows?outcome=failed").json()["count"] == 0
    assert browser.get(f"{API}/{job_id}/rows?outcome=nope").status_code == 400
    csv_response = browser.get(f"{API}/{job_id}/results.csv")
    assert csv_response.status_code == 200 and csv_response["Content-Type"].startswith("text/csv")
    lines = list(csv.reader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
    assert len(lines) == 4
    assert browser.post(f"{API}/{job_id}/confirm").status_code == 409


def test_cancel_before_confirm(world: dict[str, Any]) -> None:
    job_id = create(world).json()["job"]["id"]
    cancelled = world["browser"].post(f"{API}/{job_id}/cancel").json()
    assert cancelled["status"] == "cancelled" and cancelled["cancel_requested"] is True
    assert world["browser"].post(f"{API}/{job_id}/confirm").status_code == 409


def test_export_download(world: dict[str, Any], sent: list[dict[str, Any]]) -> None:
    job_id = create(world, action="export", params={"format": "csv"}).json()["job"]["id"]
    browser = world["browser"]
    assert browser.get(f"{API}/{job_id}/export").status_code == 404  # not run yet
    browser.post(f"{API}/{job_id}/confirm")
    deliver(service.run_bulk_job, sent[0])
    assert browser.get(f"{API}/{job_id}").json()["export_ready"] is True
    response = browser.get(f"{API}/{job_id}/export")
    assert response.status_code == 200 and b"Client 000" in response.content


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"selection": {"ids": []}}, "bulk.empty_selection"),
        ({"params": {"add": ["nope"]}}, "bulk.bad_action"),
        ({"action": "settings", "params": {"settings": {"legal_name": {}}}}, "bulk.unsafe_setting"),
    ],
)
def test_refusals(world: dict[str, Any], body: dict[str, Any], code: str) -> None:
    response = create(world, **body)
    assert response.status_code == 400 and response.json()["code"] == code
    assert not BulkJob.objects.exists()


def test_who_may_do_what(world: dict[str, Any]) -> None:
    accountant = Client()
    accountant.force_login(world["accountant_user"])
    refused = create(world, browser=accountant)  # tags need practice.groups.manage
    assert refused.status_code == 403 and refused.json()["code"] == "permission.denied"
    job_id = create(world).json()["job"]["id"]
    assert accountant.get(f"{API}/{job_id}").status_code == 200  # the practice's job, readable
    assert accountant.post(f"{API}/{job_id}/confirm").status_code == 403  # not theirs
    outsider = Client()
    outsider.force_login(user("someone@else.ca"))
    assert outsider.get(f"{API}/{job_id}").status_code == 404

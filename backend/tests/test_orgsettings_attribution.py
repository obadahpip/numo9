"""A-05-T14 — audit attribution of organisation settings: a system-initiated change shows
``System: <job>`` (gap-44).

Xero's financial settings history read "Edited by System Generated on 5 Jan 2026 at 16:33PM — GST
Type – removed": a tax registration changed by the system, with no job named and a 24-hour time
with "PM". Here a background job closes a GST/HST registration, sets the Tax lock and changes the
settings; every change is an audit event attributed to ``System: <job label>`` (with the job and
the person who started it), the audit log API and its record history show that label, the CSV
export prints it with a real 12-hour or 24-hour time, and the same change by a person names the
person. Nothing changes silently.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import re
from typing import Any

import pytest
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.audit.context import audit_context
from numo9.audit.models import ActorKind, AuditEvent
from numo9.jobs.runtime import org_job, start_job
from numo9.orgsettings.models import (
    LockDate,
    LockLevel,
    LockModule,
    RegistrationStatus,
    RegistrationType,
    TaxRegistration,
)
from numo9.orgsettings.service import get_settings
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.job_helpers import deliver

pytestmark = [pytest.mark.django_db, pytest.mark.gap("gap-44")]

BN = "123456782"
RT = f"{BN}RT0001"
JOB_LABEL = "Close GST/HST registration"
SYSTEM = f"System: {JOB_LABEL}"
#: "16:33PM" — a 24-hour time with an a.m./p.m. suffix (the Xero bug).
MIXED_TIME = re.compile(r"\b(1[3-9]|2[0-3]):[0-5]\d\s?(AM|PM|a\.m\.|p\.m\.)", re.IGNORECASE)


@org_job(name="tests.orgsettings.close_gst_registration", label=JOB_LABEL, max_retries=0)
def close_gst_registration(*, org_id: str, number: str, ended_on: str) -> dict[str, str]:
    """What a CRA-sync job would do: end the RT account, lock the Tax module, note the change."""
    ended = dt.date.fromisoformat(ended_on)
    registration = TaxRegistration.objects.get(type=RegistrationType.RT, number=number)
    registration.status = RegistrationStatus.CLOSED
    registration.effective_to = ended
    registration.save()
    lock = LockDate(module=LockModule.TAX, level=LockLevel.EVERYONE, organisation_id=org_id)
    lock.organisation = registration.organisation
    lock.set_lock(ended, "GST/HST account closed")
    lock.save()
    settings = get_settings()
    settings.industry = "Bakery (GST/HST closed)"
    settings.save()
    return {"closed": registration.display_number}


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture
def owner(org: Organisation) -> User:
    user = User.objects.create_user("avery@maple.ca", password="x" * 12, name="Avery Owner")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    return user


def as_person(user: User) -> Any:
    return audit_context(kind=ActorKind.USER, user=user, label="Avery Owner (avery@maple.ca)")


@pytest.fixture
def registration(org: Organisation, owner: User) -> TaxRegistration:
    """The owner set up the organisation and registered its BN and GST/HST account."""
    with org_context(org), as_person(owner):
        get_settings()
        TaxRegistration(organisation=org, type=RegistrationType.BN, number=BN).save()
        rt = TaxRegistration(organisation=org, type=RegistrationType.RT, number=RT)
        rt.save()
    return rt


def run_job(org: Organisation, owner: User, sent: list[dict[str, Any]]) -> Any:
    run = start_job(
        close_gst_registration,
        organisation=org,
        created_by=owner,
        number=RT,
        ended_on="2026-06-30",
    )
    assert deliver(close_gst_registration, sent[-1]) == {"closed": "123456782 RT 0001"}
    return run


def events(org: Organisation, **filters: Any) -> list[AuditEvent]:
    with org_context(org):
        return list(AuditEvent.objects.filter(**filters).order_by("id"))


def csv_text(response: Any) -> str:
    return b"".join(response.streaming_content).decode("utf-8").lstrip("\ufeff")


def api(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client


# ---- acceptance: System: <job> -------------------------------------------------------------------


def test_every_change_by_the_job_is_attributed_to_the_job(
    org: Organisation, owner: User, registration: TaxRegistration, sent: list[dict[str, Any]]
) -> None:
    run = run_job(org, owner, sent)
    changed = events(org, actor_kind=ActorKind.SYSTEM)
    assert [e.action for e in changed] == [
        "orgsettings.taxregistration.updated",
        "orgsettings.lockdate.created",
        "orgsettings.organisationsettings.updated",
    ]
    for event in changed:
        assert event.actor_label == SYSTEM
        assert event.actor_user is None
        assert event.meta["job"]["id"] == str(run.public_id)
        assert event.meta["job"]["task"] == "tests.orgsettings.close_gst_registration"
        assert event.meta["job"]["started_by"]["label"] == "Avery Owner (avery@maple.ca)"
    status_change = changed[0]
    assert status_change.object_label == "GST/HST program account (RT) 123456782 RT 0001"
    assert status_change.changes == {
        "effective_to": [None, "2026-06-30"],
        "status": ["active", "closed"],
    }
    assert changed[1].changes["reason"] == [None, "GST/HST account closed"]


def test_no_change_is_silent(
    org: Organisation, owner: User, registration: TaxRegistration, sent: list[dict[str, Any]]
) -> None:
    before = len(events(org))
    run_job(org, owner, sent)
    assert len(events(org)) - before == 3  # three records changed → three events
    assert all(e.actor_label for e in events(org))
    assert not any(e.actor_label in ("System", "System Generated") for e in events(org))


def test_the_audit_log_shows_the_job_as_the_author(
    org: Organisation, owner: User, registration: TaxRegistration, sent: list[dict[str, Any]]
) -> None:
    run_job(org, owner, sent)
    base = f"/api/v1/o/{org.public_id}/audit"
    rows = api(owner).get(f"{base}/events", {"user": "system"}).json()["results"]
    assert {row["actor"]["label"] for row in rows} == {SYSTEM}
    assert {row["actor"]["kind"] for row in rows} == {"system"}
    history = (
        api(owner)
        .get(f"{base}/records/orgsettings.TaxRegistration/{registration.public_id}")
        .json()["results"]
    )
    assert [(row["action"], row["actor"]["label"]) for row in history] == [
        ("orgsettings.taxregistration.updated", SYSTEM),
        ("orgsettings.taxregistration.created", "Avery Owner (avery@maple.ca)"),
    ]


@pytest.mark.parametrize("time_format", ["12h", "24h"])
def test_the_export_names_the_job_with_a_correct_time(
    org: Organisation,
    owner: User,
    registration: TaxRegistration,
    sent: list[dict[str, Any]],
    time_format: str,
) -> None:
    owner.time_format = time_format
    owner.save()
    run_job(org, owner, sent)
    response = api(owner).get(f"/api/v1/o/{org.public_id}/audit/export/csv", {"user": "system"})
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(csv_text(response))))
    assert rows and {row["User"] for row in rows} == {SYSTEM}
    for row in rows:
        assert not MIXED_TIME.search(row["Date and time"]), row["Date and time"]
        has_suffix = bool(re.search(r"(a\.m\.|p\.m\.|AM|PM)", row["Date and time"]))
        assert has_suffix is (time_format == "12h"), row["Date and time"]


def test_the_same_change_by_a_person_names_the_person(
    org: Organisation, owner: User, registration: TaxRegistration
) -> None:
    with org_context(org), as_person(owner):
        registration.status = RegistrationStatus.CLOSED
        registration.save()
    (event,) = events(org, action="orgsettings.taxregistration.updated")
    assert event.actor_kind == ActorKind.USER and event.actor_user == owner
    assert event.actor_label == "Avery Owner (avery@maple.ca)"

"""B-01-T08 — exemption certificates on contacts and their expiry reminder hook.

Acceptance: an expired certificate is flagged. Also: number required and unique per contact
(case-insensitive, a removed certificate frees its number); expiry never before issue; the file is
a document of the organisation (A-06), never a quarantined or deleted one; ``expiring`` within 30
days; dates in the organisation's time zone; the daily job calls the hook once per reminder (30
days before, once expired), again after a renewal, never for removed certificates or other
states; every change is audited.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import override_settings

from numo9.audit.models import AuditEvent
from numo9.contacts import exemptions
from numo9.contacts.models import (
    EXEMPTION_REMINDER_DAYS,
    Contact,
    ExemptionCertificate,
    ExemptionState,
    organisation_today,
)
from numo9.contacts.tasks import EXEMPTION_REMINDERS, exemption_reminders
from numo9.files.models import Document, DocumentStatus
from numo9.tenancy.context import current_org, org_context
from numo9.tenancy.models import Organisation
from tests.contact_helpers import contact
from tests.job_helpers import deliver

pytestmark = pytest.mark.django_db

TODAY = date(2026, 11, 15)
#: 15 November 2026, 12:00 UTC (07:00 in Toronto).
NOON = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def maple(org: Organisation) -> Contact:
    return contact(org, "Maple Supply Ltd.")


def document(org: Organisation, name: str = "certificate.pdf", **fields: Any) -> Document:
    item = Document(organisation=org, name=name, file_key=f"org/{org.public_id}/x/{name}", **fields)
    item.save()
    return item


def certificate(holder: Contact, number: str = "PST-123456", **fields: Any) -> ExemptionCertificate:
    item = ExemptionCertificate(contact=holder, number=number, **fields)
    item.save()
    return item


def codes(excinfo: pytest.ExceptionInfo[ValidationError]) -> dict[str, list[str]]:
    return {f: [e.code or "" for e in errs] for f, errs in excinfo.value.error_dict.items()}


# ---- model -------------------------------------------------------------------------------------


def test_certificate_with_file_number_and_expiry(org: Organisation, maple: Contact) -> None:
    scan = document(org)
    item = certificate(
        maple,
        number="  PST  123456 ",
        document=scan,
        issued_on=date(2026, 1, 1),
        expires_on=date(2027, 12, 31),
        notes="Reseller  exemption",
    )
    item.refresh_from_db()
    assert item.organisation_id == org.pk  # from the contact
    assert item.number == "PST 123456"
    assert item.notes == "Reseller exemption"
    assert item.document == scan
    assert list(maple.exemption_certificates.all()) == [item]
    assert item.state(TODAY) == ExemptionState.VALID
    assert item.days_left(TODAY) == (date(2027, 12, 31) - TODAY).days


@pytest.mark.parametrize(
    ("expires_on", "state"),
    [
        (None, ExemptionState.VALID),  # no expiry date
        (TODAY + timedelta(days=EXEMPTION_REMINDER_DAYS + 1), ExemptionState.VALID),
        (TODAY + timedelta(days=EXEMPTION_REMINDER_DAYS), ExemptionState.EXPIRING),
        (TODAY, ExemptionState.EXPIRING),  # still valid on its expiry date
        (TODAY - timedelta(days=1), ExemptionState.EXPIRED),
        (date(2020, 1, 1), ExemptionState.EXPIRED),
    ],
)
def test_state_flags_an_expired_certificate(
    maple: Contact, expires_on: date | None, state: str
) -> None:
    item = certificate(maple, expires_on=expires_on)
    assert item.state(TODAY) == state
    assert item.is_expired(TODAY) is (state == ExemptionState.EXPIRED)


def test_today_is_the_organisations_day(org: Organisation, maple: Contact) -> None:
    item = certificate(maple, expires_on=date(2026, 11, 14))
    # 15 Nov 03:00 UTC is still 14 Nov in Toronto (UTC-5): the certificate hasn't expired there.
    late_evening = datetime(2026, 11, 15, 3, 0, tzinfo=UTC)
    assert organisation_today(org, now=late_evening) == date(2026, 11, 14)
    with mock.patch("django.utils.timezone.now", return_value=late_evening):
        assert item.state() == ExemptionState.EXPIRING
        item.organisation.time_zone = "Europe/Helsinki"  # UTC+2: already 15 Nov
        assert item.state() == ExemptionState.EXPIRED


def test_number_is_required(maple: Contact) -> None:
    with pytest.raises(ValidationError) as excinfo:
        certificate(maple, number="   ")
    assert codes(excinfo) == {"number": ["contacts.exemption.number_required"]}


def test_number_is_unique_per_contact(org: Organisation, maple: Contact) -> None:
    first = certificate(maple, number="QST-1")
    with pytest.raises(ValidationError) as excinfo:
        certificate(maple, number="qst-1")
    assert codes(excinfo) == {"number": ["contacts.exemption.number_taken"]}
    # another contact may hold the same number
    certificate(contact(org, "Birch Ltd."), number="QST-1")
    # a removed certificate frees its number
    first.soft_delete()
    certificate(maple, number="QST-1")


def test_database_refuses_a_duplicate_number(maple: Contact) -> None:
    certificate(maple, number="QST-1")
    with pytest.raises(IntegrityError), transaction.atomic():
        ExemptionCertificate._base_manager.bulk_create(
            [ExemptionCertificate(organisation=maple.organisation, contact=maple, number="QST-1")]
        )


def test_expiry_never_before_issue(maple: Contact) -> None:
    with pytest.raises(ValidationError) as excinfo:
        certificate(maple, issued_on=date(2026, 6, 1), expires_on=date(2026, 5, 31))
    assert codes(excinfo) == {"expires_on": ["contacts.exemption.expiry_before_issue"]}
    certificate(maple, issued_on=date(2026, 6, 1), expires_on=date(2026, 6, 1))  # same day ok


def test_database_refuses_expiry_before_issue(maple: Contact) -> None:
    row = ExemptionCertificate(
        organisation=maple.organisation,
        contact=maple,
        number="X",
        issued_on=date(2026, 6, 1),
        expires_on=date(2026, 5, 1),
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        ExemptionCertificate._base_manager.bulk_create([row])


def test_file_must_be_a_clean_document_of_the_organisation(
    org: Organisation, maple: Contact
) -> None:
    other = Organisation.objects.create(name="Other Org")
    with org_context(other):
        foreign = document(other, "foreign.pdf")
    with pytest.raises(ValidationError) as excinfo:
        certificate(maple, document=foreign)
    assert codes(excinfo) == {"document": ["contacts.exemption.document"]}

    infected = document(org, "infected.pdf", status=DocumentStatus.INFECTED)
    with pytest.raises(ValidationError) as excinfo:
        certificate(maple, document=infected)
    assert codes(excinfo) == {"document": ["contacts.exemption.document_quarantined"]}

    removed = document(org, "removed.pdf")
    removed.soft_delete()
    with pytest.raises(ValidationError) as excinfo:
        certificate(maple, document=removed)
    assert codes(excinfo) == {"document": ["contacts.exemption.document_deleted"]}


def test_contact_must_belong_to_the_organisation(org: Organisation, maple: Contact) -> None:
    other = Organisation.objects.create(name="Other Org")
    with pytest.raises(ValidationError) as excinfo:
        ExemptionCertificate(organisation=other, contact=maple, number="A1").save()
    assert codes(excinfo) == {"contact": ["contacts.exemption.contact"]}


def test_a_document_with_a_certificate_cannot_be_hard_deleted(
    org: Organisation, maple: Contact
) -> None:
    from django.db.models import ProtectedError

    scan = document(org)
    certificate(maple, document=scan)
    with pytest.raises(ProtectedError):
        Document._base_manager.filter(pk=scan.pk).delete()


def test_scoped_to_the_active_organisation(org: Organisation, maple: Contact) -> None:
    certificate(maple)
    other = Organisation.objects.create(name="Other Org")
    with org_context(other):
        assert not ExemptionCertificate.objects.exists()
    assert ExemptionCertificate.objects.count() == 1


def test_changes_are_audited(maple: Contact) -> None:
    item = certificate(maple, number="PST-1", expires_on=date(2027, 1, 31))
    item.expires_on = date(2028, 1, 31)
    item.save()
    events = list(
        AuditEvent.objects.filter(object_type="contacts.ExemptionCertificate").order_by("id")
    )
    assert [e.action for e in events] == [
        "contacts.exemptioncertificate.created",
        "contacts.exemptioncertificate.updated",
    ]
    assert events[1].object_id == str(item.public_id)
    assert events[1].changes == {"expires_on": ["2027-01-31", "2028-01-31"]}


# ---- expiry reminder hook ----------------------------------------------------------------------


@pytest.fixture
def hook() -> Iterator[list[tuple[str, str, int, Any]]]:
    calls: list[tuple[str, str, int, Any]] = []

    def record(item: ExemptionCertificate, state: str, days_left: int) -> None:
        calls.append((item.number, state, days_left, current_org()))

    with mock.patch.object(exemptions, "get_hook", return_value=record):
        yield calls


def test_reminders_30_days_before_and_once_expired(
    org: Organisation, maple: Contact, hook: list[tuple[str, str, int, Any]]
) -> None:
    soon = certificate(maple, number="SOON", expires_on=TODAY + timedelta(days=30))
    certificate(maple, number="LATER", expires_on=TODAY + timedelta(days=31))
    certificate(maple, number="NEVER")  # no expiry date
    certificate(maple, number="GONE", expires_on=TODAY - timedelta(days=2))

    assert exemptions.send_reminders(NOON) == {"expiring": 1, "expired": 1}
    assert sorted(hook) == [("GONE", "expired", -2, org), ("SOON", "expiring", 30, org)]

    # same day again: nothing new
    hook.clear()
    assert exemptions.send_reminders(NOON) == {"expiring": 0, "expired": 0}
    assert hook == []

    # 31 days later SOON has expired: its second reminder
    assert exemptions.send_reminders(NOON + timedelta(days=31)) == {"expiring": 1, "expired": 1}
    assert sorted(hook) == [("LATER", "expiring", 0, org), ("SOON", "expired", -1, org)]
    soon.refresh_from_db()
    assert (soon.reminded_state, soon.reminded_for) == ("expired", soon.expires_on)


def test_renewal_starts_the_reminders_again(
    maple: Contact, hook: list[tuple[str, str, int, Any]]
) -> None:
    item = certificate(maple, number="PST-1", expires_on=TODAY - timedelta(days=1))
    exemptions.send_reminders(NOON)
    item.refresh_from_db()
    assert item.reminded_state == "expired"

    item.expires_on = TODAY + timedelta(days=10)  # renewed
    item.save(update_fields=["expires_on", "updated_at"])
    item.refresh_from_db()
    assert (item.reminded_state, item.reminded_for) == ("", None)
    hook.clear()
    exemptions.send_reminders(NOON)
    assert [(n, s) for n, s, *_ in hook] == [("PST-1", "expiring")]


def test_no_reminder_for_removed_certificates_or_contacts(
    org: Organisation, maple: Contact, hook: list[tuple[str, str, int, Any]]
) -> None:
    certificate(maple, number="A", expires_on=TODAY).soft_delete()
    gone = contact(org, "Gone Ltd.")
    certificate(gone, number="B", expires_on=TODAY)
    gone.soft_delete()
    assert exemptions.send_reminders(NOON) == {"expiring": 0, "expired": 0}
    assert hook == []


def test_reminders_cover_every_organisation_in_its_own_context(
    org: Organisation, maple: Contact, hook: list[tuple[str, str, int, Any]]
) -> None:
    other = Organisation.objects.create(name="Birch Ltd.", time_zone="America/Vancouver")
    with org_context(other):
        certificate(contact(other, "Cedar Inc."), number="BC-9", expires_on=TODAY)
    certificate(maple, number="ON-1", expires_on=TODAY)
    with org_context(None):
        exemptions.send_reminders(NOON)
    assert sorted((n, o) for n, _s, _d, o in hook) == [("BC-9", other), ("ON-1", org)]


def test_default_hook_logs_without_names(maple: Contact) -> None:
    item = certificate(maple, number="PST-1", expires_on=TODAY)
    with mock.patch.object(exemptions.log, "info") as info:
        exemptions.send_reminders(NOON)
    info.assert_called_once()
    event, fields = info.call_args.args[0], info.call_args.kwargs
    assert event == "contacts.exemption.reminder"
    assert fields["certificate"] == str(item.public_id)
    assert fields["state"] == "expiring" and fields["days_left"] == 0
    assert "Maple" not in repr(fields)


def other_hook(item: ExemptionCertificate, state: str, days_left: int) -> None:
    """A hook named in settings (``test_hook_comes_from_settings``)."""


@override_settings(NUMO9_EXEMPTION_REMINDER_HOOK="tests.test_contacts_exemptions.other_hook")
def test_hook_comes_from_settings() -> None:
    assert exemptions.get_hook() is other_hook
    with override_settings(NUMO9_EXEMPTION_REMINDER_HOOK=""):
        assert exemptions.get_hook() is exemptions.log_reminder


def test_daily_job_is_scheduled_and_runs(
    maple: Contact, hook: list[tuple[str, str, int, Any]], sent: list[dict[str, Any]]
) -> None:
    from numo9.celery import app as celery_app
    from numo9.jobs.runtime import start_job

    entry = celery_app.conf.beat_schedule[EXEMPTION_REMINDERS]
    assert entry["task"] == EXEMPTION_REMINDERS
    certificate(maple, number="PST-1", expires_on=organisation_today(maple.organisation))
    start_job(exemption_reminders, key="today")
    assert deliver(exemption_reminders, sent[0]) == {"expiring": 1, "expired": 0}
    assert [s for _n, s, *_ in hook] == ["expiring"]

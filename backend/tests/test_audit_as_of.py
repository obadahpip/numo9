"""View a record as of a date (A-04-T11).

Acceptance: the reconstructed state = the historical snapshot. A record is changed several times;
for moments between the changes, the state rebuilt from the audit log equals the record's values
as they were then (snapshots taken at the time). Also: before creation the record does not exist,
a soft delete and a restore show, masked fields stay hidden, dates mean the end of the day in the
organisation's time zone, other organisations' records answer 404.
"""

from __future__ import annotations

import datetime as dt
import zoneinfo
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from typing import Any
from unittest import mock

import pytest
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.audit.mixins import raw_state
from numo9.audit.service import MASKED, plain
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.testapp.models import AuditedInvoice

pytestmark = pytest.mark.django_db

TORONTO = zoneinfo.ZoneInfo("America/Toronto")
T1 = dt.datetime(2026, 9, 1, 10, 0, tzinfo=TORONTO)
T2 = dt.datetime(2026, 9, 15, 10, 0, tzinfo=TORONTO)
T3 = dt.datetime(2026, 10, 1, 10, 0, tzinfo=TORONTO)
T4 = dt.datetime(2026, 10, 20, 10, 0, tzinfo=TORONTO)


@contextmanager
def at(moment: dt.datetime) -> Iterator[None]:
    with mock.patch("numo9.audit.service.timezone.now", return_value=moment):
        yield


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.", time_zone="America/Toronto")


@pytest.fixture
def owner(org: Organisation) -> User:
    user = User.objects.create_user("avery@refined.ca", password="x" * 12, name="Avery Owner")
    OrganisationMember.objects.create(organisation=org, user=user, role="owner")
    return user


def snapshot(invoice: AuditedInvoice) -> dict[str, Any]:
    """The record's audited values now, as the log writes them (masked hidden, empty dropped)."""
    values: dict[str, Any] = {}
    for name, raw in raw_state(invoice).items():
        if name == "__deleted__":
            continue
        if isinstance(raw, tuple):
            values[name] = dict(MASKED) if raw[1] else None
        elif hasattr(raw, "pk"):
            values[name] = {"id": str(raw.public_id), "label": str(raw)}
        else:
            values[name] = plain(raw)
    return {k: v for k, v in values.items() if v not in (None, "")}


def as_of(client: APIClient, org: Organisation, invoice: AuditedInvoice, when: str) -> Any:
    path = (
        f"/api/v1/o/{org.public_id}/audit/records/testapp.AuditedInvoice/{invoice.public_id}/as-of"
    )
    return client.get(path, {"at": when})


def state_of(body: dict[str, Any]) -> dict[str, Any]:
    return {f["field"]: f["value"] for f in body["state"] if f["value"] not in (None, "")}


def test_reconstructed_state_equals_the_historical_snapshot(org: Organisation, owner: User) -> None:
    snapshots: dict[str, dict[str, Any]] = {}
    with org_context(org):
        with at(T1):
            invoice = AuditedInvoice.objects.create(
                number="INV-101", amount=Decimal("100.00"), notes="Net 30", payee_sin="046454286"
            )
        snapshots["after T1"] = snapshot(invoice)
        with at(T2):
            invoice.amount = Decimal("120.50")
            invoice.save()
        snapshots["after T2"] = snapshot(invoice)
        with at(T3):
            invoice.number = "INV-101-1"
            invoice.notes = ""
            invoice.amount = Decimal("90.00")
            invoice.save()
        snapshots["after T3"] = snapshot(invoice)
    client = APIClient()
    client.force_authenticate(owner)
    for label, moment in [("after T1", T1), ("after T2", T2), ("after T3", T3)]:
        body = as_of(client, org, invoice, (moment + dt.timedelta(hours=1)).isoformat()).json()
        assert body["exists"] is True and body["complete"] is True
        assert state_of(body) == snapshots[label], label
    # The SIN stays hidden: the log never held it.
    body = as_of(client, org, invoice, T4.isoformat()).json()
    sin = next(f for f in body["state"] if f["field"] == "payee_sin")
    assert sin["masked"] is True and sin["value"] == MASKED


def test_before_creation_it_does_not_exist(org: Organisation, owner: User) -> None:
    with org_context(org), at(T2):
        invoice = AuditedInvoice.objects.create(number="INV-7", amount=Decimal("7.00"))
    client = APIClient()
    client.force_authenticate(owner)
    body = as_of(client, org, invoice, T1.isoformat()).json()
    assert body["exists"] is False and body["events_applied"] == 0 and body["state"] == []


def test_deleted_and_restored(org: Organisation, owner: User) -> None:
    with org_context(org):
        with at(T1):
            invoice = AuditedInvoice.objects.create(number="INV-8", amount=Decimal("8.00"))
        with at(T2):
            invoice.soft_delete()
        with at(T3):
            invoice.restore()
    client = APIClient()
    client.force_authenticate(owner)
    between = as_of(client, org, invoice, (T2 + dt.timedelta(days=1)).isoformat()).json()
    assert between["deleted"] is True and between["exists"] is False
    assert state_of(between)["amount"] == "8.00"  # what it held when it was deleted
    later = as_of(client, org, invoice, T4.isoformat()).json()
    assert later["deleted"] is False and later["exists"] is True


def test_a_date_means_the_end_of_that_day_in_the_organisation(
    org: Organisation, owner: User
) -> None:
    with org_context(org):
        with at(T1):
            invoice = AuditedInvoice.objects.create(number="INV-9", amount=Decimal("1.00"))
        with at(dt.datetime(2026, 9, 15, 23, 30, tzinfo=TORONTO)):  # 03:30 UTC on the 16th
            invoice.amount = Decimal("2.00")
            invoice.save()
    client = APIClient()
    client.force_authenticate(owner)
    assert state_of(as_of(client, org, invoice, "2026-09-15").json())["amount"] == "2.00"
    assert state_of(as_of(client, org, invoice, "2026-09-14").json())["amount"] == "1.00"
    bad = as_of(client, org, invoice, "15/09/2026")
    assert bad.status_code == 400 and bad.json()["code"] == "audit.bad_date"
    path = (
        f"/api/v1/o/{org.public_id}/audit/records/testapp.AuditedInvoice/{invoice.public_id}/as-of"
    )
    assert state_of(client.get(path).json())["amount"] == "2.00"  # no date: now


def test_other_organisations_records_are_not_found(org: Organisation, owner: User) -> None:
    other = Organisation.objects.create(name="Maple Leaf Supply Ltd.")
    with org_context(other), at(T1):
        theirs = AuditedInvoice.objects.create(number="X-1", amount=Decimal("1.00"))
    client = APIClient()
    client.force_authenticate(owner)
    assert as_of(client, org, theirs, T4.isoformat()).status_code == 404

"""G-03a-T16 — filing cycles API: cycles (history, switch), periods, custom periods, preview.

Acceptance: the tenant sweep passes; changing needs ``tax.manage`` (an employee gets 403);
a mid-year switch without the approval reference is a 422; every change is audited on the
registration, attributed to the person; the preview writes nothing and matches the result.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.orgsettings.models import TaxRegistration
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def reg(org: Organisation) -> TaxRegistration:
    import datetime as dt

    with org_context(org):
        item = TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2026, 1, 1),
            effective_to=dt.date(2027, 12, 31),
        )
        item.save()
    return item


@pytest.fixture
def owner(org: Organisation) -> Client:
    client = Client()
    client.force_login(people(org)["owner"])
    return client


def url(org: Organisation, reg: TaxRegistration, suffix: str) -> str:
    return f"/api/v1/o/{org.public_id}/tax/registrations/{reg.public_id}/{suffix}"


def send(client: Client, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, payload, content_type="application/json")


def spans(rows: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    return [(r["start"], r["end"], r["kind"]) for r in rows]


def test_set_switch_and_read_back(org: Organisation, reg: TaxRegistration, owner: Client) -> None:
    first = send(
        owner, url(org, reg, "cycles"), {"frequency": "quarterly", "effective_from": "2026-01-01"}
    )
    assert first.status_code == 201, first.content
    assert spans(first.json()["added"])[:2] == [
        ("2026-01-01", "2026-03-31", "regular"),
        ("2026-04-01", "2026-06-30", "regular"),
    ]
    refused = send(
        owner, url(org, reg, "cycles"), {"frequency": "monthly", "effective_from": "2026-07-01"}
    )
    assert refused.status_code == 422
    assert refused.json()["code"] == "tax.filing.approval_required"
    switch = {
        "frequency": "monthly",
        "effective_from": "2026-07-01",
        "approval_ref": "2026-GST-48812",
        "approval_date": "2026-06-10",
        "note": "CRA letter",
    }
    shown = send(owner, url(org, reg, "preview"), {"action": "switch", **switch})
    assert shown.status_code == 200
    assert len(owner.get(url(org, reg, "cycles")).json()["results"]) == 1  # nothing written
    done = send(owner, url(org, reg, "cycles"), switch)
    assert done.status_code == 201
    assert spans(done.json()["added"]) == spans(shown.json()["added"])
    assert spans(done.json()["removed"]) == spans(shown.json()["removed"])
    assert [w["code"] for w in done.json()["warnings"]] == ["tax.filing.not_fiscal_year_start"]
    cycles = owner.get(url(org, reg, "cycles")).json()["results"]
    assert [(c["frequency"], c["effective_from"], c["approval_ref"]) for c in cycles] == [
        ("quarterly", "2026-01-01", ""),
        ("monthly", "2026-07-01", "2026-GST-48812"),
    ]
    assert cycles[1]["created_by"] == "Dana Lee" and cycles[1]["approval_date"] == "2026-06-10"
    periods = owner.get(url(org, reg, "periods?from=2026-06-01&to=2026-08-15")).json()
    assert spans(periods["results"]) == [
        ("2026-04-01", "2026-06-30", "regular"),
        ("2026-07-01", "2026-07-31", "regular"),
        ("2026-08-01", "2026-08-31", "regular"),
    ]
    assert periods["registration"]["number"] and periods["results"][0]["due_date"] == "2026-07-31"
    assert [(r["due_date"], r["due_rolled"]) for r in periods["results"]] == [
        ("2026-07-31", False),
        ("2026-08-31", False),
        ("2026-10-01", True),  # 30 Sep is a federal holiday
    ]
    october = owner.get(url(org, reg, "periods?from=2026-10-01&to=2026-10-31")).json()["results"]
    assert (october[0]["due_date"], october[0]["due_rolled"]) == ("2026-11-30", False)
    january = owner.get(url(org, reg, "periods?from=2027-01-01&to=2027-01-31")).json()["results"]
    assert (january[0]["due_date"], january[0]["due_rolled"]) == ("2027-03-01", True)  # 28 Feb: Sun
    assert owner.get(url(org, reg, "periods?from=nope")).status_code == 400
    with org_context(org):
        events = AuditEvent.objects.filter(action="tax.filing.frequency_changed").order_by("pk")
        assert [e.changes["frequency"] for e in events] == [
            ["", "quarterly"],
            ["quarterly", "monthly"],
        ]
        assert all(e.actor_user is not None and e.actor_user.name == "Dana Lee" for e in events)


def test_custom_periods_and_annual_instalments(
    org: Organisation, reg: TaxRegistration, owner: Client
) -> None:
    send(owner, url(org, reg, "cycles"), {"frequency": "annual", "effective_from": "2026-01-01"})
    rows = owner.get(url(org, reg, "periods")).json()["results"]
    assert [i["due_date"] for i in rows[0]["instalments"]] == [
        "2026-04-30", "2026-07-31", "2026-11-02", "2027-02-01",
    ]  # fmt: skip
    added = send(
        owner, url(org, reg, "custom-periods"), {"start": "2027-01-01", "end": "2027-03-15"}
    )
    assert added.status_code == 201
    custom = next(r for r in added.json()["periods"] if r["kind"] == "custom")
    assert (custom["start"], custom["end"]) == ("2027-01-01", "2027-03-15")
    overlap = send(
        owner, url(org, reg, "custom-periods"), {"start": "2027-03-01", "end": "2027-04-15"}
    )
    assert (overlap.status_code, overlap.json()["code"]) == (422, "tax.filing.custom_overlap")
    bad = send(owner, url(org, reg, "preview"), {"action": "custom", "start": "2027-05-01"})
    assert bad.status_code == 400 and "end" in bad.json()
    regular = next(r for r in added.json()["periods"] if r["kind"] != "custom")
    locked = owner.delete(url(org, reg, f"custom-periods/{regular['id']}"))
    assert (locked.status_code, locked.json()["code"]) == (422, "tax.filing.custom_locked")
    removed = owner.delete(url(org, reg, f"custom-periods/{custom['id']}"))
    assert removed.status_code == 200
    assert all(r["kind"] != "custom" for r in removed.json()["periods"])
    assert owner.delete(url(org, reg, f"custom-periods/{custom['id']}")).status_code == 404
    with org_context(org):
        actions = list(
            AuditEvent.objects.filter(action__startswith="tax.filing.custom").values_list(
                "action", flat=True
            )
        )
    assert sorted(actions) == ["tax.filing.custom_period_added", "tax.filing.custom_period_removed"]


def test_permissions_other_types_and_sweep(
    org: Organisation, reg: TaxRegistration, owner: Client
) -> None:
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=org, user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    body = {"frequency": "quarterly", "effective_from": "2026-01-01"}
    assert send(client, url(org, reg, "cycles"), body).status_code == 403
    assert send(client, url(org, reg, "preview"), {"action": "switch", **body}).status_code == 403
    assert send(client, url(org, reg, "custom-periods"), {}).status_code == 403
    with org_context(org):
        payroll = TaxRegistration(organisation=org, type="rp", number="123456782RP0001")
        payroll.save()
    assert owner.get(url(org, payroll, "periods")).status_code == 404  # payroll files no returns
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())

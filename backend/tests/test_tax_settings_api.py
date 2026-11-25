"""G-06-T07 — tax settings API: ``tax/settings`` and ``tax/registrations``.

Acceptance: the tenant sweep passes; changing needs ``tax.manage``; the settings (basis with its
reason and mid-year warning, rounding, quick method, default codes, restricted-ITC accounts) and
the registrations (with their filing summary) are read and changed here; changes are audited.
"""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.ledger.models import Account
from numo9.ledger.template import load_template
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.journal_helpers import people

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    organisation = Organisation.objects.create(name="Refined Interiors Inc.")
    load_template(organisation, "ON")
    return organisation


@pytest.fixture
def owner(org: Organisation) -> Client:
    client = Client()
    client.force_login(people(org)["owner"])
    return client


def url(org: Organisation, suffix: str) -> str:
    return f"/api/v1/o/{org.public_id}/tax/{suffix}"


def send(client: Client, method: str, path: str, payload: dict[str, Any]) -> Any:
    return getattr(client, method)(path, payload, content_type="application/json")


def test_settings_read_and_change(org: Organisation, owner: Client) -> None:
    body = owner.get(url(org, "settings")).json()
    assert (body["basis"], body["rounding_mode"], body["quick_method"]) == (
        "accrual",
        "line",
        False,
    )
    assert body["registered"] is False
    assert [a["pct"] for a in body["restricted_itc_accounts"]] == ["50"]  # meals, from the chart
    changed = send(
        owner, "patch", url(org, "settings"),
        {"rounding_mode": "document", "quick_method": True, "quick_method_from": "2026-01-01"},
    )  # fmt: skip
    assert changed.status_code == 200, changed.content
    assert (changed.json()["rounding_mode"], changed.json()["quick_method_from"]) == (
        "document", "2026-01-01",
    )  # fmt: skip
    undated = send(owner, "patch", url(org, "settings"), {"quick_method_from": None})
    assert undated.status_code == 400 and "quick_method_from" in undated.json()
    off = send(owner, "patch", url(org, "settings"), {"quick_method": False}).json()
    assert (off["quick_method"], off["quick_method_from"]) == (False, None)
    bad = send(owner, "patch", url(org, "settings"), {"default_codes": {"sales": {"x": "nope"}}})
    assert bad.status_code == 400
    with org_context(org):
        assert AuditEvent.objects.filter(object_type="tax.TaxSettings").count() >= 3


def test_basis_needs_a_reason_and_warns_mid_year(org: Organisation, owner: Client) -> None:
    check = owner.get(url(org, "settings/basis-check?basis=cash")).json()
    assert check["changes"] is True
    assert owner.get(url(org, "settings/basis-check?basis=other")).status_code == 400
    refused = send(
        owner, "patch", url(org, "settings"), {"basis": "cash", "rounding_mode": "document"}
    )
    assert refused.status_code == 400 and "reason" in refused.json()
    assert owner.get(url(org, "settings")).json()["rounding_mode"] == "line"  # all or nothing
    done = send(
        owner, "patch", url(org, "settings"),
        {"basis": "cash", "basis_reason": "CRA approved the cash method"},
    )  # fmt: skip
    assert done.status_code == 200 and done.json()["basis"] == "cash"
    assert bool(done.json()["basis_warning"]) == check["mid_year"]
    with org_context(org):
        event = AuditEvent.objects.get(action="tax.taxsettings.basis_changed")
    assert event.meta["reason"] == "CRA approved the cash method"
    assert event.actor_user is not None


def test_restricted_itc_accounts(org: Organisation, owner: Client) -> None:
    with org_context(org):
        account = Account.objects.filter(type="expense", itc_restriction_pct__isnull=True)[0]
    path = url(org, f"settings/restricted-itc/{account.public_id}")
    added = send(owner, "put", path, {"pct": "50"})
    assert added.status_code == 200
    assert account.code in [a["code"] for a in added.json()["restricted_itc_accounts"]]
    assert send(owner, "put", path, {"pct": "140"}).status_code == 400
    lifted = send(owner, "put", path, {"pct": None})
    assert account.code not in [a["code"] for a in lifted.json()["restricted_itc_accounts"]]
    missing = url(org, "settings/restricted-itc/00000000-0000-4000-8000-000000000000")
    assert send(owner, "put", missing, {"pct": "50"}).status_code == 404


def test_registrations_with_their_filing(org: Organisation, owner: Client) -> None:
    created = send(
        owner, "post", url(org, "registrations"),
        {"type": "rt", "number": "123456782RT0001", "effective_from": "2026-01-01",
         "frequency": "quarterly"},
    )  # fmt: skip
    assert created.status_code == 201, created.content
    reg = created.json()
    assert reg["files_returns"] is True and reg["filing"]["frequency"] == "quarterly"
    assert reg["filing"]["next_due"]["due_date"] == "2026-04-30"
    assert owner.get(url(org, "settings")).json()["registered"] is True
    periods = owner.get(url(org, f"registrations/{reg['id']}/periods")).json()["results"]
    assert (periods[0]["start"], periods[0]["end"]) == ("2026-01-01", "2026-03-31")
    invalid = send(owner, "post", url(org, "registrations"), {"type": "rt", "number": "12RT"})
    assert invalid.status_code == 400 and "123456782 RT 0001" in str(invalid.json())
    bn = send(owner, "post", url(org, "registrations"), {"type": "bn", "number": "123456782"})
    assert bn.status_code == 201 and bn.json()["filing"] is None
    rows = owner.get(url(org, "registrations")).json()["results"]
    assert sorted(r["type"] for r in rows) == ["bn", "rt"]
    moved = send(
        owner, "patch", url(org, f"registrations/{reg['id']}"), {"effective_from": "2026-02-01"}
    )
    assert moved.status_code == 200 and moved.json()["effective_from"] == "2026-02-01"
    retyped = send(owner, "patch", url(org, f"registrations/{reg['id']}"), {"type": "qst"})
    assert retyped.status_code == 400
    with org_context(org):
        from numo9.tax.models import FilingPeriod

        first = FilingPeriod.objects.order_by("start")[0]
        assert first.start.isoformat() == "2026-02-01"
        first.status = "filed"
        first.save()
    locked = send(
        owner, "patch", url(org, f"registrations/{reg['id']}"), {"effective_from": "2026-03-01"}
    )
    assert (locked.status_code, locked.json()["code"]) == (422, "tax.registration.filed_periods")
    assert owner.delete(url(org, f"registrations/{reg['id']}")).status_code == 422
    assert owner.delete(url(org, f"registrations/{bn.json()['id']}")).status_code == 204
    assert owner.get(url(org, f"registrations/{bn.json()['id']}")).status_code == 404


def test_permissions_and_sweep(org: Organisation, owner: Client) -> None:
    employee = User.objects.create_user("emp@refined.ca", name="Emp")
    OrganisationMember.objects.create(organisation=org, user=employee, role="employee")
    client = Client()
    client.force_login(employee)
    assert (
        send(client, "patch", url(org, "settings"), {"rounding_mode": "document"}).status_code
        == 403
    )
    assert send(client, "post", url(org, "registrations"), {}).status_code == 403
    with org_context(org):
        account = Account.objects.filter(type="expense")[0]
    path = url(org, f"settings/restricted-itc/{account.public_id}")
    assert send(client, "put", path, {"pct": "50"}).status_code == 403
    call_command("tenant_sweep", stdout=StringIO())
    call_command("permission_check", stdout=StringIO())

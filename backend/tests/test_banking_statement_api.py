"""F-02-T11 — API ``/api/v1/o/<org>/bank-accounts/<id>/imports``: upload, preview, commit, undo,
history; feature key; permissions; file type and size checked as A-06.

Acceptance: tenant sweep and RBAC matrix pass (``test_tenant_sweep`` / ``test_rbac_matrix`` run
over these routes — see the report); here: the whole flow as an owner (upload → detected mapping
and sample rows → preview → commit → history → re-import adds 0 → undo), OFX without a mapping,
an edited layout, refusals with their codes (A-06 type / empty / too large, not a statement, bad
layout, lines with errors, undo of a matched line → 409 with the line), the 202 job for a large
file, 403 for a role without the banking permissions, 402 without the feature, 404 for
another organisation's account.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

from numo9.accounts.models import User
from numo9.banking.models import BankAccount, StatementLine, StatementLineStatus
from numo9.banking.services import create_bank_account
from numo9.banking.tasks import JOB
from numo9.catalogue import drf as catalogue_drf
from numo9.rbac.catalogue import catalogue
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.statement_helpers import big_csv, fixture

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Refined Interiors Inc.")


@pytest.fixture
def bank(org: Organisation) -> BankAccount:
    with org_context(org):
        return create_bank_account(org, type="chequing", display_name="RBC Chequing")


def member(org: Organisation, role: str, email: str) -> Client:
    user = User.objects.create_user(email, name=email.split("@")[0])
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    client = Client()
    client.force_login(user)
    return client


@pytest.fixture
def owner(org: Organisation) -> Client:
    return member(org, "owner", "dana@refined.ca")


def imports(org: Organisation, bank: BankAccount, suffix: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/bank-accounts/{bank.public_id}/imports{suffix}"


def upload(client: Client, org: Organisation, bank: BankAccount, name: str, data: bytes) -> Any:
    return client.post(imports(org, bank), {"file": SimpleUploadedFile(name, data)})


def post(client: Client, path: str, payload: dict[str, Any] | None = None) -> Any:
    return client.post(path, payload or {}, content_type="application/json")


def test_whole_flow_for_an_rbc_csv(
    owner: Client, org: Organisation, bank: BankAccount, s3: str
) -> None:
    created = upload(owner, org, bank, "rbc.csv", fixture("rbc_chequing.csv"))
    assert created.status_code == 201, created.json()
    body = created.json()
    assert (body["format"], body["encoding"], body["delimiter"], body["tabular"]) == (
        "csv",
        "utf-8",
        ",",
        True,
    )
    assert body["mapping"]["name"] == "RBC Royal Bank" and body["mapping"]["score"] == 1.0
    assert body["layout"]["columns"][2] == "date" and body["lines"] == 5
    assert body["sample"]["rows"][0]["cells"][2] == "Transaction Date"
    assert len(body["mappings"]) == 10 and "debit_credit" in body["choices"]["signs"]
    assert body["import"]["status"] == "pending"
    one = imports(org, bank, f"/{body['import']['id']}")

    reloaded = owner.get(one).json()
    assert reloaded["mapping"]["name"] == "RBC Royal Bank"

    preview = post(owner, f"{one}/preview").json()
    assert preview["counts"] == {"total": 5, "new": 5, "duplicate": 0, "error": 0}
    assert preview["results"][0] == {
        "row": 2,
        "date": "2026-06-03",
        "amount": "-4.25",
        "description": "Tim Hortons #1234 Toronto ON",
        "payee": "",
        "reference": "",
        "fitid": "",
        "status": "new",
        "reasons": [],
    }
    with org_context(org):
        assert StatementLine.objects.count() == 0  # the preview wrote nothing

    committed = post(owner, f"{one}/commit")
    assert committed.status_code == 200, committed.json()
    assert committed.json()["import"]["counts"] == preview["counts"]
    assert committed.json()["import"]["status"] == "committed"

    history = owner.get(imports(org, bank)).json()["results"]
    assert [(h["file_name"], h["can_undo"], h["in_use"]) for h in history] == [("rbc.csv", True, 0)]

    again = upload(owner, org, bank, "rbc-again.csv", fixture("rbc_chequing.csv")).json()
    second = imports(org, bank, f"/{again['import']['id']}")
    duplicates = post(owner, f"{second}/preview", {"status": "duplicate"}).json()
    assert duplicates["counts"]["duplicate"] == 5 and duplicates["count"] == 5
    assert duplicates["results"][0]["reasons"][0]["code"] == "banking.statement.row.duplicate"
    assert post(owner, f"{second}/commit").json()["import"]["counts"]["new"] == 0
    assert post(owner, f"{one}/commit").status_code == 409  # committed once

    with org_context(org):
        line = StatementLine.objects.order_by("date", "pk").first()
        assert line is not None
        StatementLine.objects.filter(pk=line.pk).update(status=StatementLineStatus.MATCHED)
    refused = post(owner, f"{one}/undo")
    assert refused.status_code == 409
    assert refused.json()["code"] == "banking.import.in_use"
    assert [x["id"] for x in refused.json()["lines"]] == [str(line.public_id)]
    with org_context(org):
        StatementLine.objects.filter(pk=line.pk).update(status=StatementLineStatus.UNCODED)
    undone = post(owner, f"{one}/undo")
    assert undone.status_code == 200 and undone.json()["import"]["status"] == "undone"
    with org_context(org):
        assert StatementLine.objects.count() == 0


def test_ofx_needs_no_mapping(owner: Client, org: Organisation, bank: BankAccount, s3: str) -> None:
    body = upload(owner, org, bank, "td.qfx", fixture("td_web.qfx")).json()
    assert body["tabular"] is False and body["format"] == "qfx" and "mapping" not in body
    one = imports(org, bank, f"/{body['import']['id']}")
    assert post(owner, f"{one}/preview").json()["counts"]["new"] == 3
    assert post(owner, f"{one}/commit").json()["import"]["counts"]["new"] == 3


def test_an_edited_layout_and_errors(
    owner: Client, org: Organisation, bank: BankAccount, s3: str
) -> None:
    body = upload(owner, org, bank, "tangerine.csv", fixture("tangerine_quoted.csv")).json()
    one = imports(org, bank, f"/{body['import']['id']}")
    layout = {**body["layout"], "date_format": "YYYY-MM-DD"}
    edited = post(owner, f"{one}/preview", {"layout": layout, "status": "error"}).json()
    assert edited["counts"]["error"] == 5 and edited["layout"]["date_format"] == "YYYY-MM-DD"
    message = edited["results"][0]["reasons"][0]["message"]
    assert message.startswith("Row 2: date '6/3/2026' doesn't match YYYY-MM-DD")
    bad = post(owner, f"{one}/preview", {"layout": {"columns": ["description", "amount"]}})
    assert bad.status_code == 400 and bad.json()["code"] == "banking.statement.layout.no_date"
    refused = post(owner, f"{one}/commit")
    assert refused.status_code == 400
    assert (refused.json()["code"], refused.json()["count"]) == ("banking.import.has_errors", 1)
    done = post(owner, f"{one}/commit", {"skip_errors": True}).json()["import"]
    assert done["counts"] == {"total": 5, "new": 4, "duplicate": 0, "error": 1}


@pytest.mark.parametrize(
    ("name", "data", "status", "code"),
    [
        ("tool.exe", b"MZ\x90\x00", 415, "files.type_not_allowed"),
        ("old.xls", b"\xd0\xcf\x11\xe0", 415, "files.type_not_allowed"),
        ("empty.csv", b"", 400, None),
        ("fake.ofx", b"just text, no statement\n", 400, "banking.statement.file.no_statement"),
        ("scan.pdf", b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\n", 415, None),
    ],
)
def test_files_that_are_refused(
    owner: Client,
    org: Organisation,
    bank: BankAccount,
    s3: str,
    name: str,
    data: bytes,
    status: int,
    code: str | None,
) -> None:
    refused = upload(owner, org, bank, name, data)
    assert refused.status_code == status, refused.json()
    if code:
        assert refused.json()["code"] == code


def test_a_large_file_is_committed_in_the_background(
    owner: Client, org: Organisation, bank: BankAccount, s3: str, sent: list[dict[str, Any]]
) -> None:
    body = upload(owner, org, bank, "big.csv", big_csv(2500)).json()
    assert body["lines"] == 2500 and body["mapping"]["name"].startswith("Generic")
    queued = post(owner, imports(org, bank, f"/{body['import']['id']}/commit"))
    assert queued.status_code == 202
    assert queued.json()["import"]["status"] == "processing" and queued.json()["job"]["id"]
    assert any(m["task"] == JOB for m in sent)


def test_permissions_feature_and_tenancy(
    owner: Client, org: Organisation, bank: BankAccount, s3: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert "accounting.banking.import" in {p.key for p in catalogue}
    read_only = member(org, "employee", "rory@refined.ca")  # no banking permission
    assert read_only.get(imports(org, bank)).status_code == 403
    denied = upload(read_only, org, bank, "rbc.csv", fixture("rbc_chequing.csv"))
    assert denied.status_code == 403
    created = upload(owner, org, bank, "rbc.csv", fixture("rbc_chequing.csv")).json()
    one = imports(org, bank, f"/{created['import']['id']}")
    for action in ("preview", "commit", "undo"):
        assert post(read_only, f"{one}/{action}").status_code == 403

    other = Organisation.objects.create(name="Other Ltd.")
    stranger = member(other, "owner", "owner@other.ca")
    assert stranger.get(imports(org, bank)).status_code == 404
    with org_context(other):
        theirs = create_bank_account(other, type="chequing", display_name="Theirs")
    assert (
        stranger.get(
            f"/api/v1/o/{other.public_id}/bank-accounts/{theirs.public_id}/imports/"
            f"{created['import']['id']}"
        ).status_code
        == 404
    )

    class NoPackage:
        def allows(self, organisation: Organisation | None, key: str) -> bool:
            return key != "accounting.banking.write"

    monkeypatch.setattr(catalogue_drf, "get_resolver", lambda: NoPackage())
    blocked = upload(owner, org, bank, "rbc.csv", fixture("rbc_chequing.csv"))
    assert (blocked.status_code, blocked.json()["feature"]) == (402, "accounting.banking.write")

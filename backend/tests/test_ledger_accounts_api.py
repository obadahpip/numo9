"""C-01-T09 — chart of accounts API: CRUD, tree, renumber, archive, bulk; feature key; sweep.

Contract: the list (by code, depth, children flag, GIFI, balances per book; filters status,
type, q), the tree (children nested), create (code + name + sub-type; the model's rules refuse
with their code), edit (a new code is a renumber; refusals keep the stored row), delete (refused
with transactions — archive instead), renumber (conflict named), archive/restore (balance and
system-role rules), bulk (each account succeeds or fails on its own with the reason), GIFI search;
``accounting.accounts.view`` / ``.manage`` (403 without), features read/write (402 outside the
package), another organisation's account → 404; documented; the sweep has a factory.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from decimal import Decimal
from typing import Any

import pytest
import yaml
from django.test import Client

from numo9.accounts.models import User
from numo9.catalogue import drf as catalogue_drf
from numo9.ledger.models import Account
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember
from numo9.tenancy.sweep import SWEEP_FACTORIES
from tests.ledger_helpers import account, post_for_test

pytestmark = pytest.mark.django_db
D = Decimal


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


def _client(org: Organisation, role: str = "owner") -> Client:
    user = User.objects.create_user(
        f"{role}-{org.public_id.hex[:6]}@maple.ca", password="x" * 12, name=role.title()
    )
    OrganisationMember.objects.create(organisation=org, user=user, role=role)
    browser = Client()
    browser.force_login(user)
    return browser


def url(org: Organisation, suffix: str = "") -> str:
    return f"/api/v1/o/{org.public_id}/accounts{suffix}"


@pytest.fixture
def chart(org: Organisation) -> Iterator[dict[str, Account]]:
    with org_context(org):
        made = {
            "bank": account(org, "1000", "Chequing", subtype="bank", gifi_id="1001"),
            "sales": account(org, "4000", "Sales", subtype="revenue", gifi_id="8000"),
            "office": account(org, "6000", "Office", gifi_id="8811"),
        }
        made["stationery"] = account(
            org, "6010", "Stationery", gifi_id="8811", parent=made["office"]
        )
        post_for_test(
            JournalSpec(
                date=dt.date(2026, 3, 31),
                lines=[
                    LineSpec(account=made["bank"], debit=D("250.00")),
                    LineSpec(account=made["sales"], credit=D("250.00")),
                ],
            )
        )
        yield made


def test_list_with_depth_children_gifi_and_balances(org: Organisation, chart: Any) -> None:
    body = _client(org).get(url(org)).json()
    rows = {row["code"]: row for row in body["results"]}
    assert list(rows) == ["1000", "4000", "6000", "6010"]
    assert rows["1000"]["balance"] == {"accounting": "250.00", "tax": "250.00"}
    assert rows["4000"]["balance"]["accounting"] == "-250.00"
    assert rows["6000"]["has_children"] is True and rows["6010"]["depth"] == 2
    assert rows["6010"]["parent"] == rows["6000"]["id"]
    assert rows["1000"]["gifi"] == {
        "code": "1001",
        "description": rows["1000"]["gifi"]["description"],
    }
    browser = _client(org, "accountant_delegate")
    assert [r["code"] for r in browser.get(url(org), {"q": "60"}).json()["results"]] == [
        "6000",
        "6010",
    ]
    assert [r["code"] for r in browser.get(url(org), {"type": "revenue"}).json()["results"]] == [
        "4000"
    ]


def test_tree_nests_children(org: Organisation, chart: Any) -> None:
    roots = _client(org).get(url(org, "/tree")).json()["results"]
    office = next(r for r in roots if r["code"] == "6000")
    assert [c["code"] for c in office["children"]] == ["6010"]
    assert "6010" not in [r["code"] for r in roots]


def test_create_edit_and_refusals(org: Organisation, chart: Any) -> None:
    browser = _client(org)
    created = browser.post(
        url(org),
        {"code": "6100", "name": "Office supplies", "subtype": "operating_expense", "gifi": "8811"},
        content_type="application/json",
    )
    assert created.status_code == 201, created.json()
    row = created.json()
    assert (row["type"], row["gifi"]["code"]) == ("expense", "8811")

    taken = browser.post(
        url(org),
        {"code": "6100", "name": "Duplicate", "subtype": "operating_expense"},
        content_type="application/json",
    )
    assert taken.status_code == 400

    edited = browser.patch(
        url(org, f"/{row['id']}"),
        {"name": "Office supplies & postage", "code": "6105", "require_attachment": True},
        content_type="application/json",
    )
    assert edited.status_code == 200, edited.json()
    assert (edited.json()["code"], edited.json()["name"]) == ("6105", "Office supplies & postage")
    assert edited.json()["require_attachment"] is True

    conflict = browser.patch(
        url(org, f"/{row['id']}"), {"code": "1000"}, content_type="application/json"
    )
    assert conflict.status_code == 400 and "1000" in conflict.json()["detail"]

    bad_gifi = browser.patch(
        url(org, f"/{row['id']}"), {"gifi": "0001"}, content_type="application/json"
    )
    assert bad_gifi.status_code == 400 and bad_gifi.json()["code"] == "ledger.account.gifi_unknown"


def test_renumber_archive_restore_and_delete(org: Organisation, chart: Any) -> None:
    browser = _client(org)
    bank, office = chart["bank"], chart["office"]
    renumbered = browser.post(
        url(org, f"/{bank.public_id}/renumber"), {"code": "1010"}, content_type="application/json"
    )
    assert renumbered.status_code == 200 and renumbered.json()["code"] == "1010"

    refused = browser.post(url(org, f"/{bank.public_id}/archive"))
    assert refused.status_code == 400
    assert refused.json()["code"] == "ledger.account.archive_balance"

    parent = browser.post(url(org, f"/{office.public_id}/archive"))
    assert parent.json()["code"] == "ledger.account.archive_children"
    assert browser.post(url(org, f"/{chart['stationery'].public_id}/archive")).status_code == 200
    assert browser.post(url(org, f"/{office.public_id}/archive")).json()["status"] == "archived"
    assert [r["code"] for r in browser.get(url(org), {"status": "archived"}).json()["results"]] == [
        "6000",
        "6010",
    ]
    assert browser.post(url(org, f"/{office.public_id}/restore")).json()["status"] == "active"

    has_postings = browser.delete(url(org, f"/{bank.public_id}"))
    assert has_postings.status_code == 400
    assert has_postings.json()["code"] == "ledger.account.delete_has_postings"
    assert browser.delete(url(org, f"/{chart['stationery'].public_id}")).status_code == 204
    assert browser.get(url(org, f"/{chart['stationery'].public_id}")).status_code == 404


def test_bulk_outcomes_one_by_one(org: Organisation, chart: Any) -> None:
    ids = [str(chart[k].public_id) for k in ("bank", "stationery")]
    result = _client(org).post(
        url(org, "/bulk"), {"accounts": ids, "action": "archive"}, content_type="application/json"
    )
    body = result.json()
    assert (body["done"], body["failed"]) == (1, 1)
    outcome = {o["code"]: o for o in body["results"]}
    assert outcome["6010"]["ok"] is True
    assert outcome["1000"]["ok"] is False and "balance" in outcome["1000"]["detail"]

    gifi = _client(org, "accountant_delegate").post(
        url(org, "/bulk"),
        {"accounts": [str(chart["office"].public_id)], "action": "set_gifi", "value": "8810"},
        content_type="application/json",
    )
    assert gifi.json()["done"] == 1
    assert Account.objects.unscoped(reason="test").get(pk=chart["office"].pk).gifi_id == "8810"


def test_gifi_search(org: Organisation, chart: Any) -> None:
    found = _client(org).get(f"/api/v1/o/{org.public_id}/gifi", {"q": "100", "type": "asset"})
    assert found.status_code == 200
    assert all(r["code"].startswith("100") for r in found.json()["results"])
    assert found.json()["results"]


def test_permission_feature_and_isolation(
    org: Organisation, chart: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    employee = _client(org, "employee")
    assert employee.get(url(org)).status_code == 403
    assert employee.post(url(org, f"/{chart['sales'].public_id}/archive")).status_code == 403
    other = Organisation.objects.create(name="Other Inc.")
    outsider = _client(other)
    assert outsider.get(url(org)).status_code == 404
    assert outsider.get(url(other, f"/{chart['bank'].public_id}")).status_code == 404

    class NoPackage:
        def allows(self, organisation: Organisation | None, key: str) -> bool:
            return False

    monkeypatch.setattr(catalogue_drf, "get_resolver", lambda: NoPackage())
    refused = _client(org, "accountant_delegate").get(url(org))
    assert refused.status_code == 402
    assert refused.json()["feature"] == "accounting.chart_of_accounts.read"


def test_documented_and_swept(org: Organisation) -> None:
    schema = yaml.safe_load(_client(org).get("/api/schema/").content)
    paths = schema["paths"]
    assert set(paths["/api/v1/o/{org}/accounts"]) >= {"get", "post"}
    assert set(paths["/api/v1/o/{org}/accounts/{public_id}"]) >= {"get", "patch", "delete"}
    assert "post" in paths["/api/v1/o/{org}/accounts/bulk"]
    assert "ledger.Account" in SWEEP_FACTORIES

"""K-01-T11 — reports API: catalogue (categories, availability, favourites, layout tabs), run
(with a preset and a layout), export (PDF/XLSX/CSV = the run), favourites, layouts (save,
publish, immutable, delete), cell notes; a report outside the package answers 402 naming its
product; the tenant sweep passes."""

from __future__ import annotations

import csv
import datetime as dt
import io
from collections.abc import Iterator
from typing import Any

import pytest
from django.test import Client

from numo9.accounts.models import User
from numo9.ledger.services import post_journal
from numo9.reports.engine import Column, ReportDefinition, ReportRow, register, registry
from numo9.reports.models import ReportLayout
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember
from tests.journal_helpers import pay
from tests.report_helpers import report_books

pytestmark = pytest.mark.django_db


class OnlyAccounting:
    def allows(self, organisation: Any, key: str) -> bool:
        return key.startswith("accounting.") or key == "@core"


class TaxSample(ReportDefinition):
    id = "tax_sample"
    slug = "tax-sample"
    name = "Tax summary (sample)"
    category = "tax"
    feature = "tax.reports.read"

    def columns(self, params: dict[str, Any]) -> list[Column]:
        return [Column("amount", "Amount")]

    def query(self, organisation: Any, params: dict[str, Any]) -> Any:
        return None

    def rows(self, data: Any, params: dict[str, Any]) -> list[ReportRow]:
        return []


@pytest.fixture
def tax_report() -> Iterator[None]:
    register(TaxSample)
    yield
    registry.unregister(TaxSample.id)


@pytest.fixture
def books() -> dict[str, Any]:
    books = report_books()
    owner = User.objects.create_user("owner@refined.ca", name="Owner")
    OrganisationMember.objects.create(organisation=books["org"], user=owner, role="owner")
    client = Client()
    client.force_login(owner)
    return {**books, "client": client, "base": f"/api/v1/o/{books['org'].public_id}/reports"}


def test_catalogue_lists_reports_by_category_with_favourites(books: dict[str, Any]) -> None:
    client, base = books["client"], books["base"]
    assert client.put(f"{base}/trial-balance/favourite").status_code == 204
    assert client.put(f"{base}/trial-balance/favourite").status_code == 204  # idempotent
    body = client.get(base).json()
    [financial] = [c for c in body["categories"] if c["key"] == "financial"]
    reports = {r["id"]: r for r in financial["reports"]}
    assert reports["trial_balance"]["favourite"] is True
    assert reports["account_activity"]["favourite"] is False
    assert reports["trial_balance"]["available"] is True
    assert reports["trial_balance"]["slug"] == "trial-balance"
    assert body["favourites"] == ["trial_balance"]
    assert (body["drafts"], body["published"], body["custom"]) == ([], [], [])
    assert client.delete(f"{base}/trial-balance/favourite").status_code == 204
    assert client.get(base).json()["favourites"] == []


def test_run_with_a_preset_and_the_header(books: dict[str, Any]) -> None:
    client, base = books["client"], books["base"]
    answer = client.get(
        f"{base}/account-activity/run",
        {"preset": "custom", "date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert answer.status_code == 200, answer.json()
    body = answer.json()
    assert body["header"]["period_label"] == "1 Jun 2026 to 30 Jun 2026"
    assert body["totals"][0]["values"] == ["2550.00", "2550.00", "0.00"]
    assert [r["key"] for r in body["rows"]] == ["account:1000", "account:5400", "account:6100"]
    refused = client.get(f"{base}/account-activity/run", {"preset": "next_century"})
    assert (refused.status_code, refused.json()["code"]) == (400, "reports.range.unknown")
    missing = client.get(f"{base}/account-activity/run")
    assert (missing.status_code, missing.json()["code"]) == (400, "reports.param.required")
    assert client.get(f"{base}/nope/run").status_code == 404


def test_exports_equal_the_run(books: dict[str, Any]) -> None:
    client, base = books["client"], books["base"]
    params = {"date_from": "2026-05-01", "date_to": "2026-07-31"}
    run = client.get(f"{base}/account-activity/run", params).json()
    answer = client.get(f"{base}/account-activity/export", {**params, "file": "csv"})
    assert answer.status_code == 200
    assert answer["Content-Disposition"] == 'attachment; filename="account-activity-2026-07-31.csv"'
    lines = list(csv.reader(io.StringIO(answer.content.decode("utf-8").lstrip("﻿"))))
    table = lines[lines.index(["", "Debits", "Credits", "Net movement"]) + 1 :]
    assert table == [[r["label"], *r["values"]] for r in run["rows"] + run["totals"]]
    pdf = client.get(f"{base}/account-activity/export", {**params, "file": "pdf"})
    assert (pdf.status_code, pdf["Content-Type"], pdf.content[:4]) == (
        200,
        "application/pdf",
        b"%PDF",
    )
    assert (
        client.get(f"{base}/account-activity/export", {**params, "file": "xlsx"}).content[:2]
        == b"PK"
    )
    bad = client.get(f"{base}/account-activity/export", {**params, "file": "doc"})
    assert (bad.status_code, bad.json()["code"]) == (400, "reports.export.format")


def test_layouts_save_publish_and_stay_immutable(books: dict[str, Any]) -> None:
    client, base = books["client"], books["base"]
    saved = client.post(
        f"{base}/trial-balance/layouts",
        {
            "name": "Board pack",
            "params": {"as_of": "2026-06-30"},
            "config": {"rows": [{"key": "account:5400", "label": "Office rent"}]},
            "notes": "Prepared for the board.",
        },
        content_type="application/json",
    )
    assert saved.status_code == 201, saved.json()
    layout = saved.json()
    assert (layout["status"], layout["version"]) == ("draft", 1)
    assert client.get(base).json()["drafts"][0]["id"] == layout["id"]
    run = client.get(f"{base}/trial-balance/run", {"layout": layout["id"]}).json()
    assert run["rows"][0]["label"] == "Office rent"
    assert run["notes"] == "Prepared for the board."
    published = client.post(f"{base}/layouts/{layout['id']}/publish")
    assert published.status_code == 200, published.json()
    snapshot = published.json()["snapshot"]
    with org_context(books["org"]):
        post_journal(
            pay(books["rent"], books["chequing"], "100.00", dt.date(2026, 6, 5)),
            user=None,
        )
    again = client.get(f"{base}/trial-balance/run", {"layout": layout["id"]}).json()
    assert again["rows"] == snapshot["rows"]  # later postings don't touch the published run
    assert client.get(base).json()["published"][0]["id"] == layout["id"]
    refused = client.post(f"{base}/layouts/{layout['id']}/publish")
    assert (refused.status_code, refused.json()["code"]) == (400, "reports.layout.published")
    kept = client.delete(f"{base}/layouts/{layout['id']}")
    assert (kept.status_code, kept.json()["code"]) == (400, "reports.layout.published")
    custom = client.post(
        f"{base}/trial-balance/layouts",
        {"name": "Mine", "status": "custom", "params": {}, "config": {}},
        content_type="application/json",
    ).json()
    assert client.get(base).json()["custom"][0]["id"] == custom["id"]
    assert client.delete(f"{base}/layouts/{custom['id']}").status_code == 204
    assert client.get(f"{base}/layouts/{custom['id']}").status_code == 404
    bad = client.post(
        f"{base}/trial-balance/layouts",
        {"name": "x", "status": "published"},
        content_type="application/json",
    )
    assert (bad.status_code, bad.json()["code"]) == (400, "reports.layout.status")


def test_cell_note_shows_on_its_row(books: dict[str, Any]) -> None:
    client, base = books["client"], books["base"]
    saved = client.put(
        f"{base}/account-activity/notes",
        {"row": "account:5400", "column": "net", "text": "Includes June deposit"},
        content_type="application/json",
    )
    assert saved.json()["text"] == "Includes June deposit"
    run = client.get(
        f"{base}/account-activity/run", {"date_from": "2026-06-01", "date_to": "2026-06-30"}
    ).json()
    rent = next(r for r in run["rows"] if r["key"] == "account:5400")
    assert rent["notes"] == {"net": "Includes June deposit"}


def test_report_outside_the_package_answers_402_with_its_product(
    books: dict[str, Any], settings: Any, tax_report: None
) -> None:
    settings.NUMO9_ENTITLEMENT_RESOLVER = "tests.test_report_api.OnlyAccounting"
    client, base = books["client"], books["base"]
    catalogue = client.get(base).json()
    [tax] = [c for c in catalogue["categories"] if c["key"] == "tax"]
    assert tax["reports"][0]["available"] is False
    for url in (f"{base}/tax-sample/run", f"{base}/tax-sample/export?file=csv"):
        refused = client.get(url)
        assert refused.status_code == 402, url
        body = refused.json()
        assert (body["code"], body["feature"], body["product"]) == (
            "entitlement.feature_not_in_package",
            "tax.reports.read",
            "tax",
        )
    assert client.get(f"{base}/trial-balance/run", {"as_of": "2026-06-30"}).status_code == 200


def test_permissions(books: dict[str, Any]) -> None:
    org, base = books["org"], books["base"]
    hr = User.objects.create_user("hr@refined.ca", name="HR")
    OrganisationMember.objects.create(organisation=org, user=hr, role="hr")
    other = Client()
    other.force_login(hr)
    assert other.get(base).status_code == 403
    assert other.get(f"{base}/trial-balance/run").status_code == 403
    with org_context(org):
        assert ReportLayout.objects.count() == 0

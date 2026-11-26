"""G-05-T09 — the tax reports in the K-01 catalogue and API: listed under Tax, run and exported
through ``/reports/<slug>``; feature key ``tax.reports.read`` — on every package with Tax; a
package without Tax gets the explicit 402 gate naming the product; the tenant sweep passes."""

from __future__ import annotations

from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from numo9.accounts.models import User
from numo9.entitlements.engine import resolve_entitlements
from numo9.tenancy.models import OrganisationMember
from tests.entitlement_helpers import package, subscribe
from tests.tax_report_helpers import Q2, tax_books

pytestmark = pytest.mark.django_db
SLUGS = ("tax-summary", "tax-detail", "tax-audit", "itc-detail", "tax-tie-out")
RANGE = {"date_from": Q2[0].isoformat(), "date_to": Q2[1].isoformat()}


@pytest.fixture
def ctx() -> dict[str, Any]:
    books = tax_books()
    owner = User.objects.create_user("boss@refined.ca", name="Boss")
    OrganisationMember.objects.create(organisation=books["org"], user=owner, role="owner")
    client = Client()
    client.force_login(owner)
    return {**books, "client": client, "base": f"/api/v1/o/{books['org'].public_id}/reports"}


def test_every_tax_package_runs_them(ctx: dict[str, Any]) -> None:
    subscribe(ctx["org"], package("books_tax", ["accounting", "tax"]))
    assert "tax.reports.read" in resolve_entitlements(ctx["org"]).features
    catalogue = ctx["client"].get(ctx["base"]).json()
    [tax] = [c for c in catalogue["categories"] if c["key"] == "tax"]
    listed = {r["slug"]: r for r in tax["reports"]}
    assert set(SLUGS) <= set(listed)
    assert all(listed[s]["available"] and listed[s]["feature"] == "tax.reports.read" for s in SLUGS)
    for slug in SLUGS:
        ran = ctx["client"].get(f"{ctx['base']}/{slug}/run", RANGE)
        assert ran.status_code == 200, (slug, ran.content)
        assert ran.json()["report"] == slug.replace("-", "_")
    summary = ctx["client"].get(f"{ctx['base']}/tax-summary/run", RANGE).json()
    assert summary["totals"][0]["values"][1] == "195.00"


def test_a_package_without_tax_sees_the_explicit_gate(ctx: dict[str, Any]) -> None:
    subscribe(ctx["org"], package("books_only", ["accounting"]))
    assert "tax.reports.read" not in resolve_entitlements(ctx["org"]).features
    catalogue = ctx["client"].get(ctx["base"]).json()
    [tax] = [c for c in catalogue["categories"] if c["key"] == "tax"]
    assert all(r["available"] is False and r["product"] == "tax" for r in tax["reports"])
    refused = ctx["client"].get(f"{ctx['base']}/tax-summary/run", RANGE)
    assert refused.status_code == 402
    body = refused.json()
    assert (body["code"], body["feature"], body["product"]) == (
        "entitlement.feature_not_in_package",
        "tax.reports.read",
        "tax",
    )


def test_bad_range_is_a_400(ctx: dict[str, Any]) -> None:
    subscribe(ctx["org"], package("books_tax", ["accounting", "tax"]))
    bad = ctx["client"].get(f"{ctx['base']}/tax-summary/run")
    assert bad.status_code == 400


def test_sweep() -> None:
    call_command("tenant_sweep", stdout=StringIO())

"""K-01-T18 — every report is in the global search and the command palette: its name and
keywords find it, it opens the runner, gated by its feature key; "Reports" goes to the home."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.test import Client
from django.utils.translation import gettext_lazy as _

from numo9.accounts.models import User
from numo9.reports.engine import ReportDefinition, register, registry
from numo9.search.static import match_static, static_entries
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.entitlement_helpers import package, subscribe

pytestmark = pytest.mark.django_db


class BalanceSheetSample(ReportDefinition):
    id = "balance_sheet_sample"
    slug = "balance-sheet-sample"
    name = _("Balance sheet")
    keywords = (_("statement of financial position"), "bilan")


class TaxSample(ReportDefinition):
    id = "tax_search_sample"
    slug = "tax-search-sample"
    name = "GST/HST summary"
    category = "tax"
    feature = "tax.reports.read"


@pytest.fixture
def samples() -> Iterator[None]:
    register(BalanceSheetSample)
    register(TaxSample)
    yield
    registry.unregister(BalanceSheetSample.id)
    registry.unregister(TaxSample.id)


@pytest.fixture
def client_org() -> tuple[Client, Organisation]:
    org = Organisation.objects.create(name="Refined Interiors Inc.")
    owner = User.objects.create_user("owner@refined.ca", name="Owner")
    OrganisationMember.objects.create(organisation=org, user=owner, role="owner")
    client = Client()
    client.force_login(owner)
    return client, org


def test_registered_reports_are_search_entries(samples: None) -> None:
    keys = {e.key for e in static_entries()}
    assert {
        "reports.trial_balance",
        "reports.account_activity",
        "reports.balance_sheet_sample",
    } <= keys
    found = [e.key for e in match_static("balance sheet")]
    assert {"reports.balance_sheet", "reports.balance_sheet_sample"} <= set(found)
    assert "reports.balance_sheet" in [e.key for e in match_static("bilan")]
    assert "reports.profit_and_loss" in [e.key for e in match_static("income statement")]
    assert "reports.trial_balance" in [e.key for e in match_static("TB")]
    registry.unregister(TaxSample.id)
    assert "reports.tax_search_sample" not in {e.key for e in static_entries()}
    register(TaxSample)


def test_balance_sheet_search_opens_the_runner(
    samples: None, client_org: tuple[Client, Organisation]
) -> None:
    client, org = client_org
    body = client.get(f"/api/v1/o/{org.public_id}/search", {"q": "balance sheet"}).json()
    found = next(r for r in body["reports"] if r["key"] == "reports.balance_sheet")
    assert found == {
        "key": "reports.balance_sheet",
        "title": "Balance sheet",
        "url": f"/o/{org.public_id}/reports/balance-sheet",
        "locked": False,
        "reason": "",
    }
    nav = client.get(f"/api/v1/o/{org.public_id}/search", {"q": "reports"}).json()["navigation"]
    assert {"key": "nav.reports", "url": f"/o/{org.public_id}/reports"}.items() <= nav[0].items()


def test_a_report_outside_the_package_is_found_locked(
    samples: None, client_org: tuple[Client, Organisation]
) -> None:
    client, org = client_org
    subscribe(org, package("accounting_only", ["accounting"]))
    [found] = client.get(f"/api/v1/o/{org.public_id}/search", {"q": "gst hst"}).json()["reports"]
    assert found["key"] == "reports.tax_search_sample"
    assert found["locked"] is True and "Tax" in found["reason"]

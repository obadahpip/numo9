"""U-06-T06 — KPI tiles and trend charts: the metrics API and the tiles' drill-down.

Acceptance: a tile's count equals its drill-down list's count (active, MRR, trials), demo
organisations excluded; history is the stored snapshots then today's live point; only platform
staff with ``platform.console.view``.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.test import Client
from django.utils import timezone

from numo9.packages.models import PackagePrice
from numo9.platform.models import PlatformMetricDaily
from numo9.tenancy.models import Organisation
from tests.entitlement_helpers import package, subscribe
from tests.test_platform_lists import staff
from tests.workspace_helpers import user

pytestmark = pytest.mark.django_db
URL = "/api/v1/platform/metrics"


def org(name: str, status: str, plan: object, demo: bool = False) -> Organisation:
    made = Organisation.objects.create(name=name)
    subscribe(made, plan, status)  # type: ignore[arg-type]
    if demo:
        Organisation.objects.filter(pk=made.pk).update(status="demo")
    return made


@pytest.fixture
def world() -> None:
    plan = package("basic", ["accounting"])
    PackagePrice.objects.create(
        package=plan, interval="month", amount_cents=2900, effective_from=dt.date(2026, 1, 1)
    )
    for index in range(3):
        org(f"Active {index}", "active", plan)
    org("Trial", "trialing", plan)
    org("Demo", "active", plan, demo=True)
    org("Demo trial", "trialing", plan, demo=True)


def test_tile_counts_equal_their_drill_down_lists(world: None) -> None:
    browser = staff()
    current = browser.get(URL).json()["current"]
    assert (current["active"], current["trials"], current["mrr_cents"]) == (3, 1, 8700)
    for metric, expected in (("active", 3), ("mrr", 3), ("trials", 1)):
        listing = browser.get(f"{URL}/{metric}/organisations").json()
        assert listing["count"] == expected
        assert not any(row["is_demo"] for row in listing["results"])
        assert listing["count"] == (current["trials"] if metric == "trials" else current["active"])


def test_drill_down_pages_and_unknown_metric(world: None) -> None:
    browser = staff()
    page = browser.get(f"{URL}/active/organisations?page_size=2&page=2").json()
    assert (page["count"], page["pages"], len(page["results"])) == (3, 2, 1)
    assert browser.get(f"{URL}/churn/organisations").status_code == 404


def test_history_is_snapshots_then_today(world: None) -> None:
    today = timezone.localdate()
    for back, mrr in ((100, 1), (5, 2900), (1, 5800)):
        PlatformMetricDaily.objects.create(date=today - dt.timedelta(days=back), mrr_cents=mrr)
    history = staff().get(f"{URL}?days=30").json()["history"]
    assert [point["mrr_cents"] for point in history] == [2900, 5800, 8700]
    assert history[-1]["date"] == today.isoformat()


@pytest.mark.parametrize("days", ["3", "400", "x"])
def test_days_is_validated(days: str) -> None:
    response = staff().get(f"{URL}?days={days}")
    assert response.status_code == 400
    assert response.json()["field"] == "days"


def test_only_platform_staff() -> None:
    outsider = Client()
    outsider.force_login(user("someone@example.ca"))
    assert outsider.get(URL).status_code in (403, 404)
    assert outsider.get(f"{URL}/active/organisations").status_code in (403, 404)

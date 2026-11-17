"""U-06-T03 — Practices and organisations list APIs with filters (status, package, province,
created).

Acceptance: pagination and filters are correct — each filter alone and combined, several values
within one (any of them), the creation range inclusive, newest first, page sizes and the page
count; bad values are 400 with the field; only platform staff with ``platform.console.view``.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.test import Client

from numo9.entitlements.models import Subscription
from numo9.orgsettings.models import OrganisationSettings
from numo9.rbac.models import Role, RoleAssignment, RoleScope
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, PracticeAssignment
from tests.auth_helpers import enrol_two_factor
from tests.entitlement_helpers import package
from tests.workspace_helpers import member, practice, user

pytestmark = pytest.mark.django_db
URL = "/api/v1/platform/organisations"


def staff(role: str = "platform_support") -> Client:
    person = user(f"{role}@numo9.ca")
    RoleAssignment.objects.create(
        user=person, role=Role.objects.get(scope=RoleScope.PLATFORM, key=role)
    )
    enrol_two_factor(person)
    browser = Client()
    browser.force_login(person)
    return browser


def org(
    name: str, status: str, created: dt.date, province: str = "", pkg: Any = None
) -> Organisation:
    made = Organisation.objects.create(name=name, status=status)
    Organisation.objects.filter(pk=made.pk).update(
        created_at=dt.datetime.combine(created, dt.time(12), tzinfo=dt.UTC)
    )
    if province:
        with org_context(made):
            OrganisationSettings(
                organisation=made, display_name=name, mailing_province=province
            ).save()
    if pkg is not None:
        with org_context(made):
            Subscription.objects.create(organisation=made, package=pkg, status="active")
        Organisation.objects.filter(pk=made.pk).update(status=status)
    return made


@pytest.fixture
def world() -> dict[str, Organisation]:
    growth = package("growth", ["accounting", "payroll"])
    starter = package("starter", ["accounting"])
    return {
        "maple": org("Maple Leaf Supply Ltd.", "active", dt.date(2026, 10, 2), "ON", growth),
        "erable": org("Érable Bakery Inc.", "trial", dt.date(2026, 11, 6), "QC"),
        "cedar": org("Cedar Roofing Co.", "read_only", dt.date(2026, 9, 14), "BC", starter),
        "demo": org("Demo — Maple & Pine", "demo", dt.date(2026, 11, 17), "ON"),
    }


def names(body: dict[str, Any]) -> list[str]:
    return [row["name"] for row in body["results"]]


def test_filters(world: dict[str, Organisation]) -> None:
    browser = staff()
    everyone = browser.get(URL).json()
    assert names(everyone) == [  # newest first
        "Demo — Maple & Pine", "Érable Bakery Inc.", "Maple Leaf Supply Ltd.", "Cedar Roofing Co.",
    ]  # fmt: skip
    assert everyone["results"][0]["is_demo"] is True
    assert names(browser.get(URL, {"status": ["trial", "read_only"]}).json()) == [
        "Érable Bakery Inc.", "Cedar Roofing Co.",
    ]  # fmt: skip
    assert names(browser.get(URL, {"package": "growth"}).json()) == ["Maple Leaf Supply Ltd."]
    assert names(browser.get(URL, {"package": "none"}).json()) == [
        "Demo — Maple & Pine", "Érable Bakery Inc.",
    ]  # fmt: skip
    assert names(browser.get(URL, {"province": ["on"]}).json()) == [
        "Demo — Maple & Pine", "Maple Leaf Supply Ltd.",
    ]  # fmt: skip
    ranged = browser.get(URL, {"created_from": "2026-10-02", "created_to": "2026-11-06"}).json()
    assert names(ranged) == ["Érable Bakery Inc.", "Maple Leaf Supply Ltd."]  # inclusive
    combined = browser.get(URL, {"province": "ON", "status": "active", "package": "growth"}).json()
    assert names(combined) == ["Maple Leaf Supply Ltd."]
    assert names(browser.get(URL, {"q": "erable"}).json()) == ["Érable Bakery Inc."]
    row = combined["results"][0]
    assert (row["package"], row["province"], row["subscription_status"]) == (
        "growth",
        "ON",
        "active",
    )


def test_pagination(world: dict[str, Organisation]) -> None:
    browser = staff()
    first = browser.get(URL, {"page_size": 3}).json()
    second = browser.get(URL, {"page_size": 3, "page": 2}).json()
    assert (first["count"], first["pages"], len(first["results"])) == (4, 2, 3)
    assert names(second) == ["Cedar Roofing Co."]
    assert browser.get(URL, {"page": 5, "page_size": 3}).json()["results"] == []


@pytest.mark.parametrize(
    ("param", "value"),
    [("status", "paid"), ("created_from", "02/10/2026"), ("page_size", "500"), ("page", "0")],
)
def test_bad_values_are_400(world: dict[str, Organisation], param: str, value: str) -> None:
    response = staff().get(URL, {param: value})
    assert response.status_code == 400
    assert (response.json()["code"], response.json()["field"]) == ("platform.bad_filter", param)


def test_practices(world: dict[str, Organisation]) -> None:
    admin = user("admin@cpa.ca")
    firm = practice("Abuodeh CPA", admin)
    member(firm, user("sam@cpa.ca"))
    PracticeAssignment.objects.create(practice=firm, organisation=world["maple"])
    PracticeAssignment.objects.create(practice=firm, organisation=world["cedar"], active=False)
    practice("Empty Practice")
    body = staff().get("/api/v1/platform/practices", {"q": "abuodeh"}).json()
    assert [(r["name"], r["staff_count"], r["client_count"]) for r in body["results"]] == [
        ("Abuodeh CPA", 2, 1)
    ]


def test_only_platform_staff(world: dict[str, Organisation]) -> None:
    outsider = Client()
    outsider.force_login(user("dana@refined.ca"))
    owner = staff("platform_owner")
    for path in (URL, "/api/v1/platform/practices"):
        assert outsider.get(path).status_code == 403
        assert outsider.get(path).json()["code"] == "permission.denied"
        assert owner.get(path).status_code == 200

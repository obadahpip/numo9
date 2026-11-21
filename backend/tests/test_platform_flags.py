"""U-06-T12 — feature flags admin (django-waffle) per organisation / practice / percentage.

Acceptance: flag toggles reflect in ``/me/flags`` — on/off for everyone, by organisation (URL or
``X-Numo9-Org``), by practice (a practice the user belongs to), by a stable percentage of
organisations; each change audited; only ``platform.flags.manage`` edits flags.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from numo9.audit.models import AuditEvent
from numo9.platform.models import FeatureFlag, percent_bucket
from numo9.tenancy.models import Organisation, OrganisationMember
from tests.test_platform_lists import staff
from tests.workspace_helpers import member, practice, user

pytestmark = pytest.mark.django_db(transaction=True)
ADMIN = "/api/v1/platform/flags"
ME = "/api/v1/me/flags"


@pytest.fixture
def world() -> dict[str, Any]:
    maple = Organisation.objects.create(name="Maple")
    birch = Organisation.objects.create(name="Birch")
    dana = user("dana@maple.ca")
    for org in (maple, birch):
        OrganisationMember.objects.create(organisation=org, user=dana, role="owner")
    firm = practice("Abuodeh CPA")
    accountant = user("sara@cpa.ca")
    member(firm, accountant)
    browser = Client()
    browser.force_login(dana)
    sara = Client()
    sara.force_login(accountant)
    return {"maple": maple, "birch": birch, "firm": firm, "dana": browser, "sara": sara}


def flags(browser: Client, org: Organisation | None = None) -> dict[str, bool]:
    headers = {"X-Numo9-Org": str(org.public_id)} if org else {}
    response = browser.get(ME, headers=headers)
    assert response.status_code == 200, response.content
    answer: dict[str, bool] = response.json()["flags"]
    return answer


def patch(admin: Client, name: str, **body: Any) -> Any:
    response = admin.patch(f"{ADMIN}/{name}", body, content_type="application/json")
    assert response.status_code == 200, response.content
    return response.json()


def test_toggles_reflect_in_me_flags(world: dict[str, Any]) -> None:
    admin = staff("platform_owner")
    created = admin.post(
        ADMIN, {"name": "payroll.t4_screen", "note": "New T4"}, content_type="application/json"
    )
    assert created.status_code == 201 and created.json()["mode"] == "off"
    dana, maple, birch = world["dana"], world["maple"], world["birch"]
    # other flags may exist (auth.social_signin, created off by a migration, A-02-T16)
    assert flags(dana, maple)["payroll.t4_screen"] is False
    assert not any(flags(dana, maple).values())

    patch(admin, "payroll.t4_screen", mode="on")
    assert flags(dana, maple)["payroll.t4_screen"] is True
    assert flags(world["sara"])["payroll.t4_screen"] is True

    body = patch(admin, "payroll.t4_screen", mode="rules", organisations=[str(maple.public_id)])
    assert [o["name"] for o in body["organisations"]] == ["Maple"]
    assert flags(dana, maple)["payroll.t4_screen"] is True
    assert flags(dana, birch)["payroll.t4_screen"] is False
    assert flags(world["sara"])["payroll.t4_screen"] is False

    patch(admin, "payroll.t4_screen", practices=[str(world["firm"].public_id)])
    assert flags(world["sara"])["payroll.t4_screen"] is True

    patch(admin, "payroll.t4_screen", mode="off")
    assert flags(dana, maple)["payroll.t4_screen"] is False


def test_percentage_is_stable_per_organisation(world: dict[str, Any]) -> None:
    admin = staff("platform_owner")
    admin.post(ADMIN, {"name": "beta.reports"}, content_type="application/json")
    patch(admin, "beta.reports", mode="rules", percent="50.0")
    for org in (world["maple"], world["birch"]):
        expected = percent_bucket("beta.reports", org.public_id) < 50
        assert [flags(world["dana"], org)["beta.reports"] for _ in range(3)] == [expected] * 3
    patch(admin, "beta.reports", percent="99.9")
    expected = percent_bucket("beta.reports", world["maple"].public_id) < Decimal("99.9")
    assert flags(world["dana"], world["maple"])["beta.reports"] is expected
    patch(admin, "beta.reports", percent="0")
    assert flags(world["dana"], world["maple"])["beta.reports"] is False


@pytest.mark.parametrize(
    ("body", "code"),
    [
        ({"percent": "100"}, "flags.bad_percent"),
        ({"percent": "12.55"}, "flags.bad_percent"),
        ({"percent": "x"}, "flags.bad_percent"),
        ({"organisations": ["nope"]}, "flags.unknown_target"),
        ({"practices": ["00000000-0000-4000-8000-000000000000"]}, "flags.unknown_target"),
    ],
)
def test_bad_updates(world: dict[str, Any], body: dict[str, Any], code: str) -> None:
    admin = staff("platform_owner")
    admin.post(ADMIN, {"name": "x.flag"}, content_type="application/json")
    response = admin.patch(f"{ADMIN}/x.flag", body, content_type="application/json")
    assert response.status_code == 400 and response.json()["code"] == code


def test_names_and_duplicates(world: dict[str, Any]) -> None:
    admin = staff("platform_owner")
    for bad in ("", "A", "1abc", "has space"):
        response = admin.post(ADMIN, {"name": bad}, content_type="application/json")
        assert response.json()["code"] == "flags.bad_name", bad
    assert (
        admin.post(ADMIN, {"name": "ok.flag"}, content_type="application/json").status_code == 201
    )
    again = admin.post(ADMIN, {"name": "ok.flag"}, content_type="application/json")
    assert again.status_code == 409 and again.json()["code"] == "flags.exists"


def test_changes_are_audited_and_delete_removes(world: dict[str, Any]) -> None:
    admin = staff("platform_owner")
    admin.post(ADMIN, {"name": "audit.me"}, content_type="application/json")
    patch(admin, "audit.me", mode="on")
    assert admin.delete(f"{ADMIN}/audit.me").status_code == 204
    actions = list(
        AuditEvent.platform_events.filter(object_type="platform.FeatureFlag")
        .order_by("created_at")
        .values_list("action", flat=True)
    )
    assert actions == ["platform.flag.created", "platform.flag.updated", "platform.flag.deleted"]
    updated = AuditEvent.platform_events.get(action="platform.flag.updated")
    assert updated.changes["mode"] == ["off", "on"]
    assert not FeatureFlag.objects.exists()
    assert "audit.me" not in flags(world["dana"])


def test_only_flags_managers_edit(world: dict[str, Any]) -> None:
    assert world["dana"].get(ADMIN).status_code in (403, 404)
    assert staff("platform_owner").get(ADMIN).status_code == 200

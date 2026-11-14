"""The console's package fixtures are the real API answers (U-02-T09…T11).

frontend/e2e/fixtures/console-packages.json and console-promo-codes.json feed the Playwright
suites of the package editor, the price timeline and the promo-code screen; this test builds a
fixed scenario on a fixed day (14 Nov 2026) and keeps them equal to
``GET /api/v1/platform/packages`` and ``GET /api/v1/platform/packages/promo-codes``. After an API
change, rewrite them with:

    NUMO9_WRITE_FIXTURES=1 pytest tests/test_packages_fixtures.py
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from django.utils import translation
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.catalogue.models import Product
from numo9.packages.models import (
    Package,
    PackagePrice,
    PackageProduct,
    PackageStatus,
    PromoCode,
    PromoDuration,
    PromoKind,
)
from numo9.rbac.models import Role, RoleAssignment, RoleScope

pytestmark = pytest.mark.django_db

FIXTURES = Path(__file__).resolve().parents[2] / "frontend" / "e2e" / "fixtures"
TODAY = date(2026, 11, 14)
NOW = datetime(2026, 11, 14, 15, 0, tzinfo=UTC)


def package(code: str, names: tuple[str, str], products: list[str], **fields: Any) -> Package:
    status = fields.pop("status", PackageStatus.ACTIVE)
    created = Package.objects.create(
        code=code, name_i18n={"en-CA": names[0], "fr-CA": names[1]}, **fields
    )
    for product in products:
        PackageProduct.objects.create(package=created, product=Product.objects.get(code=product))
    if status != PackageStatus.DRAFT:
        created.status = PackageStatus.ACTIVE
        created.save()
    if status == PackageStatus.RETIRED:
        created.status = status
        created.save()
    return created


def price(pkg: Package, interval: str, cents: int, start: date, end: date | None = None) -> None:
    PackagePrice.objects.create(
        package=pkg, interval=interval, amount_cents=cents, effective_from=start, effective_to=end
    )


def scenario() -> None:
    starter = package(
        "starter",
        ("Starter", "Démarrage"),
        ["accounting"],
        sort=1,
        description_i18n={"en-CA": "Books for a small business."},
        limits={"max_org_users": 3},
    )
    price(starter, "month", 1900, date(2026, 1, 1))
    price(starter, "year", 19000, date(2026, 1, 1))
    growth = package(
        "growth",
        ("Growth", "Croissance"),
        ["accounting", "tax"],
        sort=2,
        description_i18n={"en-CA": "For growing teams that file their own GST/HST."},
        limits={"max_org_users": 10},
        is_founding_eligible=True,
    )
    price(growth, "month", 3900, date(2026, 1, 1), date(2026, 12, 1))
    price(growth, "month", 4900, date(2026, 12, 1))
    price(growth, "year", 46800, date(2026, 1, 1))
    package(
        "complete",
        ("Complete", "Complet"),
        ["accounting", "tax", "payroll", "inventory"],
        sort=3,
        status=PackageStatus.DRAFT,
    )
    legacy = package("legacy", ("Legacy", "Ancien"), ["accounting"], sort=9)
    price(legacy, "month", 2500, date(2025, 1, 1))
    legacy.status = PackageStatus.RETIRED
    legacy.save()

    launch = PromoCode.objects.create(
        code="LAUNCH20",
        description="Launch campaign",
        kind=PromoKind.PERCENT,
        percent_off=20,
        duration=PromoDuration.REPEATING,
        duration_months=3,
        max_redemptions=10,
        expires_at=datetime(2026, 12, 31, 5, 0, tzinfo=UTC),
    )
    launch.packages.set([growth])
    PromoCode.objects.filter(pk=launch.pk).update(redemptions_count=7)
    used = PromoCode.objects.create(
        code="ACCT50",
        kind=PromoKind.FIXED,
        amount_off_cents=5000,
        duration=PromoDuration.ONCE,
        max_redemptions=50,
    )
    PromoCode.objects.filter(pk=used.pk).update(redemptions_count=50)
    forever = PromoCode.objects.create(
        code="FOREVER10", kind=PromoKind.PERCENT, percent_off=10, duration=PromoDuration.FOREVER
    )
    PromoCode.objects.filter(pk=forever.pk).update(redemptions_count=3)
    PromoCode.objects.create(
        code="SPRING",
        kind=PromoKind.PERCENT,
        percent_off=15,
        duration=PromoDuration.ONCE,
        max_redemptions=100,
        expires_at=datetime(2026, 6, 1, 4, 0, tzinfo=UTC),
    )


def normalised(body: Any) -> Any:
    """Fixed ids and timestamps, so the fixture doesn't change from run to run."""
    text = json.dumps(body)
    rows = PackagePrice.objects.order_by("package__sort", "interval", "effective_from")
    for n, price in enumerate(rows, 1):
        text = text.replace(str(price.public_id), f"00000000-0000-4000-8000-{n:012d}")
    return json.loads(text)


def answers() -> dict[str, Any]:
    owner = User.objects.create_user("pat@numo9.ca", name="Pat Owner")
    role = Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key="platform_owner")
    RoleAssignment.objects.create(role=role, user=owner)
    api = APIClient()
    api.force_authenticate(owner)
    with (
        mock.patch("django.utils.timezone.now", return_value=NOW),
        mock.patch("django.utils.timezone.localdate", return_value=TODAY),
        translation.override("en-ca"),
    ):
        scenario()
        packages = api.get("/api/v1/platform/packages", HTTP_ACCEPT_LANGUAGE="en-CA").json()
        promos = api.get(
            "/api/v1/platform/packages/promo-codes", HTTP_ACCEPT_LANGUAGE="en-CA"
        ).json()
    return {
        "console-packages.json": normalised(packages),
        "console-promo-codes.json": normalised(promos),
    }


@pytest.mark.parametrize("name", ["console-packages.json", "console-promo-codes.json"])
def test_fixture_equals_the_api_answer(name: str) -> None:
    answer = answers()[name]
    path = FIXTURES / name
    if os.environ.get("NUMO9_WRITE_FIXTURES"):
        path.write_text(json.dumps(answer, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8")) == answer, f"rewrite {name} (see docstring)"


def test_scenario_covers_every_state() -> None:
    both = answers()
    body = both["console-packages.json"]
    assert {p["status"] for p in body["packages"]} == {"draft", "active", "retired"}
    promos = both["console-promo-codes.json"]
    assert {p["status"] for p in promos["promo_codes"]} == {"active", "used_up", "expired"}

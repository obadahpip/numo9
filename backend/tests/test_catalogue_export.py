"""Feature-matrix export (U-01-T10): CSV/XLSX for the Platform Owner — export rows = DB key
count."""

from __future__ import annotations

import csv
import io
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from openpyxl import load_workbook
from rest_framework.test import APIClient

from numo9.accounts.models import User
from numo9.audit.models import AuditEvent
from numo9.catalogue.models import FeatureKey
from numo9.rbac.models import Role, RoleAssignment, RoleScope

pytestmark = pytest.mark.django_db

EXPORT = "/api/v1/platform/catalogue/feature-matrix/export/"


def platform_user(key: str | None, email: str = "owner@numo9.ca") -> User:
    user = User.objects.create_user(email, name="Pat Owner")
    if key:
        role = Role.objects.get(is_system=True, scope=RoleScope.PLATFORM, key=key)
        RoleAssignment.objects.create(role=role, user=user)
    return user


def client_for(user: User) -> APIClient:
    api = APIClient()
    api.force_authenticate(user)
    return api


@pytest.fixture
def owner() -> APIClient:
    return client_for(platform_user("platform_owner"))


def csv_rows(body: bytes) -> list[list[str]]:
    text = body.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text[1:])))


def test_csv_rows_equal_the_database_key_count(owner: APIClient) -> None:
    response = owner.get(f"{EXPORT}csv")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert 'attachment; filename="numo9-feature-matrix_' in response["Content-Disposition"]
    header, *rows = csv_rows(response.content)
    assert header == [
        "Product",
        "Product code",
        "Feature key",
        "Description",
        "Area",
        "Action",
        "Read-only",
    ]
    assert len(rows) == FeatureKey.objects.count()
    assert {r[2] for r in rows} == set(FeatureKey.objects.values_list("key", flat=True))
    first = rows[0]
    assert first[:3] == ["Accounting", "accounting", first[2]] and first[5] in {"read", "write"}


def test_xlsx_rows_equal_the_database_key_count(owner: APIClient) -> None:
    response = owner.get(f"{EXPORT}xlsx")
    assert response.status_code == 200
    sheet = load_workbook(io.BytesIO(response.content)).active
    values = list(sheet.iter_rows(values_only=True))
    assert values[0][2] == "Feature key"
    assert len(values) - 1 == FeatureKey.objects.count()
    assert sheet.title == "Feature matrix"


def test_package_columns_tick_the_packages_of_each_product(owner: APIClient, settings: Any) -> None:
    settings.NUMO9_PACKAGE_SOURCE = "tests.test_catalogue_api.TwoPackages"
    header, *rows = csv_rows(owner.get(f"{EXPORT}csv").content)
    assert header[-2:] == ["Starter", "Complete"]
    by_key = {r[2]: r for r in rows}
    assert by_key["accounting.bills.write"][-2:] == ["Yes", "Yes"]
    assert by_key["tax.codes.read"][-2:] == ["", "Yes"]


def test_formula_like_text_is_neutralised(owner: APIClient, monkeypatch: Any) -> None:
    from numo9.catalogue import texts

    monkeypatch.setitem(texts.FEATURE_DESCRIPTIONS, "catalogue.feature.tax.codes.read", "=1+1")
    _header, *rows = csv_rows(owner.get(f"{EXPORT}csv").content)
    assert next(r for r in rows if r[2] == "tax.codes.read")[3] == "'=1+1"


def test_platform_owner_only_and_formats(owner: APIClient) -> None:
    assert APIClient().get(f"{EXPORT}csv").status_code in {401, 403}
    plain = client_for(platform_user(None, "dana@maple.ca"))
    assert plain.get(f"{EXPORT}csv").status_code == 403
    support = client_for(platform_user("platform_support", "sam@numo9.ca"))
    assert support.get(f"{EXPORT}csv").status_code == 403
    bad = owner.get(f"{EXPORT}pdf")
    assert bad.status_code == 400 and bad.json()["code"] == "catalogue.export_format"


def test_export_is_recorded_in_the_platform_audit_log(owner: APIClient) -> None:
    owner.get(f"{EXPORT}xlsx")
    event = AuditEvent.platform_events.get(action="catalogue.matrix.exported")
    assert event.organisation is None
    assert event.meta["format"] == "xlsx"
    assert event.meta["rows"] == FeatureKey.objects.count()


def test_export_in_french() -> None:
    user = platform_user("platform_owner")
    user.locale = "fr-ca"
    user.save()
    _header, *rows = csv_rows(client_for(user).get(f"{EXPORT}csv").content)
    # French text arrives in Phase 6; product names already translated show the language used.
    assert next(r for r in rows if r[1] == "tax")[0] == "Taxes"


def test_management_command(tmp_path: Path) -> None:
    out = StringIO()
    target = tmp_path / "matrix.xlsx"
    call_command("featurematrix_export", "--format", "xlsx", "--output", str(target), stdout=out)
    sheet = load_workbook(target).active
    assert sheet.max_row - 1 == FeatureKey.objects.count()


def test_console_products_for_platform_staff_with_the_permission(owner: APIClient) -> None:
    url = "/api/v1/platform/catalogue/products"
    body = owner.get(url).json()
    assert len(body["products"]) == 10
    assert all("features" in p for p in body["products"])
    refused = client_for(platform_user(None, "dana@maple.ca")).get(url)
    assert refused.status_code == 403
    assert refused.json()["code"] == "permission.denied"

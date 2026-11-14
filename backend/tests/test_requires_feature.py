"""@requires_feature + RequiresFeature (U-01-T05): a decorated view exposes `required_feature`;
the permission asks the entitlement resolver (stub until U-03) and answers 402 naming the
product when the key isn't in the package."""

from __future__ import annotations

from typing import Any

import pytest
from django.conf import settings as django_settings
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from numo9.catalogue.drf import (
    ATTRIBUTE,
    CORE,
    RequiresFeature,
    declared_feature,
    requires_feature,
)
from numo9.catalogue.entitlements import AllowAllResolver, get_resolver
from numo9.rbac.drf import PUBLIC

factory = APIRequestFactory()


class DenyAll:
    calls: list[tuple[Any, str]] = []

    def allows(self, organisation: Any, key: str) -> bool:
        DenyAll.calls.append((organisation, key))
        return False


class Invoices(APIView):
    permission_classes = [RequiresFeature]
    required_permission = PUBLIC

    @requires_feature("accounting.sales_invoices.read")
    def get(self, request: Request) -> Response:
        return Response({"ok": True})

    @requires_feature("accounting.sales_invoices.write")
    def post(self, request: Request) -> Response:
        return Response({"ok": True})

    def delete(self, request: Request) -> Response:  # undeclared: the CI check's job
        return Response({"ok": True})


class Roles(APIView):
    permission_classes = [RequiresFeature]
    required_permission = PUBLIC
    required_feature = CORE

    def get(self, request: Request) -> Response:
        return Response({"ok": True})


class PerMethod(APIView):
    required_feature = {"GET": "tax.returns.read", "POST": "tax.returns.write"}


def test_decorated_view_exposes_required_feature() -> None:
    assert getattr(Invoices.get, ATTRIBUTE) == "accounting.sales_invoices.read"
    assert Invoices.post.required_feature == "accounting.sales_invoices.write"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("view", "method", "expected"),
    [
        (Invoices, "GET", "accounting.sales_invoices.read"),
        (Invoices, "head", "accounting.sales_invoices.read"),
        (Invoices, "OPTIONS", "accounting.sales_invoices.read"),
        (Invoices, "POST", "accounting.sales_invoices.write"),
        (Invoices, "DELETE", None),
        (Roles, "GET", CORE),
        (Roles, "POST", CORE),
        (PerMethod, "GET", "tax.returns.read"),
        (PerMethod, "POST", "tax.returns.write"),
        (PerMethod, "DELETE", None),
    ],
)
def test_declared_feature(view: type, method: str, expected: str | None) -> None:
    assert declared_feature(view, method) == expected


def test_default_resolver_is_the_allow_all_stub() -> None:
    assert django_settings.NUMO9_ENTITLEMENT_RESOLVER.endswith("AllowAllResolver")
    assert isinstance(get_resolver(), AllowAllResolver)
    assert (
        "numo9.catalogue.drf.RequiresFeature"
        in (django_settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"])
    )


def test_stub_allows_every_declared_key() -> None:
    assert Invoices.as_view()(factory.get("/")).status_code == 200
    assert Invoices.as_view()(factory.post("/")).status_code == 200


def test_not_in_package_answers_402_naming_the_product(settings: Any) -> None:
    settings.NUMO9_ENTITLEMENT_RESOLVER = "tests.test_requires_feature.DenyAll"
    DenyAll.calls.clear()
    response = Invoices.as_view()(factory.post("/"))
    assert response.status_code == 402
    assert response.data["code"] == "entitlement.feature_not_in_package"
    assert response.data["feature"] == "accounting.sales_invoices.write"
    assert response.data["product"] == "accounting"
    assert "part of Accounting" in str(response.data["detail"])
    assert DenyAll.calls == [(None, "accounting.sales_invoices.write")]


def test_core_and_undeclared_methods_never_reach_the_resolver(settings: Any) -> None:
    settings.NUMO9_ENTITLEMENT_RESOLVER = "tests.test_requires_feature.DenyAll"
    DenyAll.calls.clear()
    assert Roles.as_view()(factory.get("/")).status_code == 200
    assert Invoices.as_view()(factory.delete("/")).status_code == 200
    assert Invoices.as_view()(factory.put("/")).status_code == 405
    assert DenyAll.calls == []

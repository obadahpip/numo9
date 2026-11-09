"""A-01-T04 — OrgScopedManager: every query limited to current_org(), TenantContextMissing
without a context, create() bound to the active organisation, unscoped() explicit and logged."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import pytest
from django.db.models import ProtectedError
from django.test import Client

from numo9.tenancy.context import TenantContextMissing, org_context
from numo9.tenancy.managers import OrgScopedManager
from numo9.tenancy.models import Organisation
from tests.testapp.models import Gadget, Widget

pytestmark = pytest.mark.django_db


@pytest.fixture
def org_a() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery")


@pytest.fixture
def org_b() -> Organisation:
    return Organisation.objects.create(name="Birch Garage")


@pytest.fixture
def rows(org_a: Organisation, org_b: Organisation) -> None:
    with org_context(org_a):
        Widget.objects.create(label="a1")
        Widget.objects.create(label="a2")
    with org_context(org_b):
        Widget.objects.create(label="b1")


def test_default_manager_of_every_subclass_is_scoped() -> None:
    for model in (Widget, Gadget):
        assert isinstance(model.objects, OrgScopedManager)
        assert model._default_manager is model.objects
    assert OrgScopedManager.use_in_migrations is False


@pytest.mark.parametrize(
    "query",
    [
        lambda: Widget.objects.all(),
        lambda: Widget.objects.filter(label="a1"),
        lambda: Widget.objects.count(),
        lambda: Widget.objects.exists(),
        lambda: Widget.objects.get(label="a1"),
        lambda: Widget.objects.update(label="x"),
        lambda: Widget.objects.create(label="x"),
    ],
)
def test_query_without_context_raises(rows: None, query: Callable[[], Any]) -> None:
    with pytest.raises(TenantContextMissing, match="testapp.Widget"):
        query()


def test_queries_see_only_the_active_organisation(
    rows: None, org_a: Organisation, org_b: Organisation
) -> None:
    with org_context(org_a):
        assert sorted(Widget.objects.values_list("label", flat=True)) == ["a1", "a2"]
        assert Widget.objects.count() == 2
    with org_context(org_b):
        assert list(Widget.objects.values_list("label", flat=True)) == ["b1"]


def test_other_organisations_row_is_not_found_by_id(
    rows: None, org_a: Organisation, org_b: Organisation
) -> None:
    with org_context(org_b):
        b1 = Widget.objects.get(label="b1")
    with org_context(org_a):
        with pytest.raises(Widget.DoesNotExist):
            Widget.objects.get(pk=b1.pk)
        with pytest.raises(Widget.DoesNotExist):
            Widget.objects.get(public_id=b1.public_id)


def test_bulk_update_and_delete_stay_in_the_active_organisation(
    rows: None, org_a: Organisation, org_b: Organisation
) -> None:
    with org_context(org_a):
        assert Widget.objects.update(label="changed") == 2
        Widget.objects.filter(label="changed").delete()
    with org_context(org_b):
        assert list(Widget.objects.values_list("label", flat=True)) == ["b1"]


def test_create_fills_the_active_organisation(org_a: Organisation) -> None:
    with org_context(org_a):
        widget = Widget.objects.create(label="w")
    assert widget.organisation == org_a


def test_create_accepts_the_active_organisation_explicitly(org_a: Organisation) -> None:
    with org_context(org_a):
        assert Widget.objects.create(label="w", organisation=org_a).organisation == org_a
        assert Widget.objects.create(label="v", organisation_id=org_a.pk).organisation == org_a


def test_create_for_another_organisation_is_refused(
    org_a: Organisation, org_b: Organisation
) -> None:
    with org_context(org_a):
        with pytest.raises(ValueError, match="another organisation"):
            Widget.objects.create(label="w", organisation=org_b)
        with pytest.raises(ValueError, match="another organisation"):
            Widget.objects.create(label="w", organisation_id=org_b.pk)
        assert Widget.objects.count() == 0
    assert Widget.objects.unscoped(reason="test check").count() == 0


def test_unscoped_sees_every_organisation_and_is_logged(
    rows: None, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="numo9.tenancy.unscoped"):
        labels = Widget.objects.unscoped(reason="platform report").values_list("label", flat=True)
        assert sorted(labels) == ["a1", "a2", "b1"]
    record = caplog.records[-1]
    assert record.name == "numo9.tenancy.unscoped"
    assert "testapp.Widget" in record.getMessage() and "platform report" in record.getMessage()
    assert record.reason == "platform report"  # type: ignore[attr-defined]


@pytest.mark.parametrize("reason", ["", "   "])
def test_unscoped_requires_a_reason(reason: str) -> None:
    with pytest.raises(ValueError, match="reason"):
        Widget.objects.unscoped(reason=reason)


def test_reverse_relation_is_scoped_too(
    rows: None, org_a: Organisation, org_b: Organisation
) -> None:
    with pytest.raises(TenantContextMissing):
        org_a.testapp_widget_set.count()
    with org_context(org_a):
        assert org_a.testapp_widget_set.count() == 2
    with org_context(org_b):
        assert org_a.testapp_widget_set.count() == 0  # never another tenant's rows


def test_django_internals_work_without_context(rows: None, org_a: Organisation) -> None:
    widget = Widget.objects.unscoped(reason="test setup").filter(organisation=org_a).first()
    assert widget is not None
    widget.refresh_from_db()  # base manager
    widget.label = "saved outside a request"
    widget.save()
    assert widget.organisation == org_a  # forward foreign key
    with pytest.raises(ProtectedError):
        org_a.delete()  # deletion collector


def test_request_lists_only_its_organisations_rows(
    rows: None, org_a: Organisation, org_b: Organisation, settings: Any
) -> None:
    settings.ROOT_URLCONF = "tests.testapp.urls"
    client = Client()
    assert client.get(f"/o/{org_a.public_id}/widgets/").json() == {"labels": ["a1", "a2"]}
    assert client.get(f"/o/{org_b.public_id}/widgets/").json() == {"labels": ["b1"]}
    with pytest.raises(TenantContextMissing):
        client.get("/widgets/")  # no organisation in the request

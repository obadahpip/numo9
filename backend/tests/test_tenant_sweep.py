"""A-01-T09 — manage.py tenant_sweep: every endpoint classified, organisation-scoped ones requested
as another organisation's user for every verb (expect 404), report lists all endpoints."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from numo9.tenancy.models import Organisation
from numo9.tenancy.sweep import Endpoint, build_path, iter_endpoints, run_sweep
from tests.testapp.models import Widget

pytestmark = [pytest.mark.django_db, pytest.mark.tenant_isolation]

CLEAN = "tests.testapp.sweep_urls"


def sweep(urlconf: str, *exempt: str) -> tuple[str, CommandError | None]:
    out = StringIO()
    try:
        call_command("tenant_sweep", urlconf=urlconf, exempt=list(exempt), stdout=out)
    except CommandError as exc:
        return out.getvalue(), exc
    return out.getvalue(), None


def test_project_urlconf_has_no_leaks() -> None:
    report, error = sweep("numo9.urls")
    assert error is None, report
    assert "healthz" in report and "admin/" in report


def test_clean_api_passes_and_report_lists_every_endpoint() -> None:
    report, error = sweep(CLEAN, r"^ping/$")
    assert error is None, report
    assert "4 endpoints — 3 organisation-scoped, 1 exempt, 0 failing" in report
    for route in (
        "/ping/",
        "/api/v1/o/<uuid:org>/widgets/ ",
        "/api/v1/o/<uuid:org>/widgets/<uuid:public_id>/",
        "/api/v1/o/<uuid:org>/unscoped-widgets/<uuid:public_id>/",
    ):
        assert route in report
    detail = next(line for line in report.splitlines() if "/widgets/<uuid:public_id>" in line)
    for status in ("org1:GET=404", "org1:DELETE=404", "org2+org1-id:GET=404", "own:GET=200"):
        assert status in detail


def test_leaky_endpoint_fails_the_sweep() -> None:
    report, error = sweep("tests.testapp.sweep_urls_leaky", r"^ping/$")
    assert error is not None
    leaky = [line for line in report.splitlines() if "leaky-widgets" in line]
    assert leaky and leaky[0].startswith("FAIL")
    assert "org1:GET=200" in leaky[0]
    assert "expected 404" in report
    assert "1 failing" in report


def test_endpoint_without_organisation_must_be_exempt() -> None:
    report, error = sweep("tests.testapp.sweep_urls_unclassified", r"^ping/$")
    assert error is not None
    assert "not organisation-scoped and not on the exempt list" in report
    report, error = sweep(
        "tests.testapp.sweep_urls_unclassified", r"^ping/$", r"^api/v1/widgets-everywhere/"
    )
    assert error is None, report


def test_pattern_without_named_org_group_fails() -> None:
    report, error = sweep("tests.testapp.sweep_urls_unbuildable", r"^ping/$")
    assert error is not None
    assert "URL could not be built" in report


def test_sweep_rolls_back_everything() -> None:
    before = Organisation.objects.count()
    run_sweep(CLEAN, (r"^ping/$",))
    assert Organisation.objects.count() == before
    assert Widget.objects.unscoped(reason="test: rollback check").count() == 0


def test_build_path_fills_named_groups_and_validates() -> None:
    endpoints = {e.route: e for e in iter_endpoints(CLEAN)}
    route = next(
        r
        for r in endpoints
        if r.endswith(
            "widgets/(?P<public_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/"
        )
    )
    org_id = "6f1c2a9e-0000-4000-8000-000000000001"
    obj_id = "6f1c2a9e-0000-4000-8000-000000000002"
    assert build_path(endpoints[route], {"org": org_id, "public_id": obj_id}) == (
        f"/api/v1/o/{org_id}/widgets/{obj_id}/"
    )
    assert build_path(endpoints[route], {"org": "not-a-uuid", "public_id": obj_id}) is None
    assert build_path(endpoints[route], {"org": org_id}) is None
    assert build_path(Endpoint(route="o/[^/]+/x/", callback=print), {}) is None

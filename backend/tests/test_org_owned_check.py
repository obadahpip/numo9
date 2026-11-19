"""A-01-T08 — system check tenancy.E001: every model in a business app inherits OrgOwnedModel,
except the allow-listed platform models."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.apps import apps
from django.core.management import call_command
from django.db import models
from django.test.utils import isolate_apps

from numo9.tenancy.checks import (
    PLATFORM_MODELS,
    check_business_models_are_org_owned,
    models_violating_org_ownership,
)
from numo9.tenancy.models import OrgOwnedModel

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_current_project_passes() -> None:
    assert check_business_models_are_org_owned() == []
    call_command("check")  # raises SystemCheckError on any error


def test_platform_allow_list_is_exactly_the_tenancy_and_user_models() -> None:
    assert (
        frozenset(
            {
                "accounts.User",
                # Known sign-in devices (A-02-T07): reviewed — a hash per browser/system.
                "accounts.KnownDevice",
                "tenancy.Practice",
                # Usage metering (S-06-T07): reviewed — the aggregator's stream position.
                "metering.StreamOffset",
                # Demo templates (U-07-T05): reviewed — which template serves a seed version.
                "demo.DemoTemplate",
                "tenancy.PracticeMember",
                "tenancy.Organisation",
                "tenancy.OrganisationMember",
                "tenancy.PracticeAssignment",
                "tenancy.Invitation",
                # Roles (A-03-T02): reviewed — no organisation business data.
                "rbac.Role",
                "rbac.RolePermission",
                "rbac.RoleAssignment",
                # Product catalogue (U-01-T02/T03): reviewed — the same for every tenant.
                "catalogue.Product",
                "catalogue.FeatureKey",
                # Free trial (U-05-T01/T02): reviewed — platform settings and the trial registry.
                "entitlements.TrialConfig",
                "entitlements.TrialRegistry",
                # Platform console (U-06-T05): reviewed — daily platform-wide metrics.
                "platform.PlatformMetricDaily",
                # Impersonation (U-06-T08): reviewed — staff sessions, read by the platform only.
                "platform.ImpersonationSession",
                # Feature flags (U-06-T12): reviewed — platform switches, no tenant data.
                "platform.FeatureFlag",
                "waffle.Switch",
                "waffle.Sample",
                # Packages (U-02-T02, T03, T06): reviewed — packages, prices, promo codes.
                "packages.Package",
                "packages.PackageProduct",
                "packages.PackagePrice",
                "packages.PromoCode",
                # CRA GIFI list (C-01-T04): reviewed — published codes, the same for every tenant.
                "ledger.GifiCode",
                # Organisation directory (V-01-T02): reviewed — derived read model of directory
                # facts, read only through workspace.search's access scope.
                "workspace.OrgDirectorySummary",
                # Saved directory views (V-01-T08): reviewed — a user's filter state, no records.
                "workspace.SavedView",
                # Practice email branding (A-07-T04): reviewed — name, logo address, colour.
                "notifications.PracticeBranding",
                # Email suppression list (A-07-T08): reviewed — an address and a reason.
                "notifications.EmailSuppression",
                # Stripe webhook events (U-04-T03): reviewed — Stripe's event log, idempotency.
                "billing.StripeEvent",
                # Practice groups (V-02-T02): reviewed — a practice's tree and its filing.
                "workspace.OrgGroup",
                "workspace.OrgGroupMembership",
                # Practice tags (V-02-T03): reviewed — labels and which clients carry them.
                "workspace.Tag",
                "workspace.OrgTag",
                # Group staff (V-02-T04): reviewed — practice member, group, role.
                "workspace.GroupStaffAssignment",
                # Bulk actions (V-03-T02): reviewed — practice jobs, one row per organisation.
                "bulk.BulkJob",
                "bulk.BulkJobRow",
                # Practice staff (V-05-T06): reviewed — practice-level alert log.
                "staff.DormantAlert",
                # Staff activity (V-05-T07): reviewed — per-user counts, no tenant data.
                "staff.StaffActivityDaily",
            }
        )
        == PLATFORM_MODELS
    )
    for label in PLATFORM_MODELS:
        assert apps.get_model(label) is not None  # no stale entries


def test_project_business_models_are_org_owned() -> None:
    checked = [
        model
        for config in apps.get_app_configs()
        if config.name.startswith(("numo9.", "tests."))
        for model in config.get_models()
        if model._meta.label not in PLATFORM_MODELS
    ]
    assert checked  # the test app's Widget/Gadget are covered
    assert all(issubclass(model, OrgOwnedModel) for model in checked)


def test_plain_model_is_reported_and_org_owned_or_abstract_or_proxy_are_not() -> None:
    with isolate_apps("tests.testapp") as isolated:

        class Plain(models.Model):  # noqa: DJ008
            class Meta:
                app_label = "testapp"

        class Owned(OrgOwnedModel):
            class Meta:
                app_label = "testapp"

        class AbstractBase(models.Model):
            class Meta:
                app_label = "testapp"
                abstract = True

        class OwnedProxy(Owned):
            class Meta:
                app_label = "testapp"
                proxy = True

        assert isolated is not None
        config = isolated.get_app_config("testapp")
        found = models_violating_org_ownership([config], ["tests."])
        assert [model.__name__ for model in found] == ["Plain"]
        assert models_violating_org_ownership([config], ["numo9."]) == []  # not a business app


def test_adding_a_plain_model_fails_manage_py_check() -> None:
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "tests.settings_plain_model"}
    result = subprocess.run(
        [sys.executable, "manage.py", "check"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode != 0
    assert "tenancy.E001" in result.stderr
    assert "plain_model_app.Invoice" in result.stderr

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
                "tenancy.Practice",
                "tenancy.PracticeMember",
                "tenancy.Organisation",
                "tenancy.OrganisationMember",
                "tenancy.PracticeAssignment",
                "tenancy.Invitation",
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

"""System check: every business model inherits OrgOwnedModel (A-01-T08).

A model in a business app (an installed app whose module starts with one of
``settings.TENANCY_BUSINESS_APP_PREFIXES``, default ``("numo9.",)``) that is not an
``OrgOwnedModel`` and is not on the platform allow-list fails ``manage.py check`` with
``tenancy.E001``. Without this rule a plain ``models.Model`` would bypass the organisation
scoping of ``OrgScopedManager`` and leak data between tenants.

Platform models — the tenants themselves and their users — are listed in ``PLATFORM_MODELS``.
Adding to the list is a reviewed change: the model must not hold one organisation's data.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from django.apps import AppConfig, apps
from django.conf import settings
from django.core import checks
from django.db import models

PLATFORM_MODELS: frozenset[str] = frozenset(
    {
        "accounts.User",
        "tenancy.Practice",
        "tenancy.PracticeMember",
        "tenancy.Organisation",
        "tenancy.OrganisationMember",
        "tenancy.PracticeAssignment",
    }
)

DEFAULT_BUSINESS_APP_PREFIXES: tuple[str, ...] = ("numo9.",)


def business_app_prefixes() -> tuple[str, ...]:
    return tuple(getattr(settings, "TENANCY_BUSINESS_APP_PREFIXES", DEFAULT_BUSINESS_APP_PREFIXES))


def models_violating_org_ownership(
    app_configs: Iterable[AppConfig], prefixes: Sequence[str]
) -> list[type[models.Model]]:
    """Concrete models of business apps that neither inherit OrgOwnedModel nor are allow-listed."""
    from .models import OrgOwnedModel

    violations: list[type[models.Model]] = []
    for app_config in app_configs:
        if not app_config.name.startswith(tuple(prefixes)):
            continue
        # get_models() skips abstract models and auto-created many-to-many tables.
        for model in app_config.get_models():
            if model._meta.proxy or model._meta.label in PLATFORM_MODELS:
                continue
            if not issubclass(model, OrgOwnedModel):
                violations.append(model)
    return violations


def check_business_models_are_org_owned(
    app_configs: Sequence[AppConfig] | None = None, **kwargs: Any
) -> list[checks.CheckMessage]:
    configs = app_configs if app_configs is not None else apps.get_app_configs()
    return [
        checks.Error(
            f"{model._meta.label} is a business model but does not inherit OrgOwnedModel.",
            hint=(
                "Inherit numo9.tenancy.models.OrgOwnedModel so every row belongs to one "
                "organisation and queries are scoped. Only models that hold no organisation's "
                "data may be added to PLATFORM_MODELS in numo9/tenancy/checks.py."
            ),
            obj=model,
            id="tenancy.E001",
        )
        for model in models_violating_org_ownership(configs, business_app_prefixes())
    ]

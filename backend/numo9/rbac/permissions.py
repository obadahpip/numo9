"""Permissions of roles, approval limits and the platform console (A-03-T01)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from .catalogue import Permission, Risk, Scope, register

ROLES_VIEW = register(
    Permission("roles.role.view", _("View roles and what they allow"), "users", Risk.LOW)
)
ROLES_MANAGE = register(
    Permission("roles.role.manage", _("Create and edit custom roles"), "users", Risk.CRITICAL)
)
ROLES_ASSIGN = register(
    Permission("roles.assignment.manage", _("Give and remove roles"), "users", Risk.CRITICAL)
)
LIMITS_VIEW = register(Permission("roles.limit.view", _("View approval limits"), "users", Risk.LOW))
LIMITS_MANAGE = register(
    Permission("roles.limit.manage", _("Set approval limits"), "users", Risk.CRITICAL)
)
PRACTICE_ROLES_MANAGE = register(
    Permission(
        "practice.roles.manage",
        _("Create, edit and give the practice's roles"),
        "practice",
        Risk.CRITICAL,
        Scope.PRACTICE,
    )
)

PLATFORM = Scope.PLATFORM
CONSOLE_VIEW = register(
    Permission(
        "platform.console.view", _("Open the platform console"), "platform", Risk.HIGH, PLATFORM
    )
)
CATALOGUE_MANAGE = register(
    Permission(
        "platform.catalogue.manage",
        _("Manage products, packages and prices"),
        "platform",
        Risk.CRITICAL,
        PLATFORM,
    )
)
IMPERSONATE = register(
    Permission(
        "platform.impersonate",
        _("Sign in as a user for support (time-limited, audited)"),
        "platform",
        Risk.CRITICAL,
        PLATFORM,
    )
)
JOBS_VIEW = register(
    Permission(
        "platform.jobs.view",
        _("See background jobs and failures"),
        "platform",
        Risk.MEDIUM,
        PLATFORM,
    )
)
JOBS_MANAGE = register(
    Permission(
        "platform.jobs.manage", _("Retry or purge background jobs"), "platform", Risk.HIGH, PLATFORM
    )
)
FLAGS_MANAGE = register(
    Permission(
        "platform.flags.manage", _("Turn feature flags on and off"), "platform", Risk.HIGH, PLATFORM
    )
)

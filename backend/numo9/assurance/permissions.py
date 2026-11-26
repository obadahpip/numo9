"""Permissions of the exceptions engine (K-09-T20)."""

from __future__ import annotations

from django.utils.translation import gettext_lazy as _

from numo9.rbac.catalogue import Permission, Risk, register

ASSURANCE_VIEW = register(
    Permission(
        "accounting.assurance.view",
        _("See the assurance score, findings and the activity heatmap"),
        "accounting",
        Risk.LOW,
    )
)

ASSURANCE_MANAGE = register(
    Permission(
        "accounting.assurance.manage",
        _(
            "Run the assurance checks, acknowledge findings or mark them false positives, draft "
            "fixes and change the rule settings"
        ),
        "accounting",
        Risk.MEDIUM,
    )
)

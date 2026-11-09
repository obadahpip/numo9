"""Organisation-scoped default manager for business models (A-01-T04).

``OrgScopedManager`` is the default ``objects`` manager of every ``OrgOwnedModel``:

- every query is filtered to ``current_org()``; with no active organisation the query raises
  ``TenantContextMissing`` instead of silently returning every tenant's rows;
- ``create()`` fills ``organisation`` from the context and refuses a different organisation;
- ``unscoped(reason)`` is the only way around the filter (platform jobs, reports across
  organisations); the reason is mandatory and every call is logged.

Django's own machinery (deletion checks, ``refresh_from_db``, forward foreign keys) uses the
plain base manager, so it keeps working outside a request.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, TypeVar

from django.db import models

from .context import TenantContextMissing, current_org

if TYPE_CHECKING:
    from .models import OrgOwnedModel

logger = logging.getLogger("numo9.tenancy.unscoped")

_M = TypeVar("_M", bound="OrgOwnedModel")


class OrgScopedManager(models.Manager[_M]):
    # Historical models in migrations get a plain manager (no request context there).
    use_in_migrations = False

    def get_queryset(self) -> models.QuerySet[_M]:
        organisation = current_org()
        if organisation is None:
            raise TenantContextMissing(
                f"{self.model._meta.label} queried without an active organisation; "
                "run inside org_context() or use .unscoped(reason=...)."
            )
        return super().get_queryset().filter(organisation=organisation)

    def create(self, **kwargs: Any) -> _M:
        organisation = current_org()
        if organisation is None:
            raise TenantContextMissing(
                f"{self.model._meta.label} created without an active organisation."
            )
        if "organisation" in kwargs:
            given_id = getattr(kwargs["organisation"], "pk", kwargs["organisation"])
        elif "organisation_id" in kwargs:
            given_id = kwargs["organisation_id"]
        else:
            kwargs["organisation"] = organisation
            given_id = organisation.pk
        if given_id != organisation.pk:
            raise ValueError(
                f"Cannot create {self.model._meta.label} for another organisation "
                "than the active one."
            )
        return super().get_queryset().create(**kwargs)

    def unscoped(self, *, reason: str) -> models.QuerySet[_M]:
        """All organisations' rows. Explicit and logged; ``reason`` says why it is needed."""
        if not reason or not reason.strip():
            raise ValueError("unscoped() requires a reason.")
        logger.warning(
            "Unscoped query on %s: %s",
            self.model._meta.label,
            reason,
            extra={"model": self.model._meta.label, "reason": reason},
        )
        return super().get_queryset()

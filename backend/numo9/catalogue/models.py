"""Product catalogue (U-01): products and the feature keys they own.

``Product`` — something Numo9 sells or gives: a **main** product (Accounting, Tax, Payroll,
Inventory, Finance), a **free set** (Practice, Portal — never billable) or a **companion** app
Numo9 will build (``app.commerce`` …, planned). Packages (U-02) are made of whole products.

Rules (docs/architecture/feature-keys.md):

- ``code`` is unique and immutable — feature keys start with it, packages and subscriptions
  refer to it. The display name is an i18n key (``catalogue.product.<code>``), so renaming a
  product changes text only;
- a ``retired`` product is never deleted (organisations that had it keep its history); a
  product that owns feature keys cannot be deleted at all (``PROTECT``).

``FeatureKey`` — one gated capability, ``<product>.<area>.<action>`` with action ``read``,
``write`` or ``approve`` (``accounting.sales_invoices.write``). The key is unique in the database,
so it can never belong to two products; the plan's ``ProductFeature`` relation is this foreign
key. ``is_read_only`` is true exactly for ``*.read`` keys (they survive a downgrade, U-03).

The catalogue holds no organisation's data: platform models (tenancy allow-list). Every change
to a product or a feature key — status, sort, name key, a new key — writes its field diff to the
**platform** audit log (``AuditedModel``, U-01-T14), never to the active organisation's log.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel

#: Main products and free sets: one lower-case word; companion apps: ``app.<word>``.
PRODUCT_CODE = re.compile(r"^[a-z][a-z0-9_]*$")
COMPANION_CODE = re.compile(r"^app\.[a-z][a-z0-9_]*$")


class ProductKind(models.TextChoices):
    MAIN = "main", _("Main product")
    FREE_SET = "free_set", _("Free product set")
    COMPANION = "companion", _("Companion app")


class ProductStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    PLANNED = "planned", _("Planned")
    RETIRED = "retired", _("Retired")


class CatalogueError(ValidationError):
    """A catalogue change the rules refuse (changing a code, deleting a retired product…)."""


def product_name_key(code: str) -> str:
    return f"catalogue.product.{code}"


def feature_description_key(key: str) -> str:
    return f"catalogue.feature.{key}"


#: The three actions of a feature key (docs/architecture/feature-keys.md).
ACTIONS: tuple[str, ...] = ("read", "write", "approve")
READ_ACTION = "read"
AREA = re.compile(r"^[a-z][a-z0-9_]*$")


def split_key(key: str) -> tuple[str, str, str]:
    """``(product code, area, action)`` of a feature key; ValueError when malformed."""
    parts = key.split(".")
    if len(parts) < 3:
        raise ValueError(key)
    product, area, action = ".".join(parts[:-2]), parts[-2], parts[-1]
    if not (PRODUCT_CODE.match(product) or COMPANION_CODE.match(product)):
        raise ValueError(key)
    if not AREA.match(area) or action not in ACTIONS:
        raise ValueError(key)
    return product, area, action


class ProductQuerySet(models.QuerySet["Product"]):
    def delete(self) -> tuple[int, dict[str, int]]:
        if self.filter(status=ProductStatus.RETIRED).exists():
            raise CatalogueError(
                _(
                    "A retired product can't be deleted: it stays for the history of the "
                    "organisations that had it."
                ),
                code="catalogue.product_retired",
            )
        return super().delete()


class PlatformAudited(AuditedModel):
    """``AuditedModel`` for platform records: events have no organisation, even in a request
    that has an active one (``audit.service.record`` reads ``organisation_id``)."""

    organisation_id: ClassVar[None] = None

    class Meta:
        abstract = True


class Product(PlatformAudited, models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    code = models.CharField(
        _("code"),
        max_length=40,
        unique=True,
        help_text=_("Stable identifier, e.g. 'accounting'. Never changes once created."),
    )
    name_i18n_key = models.CharField(
        _("name (translation key)"),
        max_length=100,
        help_text=_("Translation key of the product's name, e.g. 'catalogue.product.accounting'."),
    )
    kind = models.CharField(_("kind"), max_length=16, choices=ProductKind.choices)
    status = models.CharField(
        _("status"), max_length=16, choices=ProductStatus.choices, default=ProductStatus.ACTIVE
    )
    sort = models.PositiveIntegerField(_("sort order"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    objects: ClassVar[models.Manager[Product]] = ProductQuerySet.as_manager()

    class Meta:
        ordering = ("sort", "code")
        verbose_name = _("product")
        verbose_name_plural = _("products")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=ProductKind.values), name="catalogue_product_kind"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ProductStatus.values),
                name="catalogue_product_status",
            ),
        ]

    def __str__(self) -> str:
        return self.code

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.name_i18n_key:
            self.name_i18n_key = product_name_key(self.code)
        self.clean()
        if not self._state.adding:
            stored = type(self)._base_manager.filter(pk=self.pk).values_list("code", flat=True)
            if stored and stored[0] != self.code:
                message = _("A product's code never changes: feature keys and packages use it.")
                raise CatalogueError(
                    {"code": ValidationError(message, code="catalogue.code_immutable")}
                )
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        if self.status == ProductStatus.RETIRED:
            raise CatalogueError(
                _(
                    "A retired product can't be deleted: it stays for the history of the "
                    "organisations that had it."
                ),
                code="catalogue.product_retired",
            )
        return super().delete(*args, **kwargs)

    def clean(self) -> None:
        pattern = COMPANION_CODE if self.kind == ProductKind.COMPANION else PRODUCT_CODE
        if not pattern.match(self.code or ""):
            message = _("Use lower-case letters, digits and _ (companion apps: app.<name>).")
            raise CatalogueError(
                {"code": ValidationError(message, code="catalogue.bad_product_code")}
            )


class FeatureKey(PlatformAudited, models.Model):
    public_id = models.UUIDField(_("public ID"), default=uuid.uuid4, unique=True, editable=False)
    key = models.CharField(
        _("key"),
        max_length=120,
        unique=True,
        help_text=_("<product>.<area>.<action>, e.g. 'accounting.sales_invoices.write'."),
    )
    description_i18n_key = models.CharField(
        _("description (translation key)"),
        max_length=160,
        help_text=_(
            "Translation key of the plain-language description: 'catalogue.feature.<key>'."
        ),
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="feature_keys",
        verbose_name=_("product"),
    )
    is_read_only = models.BooleanField(
        _("read-only"),
        default=False,
        help_text=_("Read keys (*.read) stay granted for history after a downgrade (U-03)."),
    )
    sort = models.PositiveIntegerField(_("sort order"), default=0)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)

    class Meta:
        ordering = ("product__sort", "sort", "key")
        verbose_name = _("feature key")
        verbose_name_plural = _("feature keys")

    def __str__(self) -> str:
        return self.key

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.description_i18n_key:
            self.description_i18n_key = feature_description_key(self.key)
        self.clean()
        if not self._state.adding:
            stored = type(self)._base_manager.filter(pk=self.pk).values_list("key", flat=True)
            if stored and stored[0] != self.key:
                message = _("A feature key never changes: endpoints and screens declare it.")
                raise CatalogueError(
                    {"key": ValidationError(message, code="catalogue.key_immutable")}
                )
        super().save(*args, **kwargs)

    @property
    def area(self) -> str:
        return split_key(self.key)[1]

    @property
    def action(self) -> str:
        return split_key(self.key)[2]

    def clean(self) -> None:
        try:
            product_code, _area, action = split_key(self.key or "")
        except ValueError:
            message = _("Use <product>.<area>.<action> with action read, write or approve.")
            raise CatalogueError(
                {"key": ValidationError(message, code="catalogue.bad_feature_key")}
            ) from None
        if self.product_id is not None and product_code != self.product.code:
            message = _("A feature key starts with the code of the product that owns it.")
            raise CatalogueError(
                {"key": ValidationError(message, code="catalogue.key_product_mismatch")}
            )
        self.is_read_only = action == READ_ACTION

"""Sales-tax table (G-01): authorities, effective-dated components, tax codes.

Every organisation has its own table (``OrgOwnedModel``): rates are the same for everyone, but
each organisation's components post to **its** control accounts and an organisation can add or
version its own codes. The Canadian table is installed from ``data/tax_ca.json`` (G-01-T04).

``TaxAuthority`` (G-01-T02) — who levies the tax: CRA (GST/HST), Revenu Québec (QST), British
Columbia, Manitoba and Saskatchewan (PST / RST).

``TaxComponent`` (G-01-T02) — one rate of one tax for one period:

- ``key`` — what the rate is (``gst``, ``hst_on``, ``qst``, ``pst_bc``, ``rst_mb``…); a key's
  versions follow each other in time and **never overlap** (database exclusion constraint
  ``tax_component_no_overlap``): NS HST 15 % to 31 Mar 2025, then 14 % from 1 Apr 2025;
- ``rate`` — percent, numeric(7,4) (``9.9750``);
- ``effective_from`` / ``effective_to`` — first and **last** day in force (``effective_to`` null =
  open); a rate is offered and accepted only on documents dated inside its range;
- ``kind`` — GST, HST, PST or QST: decides the control account by default (GST/HST payable /
  receivable, PST payable, QST payable / ITR) when no explicit account is set;
- ``recoverable`` — on purchases, the tax comes back as an input tax credit (GST/HST) or refund
  (QST ITR); PST is never recoverable (it is added to the cost);
- ``side`` — the documents it may appear on: both, sales only or purchases only;
- ``control_account_sales`` / ``control_account_purchase`` — the organisation's accounts the
  collected / paid tax posts to (null → the system account of the kind's role).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import translation
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel

SOURCE_LANGUAGE = "en-ca"


def active_on(start: Any, end: Any, day: Any) -> bool:
    """``day`` is inside ``[start, end]`` (``end`` null = open)."""
    return bool(start <= day and (end is None or day <= end))


def _overlaps(start: Any, end: Any, other_start: Any, other_end: Any) -> bool:
    return (other_end is None or start <= other_end) and (end is None or end >= other_start)


class TaxError(ValidationError):
    """A tax-table rule refused the change (``code`` names it)."""


class DateRange(models.Func):
    """``daterange(from, to, '[]')`` — a component's days; both ends inclusive, null = open."""

    function = "DATERANGE"
    output_field = DateRangeField()


class NamedMixin(models.Model):
    name_i18n = models.JSONField(_("name"), default=dict)

    class Meta:
        abstract = True

    @property
    def name(self) -> str:
        return self.name_in(translation.get_language() or SOURCE_LANGUAGE)

    def name_in(self, language: str) -> str:
        names = self.name_i18n or {}
        return str(names.get(language.lower()) or names.get(SOURCE_LANGUAGE) or "")


class TaxAuthority(NamedMixin, OrgOwnedModel):
    """CRA, Revenu Québec, British Columbia, Manitoba, Saskatchewan."""

    code = models.CharField(_("code"), max_length=10)

    class Meta:
        ordering = ("code",)
        verbose_name = _("tax authority")
        verbose_name_plural = _("tax authorities")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["organisation", "code"], name="tax_authority_code")
        ]

    def __str__(self) -> str:
        return self.code


class TaxKind(models.TextChoices):
    GST = "gst", _("GST")
    HST = "hst", _("HST")
    PST = "pst", _("PST")
    QST = "qst", _("QST")


class TaxSide(models.TextChoices):
    SALES = "sales", _("Sales")
    PURCHASE = "purchase", _("Purchases")


class ComponentSide(models.TextChoices):
    BOTH = "both", _("Sales and purchases")
    SALES = "sales", _("Sales only")
    PURCHASE = "purchase", _("Purchases only")


class TaxComponent(NamedMixin, AuditedModel, OrgOwnedModel):
    authority = models.ForeignKey(
        TaxAuthority,
        on_delete=models.PROTECT,
        related_name="components",
        verbose_name=_("authority"),
    )
    key = models.CharField(_("key"), max_length=40)
    kind = models.CharField(_("tax"), max_length=4, choices=TaxKind.choices)
    rate = models.DecimalField(
        _("rate (%)"),
        max_digits=7,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    effective_from = models.DateField(_("effective from"))
    effective_to = models.DateField(_("effective to"), null=True, blank=True)
    recoverable = models.BooleanField(_("recoverable on purchases"), default=True)
    side = models.CharField(
        _("used on"), max_length=10, choices=ComponentSide.choices, default=ComponentSide.BOTH
    )
    control_account_sales = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("control account (sales)"),
    )
    control_account_purchase = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("control account (purchases)"),
    )

    class Meta:
        ordering = ("key", "effective_from")
        verbose_name = _("tax component")
        verbose_name_plural = _("tax components")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="tax_component_range_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(rate__gte=0) & models.Q(rate__lte=100),
                name="tax_component_rate_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=TaxKind.values), name="tax_component_kind_valid"
            ),
            # PostgreSQL only (btree_gist): added by PostgresOnlyAddConstraint in migration 0001.
            ExclusionConstraint(
                name="tax_component_no_overlap",
                index_type="GIST",
                expressions=[
                    ("organisation", RangeOperators.EQUAL),
                    ("key", RangeOperators.EQUAL),
                    (
                        DateRange("effective_from", "effective_to", models.Value("[]")),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                violation_error_code="tax.component.overlap",
                violation_error_message=_(
                    "Another version of this tax component is already in force on some of these "
                    "days."
                ),
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} {self.rate.normalize():f} %"

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        super().save(*args, **kwargs)

    def is_active_on(self, day: Any) -> bool:
        return active_on(self.effective_from, self.effective_to, day)

    def clean(self) -> None:
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise TaxError(
                _("A component can't end before it starts."), code="tax.component.range_invalid"
            )
        overlapping = TaxComponent._base_manager.filter(
            organisation_id=self.organisation_id, key=self.key
        ).exclude(pk=self.pk)
        for other in overlapping:
            starts_before_other_ends = (
                other.effective_to is None or self.effective_from <= other.effective_to
            )
            ends_after_other_starts = (
                self.effective_to is None or self.effective_to >= other.effective_from
            )
            if starts_before_other_ends and ends_after_other_starts:
                raise TaxError(
                    _(
                        "%(component)s already has a version in force from %(start)s: versions of "
                        "a component can't overlap."
                    ),
                    code="tax.component.overlap",
                    params={"component": self.key, "start": other.effective_from.isoformat()},
                )

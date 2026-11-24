"""Conversion balances (C-05).

- ``ConversionSession`` (C-05-T01) — the organisation's conversion: its date, status (draft →
  finalised), who finalised it and when. **One per organisation** (a second is refused by the
  database, ``conversion_one_per_org``); corrections after finalising are correcting opening
  journals (C-05-T07), never a second session.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel

MONEY = {"max_digits": 18, "decimal_places": 2}
ZERO = Decimal("0.00")


class ConversionStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    FINALISED = "finalised", _("Finalised")


class ConversionSession(AuditedModel, OrgOwnedModel):
    conversion_date = models.DateField(
        _("conversion date"),
        help_text=_("The first day the organisation's books are kept in Numo9."),
    )
    status = models.CharField(
        _("status"), max_length=10, choices=ConversionStatus.choices, default=ConversionStatus.DRAFT
    )
    finalised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("finalised by"),
    )
    finalised_at = models.DateTimeField(_("finalised at"), null=True, blank=True)

    class Meta:
        verbose_name = _("conversion")
        verbose_name_plural = _("conversions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation"],
                condition=models.Q(deleted_at__isnull=True),
                name="conversion_one_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ConversionStatus.values),
                name="conversion_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status="draft") | models.Q(finalised_at__isnull=False),
                name="conversion_finalised_dated",
            ),
        ]

    def __str__(self) -> str:
        return str(_("Conversion at %(date)s") % {"date": self.conversion_date.isoformat()})

    @property
    def is_finalised(self) -> bool:
        return self.status == ConversionStatus.FINALISED

    def clean(self) -> None:
        others = ConversionSession._base_manager.filter(
            organisation_id=self.organisation_id, deleted_at__isnull=True
        ).exclude(pk=self.pk)
        if others.exists():
            raise ValidationError(
                _("This organisation already has a conversion: continue that one."),
                code="conversion.session.exists",
            )

"""Staff management models (V-05).

``DormantAlert`` (V-05-T06) — a dormant staff member was reported to the practice's admins: one
row per member and per period of inactivity (``inactive_since`` — the last sign-in, or the day
they joined), so the alert goes out once on day 60 and again only after they sign in and go
quiet again.
"""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Practice, PracticeMember


class DormantAlert(models.Model):
    practice = models.ForeignKey(
        Practice, on_delete=models.CASCADE, related_name="+", verbose_name=_("practice")
    )
    member = models.ForeignKey(
        PracticeMember,
        on_delete=models.CASCADE,
        related_name="dormant_alerts",
        verbose_name=_("staff member"),
    )
    inactive_since = models.DateTimeField(_("inactive since"))
    alerted_at = models.DateTimeField(_("alerted at"), default=timezone.now)
    recipients = models.PositiveSmallIntegerField(_("admins alerted"), default=0)

    class Meta:
        ordering = ("-alerted_at",)
        verbose_name = _("dormant staff alert")
        verbose_name_plural = _("dormant staff alerts")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("member", "inactive_since"), name="staff_dormant_alert_once"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.member} dormant since {self.inactive_since:%Y-%m-%d}"

"""Demo organisation models (U-07).

``DemoTemplate`` — the prebuilt, hidden template organisation of one seed version: built once
through the seeders, then cloned into every new demo (U-07-T05) and every reset (U-07-T06).
``pristine_hash`` is the hash of its seed tables, the value a freshly reset demo must match.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation


class DemoTemplate(models.Model):
    seed_version = models.PositiveSmallIntegerField(_("seed version"), unique=True)
    organisation = models.OneToOneField(
        Organisation,
        on_delete=models.PROTECT,
        related_name="demo_template",
        verbose_name=_("template organisation"),
    )
    pristine_hash = models.CharField(_("pristine hash"), max_length=64)
    built_at = models.DateTimeField(_("built at"), auto_now_add=True)

    class Meta:
        verbose_name = _("demo template")
        verbose_name_plural = _("demo templates")

    def __str__(self) -> str:
        return f"Demo template v{self.seed_version}"

"""Demo organisation models (U-07).

``DemoOutbox`` — emails of a demo organisation, kept in the app instead of sent (U-07-T07).

``DemoTemplate`` — the prebuilt, hidden template organisation of one seed version: built once
through the seeders, then cloned into every new demo (U-07-T05) and every reset (U-07-T06).
``pristine_hash`` is the hash of its seed tables, the value a freshly reset demo must match.
"""

from __future__ import annotations

from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation, OrgOwnedModel


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


class DemoOutbox(OrgOwnedModel):
    """An email a demo organisation would have sent (U-07-T07): kept here, shown in the in-app
    demo outbox, never handed to the mail provider."""

    to_email = models.EmailField(_("to"), max_length=254)
    subject = models.CharField(_("subject"), max_length=998)
    text_body = models.TextField(_("text"), blank=True)
    html_body = models.TextField(_("HTML"), blank=True)
    kind = models.CharField(_("kind"), max_length=64, blank=True)
    attachments = models.JSONField(_("attachments"), default=list, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        verbose_name = _("demo outbox email")
        verbose_name_plural = _("demo outbox emails")
        indexes = [models.Index(fields=["organisation", "-created_at"], name="demo_outbox_org_idx")]

    def __str__(self) -> str:
        return f"{self.subject} → {self.to_email}"

"""Conversion balances (C-05).

- ``ConversionSession`` (C-05-T01) — the organisation's conversion: its date, status (draft →
  finalised), who finalised it and when, and the opening journal finalising posted
  (``opening_entry``, C-05-T05: a finalised conversion has one); ``lock_balances`` (C-05-T06) —
  lock the GL, AR and AP at the conversion date − 1 when it is finalised. **One per
  organisation** (a second is refused by the database, ``conversion_one_per_org``); corrections
  after finalising are correcting opening journals (C-05-T07), never a second session.
- ``ConversionLine`` (C-05-T02) — one account's opening balance: a debit **or** a credit
  (``conversion_line_one_side``), one line per account (``conversion_line_one_per_account``).
- ``OpeningDocument`` (C-05-T03) — links the session to an invoice or a bill **open at the
  conversion date**: the document itself is an ordinary ``sales.Invoice`` / ``purchases.Bill``
  with ``is_opening=True`` (so aging, statements and payments work on it as on any other), open
  for what was still owed, with no journal of its own; its receivable or payable is posted by
  the conversion's opening journal (C-05-T05). Exactly one of ``invoice`` / ``bill``;
  ``outstanding`` is what it had open at the conversion date (what the AR/AP control line must
  add up to — payments made in Numo9 afterwards don't change it).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel

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
    lock_balances = models.BooleanField(
        _("lock balances"),
        default=False,
        help_text=_(
            "On finalising, lock the general ledger, sales and purchases to the day before the "
            "conversion date for everyone except advisers."
        ),
    )
    opening_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="conversion",
        verbose_name=_("opening journal"),
    )

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
            models.CheckConstraint(
                condition=models.Q(status="draft") | models.Q(opening_entry__isnull=False),
                name="conversion_finalised_posted",
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


class ConversionLine(AuditedModel, OrgOwnedModel):
    session = models.ForeignKey(
        ConversionSession,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name=_("conversion"),
    )
    account = models.ForeignKey(
        "ledger.Account", on_delete=models.PROTECT, related_name="+", verbose_name=_("account")
    )
    debit = models.DecimalField(_("debit"), max_digits=18, decimal_places=2, default=ZERO)
    credit = models.DecimalField(_("credit"), max_digits=18, decimal_places=2, default=ZERO)
    description = models.CharField(_("description"), max_length=500, blank=True)

    class Meta:
        ordering = ("session", "account__code", "pk")
        verbose_name = _("conversion line")
        verbose_name_plural = _("conversion lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0) & models.Q(credit=0))
                | (models.Q(debit=0) & models.Q(credit__gt=0)),
                name="conversion_line_one_side",
            ),
            models.UniqueConstraint(
                fields=["session", "account"],
                condition=models.Q(deleted_at__isnull=True),
                name="conversion_line_one_per_account",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.account} · {self.debit or self.credit}"

    def clean(self) -> None:
        debit, credit = self.debit or ZERO, self.credit or ZERO
        if debit < 0 or credit < 0:
            raise ValidationError(
                _("Enter a positive amount: a credit balance goes in the Credit column."),
                code="conversion.line.negative",
            )
        if debit > 0 and credit > 0:
            raise ValidationError(
                _("A line has a debit or a credit, not both."), code="conversion.line.both_sides"
            )
        if debit == 0 and credit == 0:
            raise ValidationError(
                _("Enter the account's balance as a debit or a credit."),
                code="conversion.line.empty",
            )
        if self.session_id and self.session.is_finalised:
            raise ValidationError(
                _("The conversion is finalised: correct it with a correcting opening journal."),
                code="conversion.session.finalised",
            )


class OpeningDocumentKind(models.TextChoices):
    INVOICE = "invoice", _("Invoice")
    BILL = "bill", _("Bill")


class OpeningDocument(OrgOwnedModel):
    session = models.ForeignKey(
        ConversionSession,
        on_delete=models.CASCADE,
        related_name="documents",
        verbose_name=_("conversion"),
    )
    kind = models.CharField(_("kind"), max_length=8, choices=OpeningDocumentKind.choices)
    invoice = models.OneToOneField(
        "sales.Invoice",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="opening_link",
        verbose_name=_("invoice"),
    )
    bill = models.OneToOneField(
        "purchases.Bill",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="opening_link",
        verbose_name=_("bill"),
    )
    outstanding = models.DecimalField(
        _("owed at the conversion date"), max_digits=18, decimal_places=2, default=ZERO
    )

    class Meta:
        ordering = ("session", "kind", "pk")
        verbose_name = _("opening document")
        verbose_name_plural = _("opening documents")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=(
                    models.Q(kind="invoice", invoice__isnull=False, bill__isnull=True)
                    | models.Q(kind="bill", bill__isnull=False, invoice__isnull=True)
                ),
                name="conversion_document_one_target",
            ),
            models.CheckConstraint(
                condition=models.Q(outstanding__gt=0), name="conversion_document_outstanding"
            ),
        ]

    def __str__(self) -> str:
        return str(self.invoice or self.bill)

    @property
    def document(self) -> Any:
        return self.invoice if self.kind == OpeningDocumentKind.INVOICE else self.bill

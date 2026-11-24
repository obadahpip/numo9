"""Invoices (D-03a-T01): ``Invoice`` and ``InvoiceLine`` on the shared document base (D-01).

Status: Draft → (Awaiting approval, when the organisation's rule asks, D-03a-T05) → Approved →
Sent → Partially paid → Paid, or Void. The **number** is allocated at approval, in the posting
transaction (D-03a-T02) — a draft has none and shows "Draft"; a void invoice keeps its number.
``journal_entry`` is the posting of the approval (D-03a-T03), ``void_entry`` its reversal
(D-03a-T07). ``current_revision`` is the latest ``InvoiceRevision`` once posted invoices become
editable (D-03b fills it; empty until then).
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.documents.models import DocumentBase, DocumentLineBase, _money
from numo9.tenancy.models import OrgOwnedModel


class InvoiceStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    AWAITING_APPROVAL = "awaiting_approval", _("Awaiting approval")
    APPROVED = "approved", _("Approved")
    SENT = "sent", _("Sent")
    PARTIALLY_PAID = "partially_paid", _("Partially paid")
    PAID = "paid", _("Paid")
    VOID = "void", _("Void")


#: Statuses of an invoice that has posted to the ledger (it has a number).
POSTED_STATUSES: frozenset[str] = frozenset(
    {
        InvoiceStatus.APPROVED,
        InvoiceStatus.SENT,
        InvoiceStatus.PARTIALLY_PAID,
        InvoiceStatus.PAID,
        InvoiceStatus.VOID,
    }
)


class Invoice(DocumentBase):
    number = models.CharField(_("number"), max_length=40, blank=True)
    status = models.CharField(
        _("status"), max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT
    )
    notes = models.TextField(_("notes"), blank=True)
    amount_paid = _money(_("amount paid"))
    journal_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="invoice",
        verbose_name=_("journal"),
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("submitted by"),
    )
    submitted_at = models.DateTimeField(_("submitted at"), null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("approved by"),
    )
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)
    viewed_at = models.DateTimeField(_("first viewed at"), null=True, blank=True)
    voided_at = models.DateTimeField(_("voided at"), null=True, blank=True)
    void_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voided_invoice",
        verbose_name=_("void journal"),
    )
    current_revision = models.ForeignKey(
        "sales.InvoiceRevision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("current revision"),
    )

    class Meta(DocumentBase.Meta):
        abstract = False
        ordering = ("-date", "-pk")
        verbose_name = _("invoice")
        verbose_name_plural = _("invoices")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *DocumentBase.header_constraints("sales_invoice"),
            models.CheckConstraint(
                condition=models.Q(status__in=InvoiceStatus.values),
                name="sales_invoice_status_valid",
            ),
            models.UniqueConstraint(
                fields=["organisation", "number"],
                condition=~models.Q(number=""),
                name="sales_invoice_number_unique",
            ),
            # A posted invoice has its number and its journal; a draft has neither.
            models.CheckConstraint(
                condition=~models.Q(status__in=sorted(POSTED_STATUSES))
                | (~models.Q(number="") & models.Q(journal_entry__isnull=False)),
                name="sales_invoice_posted_numbered",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_paid__gte=0), name="sales_invoice_paid_positive"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "status"], name="sales_invoice_status_idx"),
            models.Index(
                fields=["organisation", "contact", "date"], name="sales_invoice_contact_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.number or str(_("Draft invoice"))

    @property
    def is_posted(self) -> bool:
        return self.status in POSTED_STATUSES

    @property
    def amount_due(self) -> Decimal:
        return Decimal(self.total) - Decimal(self.amount_paid)


class InvoiceLine(DocumentLineBase):
    document = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="lines", verbose_name=_("invoice")
    )

    class Meta(DocumentLineBase.Meta):
        abstract = False
        verbose_name = _("invoice line")
        verbose_name_plural = _("invoice lines")
        constraints: ClassVar[list[models.BaseConstraint]] = DocumentLineBase.line_constraints(
            "sales_invoiceline"
        )


class InvoiceRevision(OrgOwnedModel):
    """A posted invoice's revision (D-03b fills these; here so ``current_revision`` can point at
    one): its number within the invoice, a snapshot of header and lines, and its journal."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="revisions", verbose_name=_("invoice")
    )
    revision = models.PositiveIntegerField(_("revision"))
    snapshot = models.JSONField(_("snapshot"), default=dict)

    class Meta:
        ordering = ("invoice", "revision")
        verbose_name = _("invoice revision")
        verbose_name_plural = _("invoice revisions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["invoice", "revision"], name="sales_invoice_revision_unique"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invoice} r{self.revision}"


class InvoiceEmail(OrgOwnedModel):
    """One send of an invoice by email (D-03a-T12): who it went to, what it said, the PDF that
    was attached (in object storage) and the email log rows (A-07). ``viewed_at`` is the first
    time the customer opened the invoice from the email's link."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="emails", verbose_name=_("invoice")
    )
    recipients = models.JSONField(_("recipients"), default=list)
    subject = models.CharField(_("subject"), max_length=998)
    message = models.TextField(_("message"), blank=True)
    language = models.CharField(_("language"), max_length=10, blank=True)
    file_key = models.CharField(_("PDF key"), max_length=500)
    file_name = models.CharField(_("PDF file name"), max_length=255)
    email_messages = models.JSONField(_("email messages"), default=list)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("sent by"),
    )
    viewed_at = models.DateTimeField(_("first viewed at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = _("invoice email")
        verbose_name_plural = _("invoice emails")

    def __str__(self) -> str:
        return f"{self.invoice} → {', '.join(self.recipients)}"

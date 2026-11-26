"""Invoices (D-03a-T01): ``Invoice`` and ``InvoiceLine`` on the shared document base (D-01).

Status: Draft → (Awaiting approval, when the organisation's rule asks, D-03a-T05) → Approved →
Sent → Partially paid → Paid, or Void. The **number** is allocated at approval, in the posting
transaction (D-03a-T02) — a draft has none and shows "Draft"; a void invoice keeps its number.
``journal_entry`` is the posting of the approval (D-03a-T03), ``void_entry`` its reversal
(D-03a-T07). ``is_opening`` (C-05-T03) marks an invoice open at the conversion date: entered with
the conversion balances, numbered with the old system's number, open (Approved or Partially
paid) so payments and aging see it, and **without a journal** — the opening journal of the
conversion carries the receivable. ``current_revision`` is the latest ``InvoiceRevision`` once
posted invoices become editable (D-03b fills it; empty until then). ``disputed`` (D-07-T07) — the
customer disputes the invoice: reminders and late fees stop until it is resolved
(``sales.disputes``).

Credit notes (D-06-T01): ``CreditNote`` and ``CreditNoteLine`` on the same document base, numbered
``CN-0001`` at approval; optionally the invoice it credits ("Credit this invoice", D-06-T02).
Approval posts Dr revenue / Dr tax / Cr AR (D-06-T03). ``CreditApplication`` applies part of a
credit note to an invoice (amount ≤ the invoice's open balance and ≤ the credit remaining,
D-06-T04); ``amount_applied`` and ``amount_refunded`` are the credit used so far.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.documents.models import (
    DiscountType,
    DocumentBase,
    DocumentLineBase,
    RecurringRunBase,
    TaxMode,
    _money,
)
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
    is_opening = models.BooleanField(
        _("opening balance"),
        default=False,
        help_text=_(
            "An invoice still open at the conversion date, entered with the conversion balances: "
            "it posts nothing itself (the opening journal carries Accounts receivable)."
        ),
    )
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
    disputed = models.BooleanField(
        _("disputed"),
        default=False,
        help_text=_("The customer disputes the invoice: no reminder or late fee until resolved."),
    )
    disputed_at = models.DateTimeField(_("disputed since"), null=True, blank=True)
    dispute_reason = models.TextField(_("what is disputed"), blank=True, default="")
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
            # A posted invoice has its number and its journal; a draft has neither. An opening
            # invoice (C-05-T03) has its number and no journal of its own.
            models.CheckConstraint(
                condition=~models.Q(status__in=sorted(POSTED_STATUSES))
                | (
                    ~models.Q(number="")
                    & (models.Q(journal_entry__isnull=False) | models.Q(is_opening=True))
                ),
                name="sales_invoice_posted_numbered",
            ),
            models.CheckConstraint(
                condition=models.Q(is_opening=False) | models.Q(journal_entry__isnull=True),
                name="sales_invoice_opening_unposted",
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
    """A posted invoice's revision (D-03b-T02, ADR-0006): revision 0 at first approval, then 1,
    2… for each edit of the posted invoice — ``number_display`` "101", "101-1"; a ``snapshot``
    of the header and lines with the totals as it was issued; the ``reason`` of the edit; the
    journal it reversed (``journal_reversal``: the reversal of the previous revision's posting)
    and the journal it posted (``journal_post``); ``superseded_at`` once a later revision
    replaces it. The invoice rows always hold the current revision."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.CASCADE, related_name="revisions", verbose_name=_("invoice")
    )
    revision = models.PositiveIntegerField(_("revision"))
    number_display = models.CharField(_("number shown"), max_length=50, blank=True, db_default="")
    snapshot = models.JSONField(_("snapshot"), default=dict)
    total = models.DecimalField(
        _("total"),
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
        db_default=Decimal("0"),
    )
    tax_total = models.DecimalField(
        _("tax"), max_digits=18, decimal_places=2, default=Decimal("0.00"), db_default=Decimal("0")
    )
    reason = models.TextField(_("reason"), blank=True, db_default="")
    journal_reversal = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_invoice_revision",
        verbose_name=_("reversal journal"),
    )
    journal_post = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="posted_invoice_revision",
        verbose_name=_("posted journal"),
    )
    superseded_at = models.DateTimeField(_("superseded at"), null=True, blank=True)

    class Meta:
        ordering = ("invoice", "revision")
        verbose_name = _("invoice revision")
        verbose_name_plural = _("invoice revisions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["invoice", "revision"], name="sales_invoice_revision_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(revision=0) | ~models.Q(reason=""),
                name="sales_invoice_revision_reason",
            ),
        ]

    def __str__(self) -> str:
        return self.number_display or f"{self.invoice} r{self.revision}"

    @property
    def is_current(self) -> bool:
        return self.superseded_at is None


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


class CreditNoteStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    AWAITING_APPROVAL = "awaiting_approval", _("Awaiting approval")
    APPROVED = "approved", _("Approved")
    PARTIALLY_APPLIED = "partially_applied", _("Partially applied")
    APPLIED = "applied", _("Applied")
    VOID = "void", _("Void")


CREDIT_POSTED_STATUSES: frozenset[str] = frozenset(
    {
        CreditNoteStatus.APPROVED,
        CreditNoteStatus.PARTIALLY_APPLIED,
        CreditNoteStatus.APPLIED,
        CreditNoteStatus.VOID,
    }
)


class CreditNote(DocumentBase):
    number = models.CharField(_("number"), max_length=40, blank=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=CreditNoteStatus.choices,
        default=CreditNoteStatus.DRAFT,
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_notes",
        verbose_name=_("credited invoice"),
    )
    notes = models.TextField(_("notes"), blank=True)
    amount_applied = _money(_("amount applied"))
    amount_refunded = _money(_("amount refunded"))
    journal_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credit_note",
        verbose_name=_("journal"),
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("approved by"),
    )
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)
    voided_at = models.DateTimeField(_("voided at"), null=True, blank=True)
    void_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voided_credit_note",
        verbose_name=_("void journal"),
    )

    class Meta(DocumentBase.Meta):
        abstract = False
        ordering = ("-date", "-pk")
        verbose_name = _("credit note")
        verbose_name_plural = _("credit notes")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *DocumentBase.header_constraints("sales_creditnote"),
            models.CheckConstraint(
                condition=models.Q(status__in=CreditNoteStatus.values),
                name="sales_creditnote_status_valid",
            ),
            models.UniqueConstraint(
                fields=["organisation", "number"],
                condition=~models.Q(number=""),
                name="sales_creditnote_number_unique",
            ),
            models.CheckConstraint(
                condition=~models.Q(status__in=sorted(CREDIT_POSTED_STATUSES))
                | (~models.Q(number="") & models.Q(journal_entry__isnull=False)),
                name="sales_creditnote_posted_numbered",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_applied__gte=0, amount_refunded__gte=0)
                & models.Q(total__gte=models.F("amount_applied") + models.F("amount_refunded")),
                name="sales_creditnote_used_within_total",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "status"], name="sales_creditnote_status_idx"),
            models.Index(
                fields=["organisation", "contact", "date"], name="sales_creditnote_contact_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.number or str(_("Draft credit note"))

    @property
    def is_posted(self) -> bool:
        return self.status in CREDIT_POSTED_STATUSES

    @property
    def remaining(self) -> Decimal:
        return Decimal(self.total) - Decimal(self.amount_applied) - Decimal(self.amount_refunded)


class CreditNoteLine(DocumentLineBase):
    document = models.ForeignKey(
        CreditNote, on_delete=models.CASCADE, related_name="lines", verbose_name=_("credit note")
    )

    class Meta(DocumentLineBase.Meta):
        abstract = False
        verbose_name = _("credit note line")
        verbose_name_plural = _("credit note lines")
        constraints: ClassVar[list[models.BaseConstraint]] = DocumentLineBase.line_constraints(
            "sales_creditnoteline"
        )


class CreditApplication(OrgOwnedModel):
    """Part of a credit note applied to an invoice on a date (D-06-T04 checks the limits)."""

    credit_note = models.ForeignKey(
        CreditNote,
        on_delete=models.PROTECT,
        related_name="applications",
        verbose_name=_("credit note"),
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="credit_applications",
        verbose_name=_("invoice"),
    )
    amount = _money(_("amount"))
    date = models.DateField(_("date"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("applied by"),
    )
    created_at = models.DateTimeField(_("applied at"), auto_now_add=True)
    reversed_at = models.DateTimeField(_("removed at"), null=True, blank=True)

    class Meta:
        ordering = ("date", "pk")
        verbose_name = _("credit application")
        verbose_name_plural = _("credit applications")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="sales_creditapplication_positive"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "credit_note"], name="sales_creditapp_credit_idx"),
            models.Index(fields=["organisation", "invoice"], name="sales_creditapp_invoice_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.credit_note} → {self.invoice}: {self.amount}"


# ---- quotes (D-02) -----------------------------------------------------------------------------


class QuoteStatus(models.TextChoices):
    """The one status vocabulary of quotes (D-02-T01, gap-05): the same enum in the overview,
    the list tabs and the filters (exported to the frontend as ``QUOTE_STATUSES``)."""

    DRAFT = "draft", _("Draft")
    SENT = "sent", _("Sent")
    VIEWED = "viewed", _("Viewed")
    ACCEPTED = "accepted", _("Accepted")
    DECLINED = "declined", _("Declined")
    EXPIRED = "expired", _("Expired")
    INVOICED = "invoiced", _("Invoiced")


class DepositType(models.TextChoices):
    NONE = "none", _("No deposit")
    AMOUNT = "amount", _("Amount")
    PERCENT = "percent", _("Percentage")


class Quote(DocumentBase):
    """A quote (D-02-T01) on the shared document base: ``title`` and ``summary``; ``expiry_date``
    (required — the customer can't accept after it, D-02-T05); optional lines and alternative
    groups (``QuoteLine``); a deposit request (``deposit_type`` amount or percent of the
    accepted total); the lifecycle dates (sent, first viewed, accepted, declined, expired,
    invoiced), the invoice it became and the deposit invoice its acceptance created (D-02-T08).

    ``number`` — ``QU-0001``, taken when the quote is created (D-02-T02). An accepted quote is
    immutable; a revision is a new quote (``revises``), the old link shows "superseded".
    """

    number = models.CharField(_("number"), max_length=40)
    status = models.CharField(
        _("status"), max_length=10, choices=QuoteStatus.choices, default=QuoteStatus.DRAFT
    )
    title = models.CharField(_("title"), max_length=200, blank=True)
    summary = models.TextField(_("summary"), blank=True)
    expiry_date = models.DateField(_("expiry date"))
    deposit_type = models.CharField(
        _("deposit"), max_length=8, choices=DepositType.choices, default=DepositType.NONE
    )
    deposit_value = models.DecimalField(
        _("deposit amount or %"), max_digits=18, decimal_places=4, default=Decimal("0")
    )
    notes = models.TextField(_("notes"), blank=True)
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)
    viewed_at = models.DateTimeField(_("first viewed at"), null=True, blank=True)
    accepted_at = models.DateTimeField(_("accepted at"), null=True, blank=True)
    declined_at = models.DateTimeField(_("declined at"), null=True, blank=True)
    decline_reason = models.TextField(_("reason for declining"), blank=True)
    expired_at = models.DateTimeField(_("expired at"), null=True, blank=True)
    invoiced_at = models.DateTimeField(_("invoiced at"), null=True, blank=True)
    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quote",
        verbose_name=_("invoice"),
    )
    deposit_invoice = models.OneToOneField(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="deposit_for",
        verbose_name=_("deposit invoice"),
    )
    revises = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="revisions",
        verbose_name=_("revision of"),
    )

    class Meta(DocumentBase.Meta):
        abstract = False
        ordering = ("-date", "-pk")
        verbose_name = _("quote")
        verbose_name_plural = _("quotes")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *DocumentBase.header_constraints("sales_quote"),
            models.CheckConstraint(
                condition=models.Q(status__in=QuoteStatus.values), name="sales_quote_status_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(deposit_type__in=DepositType.values),
                name="sales_quote_deposit_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(deposit_value__gte=0)
                & (~models.Q(deposit_type=DepositType.PERCENT) | models.Q(deposit_value__lte=100)),
                name="sales_quote_deposit_value_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(expiry_date__gte=models.F("date")),
                name="sales_quote_expiry_after_date",
            ),
            models.CheckConstraint(condition=~models.Q(number=""), name="sales_quote_numbered"),
            models.UniqueConstraint(
                fields=["organisation", "number"], name="sales_quote_number_unique"
            ),
            models.CheckConstraint(
                condition=~models.Q(status=QuoteStatus.INVOICED) | models.Q(invoice__isnull=False),
                name="sales_quote_invoiced_linked",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "status"], name="sales_quote_status_idx"),
            models.Index(fields=["organisation", "expiry_date"], name="sales_quote_expiry_idx"),
        ]

    def __str__(self) -> str:
        return self.number


class QuoteLine(DocumentLineBase):
    """A line of a quote: ``is_optional`` — the customer may tick it (``selected``, default off
    for optional lines); ``alternative_group`` — lines of the same group are alternatives, the
    customer chooses one (``selected``). Unselected optional or alternative lines are left out of
    the totals (D-02-T03)."""

    document = models.ForeignKey(
        Quote, on_delete=models.CASCADE, related_name="lines", verbose_name=_("quote")
    )
    is_optional = models.BooleanField(_("optional"), default=False)
    alternative_group = models.CharField(_("alternative group"), max_length=40, blank=True)
    selected = models.BooleanField(_("selected"), default=True)

    class Meta(DocumentLineBase.Meta):
        abstract = False
        verbose_name = _("quote line")
        verbose_name_plural = _("quote lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *DocumentLineBase.line_constraints("sales_quoteline"),
            models.CheckConstraint(
                condition=~(models.Q(is_optional=True) & ~models.Q(alternative_group="")),
                name="sales_quoteline_optional_or_alternative",
            ),
        ]


class QuoteLink(OrgOwnedModel):
    """A public link to a quote (D-02-T06): the customer opens it without signing in. The URL
    carries a **signed** token naming the quote and this row; revoking the row (``revoked_at``)
    makes the link answer 410 Gone. ``views`` / ``last_viewed_at`` — the view tracking."""

    quote = models.ForeignKey(
        Quote, on_delete=models.CASCADE, related_name="links", verbose_name=_("quote")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("created by"),
    )
    revoked_at = models.DateTimeField(_("revoked at"), null=True, blank=True)
    views = models.PositiveIntegerField(_("views"), default=0)
    last_viewed_at = models.DateTimeField(_("last viewed at"), null=True, blank=True)

    class Meta:
        ordering = ("quote", "-created_at")
        verbose_name = _("quote link")
        verbose_name_plural = _("quote links")

    def __str__(self) -> str:
        return f"{self.quote} link"


class QuoteAcceptance(OrgOwnedModel):
    """The evidence of a customer's acceptance (D-02-T07): who typed their name, the drawn
    signature (a PNG in object storage — optional: typing the name alone is the accessible way),
    the IP address and browser, the lines chosen, and the **SHA-256 of the PDF as accepted**
    (the PDF itself is stored too, so the hash can be checked against it)."""

    quote = models.OneToOneField(
        Quote, on_delete=models.PROTECT, related_name="acceptance", verbose_name=_("quote")
    )
    typed_name = models.CharField(_("name typed"), max_length=200)
    signature_key = models.CharField(_("signature (PNG) key"), max_length=500, blank=True)
    ip = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.CharField(_("browser"), max_length=512, blank=True)
    selections = models.JSONField(_("lines chosen"), default=dict, blank=True)
    pdf_key = models.CharField(_("accepted PDF key"), max_length=500)
    pdf_sha256 = models.CharField(_("accepted PDF SHA-256"), max_length=64)
    accepted_at = models.DateTimeField(_("accepted at"))

    class Meta:
        verbose_name = _("quote acceptance")
        verbose_name_plural = _("quote acceptances")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=~models.Q(typed_name=""), name="sales_quoteacceptance_named"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.quote} accepted by {self.typed_name}"


class RecurringInvoiceMode(models.TextChoices):
    """What each occurrence of a recurring invoice becomes (D-04)."""

    DRAFT = "draft", _("Save as a draft")
    APPROVE = "approve", _("Approve")
    APPROVE_SEND = "approve_send", _("Approve and send")


class RecurringInvoiceTemplate(AuditedModel, OrgOwnedModel):
    """An invoice that repeats on a schedule (D-04-T01): the header and lines of the invoice, an
    RFC 5545 rule (the recurring-journal engine, C-04-T05: a 31st clamps to the month's last
    day), a start and an optional end date, the due-date rule (``terms`` — the contact's or the
    organisation's default when empty) and the mode (draft / approve / approve and send).

    Text in the reference, the notes and the line descriptions may carry the placeholders
    ``{{period_start}}``, ``{{period_end}}``, ``{{month}}`` and ``{{year}}`` (D-04-T03); ``prorate``
    charges a first or last partial period by days (D-04-T04). ``next_run`` is the next occurrence
    to generate (``None``: finished), ``last_run`` the latest generated; ``paused`` templates skip;
    ``version`` goes up on every edit — changes apply to future occurrences only."""

    name = models.CharField(_("name"), max_length=200)
    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.PROTECT, related_name="+", verbose_name=_("contact")
    )
    terms = models.ForeignKey(
        "contacts.PaymentTerm",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("terms"),
    )
    reference = models.CharField(_("reference"), max_length=255, blank=True)
    currency = models.CharField(_("currency"), max_length=3, default="CAD")
    tax_mode = models.CharField(
        _("amounts are"), max_length=16, choices=TaxMode.choices, default=TaxMode.EXCLUSIVE
    )
    ship_to_country = models.CharField(_("ship-to country"), max_length=2, blank=True)
    ship_to_province = models.CharField(_("ship-to province"), max_length=2, blank=True)
    discount_type = models.CharField(
        _("discount"), max_length=8, choices=DiscountType.choices, default=DiscountType.NONE
    )
    discount_value = models.DecimalField(
        _("discount value"), max_digits=18, decimal_places=4, default=Decimal("0")
    )
    notes = models.TextField(_("notes"), blank=True)
    rrule = models.CharField(
        _("schedule"),
        max_length=500,
        help_text=_("An RFC 5545 recurrence rule, e.g. FREQ=MONTHLY;INTERVAL=1."),
    )
    start_date = models.DateField(_("start date"))
    end_date = models.DateField(_("end date"), null=True, blank=True)
    mode = models.CharField(
        _("mode"),
        max_length=12,
        choices=RecurringInvoiceMode.choices,
        default=RecurringInvoiceMode.DRAFT,
    )
    prorate = models.BooleanField(_("prorate partial periods"), default=False)
    service_start = models.DateField(_("service starts"), null=True, blank=True)
    service_end = models.DateField(_("service ends"), null=True, blank=True)
    next_run = models.DateField(_("next run"), null=True, blank=True)
    last_run = models.DateField(_("last run"), null=True, blank=True)
    paused = models.BooleanField(_("paused"), default=False)
    version = models.PositiveIntegerField(_("version"), default=1)

    class Meta:
        ordering = ("name", "pk")
        verbose_name = _("recurring invoice")
        verbose_name_plural = _("recurring invoices")
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "paused", "next_run"], name="sales_recur_due"),
        ]
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(mode__in=RecurringInvoiceMode.values),
                name="sales_recur_mode_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(tax_mode__in=TaxMode.values),
                name="sales_recur_tax_mode_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_type__in=DiscountType.values)
                & models.Q(discount_value__gte=0)
                & (
                    ~models.Q(discount_type=DiscountType.PERCENT)
                    | models.Q(discount_value__lte=100)
                ),
                name="sales_recur_discount_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__isnull=True)
                | models.Q(end_date__gte=models.F("start_date")),
                name="sales_recur_end_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(service_start__isnull=True)
                | models.Q(service_end__isnull=True)
                | models.Q(service_end__gte=models.F("service_start")),
                name="sales_recur_service_end_after_start",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        from .recurring_invoices import validate_schedule

        validate_schedule(self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self._state.adding and self.next_run is None:
            from .recurring_invoices import first_run

            self.next_run = first_run(self)
        super().save(*args, **kwargs)


class RecurringInvoiceLine(DocumentLineBase):
    """A line of a recurring invoice template — the invoice line's fields (D-01), copied onto
    each generated invoice with placeholders resolved and, when prorated, a partial quantity."""

    document = models.ForeignKey(
        RecurringInvoiceTemplate,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name=_("recurring invoice"),
    )

    class Meta(DocumentLineBase.Meta):
        abstract = False
        verbose_name = _("recurring invoice line")
        verbose_name_plural = _("recurring invoice lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *DocumentLineBase.line_constraints("sales_recurline"),
        ]


class RecurringInvoiceRun(RecurringRunBase):
    """One occurrence of a recurring invoice (D-04-T05): unique per (template, date) — the
    idempotency row; ``document`` is the invoice it created (``None`` when skipped, D-04-T06)."""

    template = models.ForeignKey(
        RecurringInvoiceTemplate,
        on_delete=models.CASCADE,
        related_name="runs",
        verbose_name=_("recurring invoice"),
    )
    document = models.OneToOneField(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="recurring_run",
        verbose_name=_("invoice"),
    )

    class Meta(RecurringRunBase.Meta):
        abstract = False
        verbose_name = _("recurring invoice run")
        verbose_name_plural = _("recurring invoice runs")
        constraints: ClassVar[list[models.BaseConstraint]] = RecurringRunBase.run_constraints(
            "sales_recur_run"
        )

    def __str__(self) -> str:
        return f"{self.template} · {self.occurrence_date}"


# ---- Invoice reminders (D-07) ------------------------------------------------------------------


class ReminderChannelKind(models.TextChoices):
    """How a reminder step reaches the customer (D-07-T02 adapters)."""

    EMAIL = "email", _("Email")
    SMS = "sms", _("Text message (SMS)")
    WHATSAPP = "whatsapp", _("WhatsApp")


class ReminderEscalation(models.TextChoices):
    """What a step does besides reminding (D-07-T05)."""

    NOTIFY_OWNER = "notify_owner", _("Notify the organisation's owner")
    NOTIFY_SALESPERSON = "notify_salesperson", _("Notify the invoice's salesperson")
    CREDIT_HOLD = "credit_hold", _("Put the customer on credit hold")


#: Steps run from three months before the due date to a year after it.
REMINDER_OFFSET_MIN = -90
REMINDER_OFFSET_MAX = 365


class ReminderSchedule(AuditedModel, OrgOwnedModel):
    """An organisation's invoice reminder schedule (D-07-T01): its steps before and after the
    due date (``steps``), whether it runs (``is_active``) and the **sending window** in the
    organisation's time zone — reminders go out between ``window_start`` and ``window_end`` on
    business days — and at most ``daily_cap_per_contact`` reminders a day to one customer (no
    spamming, even when several invoices are due). One schedule per organisation is the default
    (``is_default``): the one new invoices follow."""

    name = models.CharField(_("name"), max_length=200)
    is_active = models.BooleanField(_("active"), default=True)
    is_default = models.BooleanField(_("default"), default=False)
    window_start = models.TimeField(_("send from"), default=dt.time(9, 0))
    window_end = models.TimeField(_("send until"), default=dt.time(17, 0))
    business_days_only = models.BooleanField(_("business days only"), default=True)
    daily_cap_per_contact = models.PositiveSmallIntegerField(
        _("reminders a day per customer"), default=1
    )

    class Meta:
        ordering = ("name", "pk")
        verbose_name = _("reminder schedule")
        verbose_name_plural = _("reminder schedules")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation"],
                condition=models.Q(is_default=True),
                name="sales_reminder_one_default",
            ),
            models.CheckConstraint(
                condition=models.Q(window_end__gt=models.F("window_start")),
                name="sales_reminder_window_order",
            ),
            models.CheckConstraint(
                condition=models.Q(daily_cap_per_contact__gte=1),
                name="sales_reminder_daily_cap_min",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class ReminderStep(OrgOwnedModel):
    """One step of a reminder schedule (D-07-T01): ``offset_days`` from the invoice's due date
    (−7 = a week before, 0 = on the day, +14 = two weeks late), the email/text ``template`` (a
    notification template key, rendered in the customer's language — EN/FR seeded, D-07-T13),
    the ``channel``, the ``min_amount`` the invoice must still owe for the step to run and its
    ``escalation`` actions (``ReminderEscalation`` values)."""

    schedule = models.ForeignKey(
        ReminderSchedule, on_delete=models.CASCADE, related_name="steps", verbose_name=_("schedule")
    )
    offset_days = models.SmallIntegerField(
        _("days from the due date"),
        help_text=_("Negative before the due date, 0 on the day, positive after it."),
    )
    template = models.CharField(_("template"), max_length=100)
    channel = models.CharField(
        _("channel"),
        max_length=10,
        choices=ReminderChannelKind.choices,
        default=ReminderChannelKind.EMAIL,
    )
    min_amount = _money(_("minimum amount owing"))
    escalation = models.JSONField(_("escalation"), default=list, blank=True)
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ("schedule", "offset_days", "pk")
        verbose_name = _("reminder step")
        verbose_name_plural = _("reminder steps")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["schedule", "offset_days", "channel"], name="sales_reminder_step_once"
            ),
            models.CheckConstraint(
                condition=models.Q(offset_days__gte=REMINDER_OFFSET_MIN)
                & models.Q(offset_days__lte=REMINDER_OFFSET_MAX),
                name="sales_reminder_step_offset_range",
            ),
            models.CheckConstraint(
                condition=models.Q(min_amount__gte=0), name="sales_reminder_step_min_amount"
            ),
            models.CheckConstraint(
                condition=models.Q(channel__in=ReminderChannelKind.values),
                name="sales_reminder_step_channel_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.schedule} {self.offset_days:+d}"

    def clean(self) -> None:
        from django.core.exceptions import ValidationError

        actions = self.escalation if isinstance(self.escalation, list) else None
        if actions is None or any(a not in ReminderEscalation.values for a in actions):
            raise ValidationError(
                {
                    "escalation": ValidationError(
                        _("Escalation is a list of: %(actions)s.")
                        % {"actions": ", ".join(ReminderEscalation.values)},
                        code="sales.reminder.escalation_invalid",
                    )
                }
            )
        if len(set(actions)) != len(actions):
            raise ValidationError(
                {
                    "escalation": ValidationError(
                        _("Each escalation action is listed once."),
                        code="sales.reminder.escalation_invalid",
                    )
                }
            )


# ---- payments received (D-05) ------------------------------------------------------------------
#
# ``CustomerPayment`` — money received from a customer into a bank account on a date (posted Dr
# bank / Cr accounts receivable by D-05-T03); ``PaymentAllocation`` — part of a payment, or of a
# customer credit, applied to an invoice (≤ the invoice's open balance and ≤ what the source has
# left, D-05-T02); ``CustomerCredit`` — money a customer has with you that no invoice used: an
# overpayment or a prepayment (D-05-T04), applied to invoices later or refunded (D-05-T06). In the
# ledger a credit stays on the accounts receivable control account, as a credit balance of the
# customer: allocating it moves nothing in the general ledger, a refund posts Dr AR / Cr bank.


class PaymentStatus(models.TextChoices):
    POSTED = "posted", _("Posted")
    VOID = "void", _("Void")


class CustomerPayment(AuditedModel, OrgOwnedModel):
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        related_name="payments_received",
        verbose_name=_("customer"),
    )
    bank_account = models.ForeignKey(
        "banking.BankAccount",
        on_delete=models.PROTECT,
        related_name="customer_payments",
        verbose_name=_("bank account"),
    )
    date = models.DateField(_("date"))
    amount = _money(_("amount"))
    currency = models.CharField(_("currency"), max_length=3, default="CAD")
    reference = models.CharField(_("reference"), max_length=255, blank=True)
    status = models.CharField(
        _("status"), max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.POSTED
    )
    journal_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_payment",
        verbose_name=_("journal"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("recorded by"),
    )
    version = models.PositiveIntegerField(_("version"), default=1)

    class Meta:
        ordering = ("-date", "-pk")
        verbose_name = _("payment received")
        verbose_name_plural = _("payments received")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="sales_customerpayment_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=PaymentStatus.values),
                name="sales_customerpayment_status_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "contact"], name="sales_payment_contact_idx"),
            models.Index(fields=["organisation", "date"], name="sales_payment_date_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.contact} {self.date:%Y-%m-%d} {self.amount}"

    @property
    def allocated(self) -> Decimal:
        rows = self.allocations.filter(reversed_at__isnull=True)
        return Decimal(rows.aggregate(total=models.Sum("amount"))["total"] or 0)

    @property
    def unallocated(self) -> Decimal:
        return Decimal(self.amount) - self.allocated


class CreditSource(models.TextChoices):
    OVERPAYMENT = "overpayment", _("Overpayment")
    PREPAYMENT = "prepayment", _("Prepayment")


class CustomerCredit(AuditedModel, OrgOwnedModel):
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        related_name="customer_credits",
        verbose_name=_("customer"),
    )
    source = models.CharField(_("source"), max_length=12, choices=CreditSource.choices)
    payment = models.ForeignKey(
        CustomerPayment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="credits",
        verbose_name=_("payment"),
    )
    date = models.DateField(_("date"))
    amount = _money(_("amount"))
    amount_refunded = _money(_("refunded"))
    currency = models.CharField(_("currency"), max_length=3, default="CAD")

    class Meta:
        ordering = ("date", "pk")
        verbose_name = _("customer credit")
        verbose_name_plural = _("customer credits")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="sales_customercredit_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(amount_refunded__gte=0)
                & models.Q(amount_refunded__lte=models.F("amount")),
                name="sales_customercredit_refund_within",
            ),
            models.CheckConstraint(
                condition=models.Q(source__in=CreditSource.values),
                name="sales_customercredit_source_valid",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "contact"], name="sales_credit_contact_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.contact} {self.get_source_display()} {self.amount}"

    @property
    def applied(self) -> Decimal:
        rows = self.allocations.filter(reversed_at__isnull=True)
        return Decimal(rows.aggregate(total=models.Sum("amount"))["total"] or 0)

    @property
    def remaining(self) -> Decimal:
        return Decimal(self.amount) - self.applied - Decimal(self.amount_refunded)


class PaymentAllocation(OrgOwnedModel):
    """Part of a payment — or of a customer credit — applied to an invoice on a date."""

    payment = models.ForeignKey(
        CustomerPayment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="allocations",
        verbose_name=_("payment"),
    )
    credit = models.ForeignKey(
        CustomerCredit,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="allocations",
        verbose_name=_("customer credit"),
    )
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name="allocations",
        verbose_name=_("invoice"),
    )
    amount = _money(_("amount"))
    date = models.DateField(_("date"))
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("allocated by"),
    )
    created_at = models.DateTimeField(_("allocated at"), auto_now_add=True)
    reversed_at = models.DateTimeField(_("removed at"), null=True, blank=True)

    class Meta:
        ordering = ("date", "pk")
        verbose_name = _("payment allocation")
        verbose_name_plural = _("payment allocations")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="sales_paymentallocation_positive"
            ),
            models.CheckConstraint(
                condition=(models.Q(payment__isnull=False) & models.Q(credit__isnull=True))
                | (models.Q(payment__isnull=True) & models.Q(credit__isnull=False)),
                name="sales_paymentallocation_one_source",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "invoice"], name="sales_alloc_invoice_idx"),
            models.Index(fields=["organisation", "payment"], name="sales_alloc_payment_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.payment or self.credit} → {self.invoice}: {self.amount}"


class CustomerCreditRefund(AuditedModel, OrgOwnedModel):
    """Part of a customer credit paid back to the customer from a bank account (D-05-T06):
    posted Dr accounts receivable (the customer's credit) / Cr the bank."""

    credit = models.ForeignKey(
        CustomerCredit,
        on_delete=models.PROTECT,
        related_name="refunds",
        verbose_name=_("customer credit"),
    )
    bank_account = models.ForeignKey(
        "banking.BankAccount",
        on_delete=models.PROTECT,
        related_name="customer_refunds",
        verbose_name=_("bank account"),
    )
    date = models.DateField(_("date"))
    amount = _money(_("amount"))
    reference = models.CharField(_("reference"), max_length=255, blank=True)
    journal_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="customer_credit_refund",
        verbose_name=_("journal"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("refunded by"),
    )

    class Meta:
        ordering = ("date", "pk")
        verbose_name = _("customer credit refund")
        verbose_name_plural = _("customer credit refunds")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="sales_customercreditrefund_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.credit} ← {self.amount}"


# ---- Late fees and interest (D-07-T06) ---------------------------------------------------------


class LateFeeTarget(models.TextChoices):
    STATEMENT = "statement", _("A line on the next statement")
    FEE_INVOICE = "fee_invoice", _("A separate fee invoice")


class LateFeePolicy(AuditedModel, OrgOwnedModel):
    """How an organisation charges interest on overdue invoices (D-07-T06; FN-04 extends it).

    The **rate** is data: the invoice's payment term's ``late_interest_pct`` (% a year, the
    terms master of B-01 stays the single source of truth) and, when the term has none,
    ``rate_pct`` here. Nothing is charged until ``grace_days`` after the due date; then
    interest runs from the due date (or the end of the last charge) to the charge date —
    simple interest, ``balance × rate × days / 365``, to the cent — and a charge below
    ``min_fee`` is raised to it. ``target`` says where the fee goes: a line appended to the
    customer's next statement, or a separate fee invoice (``fee_account`` is its revenue)."""

    is_active = models.BooleanField(_("charge late interest"), default=False)
    rate_pct = models.DecimalField(
        _("interest (% a year) when the payment term has none"),
        max_digits=6,
        decimal_places=3,
        default=Decimal("0"),
    )
    grace_days = models.PositiveSmallIntegerField(_("grace period (days)"), default=0)
    min_fee = _money(_("minimum fee"))
    target = models.CharField(
        _("charged on"),
        max_length=12,
        choices=LateFeeTarget.choices,
        default=LateFeeTarget.STATEMENT,
    )
    fee_account = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("fee income account"),
    )

    class Meta:
        verbose_name = _("late fee policy")
        verbose_name_plural = _("late fee policies")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["organisation"], name="sales_late_fee_policy_once"),
            models.CheckConstraint(
                condition=models.Q(rate_pct__gte=0, rate_pct__lte=100),
                name="sales_late_fee_policy_rate_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(min_fee__gte=0), name="sales_late_fee_policy_min_fee"
            ),
            models.CheckConstraint(
                condition=models.Q(target__in=LateFeeTarget.values),
                name="sales_late_fee_policy_target_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.organisation} late fees"


class LateFeeCharge(OrgOwnedModel):
    """Interest charged on one overdue invoice for one stretch of days (D-07-T06): kept so the
    next charge starts where this one ended (never twice for the same days), with the figures
    it was computed from and where it went (a statement date or a fee invoice)."""

    invoice = models.ForeignKey(
        Invoice, on_delete=models.PROTECT, related_name="late_fees", verbose_name=_("invoice")
    )
    start = models.DateField(_("from"))
    end = models.DateField(_("to"))
    days = models.PositiveIntegerField(_("days"))
    balance = _money(_("overdue balance"))
    rate_pct = models.DecimalField(_("rate (% a year)"), max_digits=6, decimal_places=3)
    amount = _money(_("fee"))
    target = models.CharField(_("charged on"), max_length=12, choices=LateFeeTarget.choices)
    fee_invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="fee_charges",
        verbose_name=_("fee invoice"),
    )

    class Meta:
        ordering = ("invoice", "end", "pk")
        verbose_name = _("late fee charge")
        verbose_name_plural = _("late fee charges")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["invoice", "end"], name="sales_late_fee_once_per_day"),
            models.CheckConstraint(
                condition=models.Q(end__gt=models.F("start")), name="sales_late_fee_period_order"
            ),
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="sales_late_fee_amount_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(target__in=LateFeeTarget.values),
                name="sales_late_fee_target_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.invoice} {self.start:%Y-%m-%d}–{self.end:%Y-%m-%d}: {self.amount}"

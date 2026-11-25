"""Invoices (D-03a-T01): ``Invoice`` and ``InvoiceLine`` on the shared document base (D-01).

Status: Draft → (Awaiting approval, when the organisation's rule asks, D-03a-T05) → Approved →
Sent → Partially paid → Paid, or Void. The **number** is allocated at approval, in the posting
transaction (D-03a-T02) — a draft has none and shows "Draft"; a void invoice keeps its number.
``journal_entry`` is the posting of the approval (D-03a-T03), ``void_entry`` its reversal
(D-03a-T07). ``current_revision`` is the latest ``InvoiceRevision`` once posted invoices become
editable (D-03b fills it; empty until then).

Credit notes (D-06-T01): ``CreditNote`` and ``CreditNoteLine`` on the same document base, numbered
``CN-0001`` at approval; optionally the invoice it credits ("Credit this invoice", D-06-T02).
Approval posts Dr revenue / Dr tax / Cr AR (D-06-T03). ``CreditApplication`` applies part of a
credit note to an invoice (amount ≤ the invoice's open balance and ≤ the credit remaining,
D-06-T04); ``amount_applied`` and ``amount_refunded`` are the credit used so far.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.documents.models import (
    DiscountType,
    DocumentBase,
    DocumentLineBase,
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
    invoiced) and the invoice it became.

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

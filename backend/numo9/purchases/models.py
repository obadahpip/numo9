"""Purchase orders (E-01-T01) on the shared document base (D-01), purchase side.

A purchase order is **non-posting**: it records a commitment (E-01-T08), never a journal. Its
status (``PurchaseOrderStatus``):

- ``draft`` → ``awaiting_approval`` (when the approver's limit or a rule asks, E-01-T02) →
  ``approved`` (numbered ``PO-0001`` at approval);
- ``partially_received`` / ``received`` — goods receipts (E-01-T04) against its lines;
- ``billed`` — every line billed (E-02); ``closed`` — closed by hand, outstanding quantities
  dropped; ``cancelled`` — cancelled (a partially received PO is closed instead).

``approved_total`` — the total when it was last approved: an approved PO whose total goes above
it goes back to Awaiting approval (E-01-T03). Delivery block: ``delivery_attention``,
``delivery_address``, ``delivery_date``, ``delivery_instructions``.

A line (``PurchaseOrderLine``) adds ``quantity_received`` and ``quantity_billed`` (kept by the
receipt and bill services); outstanding = ordered − received.

Supplier credits (E-03-T04): ``SupplierCredit`` and ``SupplierCreditLine`` — money a supplier
owes back (a returned item, an overcharge) — on the same document base, the supplier's own credit
note number in ``supplier_reference``, optionally the bill it credits. Approval posts Dr AP /
Cr expense / Cr ITC (E-03-T05). ``SupplierCreditApplication`` applies part of a credit to a bill
(≤ the bill's open balance and the credit remaining, E-03-T06).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.documents.models import DocumentBase, DocumentLineBase
from numo9.tenancy.models import OrgOwnedModel


class PurchaseOrderStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    AWAITING_APPROVAL = "awaiting_approval", _("Awaiting approval")
    APPROVED = "approved", _("Approved")
    PARTIALLY_RECEIVED = "partially_received", _("Partially received")
    RECEIVED = "received", _("Received")
    BILLED = "billed", _("Billed")
    CLOSED = "closed", _("Closed")
    CANCELLED = "cancelled", _("Cancelled")


#: Statuses of a PO that commits the organisation (open, E-01-T08 commitments).
OPEN_STATUSES: frozenset[str] = frozenset(
    {
        PurchaseOrderStatus.APPROVED,
        PurchaseOrderStatus.PARTIALLY_RECEIVED,
        PurchaseOrderStatus.RECEIVED,
    }
)
#: Statuses of a PO that has been approved (it has a number).
NUMBERED_STATUSES: frozenset[str] = frozenset(
    {
        PurchaseOrderStatus.APPROVED,
        PurchaseOrderStatus.PARTIALLY_RECEIVED,
        PurchaseOrderStatus.RECEIVED,
        PurchaseOrderStatus.BILLED,
        PurchaseOrderStatus.CLOSED,
    }
)


def _user(name: Any) -> Any:
    return models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=name,
    )


class PurchaseOrder(DocumentBase):
    number = models.CharField(_("number"), max_length=40, blank=True)
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=PurchaseOrderStatus.choices,
        default=PurchaseOrderStatus.DRAFT,
    )
    notes = models.TextField(_("notes"), blank=True)
    delivery_attention = models.CharField(_("delivery attention"), max_length=100, blank=True)
    delivery_address = models.TextField(_("delivery address"), blank=True)
    delivery_date = models.DateField(_("delivery date"), null=True, blank=True)
    delivery_instructions = models.TextField(_("delivery instructions"), blank=True)
    submitted_by = _user(_("submitted by"))
    submitted_at = models.DateTimeField(_("submitted at"), null=True, blank=True)
    approved_by = _user(_("approved by"))
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)
    approved_total = models.DecimalField(
        _("total when approved"), max_digits=18, decimal_places=2, null=True, blank=True
    )
    sent_at = models.DateTimeField(_("sent at"), null=True, blank=True)
    closed_at = models.DateTimeField(_("closed at"), null=True, blank=True)
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)

    class Meta(DocumentBase.Meta):
        abstract = False
        ordering = ("-date", "-pk")
        verbose_name = _("purchase order")
        verbose_name_plural = _("purchase orders")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *DocumentBase.header_constraints("purchases_po"),
            models.CheckConstraint(
                condition=models.Q(status__in=PurchaseOrderStatus.values),
                name="purchases_po_status_valid",
            ),
            models.UniqueConstraint(
                fields=["organisation", "number"],
                condition=~models.Q(number=""),
                name="purchases_po_number_unique",
            ),
            # An approved PO has its number (kept when closed); a draft has none.
            models.CheckConstraint(
                condition=~models.Q(status__in=sorted(NUMBERED_STATUSES)) | ~models.Q(number=""),
                name="purchases_po_approved_numbered",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "status"], name="purchases_po_status_idx"),
            models.Index(
                fields=["organisation", "contact", "date"], name="purchases_po_contact_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.number or str(_("Draft purchase order"))


class PurchaseOrderLine(DocumentLineBase):
    document = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="lines", verbose_name=_("PO")
    )
    quantity_received = models.DecimalField(
        _("received"), max_digits=18, decimal_places=4, default=Decimal("0")
    )
    quantity_billed = models.DecimalField(
        _("billed"), max_digits=18, decimal_places=4, default=Decimal("0")
    )

    class Meta(DocumentLineBase.Meta):
        abstract = False
        verbose_name = _("purchase order line")
        verbose_name_plural = _("purchase order lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *DocumentLineBase.line_constraints("purchases_poline"),
            models.CheckConstraint(
                condition=models.Q(quantity_received__gte=0) & models.Q(quantity_billed__gte=0),
                name="purchases_poline_quantities_positive",
            ),
        ]

    @property
    def outstanding(self) -> Decimal:
        return max(Decimal(self.quantity) - Decimal(self.quantity_received), Decimal("0"))


class GoodsReceipt(AuditedModel, OrgOwnedModel):
    """A delivery received against a purchase order (E-01-T04): the date, who received it, notes,
    and its lines (quantity per PO line). A reversed receipt (E-01-T06) keeps its row with when,
    who and why; its quantities no longer count."""

    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        related_name="receipts",
        verbose_name=_("purchase order"),
    )
    date = models.DateField(_("date received"))
    received_by = _user(_("received by"))
    notes = models.TextField(_("notes"), blank=True)
    reversed_at = models.DateTimeField(_("reversed at"), null=True, blank=True)
    reversed_by = _user(_("reversed by"))
    reversal_reason = models.CharField(_("reversal reason"), max_length=500, blank=True)

    class Meta:
        ordering = ("-date", "-pk")
        verbose_name = _("goods receipt")
        verbose_name_plural = _("goods receipts")

    def __str__(self) -> str:
        return f"{self.purchase_order} · {self.date:%Y-%m-%d}"


class GoodsReceiptLine(OrgOwnedModel):
    receipt = models.ForeignKey(
        GoodsReceipt, on_delete=models.CASCADE, related_name="lines", verbose_name=_("receipt")
    )
    po_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.PROTECT,
        related_name="receipt_lines",
        verbose_name=_("PO line"),
    )
    quantity = models.DecimalField(_("quantity received"), max_digits=18, decimal_places=4)

    class Meta:
        ordering = ("receipt", "pk")
        verbose_name = _("goods receipt line")
        verbose_name_plural = _("goods receipt lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0), name="purchases_grnline_quantity_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.po_line} × {self.quantity}"


# ---- Bills (E-02) ------------------------------------------------------------------------------


class BillStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    AWAITING_APPROVAL = "awaiting_approval", _("Awaiting approval")
    AWAITING_PAYMENT = "awaiting_payment", _("Awaiting payment")
    PARTIALLY_PAID = "partially_paid", _("Partially paid")
    PAID = "paid", _("Paid")
    VOID = "void", _("Void")


#: Statuses of a bill that has posted to the ledger (it has its number and journal).
BILL_POSTED_STATUSES: frozenset[str] = frozenset(
    {
        BillStatus.AWAITING_PAYMENT,
        BillStatus.PARTIALLY_PAID,
        BillStatus.PAID,
        BillStatus.VOID,
    }
)


class HoldbackType(models.TextChoices):
    NONE = "none", _("No holdback")
    AMOUNT = "amount", _("Amount")
    PERCENT = "percent", _("Percent of the total")


class Bill(DocumentBase):
    """A supplier's bill (E-02-T01) on the shared document base, purchase side.

    Status: Draft → (Awaiting approval, when a routing rule or the approver's limit asks,
    E-02-T07) → Awaiting payment (approved and posted: Dr expense / asset, Dr ITC, Cr AP, Cr
    holdback, E-02-T05) → Partially paid → Paid, or Void (E-02-T09).

    - ``number`` — Numo9's own number (``BILL-0001``), taken at approval; a draft has none;
    - ``supplier_invoice_no`` — the supplier's invoice number, **unique per supplier** among the
      bills that aren't void (the same number from two suppliers is fine, gap-24);
    - ``department`` — the department (a tracking option) the routing rules read (E-02-T07);
    - holdback (construction): ``holdback_type`` none / amount / percent of the total and
      ``holdback_value``; ``holdback_amount`` is posted to Holdback payable instead of AP and
      ``holdback_released`` is what has been released to AP since (E-02-T06);
    - ``purchase_order`` — the PO it bills (E-02-T08), if any.
    """

    number = models.CharField(_("number"), max_length=40, blank=True)
    supplier_invoice_no = models.CharField(_("supplier invoice number"), max_length=100, blank=True)
    status = models.CharField(
        _("status"), max_length=20, choices=BillStatus.choices, default=BillStatus.DRAFT
    )
    notes = models.TextField(_("notes"), blank=True)
    department = models.CharField(_("department"), max_length=100, blank=True)
    purchase_order = models.ForeignKey(
        PurchaseOrder,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bills",
        verbose_name=_("purchase order"),
    )
    holdback_type = models.CharField(
        _("holdback"), max_length=8, choices=HoldbackType.choices, default=HoldbackType.NONE
    )
    holdback_value = models.DecimalField(
        _("holdback value"), max_digits=18, decimal_places=4, default=Decimal("0")
    )
    holdback_amount = models.DecimalField(
        _("holdback amount"), max_digits=18, decimal_places=2, default=Decimal("0")
    )
    holdback_released = models.DecimalField(
        _("holdback released"), max_digits=18, decimal_places=2, default=Decimal("0")
    )
    amount_paid = models.DecimalField(
        _("amount paid"), max_digits=18, decimal_places=2, default=Decimal("0")
    )
    journal_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bill",
        verbose_name=_("journal"),
    )
    void_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voided_bill",
        verbose_name=_("void journal"),
    )
    submitted_by = _user(_("submitted by"))
    submitted_at = models.DateTimeField(_("submitted at"), null=True, blank=True)
    approved_by = _user(_("approved by"))
    approved_at = models.DateTimeField(_("approved at"), null=True, blank=True)
    voided_at = models.DateTimeField(_("voided at"), null=True, blank=True)

    class Meta(DocumentBase.Meta):
        abstract = False
        ordering = ("-date", "-pk")
        verbose_name = _("bill")
        verbose_name_plural = _("bills")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *DocumentBase.header_constraints("purchases_bill"),
            models.CheckConstraint(
                condition=models.Q(status__in=BillStatus.values),
                name="purchases_bill_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(holdback_type__in=HoldbackType.values),
                name="purchases_bill_holdback_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(holdback_value__gte=0)
                & models.Q(holdback_amount__gte=0)
                & models.Q(holdback_released__gte=0)
                & models.Q(holdback_released__lte=models.F("holdback_amount")),
                name="purchases_bill_holdback_amounts",
            ),
            models.CheckConstraint(
                condition=~models.Q(holdback_type=HoldbackType.PERCENT)
                | models.Q(holdback_value__lte=100),
                name="purchases_bill_holdback_pct_max",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_paid__gte=0), name="purchases_bill_paid_positive"
            ),
            models.UniqueConstraint(
                fields=["organisation", "number"],
                condition=~models.Q(number=""),
                name="purchases_bill_number_unique",
            ),
            # gap-24: one supplier invoice number per supplier, among bills that aren't void.
            models.UniqueConstraint(
                fields=["organisation", "contact", "supplier_invoice_no"],
                condition=~models.Q(supplier_invoice_no="")
                & ~models.Q(status="void")
                & models.Q(deleted_at__isnull=True),
                name="purchases_bill_supplier_invoice_unique",
            ),
            # A posted bill has its number and its journal; a draft has neither.
            models.CheckConstraint(
                condition=~models.Q(status__in=sorted(BILL_POSTED_STATUSES))
                | (~models.Q(number="") & models.Q(journal_entry__isnull=False)),
                name="purchases_bill_posted_numbered",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=["organisation", "status"], name="purchases_bill_status_idx"),
            models.Index(
                fields=["organisation", "contact", "date"], name="purchases_bill_contact_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.number or str(_("Draft bill"))

    @property
    def is_posted(self) -> bool:
        return self.status in BILL_POSTED_STATUSES

    @property
    def amount_due(self) -> Decimal:
        """What is owed now (AP): the total less the holdback still held and the payments."""
        held = Decimal(self.holdback_amount) - Decimal(self.holdback_released)
        return Decimal(self.total) - held - Decimal(self.amount_paid)

    @property
    def holdback_outstanding(self) -> Decimal:
        return Decimal(self.holdback_amount) - Decimal(self.holdback_released)


class BillLine(DocumentLineBase):
    document = models.ForeignKey(
        Bill, on_delete=models.CASCADE, related_name="lines", verbose_name=_("bill")
    )
    po_line = models.ForeignKey(
        PurchaseOrderLine,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bill_lines",
        verbose_name=_("PO line"),
    )

    class Meta(DocumentLineBase.Meta):
        abstract = False
        verbose_name = _("bill line")
        verbose_name_plural = _("bill lines")
        constraints: ClassVar[list[models.BaseConstraint]] = DocumentLineBase.line_constraints(
            "purchases_billline"
        )


class ApprovalRoutingRule(AuditedModel, OrgOwnedModel):
    """Who approves a bill (E-02-T07): bills whose total is in an **amount band** (``min_amount``
    < total ≤ ``max_amount``; an empty bound is open) and, optionally, of one **department** go
    to the people holding ``approver_role`` — "Routed to Finance approvers (amount > 2,000)".
    Rules are tried in ``position`` order; the first that matches wins. ``doc_type`` is ``bill``
    now (the approval document types of A-03), so other documents can route the same way later.
    """

    doc_type = models.CharField(_("document type"), max_length=32, default="bill")
    name = models.CharField(_("name"), max_length=100)
    position = models.PositiveIntegerField(_("order"), default=0)
    min_amount = models.DecimalField(
        _("more than"), max_digits=18, decimal_places=2, null=True, blank=True
    )
    max_amount = models.DecimalField(
        _("up to"), max_digits=18, decimal_places=2, null=True, blank=True
    )
    department = models.CharField(_("department"), max_length=100, blank=True)
    approver_role = models.ForeignKey(
        "rbac.Role", on_delete=models.PROTECT, related_name="+", verbose_name=_("approvers")
    )
    is_active = models.BooleanField(_("active"), default=True)

    class Meta:
        ordering = ("doc_type", "position", "pk")
        verbose_name = _("approval routing rule")
        verbose_name_plural = _("approval routing rules")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(min_amount__isnull=True)
                | models.Q(max_amount__isnull=True)
                | models.Q(max_amount__gt=models.F("min_amount")),
                name="purchases_routing_band_valid",
            ),
            models.CheckConstraint(
                condition=(models.Q(min_amount__isnull=True) | models.Q(min_amount__gte=0))
                & (models.Q(max_amount__isnull=True) | models.Q(max_amount__gte=0)),
                name="purchases_routing_amounts_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class SupplierCreditStatus(models.TextChoices):
    DRAFT = "draft", _("Draft")
    APPROVED = "approved", _("Approved")
    PARTIALLY_APPLIED = "partially_applied", _("Partially applied")
    APPLIED = "applied", _("Applied")
    VOID = "void", _("Void")


SUPPLIER_CREDIT_POSTED: frozenset[str] = frozenset(
    {
        SupplierCreditStatus.APPROVED,
        SupplierCreditStatus.PARTIALLY_APPLIED,
        SupplierCreditStatus.APPLIED,
        SupplierCreditStatus.VOID,
    }
)


def _amount(label: Any) -> models.DecimalField[Any, Any]:
    return models.DecimalField(label, max_digits=18, decimal_places=2, default=Decimal("0"))


class SupplierCredit(DocumentBase):
    status = models.CharField(
        _("status"),
        max_length=20,
        choices=SupplierCreditStatus.choices,
        default=SupplierCreditStatus.DRAFT,
    )
    supplier_reference = models.CharField(
        _("supplier's credit note number"), max_length=100, blank=True
    )
    bill = models.ForeignKey(
        Bill,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supplier_credits",
        verbose_name=_("credited bill"),
    )
    notes = models.TextField(_("notes"), blank=True)
    amount_applied = _amount(_("amount applied"))
    amount_refunded = _amount(_("amount refunded"))
    journal_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="supplier_credit",
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

    class Meta(DocumentBase.Meta):
        abstract = False
        ordering = ("-date", "-pk")
        verbose_name = _("supplier credit")
        verbose_name_plural = _("supplier credits")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            *DocumentBase.header_constraints("purchases_suppliercredit"),
            models.CheckConstraint(
                condition=models.Q(status__in=SupplierCreditStatus.values),
                name="purchases_suppliercredit_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(status__in=sorted(SUPPLIER_CREDIT_POSTED))
                | models.Q(journal_entry__isnull=False),
                name="purchases_suppliercredit_posted_journal",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_applied__gte=0, amount_refunded__gte=0)
                & models.Q(total__gte=models.F("amount_applied") + models.F("amount_refunded")),
                name="purchases_suppliercredit_used_within_total",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "contact", "date"], name="purch_supcredit_contact_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.supplier_reference or str(_("Supplier credit"))

    @property
    def remaining(self) -> Decimal:
        return Decimal(self.total) - Decimal(self.amount_applied) - Decimal(self.amount_refunded)


class SupplierCreditLine(DocumentLineBase):
    document = models.ForeignKey(
        SupplierCredit,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name=_("supplier credit"),
    )

    class Meta(DocumentLineBase.Meta):
        abstract = False
        verbose_name = _("supplier credit line")
        verbose_name_plural = _("supplier credit lines")
        constraints: ClassVar[list[models.BaseConstraint]] = DocumentLineBase.line_constraints(
            "purchases_suppliercreditline"
        )


class SupplierCreditApplication(OrgOwnedModel):
    credit = models.ForeignKey(
        SupplierCredit,
        on_delete=models.PROTECT,
        related_name="applications",
        verbose_name=_("supplier credit"),
    )
    bill = models.ForeignKey(
        Bill, on_delete=models.PROTECT, related_name="credit_applications", verbose_name=_("bill")
    )
    amount = _amount(_("amount"))
    date = models.DateField(_("date"))
    created_at = models.DateTimeField(_("applied at"), auto_now_add=True)

    class Meta:
        ordering = ("date", "pk")
        verbose_name = _("supplier credit application")
        verbose_name_plural = _("supplier credit applications")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="purchases_supcreditapp_positive"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.credit} → {self.bill}: {self.amount}"

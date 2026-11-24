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

"""Item stub (D-01-T02), pending H-01: what a document line takes from an item.

- ``code`` (unique in the organisation, case-insensitive, among items not archived) and ``name``;
- ``description`` — the line's default description (else the name);
- ``sales_price`` / ``purchase_price`` — default unit prices (4 decimals);
- ``sales_account`` / ``purchase_account`` — default accounts (C-01);
- ``sales_tax_key`` / ``purchase_tax_key`` — default tax codes by key (G-01 code keys, such as
  ``sales.zero_rated`` for basic groceries or ``sales.exempt`` for exempt services). Keys, not
  code versions: the version in force on the document date is resolved per document (G-01-T08),
  and the key is the item step of the place-of-supply precedence (G-02);
- ``is_tracked`` — always False until H-01 adds inventory;
- ``archived_at`` — archived items are hidden from pickers.

``numo9.documents.lines.apply_item`` copies the defaults into a line.
"""

from __future__ import annotations

from decimal import Decimal
from typing import ClassVar

from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel


class Item(AuditedModel, OrgOwnedModel):
    code = models.CharField(_("code"), max_length=40)
    name = models.CharField(_("name"), max_length=200)
    description = models.TextField(_("description"), blank=True)
    sales_price = models.DecimalField(
        _("sale price"), max_digits=18, decimal_places=4, null=True, blank=True
    )
    purchase_price = models.DecimalField(
        _("purchase price"), max_digits=18, decimal_places=4, null=True, blank=True
    )
    sales_account = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("sales account"),
    )
    purchase_account = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("purchase account"),
    )
    sales_tax_key = models.CharField(_("sales tax code"), max_length=60, blank=True)
    purchase_tax_key = models.CharField(_("purchase tax code"), max_length=60, blank=True)
    is_tracked = models.BooleanField(_("track inventory"), default=False)
    archived_at = models.DateTimeField(_("archived"), null=True, blank=True)

    class Meta:
        ordering = ("code",)
        verbose_name = _("item")
        verbose_name_plural = _("items")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "organisation",
                Lower("code"),
                condition=models.Q(archived_at__isnull=True),
                name="items_item_code_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(is_tracked=False), name="items_item_untracked_until_h01"
            ),
            models.CheckConstraint(
                condition=models.Q(sales_tax_key="") | models.Q(sales_tax_key__startswith="sales."),
                name="items_item_sales_tax_key_side",
            ),
            models.CheckConstraint(
                condition=models.Q(purchase_tax_key="")
                | models.Q(purchase_tax_key__startswith="purchase."),
                name="items_item_purchase_tax_key_side",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.name}"

    def audit_label(self) -> str:
        return str(self)

    @property
    def is_taxable(self) -> bool:
        """False for an item whose sales code is zero-rated or exempt (no PST warning, G-02)."""
        return self.sales_tax_key not in ("sales.zero_rated", "sales.exempt", "sales.out_of_scope")

    def default_price(self, side: str) -> Decimal | None:
        return self.sales_price if side == "sales" else self.purchase_price

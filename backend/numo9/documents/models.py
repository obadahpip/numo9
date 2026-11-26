"""Shared document models (D-01-T01): the abstract header and line every sales and purchase
document inherits — quotes, invoices, recurring invoices, credit notes (D-02…D-04) and, in E-02,
bills, purchase orders and supplier credits.

``DocumentBase`` (header):

- ``contact`` — the customer or supplier (B-01); ``date`` and ``due_date`` (required on save by
  the editors, D-01-T17; resolved from ``terms`` by ``numo9.documents.due_dates``);
- ``terms`` — the payment term from the master list (B-01-T05);
- ``currency`` — CAD in Phase 1 (R-01 adds the others);
- ``tax_mode`` — exclusive / inclusive / no tax (the same three as spend money);
- ``ship_to_country`` / ``ship_to_province`` — the document ship-to that places the supply
  (G-02); empty → the contact's own addresses;
- ``discount_type`` / ``discount_value`` — the document-level discount (amount or %),
  allocated pro-rata to lines for tax (D-01-T05);
- ``subtotal`` / ``discount_total`` / ``tax_total`` / ``total`` — the stored result of the
  ``DocumentCalculator`` (server-authoritative);
- ``version`` — bumped on every saved change (optimistic concurrency for the editors).

``DocumentLineBase`` (line): ``position``, ``item`` (D-01-T02 stub), ``description``,
``quantity`` (4 decimals), ``unit_price`` (4 decimals), line discount (amount or %), ``account``,
``tax_code`` (a version, G-01), ``tax_overridden`` (the "changed from default" dot, G-02),
``tracking`` and the calculated ``net`` / ``tax_amount`` / ``amount``.

Concrete documents add their own number, status and the line's foreign key to the header
(``document = ForeignKey(<Header>, related_name="lines")``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, ClassVar

from django.db import models
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.tenancy.models import OrgOwnedModel

ZERO = Decimal("0")


class TaxMode(models.TextChoices):
    EXCLUSIVE = "exclusive", _("Tax exclusive")
    INCLUSIVE = "inclusive", _("Tax inclusive")
    NO_TAX = "no_tax", _("No tax")


class DiscountType(models.TextChoices):
    NONE = "none", _("No discount")
    AMOUNT = "amount", _("Amount")
    PERCENT = "percent", _("Percent")


def _money(verbose: Any) -> Any:
    return models.DecimalField(verbose, max_digits=18, decimal_places=2, default=ZERO)


def _choices_q(field: str, choices: type[models.TextChoices]) -> models.Q:
    return models.Q(**{f"{field}__in": choices.values})


class DocumentBase(AuditedModel, OrgOwnedModel):
    """The header of a sales or purchase document (module docstring)."""

    contact = models.ForeignKey(
        "contacts.Contact", on_delete=models.PROTECT, related_name="+", verbose_name=_("contact")
    )
    date = models.DateField(_("date"))
    due_date = models.DateField(_("due date"), null=True, blank=True)
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
        _("discount value"), max_digits=18, decimal_places=4, default=ZERO
    )
    subtotal = _money(_("subtotal"))
    discount_total = _money(_("discount"))
    tax_total = _money(_("tax"))
    total = _money(_("total"))
    version = models.PositiveIntegerField(_("version"), default=1)

    class Meta:
        abstract = True
        constraints: ClassVar[list[models.BaseConstraint]] = []

    @classmethod
    def header_constraints(cls, prefix: str) -> list[models.BaseConstraint]:
        """Check constraints a concrete header adds to its ``Meta.constraints`` (names must be
        unique per table, so each document passes its own prefix)."""
        return [
            models.CheckConstraint(
                condition=_choices_q("tax_mode", TaxMode), name=f"{prefix}_tax_mode_valid"
            ),
            models.CheckConstraint(
                condition=_choices_q("discount_type", DiscountType),
                name=f"{prefix}_discount_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_value__gte=0), name=f"{prefix}_discount_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(discount_type=DiscountType.PERCENT)
                | models.Q(discount_value__lte=100),
                name=f"{prefix}_discount_pct_max",
            ),
            models.CheckConstraint(
                condition=models.Q(due_date__isnull=True)
                | models.Q(due_date__gte=models.F("date")),
                name=f"{prefix}_due_after_date",
            ),
        ]


class DocumentLineBase(OrgOwnedModel):
    """A line of a sales or purchase document (module docstring)."""

    position = models.PositiveIntegerField(_("position"), default=0)
    item = models.ForeignKey(
        "items.Item",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("item"),
    )
    description = models.TextField(_("description"), blank=True)
    quantity = models.DecimalField(_("quantity"), max_digits=18, decimal_places=4, default=1)
    unit_price = models.DecimalField(_("unit price"), max_digits=18, decimal_places=4, default=ZERO)
    discount_type = models.CharField(
        _("line discount"), max_length=8, choices=DiscountType.choices, default=DiscountType.NONE
    )
    discount_value = models.DecimalField(
        _("line discount value"), max_digits=18, decimal_places=4, default=ZERO
    )
    account = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("account"),
    )
    tax_code = models.ForeignKey(
        "tax.TaxCode",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("tax code"),
    )
    tax_overridden = models.BooleanField(_("tax changed from the default"), default=False)
    tracking = models.JSONField(_("tracking"), default=dict, blank=True)
    net = _money(_("net"))
    tax_amount = _money(_("tax"))
    amount = _money(_("amount"))

    class Meta:
        abstract = True
        ordering = ("position", "id")

    @classmethod
    def line_constraints(cls, prefix: str) -> list[models.BaseConstraint]:
        return [
            models.CheckConstraint(
                condition=_choices_q("discount_type", DiscountType),
                name=f"{prefix}_discount_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_value__gte=0), name=f"{prefix}_discount_positive"
            ),
            models.CheckConstraint(
                condition=~models.Q(discount_type=DiscountType.PERCENT)
                | models.Q(discount_value__lte=100),
                name=f"{prefix}_discount_pct_max",
            ),
        ]


# ---- recurring documents (D-04-T05, shared with E-03-T02) -------------------------------------


class RecurringRunStatus(models.TextChoices):
    CREATED = "created", _("Created")
    SKIPPED = "skipped", _("Skipped")


class RecurringRunBase(OrgOwnedModel):
    """One occurrence of a recurring document (``numo9.documents.recurring``): the idempotency
    row. A concrete run adds ``template`` (the template, ``related_name="runs"``) and
    ``document`` (the invoice or bill it created, one-to-one) and the unique constraint on
    (template, occurrence date) from ``run_constraints`` — a tick that runs twice (two workers, a
    restart) inserts the row once, and only the insert that wins keeps its document.

    ``status`` — created, or skipped (``code`` / ``message`` say why: paused, ended, locked
    period, archived contact); a created run may carry a ``code`` too when the mode's next step
    was refused (the document then stays a draft, or approved but not sent)."""

    occurrence_date = models.DateField(_("occurrence date"))
    template_version = models.PositiveIntegerField(_("template version"))
    status = models.CharField(_("status"), max_length=10, choices=RecurringRunStatus.choices)
    code = models.CharField(_("reason code"), max_length=100, blank=True)
    message = models.TextField(_("reason"), blank=True)

    class Meta:
        abstract = True
        ordering = ("template", "-occurrence_date")

    @classmethod
    def run_constraints(cls, prefix: str) -> list[models.BaseConstraint]:
        return [
            models.UniqueConstraint(fields=["template", "occurrence_date"], name=f"{prefix}_once"),
            models.CheckConstraint(
                condition=_choices_q("status", RecurringRunStatus),
                name=f"{prefix}_status_valid",
            ),
            # A created run has its document; a skipped one has none.
            models.CheckConstraint(
                condition=models.Q(status=RecurringRunStatus.CREATED, document__isnull=False)
                | models.Q(status=RecurringRunStatus.SKIPPED, document__isnull=True),
                name=f"{prefix}_document_iff_created",
            ),
        ]

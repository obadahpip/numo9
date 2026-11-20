"""Bank accounts (F-01-T02): the banking profile of a ledger account.

A ``BankAccount`` is attached one-to-one to a ledger account (C-01) and says what kind of money it
holds — ``BankAccountType``: Chequing, Savings, Credit card, Line of credit, Loan, Cash / petty
cash or Clearing. It is usable the moment it exists: spend money, receive money and transfers post
to its ledger account (F-01-T05); there is no feed, import, reconciliation or plan gate.

- ``display_name`` — what people call it ("TD Business Chequing"), unique in the organisation
  (case-insensitive, among accounts not deleted);
- ``institution`` — the bank ("TD Canada Trust"); free text, picked from a Canadian list in the UI;
- ``currency`` — CAD by default; fixed once the account has transactions (F-01-T04; R-01 adds
  multi-currency);
- ``account_last4`` / ``transit_number`` / ``institution_number`` — stored encrypted
  (``EncryptedField``), shown masked (``masked_number`` → "•••• 4821"), never in the audit log;
- ``statement_balance`` / ``statement_balance_date`` — optional, beside the ledger balance (which is
  never edited: it is the ledger account's posted lines);
- ``is_reconciled_tracking`` — the organisation chose to reconcile this account (optional, never
  blocks anything);
- ``archived_at`` — archived accounts are hidden from pickers and kept in reports.
"""

from __future__ import annotations

from typing import ClassVar

from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.security.fields import EncryptedField
from numo9.tenancy.models import OrgOwnedModel

MONEY_DIGITS, MONEY_PLACES = 18, 2


class BankAccountType(models.TextChoices):
    CHEQUING = "chequing", _("Chequing")
    SAVINGS = "savings", _("Savings")
    CREDIT_CARD = "credit_card", _("Credit card")
    LINE_OF_CREDIT = "line_of_credit", _("Line of credit")
    LOAN = "loan", _("Loan")
    CASH = "cash", _("Cash / petty cash")
    CLEARING = "clearing", _("Clearing")


class BankAccount(AuditedModel, OrgOwnedModel):
    audit_masked: ClassVar[frozenset[str]] = frozenset(
        {"account_last4", "transit_number", "institution_number"}
    )

    gl_account = models.OneToOneField(
        "ledger.Account",
        on_delete=models.PROTECT,
        related_name="bank_account",
        verbose_name=_("ledger account"),
    )
    type = models.CharField(_("account type"), max_length=20, choices=BankAccountType.choices)
    display_name = models.CharField(_("name"), max_length=120)
    institution = models.CharField(_("institution"), max_length=120, blank=True)
    currency = models.CharField(_("currency"), max_length=3, default="CAD")
    account_last4 = EncryptedField(
        _("last 4 digits of the account number"), max_length=4, blank=True
    )
    transit_number = EncryptedField(_("transit number"), max_length=5, blank=True)
    institution_number = EncryptedField(_("institution number"), max_length=3, blank=True)
    statement_balance = models.DecimalField(
        _("statement balance"),
        max_digits=MONEY_DIGITS,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
    )
    statement_balance_date = models.DateField(_("statement balance date"), null=True, blank=True)
    is_reconciled_tracking = models.BooleanField(
        _("reconciliation tracked"), default=False, db_default=False
    )
    archived_at = models.DateTimeField(_("archived at"), null=True, blank=True)

    class Meta:
        ordering = ("display_name", "pk")
        verbose_name = _("bank account")
        verbose_name_plural = _("bank accounts")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "organisation",
                Lower("display_name"),
                condition=models.Q(deleted_at__isnull=True),
                name="banking_account_name_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(type__in=BankAccountType.values),
                name="banking_account_type_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(display_name=""), name="banking_account_name_required"
            ),
        ]

    def __str__(self) -> str:
        return self.display_name

    @property
    def masked_number(self) -> str:
        """``•••• 4821`` — the last 4 digits, masked; "" when not given."""
        return f"•••• {self.account_last4}" if self.account_last4 else ""

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

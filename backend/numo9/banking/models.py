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

from typing import Any, ClassVar

from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.security.fields import EncryptedField
from numo9.tenancy.managers import OrgScopedManager
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


class BankAccountQuerySet(models.QuerySet["BankAccount"]):
    def pickable(self) -> BankAccountQuerySet:
        """Accounts a person can choose on a new transaction: not archived, not deleted
        (F-01-T04). Reports read every account, archived ones included."""
        return self.filter(archived_at__isnull=True, deleted_at__isnull=True)


#: Organisation-scoped (A-01-T04) with the bank-account queryset's helpers.
BankAccountManager = OrgScopedManager.from_queryset(BankAccountQuerySet)


class BankAccount(AuditedModel, OrgOwnedModel):
    objects: ClassVar[Any] = BankAccountManager()

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


# ---- spend money / receive money (F-01-T05) -----------------------------------------------------


class BankTransactionKind(models.TextChoices):
    SPEND = "spend", _("Spend money")
    RECEIVE = "receive", _("Receive money")


class TaxMode(models.TextChoices):
    """How the line amounts are read: before tax, including tax, or with no tax at all."""

    EXCLUSIVE = "exclusive", _("Tax exclusive")
    INCLUSIVE = "inclusive", _("Tax inclusive")
    NO_TAX = "no_tax", _("No tax")


class BankTransactionStatus(models.TextChoices):
    POSTED = "posted", _("Posted")
    VOIDED = "voided", _("Voided")


class BankTransaction(AuditedModel, OrgOwnedModel):
    """Money spent from or received into a bank account, posted as one balanced journal.

    The header carries the totals (``subtotal`` before tax, ``tax_total``, ``total`` — the amount
    that left or reached the bank); the lines say where the money went. ``journal_entry`` is the
    posted journal (its ``source_type`` / ``source_id`` point back here); voiding reverses it."""

    kind = models.CharField(_("kind"), max_length=10, choices=BankTransactionKind.choices)
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="transactions",
        verbose_name=_("bank account"),
    )
    date = models.DateField(_("date"))
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_transactions",
        verbose_name=_("contact"),
    )
    reference = models.CharField(_("reference"), max_length=255, blank=True)
    tax_mode = models.CharField(
        _("amounts are"), max_length=10, choices=TaxMode.choices, default=TaxMode.EXCLUSIVE
    )
    subtotal = models.DecimalField(
        _("subtotal"), max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES
    )
    tax_total = models.DecimalField(_("tax"), max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES)
    total = models.DecimalField(_("total"), max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=BankTransactionStatus.choices,
        default=BankTransactionStatus.POSTED,
    )
    journal_entry = models.OneToOneField(
        "ledger.JournalEntry",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_transaction",
        verbose_name=_("journal"),
    )
    voided_at = models.DateTimeField(_("voided at"), null=True, blank=True)

    class Meta:
        ordering = ("-date", "-pk")
        verbose_name = _("bank transaction")
        verbose_name_plural = _("bank transactions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(kind__in=BankTransactionKind.values),
                name="banking_txn_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(total=models.F("subtotal") + models.F("tax_total")),
                name="banking_txn_total_adds_up",
            ),
            models.CheckConstraint(condition=models.Q(total__gt=0), name="banking_txn_positive"),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "bank_account", "date"], name="banking_txn_acct_idx"
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.total} {self.date:%Y-%m-%d}"


class BankTransactionLine(OrgOwnedModel):
    """One line of a spend / receive: the account the money went to or came from."""

    transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name=_("bank transaction"),
    )
    line_no = models.PositiveSmallIntegerField(_("line"))
    description = models.CharField(_("description"), max_length=500, blank=True)
    account = models.ForeignKey(
        "ledger.Account",
        on_delete=models.PROTECT,
        related_name="bank_transaction_lines",
        verbose_name=_("account"),
    )
    #: As entered (before or including tax, per the header's tax mode).
    amount = models.DecimalField(_("amount"), max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES)
    net = models.DecimalField(_("net"), max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES)
    tax_amount = models.DecimalField(
        _("tax"), max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES, default=0
    )
    tax_code = models.CharField(_("tax code"), max_length=60, blank=True)
    #: The tax portions: ``[{"role": "itc_receivable", "amount": "13.00", "recoverable": true}]``.
    taxes = models.JSONField(_("tax portions"), default=list, blank=True)

    class Meta:
        ordering = ("transaction", "line_no")
        verbose_name = _("bank transaction line")
        verbose_name_plural = _("bank transaction lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=["transaction", "line_no"], name="banking_txn_line_no")
        ]

    def __str__(self) -> str:
        return f"{self.line_no}: {self.net}"

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


# ---- statement import (F-02-T02) ----------------------------------------------------------------


class StatementImportStatus(models.TextChoices):
    """``pending`` (uploaded, not yet committed) → ``processing`` (a large file in a background job)
    → ``committed``; ``undone`` once the batch's lines are removed (F-02-T10); ``failed``."""

    PENDING = "pending", _("Pending")
    PROCESSING = "processing", _("Processing")
    COMMITTED = "committed", _("Committed")
    UNDONE = "undone", _("Undone")
    FAILED = "failed", _("Failed")


class StatementImport(AuditedModel, OrgOwnedModel):
    """One statement file imported into one bank account — the batch its lines belong to.

    ``file`` is the uploaded file (A-06 document store); ``source_name`` the statement source that
    read it (``file`` for uploads, W-02 adds Numo9's banking app); ``file_format`` what the parser
    found (``ofx``, ``qfx``, ``qbo``, ``csv``, ``xlsx``); ``mapping`` the column mapping used, as it
    was at import time (F-02-T05 adds the saved-mapping link). The counts are those of the commit:
    ``lines_total`` read from the file = ``lines_new`` + ``lines_duplicate`` + ``lines_error``."""

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="statement_imports",
        verbose_name=_("bank account"),
    )
    file = models.ForeignKey(
        "files.Document",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="statement_imports",
        verbose_name=_("file"),
    )
    file_name = models.CharField(_("file name"), max_length=255, blank=True)
    source_name = models.CharField(_("source"), max_length=40, default="file")
    file_format = models.CharField(_("format"), max_length=10, blank=True)
    mapping = models.JSONField(_("mapping"), default=dict, blank=True)
    status = models.CharField(
        _("status"),
        max_length=12,
        choices=StatementImportStatus.choices,
        default=StatementImportStatus.PENDING,
    )
    lines_total = models.PositiveIntegerField(_("lines read"), default=0)
    lines_new = models.PositiveIntegerField(_("new lines"), default=0)
    lines_duplicate = models.PositiveIntegerField(_("duplicate lines"), default=0)
    lines_error = models.PositiveIntegerField(_("lines with errors"), default=0)
    committed_at = models.DateTimeField(_("committed at"), null=True, blank=True)
    undone_at = models.DateTimeField(_("undone at"), null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = _("statement import")
        verbose_name_plural = _("statement imports")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(status__in=StatementImportStatus.values),
                name="banking_import_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.file_name or self.source_name} → {self.bank_account_id}"


class StatementLineStatus(models.TextChoices):
    """A statement line is not a ledger posting until it is coded (F-04, spend/receive) or matched
    to a ledger transaction (F-05); ``ignored`` lines are kept but never coded."""

    UNCODED = "uncoded", _("Uncoded")
    CODED = "coded", _("Coded")
    MATCHED = "matched", _("Matched")
    IGNORED = "ignored", _("Ignored")


class StatementLine(OrgOwnedModel):
    """One line of a bank statement, as the bank reported it.

    ``amount`` is signed from the account holder's side: positive = money in (deposit, card
    refund), negative = money out. ``fingerprint`` identifies the line across imports (F-02-T07:
    account + date + amount + normalised description + bank reference/FITID, plus a sequence for
    identical lines on the same day) and is unique per bank account, so the same file imported
    twice adds no line."""

    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name="statement_lines",
        verbose_name=_("bank account"),
    )
    statement_import = models.ForeignKey(
        StatementImport,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="lines",
        verbose_name=_("import"),
    )
    date = models.DateField(_("date"))
    amount = models.DecimalField(_("amount"), max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES)
    description = models.CharField(_("description"), max_length=500, blank=True)
    payee = models.CharField(_("payee"), max_length=255, blank=True)
    reference = models.CharField(_("reference"), max_length=255, blank=True)
    fitid = models.CharField(_("bank transaction ID"), max_length=255, blank=True)
    fingerprint = models.CharField(_("fingerprint"), max_length=64)
    status = models.CharField(
        _("status"),
        max_length=10,
        choices=StatementLineStatus.choices,
        default=StatementLineStatus.UNCODED,
    )

    class Meta:
        ordering = ("bank_account", "-date", "-pk")
        verbose_name = _("statement line")
        verbose_name_plural = _("statement lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["bank_account", "fingerprint"], name="banking_stmt_line_fingerprint"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=StatementLineStatus.values),
                name="banking_stmt_line_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(fingerprint=""), name="banking_stmt_line_fingerprint_required"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(
                fields=["organisation", "bank_account", "status", "date"],
                name="banking_stmt_line_status_idx",
            )
        ]

    def __str__(self) -> str:
        return f"{self.date:%Y-%m-%d} {self.amount} {self.description}"

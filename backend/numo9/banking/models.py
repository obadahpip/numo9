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
from django.db.models import Deferrable
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
    #: The statement mapping last chosen for this account's CSV / XLSX files (F-02-T06).
    statement_mapping = models.ForeignKey(
        "banking.StatementMapping",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("statement mapping"),
    )

    audit_exclude: ClassVar[frozenset[str]] = frozenset({"statement_mapping"})

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
    """``draft`` — written but not posted: a bank rule's suggested coding of a statement line,
    waiting for review (F-04-T07); it has no journal until it is posted."""

    DRAFT = "draft", _("Draft")
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
    was at import time, and ``statement_mapping`` the saved mapping it started from (F-02-T05).
    The counts are those of the commit:
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
    statement_mapping = models.ForeignKey(
        "banking.StatementMapping",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imports",
        verbose_name=_("saved mapping"),
    )
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
    #: The statement's balances when the file gives them (F-02-T14: OFX ``LEDGERBAL``, or a
    #: running-balance column).
    opening_balance = models.DecimalField(
        _("opening balance"),
        max_digits=MONEY_DIGITS,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
    )
    opening_balance_date = models.DateField(_("opening balance date"), null=True, blank=True)
    closing_balance = models.DecimalField(
        _("closing balance"),
        max_digits=MONEY_DIGITS,
        decimal_places=MONEY_PLACES,
        null=True,
        blank=True,
    )
    closing_balance_date = models.DateField(_("closing balance date"), null=True, blank=True)

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

    @property
    def account_public_id(self) -> Any:
        """The bank account's public id (the ``bank-accounts/<id>/imports/<id>`` routes)."""
        return self.bank_account.public_id


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
    #: The spend / receive the line was coded into (F-04-T07): a draft while a rule's suggestion
    #: waits for review, posted once coded.
    bank_transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="statement_lines",
        verbose_name=_("bank transaction"),
    )
    #: The bank rule that coded the line (every application is logged, F-04).
    applied_rule = models.ForeignKey(
        "banking.BankRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="coded_lines",
        verbose_name=_("applied rule"),
    )
    #: Coded and posted by an auto-apply rule without review — can be reviewed and reverted.
    auto_coded = models.BooleanField(_("auto-coded"), default=False, db_default=False)

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


# ---- statement mappings (F-02-T05) -------------------------------------------------------------


class StatementMapping(AuditedModel, OrgOwnedModel):
    """How an organisation's CSV / XLSX statements of one layout are read — a saved mapping.

    The fields are those of ``statements.layout.Layout``: ``columns`` (the role of each column by
    position: date, description, payee, reference, fitid, amount, debit, credit, balance,
    ignore), ``date_format``, ``sign`` (signed / inverted / debit_credit), ``has_header``,
    ``skip_rows`` and ``decimal_separator``. ``headers`` is the header row the mapping was made
    from (empty for files without a header): the auto-detection (F-02-T06) scores a new file's
    header against it.

    ``builtin_key`` marks the built-in layouts of the Canadian banks (``statements.mappings
    .BUILTIN``: RBC, TD, Scotiabank, BMO, CIBC, Desjardins, National Bank, Tangerine, a generic
    credit union and a generic layout), seeded into each organisation on first use and never
    edited — a person who changes the columns saves their own mapping. ``use_count`` /
    ``last_used_at`` are bumped by each import that uses it."""

    name = models.CharField(_("name"), max_length=120)
    institution = models.CharField(_("institution"), max_length=120, blank=True)
    builtin_key = models.CharField(_("built-in layout"), max_length=40, blank=True)
    headers = models.JSONField(_("header row"), default=list, blank=True)
    columns = models.JSONField(_("column roles"), default=list)
    date_format = models.CharField(_("date format"), max_length=20, default="YYYY-MM-DD")
    sign = models.CharField(_("sign convention"), max_length=20, default="signed")
    has_header = models.BooleanField(_("has a header row"), default=True)
    skip_rows = models.PositiveSmallIntegerField(_("rows to skip"), default=0)
    decimal_separator = models.CharField(_("decimal separator"), max_length=1, default=".")
    use_count = models.PositiveIntegerField(_("times used"), default=0)
    last_used_at = models.DateTimeField(_("last used"), null=True, blank=True)

    audit_exclude: ClassVar[frozenset[str]] = frozenset({"use_count", "last_used_at"})

    class Meta:
        ordering = ("name", "pk")
        verbose_name = _("statement mapping")
        verbose_name_plural = _("statement mappings")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "organisation",
                Lower("name"),
                condition=models.Q(deleted_at__isnull=True),
                name="banking_stmt_mapping_name_unique",
            ),
            models.UniqueConstraint(
                fields=["organisation", "builtin_key"],
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(builtin_key=""),
                name="banking_stmt_mapping_builtin_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(sign__in=["signed", "inverted", "debit_credit"]),
                name="banking_stmt_mapping_sign_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(decimal_separator__in=[".", ","]),
                name="banking_stmt_mapping_decimal_valid",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_builtin(self) -> bool:
        return bool(self.builtin_key)

    def layout(self) -> Any:
        """The mapping as a ``statements.layout.Layout``."""
        from .statements.layout import Layout

        return Layout.from_dict(
            {
                "columns": self.columns,
                "date_format": self.date_format,
                "sign": self.sign,
                "has_header": self.has_header,
                "skip_rows": self.skip_rows,
                "decimal_separator": self.decimal_separator,
            }
        )


# ---- bank rules (F-04-T02) ----------------------------------------------------------------------


class BankRuleType(models.TextChoices):
    """What a rule codes a line into: money out (spend), money in (receive), or a transfer to or
    from another bank account (either sign)."""

    SPEND = "spend", _("Spend money")
    RECEIVE = "receive", _("Receive money")
    TRANSFER = "transfer", _("Transfer")


class MatchMode(models.TextChoices):
    ALL = "all", _("All conditions")
    ANY = "any", _("Any condition")


class ContactStrategy(models.TextChoices):
    """``none`` — no contact; ``fixed`` — the rule's contact; ``match_payee`` — the contact whose
    name is the line's payee (no contact when none is found)."""

    NONE = "none", _("No contact")
    FIXED = "fixed", _("Set this contact")
    MATCH_PAYEE = "match_payee", _("Contact named like the payee")


class BankRule(AuditedModel, OrgOwnedModel):
    """An ordered, testable rule that codes statement lines (F-04).

    ``priority`` orders the rules of one type: 1 is evaluated first and the first match wins
    (F-04-T05). It is unique per organisation and type — **deferred** to the end of the
    transaction, so a reorder renumbers every rule at once (F-04-T09); a deleted rule gives its
    number up (``priority`` null). ``scope_accounts`` empty = every bank account.

    ``reference_template`` builds the transaction's reference from the line: ``{payee}``,
    ``{description}``, ``{reference}``, ``{date}``, ``{amount}``. ``auto_apply`` (off by default)
    posts the coding without review and flags the line *auto-coded*; otherwise the rule leaves a
    draft transaction to review. ``transfer_account`` is the other bank account of a transfer rule.
    ``applied_count`` / ``last_applied_at`` are the list's counters."""

    type = models.CharField(_("type"), max_length=10, choices=BankRuleType.choices)
    name = models.CharField(_("name"), max_length=120)
    match_mode = models.CharField(
        _("match"), max_length=3, choices=MatchMode.choices, default=MatchMode.ALL
    )
    priority = models.PositiveIntegerField(_("priority"), null=True, blank=True)
    scope_accounts = models.ManyToManyField(
        BankAccount, blank=True, related_name="bank_rules", verbose_name=_("bank accounts")
    )
    contact_strategy = models.CharField(
        _("contact"),
        max_length=12,
        choices=ContactStrategy.choices,
        default=ContactStrategy.NONE,
    )
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bank_rules",
        verbose_name=_("contact"),
    )
    reference_template = models.CharField(_("reference"), max_length=255, blank=True)
    transfer_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="transfer_rules",
        verbose_name=_("transfer account"),
    )
    auto_apply = models.BooleanField(_("auto-apply"), default=False, db_default=False)
    active = models.BooleanField(_("active"), default=True, db_default=True)
    applied_count = models.PositiveIntegerField(_("times applied"), default=0, db_default=0)
    last_applied_at = models.DateTimeField(_("last applied"), null=True, blank=True)

    audit_exclude: ClassVar[frozenset[str]] = frozenset({"applied_count", "last_applied_at"})

    class Meta:
        ordering = ("type", "priority", "pk")
        verbose_name = _("bank rule")
        verbose_name_plural = _("bank rules")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=["organisation", "type", "priority"],
                name="banking_rule_priority_unique",
                deferrable=Deferrable.DEFERRED,
            ),
            models.CheckConstraint(
                condition=models.Q(type__in=BankRuleType.values), name="banking_rule_type_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(match_mode__in=MatchMode.values),
                name="banking_rule_match_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(contact_strategy__in=ContactStrategy.values),
                name="banking_rule_contact_strategy_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(contact_strategy=ContactStrategy.FIXED)
                | models.Q(contact__isnull=False),
                name="banking_rule_fixed_contact_required",
            ),
            models.CheckConstraint(condition=~models.Q(name=""), name="banking_rule_name_required"),
        ]

    def __str__(self) -> str:
        return self.name


class ConditionField(models.TextChoices):
    PAYEE = "payee", _("Payee")
    DESCRIPTION = "description", _("Description")
    REFERENCE = "reference", _("Reference")
    ANY_TEXT = "any_text", _("Any text field")
    AMOUNT = "amount", _("Amount")


class ConditionOperator(models.TextChoices):
    EQUALS = "equals", _("equals")
    CONTAINS = "contains", _("contains")
    NOT_CONTAINS = "not_contains", _("does not contain")
    STARTS_WITH = "starts_with", _("starts with")
    ENDS_WITH = "ends_with", _("ends with")
    REGEX = "regex", _("matches the pattern")
    IS_BLANK = "is_blank", _("is blank")
    BETWEEN = "between", _("is between")
    GREATER_THAN = "gt", _("is greater than")
    LESS_THAN = "lt", _("is less than")


#: The operators each kind of field accepts (F-04-T04).
TEXT_OPERATORS: frozenset[str] = frozenset(
    {
        ConditionOperator.EQUALS,
        ConditionOperator.CONTAINS,
        ConditionOperator.NOT_CONTAINS,
        ConditionOperator.STARTS_WITH,
        ConditionOperator.ENDS_WITH,
        ConditionOperator.REGEX,
        ConditionOperator.IS_BLANK,
    }
)
AMOUNT_OPERATORS: frozenset[str] = frozenset(
    {
        ConditionOperator.EQUALS,
        ConditionOperator.BETWEEN,
        ConditionOperator.GREATER_THAN,
        ConditionOperator.LESS_THAN,
    }
)


class BankRuleCondition(OrgOwnedModel):
    """One condition of a rule: ``field`` ``operator`` ``value`` (and ``value_to``, the upper
    bound of *amount between*). Amount conditions compare the line's amount without its sign."""

    rule = models.ForeignKey(
        BankRule, on_delete=models.CASCADE, related_name="conditions", verbose_name=_("rule")
    )
    order = models.PositiveSmallIntegerField(_("order"), default=0)
    field = models.CharField(_("field"), max_length=12, choices=ConditionField.choices)
    operator = models.CharField(_("operator"), max_length=12, choices=ConditionOperator.choices)
    value = models.CharField(_("value"), max_length=500, blank=True)
    value_to = models.CharField(_("to"), max_length=40, blank=True)

    class Meta:
        ordering = ("rule", "order", "pk")
        verbose_name = _("bank rule condition")
        verbose_name_plural = _("bank rule conditions")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(field__in=ConditionField.values),
                name="banking_rule_cond_field_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(operator__in=ConditionOperator.values),
                name="banking_rule_cond_operator_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.field} {self.operator} {self.value}"

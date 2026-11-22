"""Chart of accounts (C-01): account types, sub-types, system roles, GIFI master list, accounts.

``Account`` (C-01-T02) is an organisation record (``OrgOwnedModel``) with every change in the audit
log (``AuditedModel``):

- ``code`` — unique per organisation, case-insensitive (database constraint), 1–10 characters;
  the Canadian template uses consistent 4-digit codes. Everything that refers to an account does
  it by foreign key (id), never by code, so renumbering (C-01-T07) is a change of this one field;
- ``name_i18n`` — the name per language (``{"en-ca": …, "fr-ca": …}``); ``name`` reads it in the
  active language and falls back to English (French names arrive with Phase 6);
- ``type`` (Asset, Liability, Equity, Revenue, Expense) and ``subtype`` — the sub-type decides the
  type (``SUBTYPE_TYPE``); the database refuses a sub-type outside its type;
- ``parent`` — sub-accounts (C-01-T03): depth ≤ 4, same type as the parent, posting only to leaf
  accounts (``numo9.ledger.tree``);
- ``system_role`` — the account the engine posts to for a role (AR, AP, GST/HST payable…): one
  account per role per organisation (database constraint); a system account can't be archived or
  deleted and its role, type and sub-type never change (C-01-T06, ``numo9.ledger.guards``);
- ``is_bank`` — true for every Bank sub-type account; liabilities (credit card, line of credit,
  loan) may also be bank accounts (F-01);
- ``gifi`` — the CRA GIFI code (``GifiCode``, C-01-T04), validated against the seeded list:
  never a total line, and in a section that fits the account's type;
- ``require_contact`` / ``require_tracking`` / ``require_attachment`` — enforced on journal lines
  by C-03 (gap-46);
- ``itc_restriction_pct`` — the share of an ITC/ITR that may be claimed on this account's
  purchases (50 for meals and entertainment, G-01-T05); null = the tax code's rule;
- ``default_tax_key`` — the default sales/purchase tax code key, resolved to a G-01 tax code in
  Phase 1 (``purchase.ON.standard``, ``purchase.exempt``… — see ``numo9.ledger.template``);
- ``status`` — active or archived (accounts are archived, never deleted: C-01-T08);
- ``template_ref`` — the template row the account was created from (``ca_v1:1100``): a stable key
  that survives renumbering, for code that must find "the template's payment fees account".
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
from numo9.orgsettings.locks import LockGuardMixin
from numo9.tenancy.managers import OrgScopedManager
from numo9.tenancy.models import OrgOwnedModel

# ---- types and sub-types -------------------------------------------------------------------


class AccountType(models.TextChoices):
    ASSET = "asset", _("Asset")
    LIABILITY = "liability", _("Liability")
    EQUITY = "equity", _("Equity")
    REVENUE = "revenue", _("Revenue")
    EXPENSE = "expense", _("Expense")


class AccountSubtype(models.TextChoices):
    # Asset
    CURRENT_ASSET = "current_asset", _("Current asset")
    BANK = "bank", _("Bank")
    INVENTORY = "inventory", _("Inventory")
    PREPAYMENT = "prepayment", _("Prepayment")
    FIXED_ASSET = "fixed_asset", _("Fixed asset")
    ACCUMULATED_AMORTISATION = "accumulated_amortisation", _("Accumulated amortization")
    NON_CURRENT_ASSET = "non_current_asset", _("Non-current asset")
    INTANGIBLE = "intangible", _("Intangible asset")
    # Liability
    CURRENT_LIABILITY = "current_liability", _("Current liability")
    SALES_TAX_CONTROL = "sales_tax_control", _("Sales tax control")
    PAYROLL_LIABILITY = "payroll_liability", _("Payroll liability")
    NON_CURRENT_LIABILITY = "non_current_liability", _("Non-current liability")
    # Equity
    SHARE_CAPITAL = "share_capital", _("Share capital")
    RETAINED_EARNINGS = "retained_earnings", _("Retained earnings")
    CURRENT_YEAR_EARNINGS = "current_year_earnings", _("Current year earnings")
    DIVIDENDS = "dividends", _("Dividends")
    OTHER_EQUITY = "other_equity", _("Other equity")
    # Revenue
    REVENUE = "revenue", _("Revenue")
    OTHER_INCOME = "other_income", _("Other income")
    # Expense
    COST_OF_SALES = "cost_of_sales", _("Cost of sales")
    OPERATING_EXPENSE = "operating_expense", _("Operating expense")
    AMORTISATION = "amortisation", _("Amortization")
    INCOME_TAX = "income_tax", _("Income tax")
    OTHER_EXPENSE = "other_expense", _("Other expense")


T, S = AccountType, AccountSubtype

#: The type each sub-type belongs to (its "type family").
SUBTYPE_TYPE: dict[str, str] = {
    **dict.fromkeys(
        (
            S.CURRENT_ASSET,
            S.BANK,
            S.INVENTORY,
            S.PREPAYMENT,
            S.FIXED_ASSET,
            S.ACCUMULATED_AMORTISATION,
            S.NON_CURRENT_ASSET,
            S.INTANGIBLE,
        ),
        T.ASSET,
    ),
    **dict.fromkeys(
        (S.CURRENT_LIABILITY, S.SALES_TAX_CONTROL, S.PAYROLL_LIABILITY, S.NON_CURRENT_LIABILITY),
        T.LIABILITY,
    ),
    **dict.fromkeys(
        (
            S.SHARE_CAPITAL,
            S.RETAINED_EARNINGS,
            S.CURRENT_YEAR_EARNINGS,
            S.DIVIDENDS,
            S.OTHER_EQUITY,
        ),
        T.EQUITY,
    ),
    **dict.fromkeys((S.REVENUE, S.OTHER_INCOME), T.REVENUE),
    **dict.fromkeys(
        (S.COST_OF_SALES, S.OPERATING_EXPENSE, S.AMORTISATION, S.INCOME_TAX, S.OTHER_EXPENSE),
        T.EXPENSE,
    ),
}

#: Normal balance side per type; contra sub-types (accumulated amortization) are the exception.
NORMAL_SIDE: dict[str, str] = {
    T.ASSET: "debit",
    T.EXPENSE: "debit",
    T.LIABILITY: "credit",
    T.EQUITY: "credit",
    T.REVENUE: "credit",
}
CONTRA_SUBTYPES: frozenset[str] = frozenset({S.ACCUMULATED_AMORTISATION})

#: Sub-types that may be bank accounts (F-01): every Bank account, and liabilities such as a
#: credit card, a line of credit or a loan.
BANK_CAPABLE_SUBTYPES: frozenset[str] = frozenset(
    {S.BANK, S.CURRENT_LIABILITY, S.NON_CURRENT_LIABILITY}
)


class SystemRole(models.TextChoices):
    """Accounts the engine posts to by role. One account per role per organisation."""

    AR = "ar", _("Accounts receivable")
    AP = "ap", _("Accounts payable")
    GST_HST_PAYABLE = "gst_hst_payable", _("GST/HST payable")
    ITC_RECEIVABLE = "itc_receivable", _("GST/HST receivable (ITCs)")
    PST_PAYABLE = "pst_payable", _("PST payable")
    QST_PAYABLE = "qst_payable", _("QST payable")
    QST_ITR = "qst_itr", _("QST receivable (ITRs)")
    RETAINED_EARNINGS = "retained_earnings", _("Retained earnings")
    CURRENT_YEAR_EARNINGS = "current_year_earnings", _("Current year earnings")
    ROUNDING = "rounding", _("Rounding")
    SUSPENSE_CONVERSION = "suspense_conversion", _("Conversion balances suspense")
    UNPAID_EXPENSE_CLAIMS = "unpaid_expense_claims", _("Unpaid expense claims")
    WAGES_PAYABLE = "wages_payable", _("Wages payable")
    CPP_PAYABLE = "cpp_payable", _("CPP payable")
    QPP_PAYABLE = "qpp_payable", _("QPP payable")
    EI_PAYABLE = "ei_payable", _("EI payable")
    QPIP_PAYABLE = "qpip_payable", _("QPIP payable")
    INCOME_TAX_WITHHELD = "income_tax_withheld", _("Income tax withheld")
    VACATION_PAYABLE = "vacation_payable", _("Vacation pay payable")
    WORKERS_COMP_PAYABLE = "workers_comp_payable", _("Workers' compensation payable")
    EHT_PAYABLE = "eht_payable", _("Employer health tax payable")
    INVENTORY = "inventory", _("Inventory")
    FX_GAIN_LOSS = "fx_gain_loss", _("Foreign exchange gain or loss")


R = SystemRole

#: The sub-types a system account may have (the role decides how the engine posts to it).
ROLE_SUBTYPES: dict[str, frozenset[str]] = {
    R.AR: frozenset({S.CURRENT_ASSET}),
    R.AP: frozenset({S.CURRENT_LIABILITY}),
    R.GST_HST_PAYABLE: frozenset({S.SALES_TAX_CONTROL}),
    R.ITC_RECEIVABLE: frozenset({S.CURRENT_ASSET}),
    R.PST_PAYABLE: frozenset({S.SALES_TAX_CONTROL}),
    R.QST_PAYABLE: frozenset({S.SALES_TAX_CONTROL}),
    R.QST_ITR: frozenset({S.CURRENT_ASSET}),
    R.RETAINED_EARNINGS: frozenset({S.RETAINED_EARNINGS}),
    R.CURRENT_YEAR_EARNINGS: frozenset({S.CURRENT_YEAR_EARNINGS}),
    R.ROUNDING: frozenset({S.OTHER_EXPENSE, S.OPERATING_EXPENSE, S.OTHER_INCOME}),
    R.SUSPENSE_CONVERSION: frozenset({S.CURRENT_LIABILITY, S.OTHER_EQUITY}),
    R.UNPAID_EXPENSE_CLAIMS: frozenset({S.CURRENT_LIABILITY}),
    R.WAGES_PAYABLE: frozenset({S.PAYROLL_LIABILITY}),
    R.CPP_PAYABLE: frozenset({S.PAYROLL_LIABILITY}),
    R.QPP_PAYABLE: frozenset({S.PAYROLL_LIABILITY}),
    R.EI_PAYABLE: frozenset({S.PAYROLL_LIABILITY}),
    R.QPIP_PAYABLE: frozenset({S.PAYROLL_LIABILITY}),
    R.INCOME_TAX_WITHHELD: frozenset({S.PAYROLL_LIABILITY}),
    R.VACATION_PAYABLE: frozenset({S.PAYROLL_LIABILITY}),
    R.WORKERS_COMP_PAYABLE: frozenset({S.PAYROLL_LIABILITY}),
    R.EHT_PAYABLE: frozenset({S.PAYROLL_LIABILITY}),
    R.INVENTORY: frozenset({S.INVENTORY}),
    R.FX_GAIN_LOSS: frozenset({S.OTHER_INCOME, S.OTHER_EXPENSE}),
}


class AccountStatus(models.TextChoices):
    ACTIVE = "active", _("Active")
    ARCHIVED = "archived", _("Archived")


class LedgerError(ValidationError):
    """A chart-of-accounts change the rules refuse; ``code`` is a stable machine-readable key."""


# ---- GIFI master list (C-01-T04) -----------------------------------------------------------


class GifiSection(models.TextChoices):
    CURRENT_ASSETS = "current_assets", _("Current assets")
    TANGIBLE_CAPITAL_ASSETS = "tangible_capital_assets", _("Tangible capital assets")
    INTANGIBLE_CAPITAL_ASSETS = "intangible_capital_assets", _("Intangible capital assets")
    LONG_TERM_ASSETS = "long_term_assets", _("Long-term assets")
    CURRENT_LIABILITIES = "current_liabilities", _("Current liabilities")
    LONG_TERM_LIABILITIES = "long_term_liabilities", _("Long-term liabilities")
    SHAREHOLDER_EQUITY = "shareholder_equity", _("Shareholder equity")
    PARTNERS_CAPITAL = "partners_capital", _("Partners' capital")
    RETAINED_EARNINGS = "retained_earnings", _("Retained earnings")
    OTHER_COMPREHENSIVE_INCOME = "other_comprehensive_income", _("Other comprehensive income")
    REVENUE = "revenue", _("Revenue")
    COST_OF_SALES = "cost_of_sales", _("Cost of sales")
    OPERATING_EXPENSES = "operating_expenses", _("Operating expenses")
    FARM_REVENUE = "farm_revenue", _("Farming revenue")
    FARM_EXPENSES = "farm_expenses", _("Farming expenses")
    EXTRAORDINARY_ITEMS_AND_TAXES = (
        "extraordinary_items_and_taxes",
        _("Extraordinary items and income taxes"),
    )


G = GifiSection

#: GIFI sections an account of each type may map to (gap-30: a mapping the T2 can use).
TYPE_GIFI_SECTIONS: dict[str, frozenset[str]] = {
    T.ASSET: frozenset(
        {
            G.CURRENT_ASSETS,
            G.TANGIBLE_CAPITAL_ASSETS,
            G.INTANGIBLE_CAPITAL_ASSETS,
            G.LONG_TERM_ASSETS,
        }
    ),
    T.LIABILITY: frozenset({G.CURRENT_LIABILITIES, G.LONG_TERM_LIABILITIES}),
    T.EQUITY: frozenset({G.SHAREHOLDER_EQUITY, G.PARTNERS_CAPITAL, G.RETAINED_EARNINGS}),
    T.REVENUE: frozenset(
        {
            G.REVENUE,
            G.FARM_REVENUE,
            G.EXTRAORDINARY_ITEMS_AND_TAXES,
            G.OTHER_COMPREHENSIVE_INCOME,
        }
    ),
    T.EXPENSE: frozenset(
        {
            G.COST_OF_SALES,
            G.OPERATING_EXPENSES,
            G.FARM_EXPENSES,
            G.EXTRAORDINARY_ITEMS_AND_TAXES,
            G.OTHER_COMPREHENSIVE_INCOME,
        }
    ),
}


class GifiCode(models.Model):
    """One line of the CRA General Index of Financial Information (platform data, C-01-T04).

    Seeded from the published list (``data/gifi_rc4088_rev23.csv`` — RC4088(E) Rev. 23); every
    row records the list version and its publication date. A later CRA list adds a data
    migration: new codes are added with their version, codes the CRA drops get ``retired_in``
    (they stay, because accounts and past T2 exports refer to them).
    """

    code = models.CharField(_("code"), max_length=4, unique=True)
    description = models.CharField(_("description"), max_length=200)
    section = models.CharField(_("section"), max_length=40, choices=GifiSection.choices)
    is_summary = models.BooleanField(
        _("total line"),
        default=False,
        help_text=_("Totals and computed lines (e.g. 1599 Total current assets): never mapped."),
    )
    list_version = models.CharField(_("list version"), max_length=40)
    published_on = models.DateField(_("published on"))
    retired_in = models.CharField(_("retired in list version"), max_length=40, blank=True)

    class Meta:
        ordering = ("code",)
        verbose_name = _("GIFI code")
        verbose_name_plural = _("GIFI codes")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(code__regex=r"^[0-9]{4}$"), name="ledger_gifi_code_4_digits"
            ),
            models.CheckConstraint(
                condition=models.Q(section__in=GifiSection.values),
                name="ledger_gifi_section_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.description}"

    @property
    def is_assignable(self) -> bool:
        return not self.is_summary and not self.retired_in


# ---- accounts --------------------------------------------------------------------------------

#: An account code: 1–10 letters, digits, "." or "-", starting with a letter or digit.
ACCOUNT_CODE = re.compile(r"^[0-9A-Za-z][0-9A-Za-z.\-]{0,9}$")
NAME_MAX = 150
SOURCE_LANGUAGE = "en-ca"


def _subtype_matches_type() -> models.Q:
    condition = models.Q()
    for type_ in AccountType.values:
        subtypes = [s for s, t in SUBTYPE_TYPE.items() if t == type_]
        condition |= models.Q(type=type_, subtype__in=subtypes)
    return condition


class AccountQuerySet(models.QuerySet["Account"]):
    def delete(self) -> tuple[int, dict[str, int]]:
        from .guards import refuse_bulk_delete

        refuse_bulk_delete(self)
        return super().delete()

    def active(self) -> AccountQuerySet:
        return self.filter(status=AccountStatus.ACTIVE, deleted_at__isnull=True)


#: Organisation-scoped (A-01-T04) with the account queryset's guards and helpers.
AccountManager = OrgScopedManager.from_queryset(AccountQuerySet)


class Account(AuditedModel, OrgOwnedModel):
    code = models.CharField(_("code"), max_length=10)
    name_i18n = models.JSONField(
        _("name"),
        default=dict,
        help_text=_('The name per language, e.g. {"en-ca": "Chequing account"}.'),
    )
    description = models.TextField(_("description"), blank=True)
    type = models.CharField(_("type"), max_length=16, choices=AccountType.choices)
    subtype = models.CharField(_("sub-type"), max_length=32, choices=AccountSubtype.choices)
    parent = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("parent account"),
    )
    system_role = models.CharField(
        _("system role"), max_length=32, choices=SystemRole.choices, blank=True, default=""
    )
    is_bank = models.BooleanField(_("bank account"), default=False)
    gifi = models.ForeignKey(
        GifiCode,
        to_field="code",
        db_column="gifi_code",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("GIFI code"),
    )
    require_contact = models.BooleanField(_("require a contact"), default=False)
    require_tracking = models.BooleanField(_("require a tracking category"), default=False)
    require_attachment = models.BooleanField(_("require an attachment"), default=False)
    default_tax_key = models.CharField(_("default tax code"), max_length=60, blank=True)
    #: Share of the input tax credit (and QST refund) that may be claimed on purchases posted to
    #: this account, e.g. 50 for meals and entertainment (G-01-T05); null = the tax code's rule.
    itc_restriction_pct = models.DecimalField(
        _("claimable ITC %"), max_digits=5, decimal_places=2, null=True, blank=True
    )
    status = models.CharField(
        _("status"), max_length=16, choices=AccountStatus.choices, default=AccountStatus.ACTIVE
    )
    archived_at = models.DateTimeField(_("archived at"), null=True, blank=True)
    template_ref = models.CharField(_("template row"), max_length=40, blank=True)

    objects: ClassVar[Any] = AccountManager()

    audit_exclude: ClassVar[frozenset[str]] = frozenset({"archived_at"})

    class Meta:
        ordering = ("code",)
        verbose_name = _("account")
        verbose_name_plural = _("accounts")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                "organisation", Lower("code"), name="ledger_account_code_unique_per_org"
            ),
            models.UniqueConstraint(
                fields=("organisation", "system_role"),
                condition=~models.Q(system_role=""),
                name="ledger_account_one_per_system_role",
            ),
            models.CheckConstraint(
                condition=models.Q(type__in=AccountType.values), name="ledger_account_type_valid"
            ),
            models.CheckConstraint(
                condition=_subtype_matches_type(), name="ledger_account_subtype_in_type"
            ),
            models.CheckConstraint(
                condition=models.Q(system_role="") | models.Q(system_role__in=SystemRole.values),
                name="ledger_account_system_role_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=AccountStatus.values),
                name="ledger_account_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(subtype=S.BANK) | models.Q(is_bank=True),
                name="ledger_account_bank_subtype_is_bank",
            ),
            models.CheckConstraint(
                condition=models.Q(is_bank=False) | models.Q(subtype__in=BANK_CAPABLE_SUBTYPES),
                name="ledger_account_is_bank_subtype",
            ),
            models.CheckConstraint(
                condition=~models.Q(parent=models.F("pk")), name="ledger_account_not_own_parent"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "parent"), name="ledger_account_parent_idx"),
            models.Index(fields=("organisation", "type", "code"), name="ledger_account_type_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code} · {self.name}"

    # ---- names ---------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return self.name_in(translation.get_language() or SOURCE_LANGUAGE)

    def name_in(self, language: str) -> str:
        names = self.name_i18n or {}
        return str(names.get(language.lower()) or names.get(SOURCE_LANGUAGE) or "")

    def set_name(self, name: str, language: str = SOURCE_LANGUAGE) -> None:
        self.name_i18n = {**(self.name_i18n or {}), language.lower(): name.strip()}

    # ---- derived -------------------------------------------------------------------------

    @property
    def is_system(self) -> bool:
        return bool(self.system_role)

    @property
    def is_archived(self) -> bool:
        return self.status == AccountStatus.ARCHIVED

    @property
    def normal_side(self) -> str:
        side = NORMAL_SIDE[self.type]
        if self.subtype in CONTRA_SUBTYPES:
            return "credit" if side == "debit" else "debit"
        return side

    def role_label(self) -> str:
        return str(SystemRole(self.system_role).label) if self.system_role else ""

    # ---- validation and save -------------------------------------------------------------

    def clean(self) -> None:
        from .guards import check_system_role_rules
        from .tree import check_tree_rules

        self._validate_fields()
        check_system_role_rules(self)
        check_tree_rules(self)

    def _validate_fields(self) -> None:
        self.code = (self.code or "").strip()
        if not ACCOUNT_CODE.match(self.code):
            raise LedgerError(
                _(
                    "An account code is 1 to 10 letters, digits, dots or dashes, starting with a "
                    "letter or a digit (e.g. 6100)."
                ),
                code="ledger.account.code_invalid",
            )
        name = self.name_in(SOURCE_LANGUAGE).strip()
        if not name:
            raise LedgerError(_("Give the account a name."), code="ledger.account.name_required")
        if any(len(str(value)) > NAME_MAX for value in (self.name_i18n or {}).values()):
            raise LedgerError(
                _("An account name is at most %(max)d characters."),
                code="ledger.account.name_too_long",
                params={"max": NAME_MAX},
            )
        if self.subtype not in SUBTYPE_TYPE:
            raise LedgerError(_("Choose a sub-type."), code="ledger.account.subtype_invalid")
        if not self.type:
            self.type = SUBTYPE_TYPE[self.subtype]
        if SUBTYPE_TYPE[self.subtype] != self.type:
            raise LedgerError(
                _("The sub-type %(subtype)s belongs to %(type)s accounts."),
                code="ledger.account.subtype_type_mismatch",
                params={
                    "subtype": AccountSubtype(self.subtype).label,
                    "type": AccountType(SUBTYPE_TYPE[self.subtype]).label,
                },
            )
        if self.subtype == S.BANK:
            self.is_bank = True
        if self.is_bank and self.subtype not in BANK_CAPABLE_SUBTYPES:
            raise LedgerError(
                _(
                    "Only Bank accounts and liabilities (credit card, line of credit, loan) can "
                    "be bank accounts."
                ),
                code="ledger.account.bank_subtype",
            )
        if self.gifi_id is not None:
            self._validate_gifi()

    def _validate_gifi(self) -> None:
        gifi = GifiCode.objects.filter(code=self.gifi_id).first()
        if gifi is None:
            raise LedgerError(
                _("%(code)s is not a GIFI code on the CRA list."),
                code="ledger.account.gifi_unknown",
                params={"code": self.gifi_id},
            )
        if not gifi.is_assignable:
            raise LedgerError(
                _("%(code)s %(description)s is a total line: choose the GIFI code of the item."),
                code="ledger.account.gifi_total",
                params={"code": gifi.code, "description": gifi.description},
            )
        if gifi.section not in TYPE_GIFI_SECTIONS[self.type]:
            raise LedgerError(
                _("GIFI %(code)s is in %(section)s: it doesn't fit a %(type)s account."),
                code="ledger.account.gifi_section",
                params={
                    "code": gifi.code,
                    "section": GifiSection(gifi.section).label,
                    "type": AccountType(self.type).label.lower(),
                },
            )

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.clean()
        if self.status == AccountStatus.ARCHIVED and self.archived_at is None:
            self.archived_at = timezone.now()
        elif self.status == AccountStatus.ACTIVE:
            self.archived_at = None
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        from .guards import refuse_delete

        refuse_delete(self)
        return super().delete(*args, **kwargs)

    def soft_delete(self) -> None:
        from .guards import refuse_delete

        refuse_delete(self)
        super().soft_delete()


# ---- journals (C-02, ADR-0003) -------------------------------------------------------------


class JournalStatus(models.TextChoices):
    """Draft → Awaiting approval → Posted → Reversed (explicit transitions, C-02-T09)."""

    DRAFT = "draft", _("Draft")
    AWAITING_APPROVAL = "awaiting_approval", _("Awaiting approval")
    POSTED = "posted", _("Posted")
    REVERSED = "reversed", _("Reversed")


#: Entries whose rows can't change any more (append-only, C-02-T04).
LOCKED_STATUSES: frozenset[str] = frozenset({JournalStatus.POSTED, JournalStatus.REVERSED})


class Book(models.TextChoices):
    """Which book a journal line belongs to (ADR-0003 §1).

    The accounting book is the lines with ``both`` or ``accounting``; the tax book the lines with
    ``both`` or ``tax``. An ordinary transaction is all ``both``; a book-tax difference (CCA vs.
    book amortization) is an extra balanced pair in one book only.
    """

    BOTH = "both", _("Both books")
    ACCOUNTING = "accounting", _("Accounting book")
    TAX = "tax", _("Tax book")


class JournalType(models.TextChoices):
    """What posted the entry; modules add their own types (kept open at the database)."""

    MANUAL = "manual", _("Manual journal")
    SALES = "sales", _("Sales")
    PURCHASE = "purchase", _("Purchases")
    PAYMENT = "payment", _("Payment")
    PAYROLL = "payroll", _("Payroll")
    OPENING = "opening", _("Opening balance")
    ADJUSTMENT = "adjustment", _("Adjustment")
    REVERSAL = "reversal", _("Reversal")
    BANK = "bank", _("Bank transaction")


class JournalCategory(models.TextChoices):
    """The plan's journal type (C-03-T01): what kind of accounting entry a journal is.

    (``JournalType`` above says what *posted* it — manual, sales, payroll…; this classifies the
    entry itself, for people and reports.) General, Adjusting, Reclass and Tax adjustment are
    chosen by people; Closing (the year-end process, C-06), Payroll and Depreciation are given by
    the modules that post them and are never offered in a picker (``SELECTABLE_CATEGORIES``).
    """

    GENERAL = "general", _("General")
    ADJUSTING = "adjusting", _("Adjusting")
    RECLASS = "reclass", _("Reclass")
    TAX_ADJUSTMENT = "tax_adjustment", _("Tax adjustment")
    CLOSING = "closing", _("Closing")
    PAYROLL = "payroll", _("Payroll")
    DEPRECIATION = "depreciation", _("Depreciation")


#: Journal types a person may choose; the others are set by the system (C-03-T01).
SELECTABLE_CATEGORIES: tuple[str, ...] = (
    JournalCategory.GENERAL,
    JournalCategory.ADJUSTING,
    JournalCategory.RECLASS,
    JournalCategory.TAX_ADJUSTMENT,
)
SYSTEM_CATEGORIES: frozenset[str] = frozenset(JournalCategory.values) - set(SELECTABLE_CATEGORIES)


#: numeric(18, 2): 16 digits before the decimal point, two after.
MONEY_DIGITS = 18
MONEY_PLACES = 2


class JournalLocked(LedgerError):
    """A posted or reversed journal can't change (C-02-T04); the database refuses it too."""


def _locked_error(entry: JournalEntry | None, number: int | None = None) -> JournalLocked:
    number = number if number is not None else (entry.number if entry is not None else None)
    return JournalLocked(
        _("Journal %(number)s is posted: it can't be changed or deleted. Reverse it instead."),
        code="ledger.journal.locked",
        params={"number": number if number is not None else "—"},
    )


#: Columns of an entry that may change on Posted → Reversed.
_REVERSAL_CHANGES = frozenset({"status", "updated_at"})


class JournalEntry(LockGuardMixin, AuditedModel, OrgOwnedModel):
    """One double-entry journal (C-02-T02): header of the lines that post together.

    - ``number`` — the organisation's journal number, given when the entry is posted (gap-free
      ``JournalSequence``, C-02-T05); empty for drafts; unique per organisation;
    - ``date`` — the accounting date of every line;
    - ``type`` — manual, sales, purchase, payment… (``JournalType``; modules may add types);
    - ``journal_type`` — General, Adjusting, Reclass, Tax adjustment, or a system type (Closing,
      Payroll, Depreciation) — ``JournalCategory`` (C-03-T01);
    - ``status`` — draft, awaiting approval, posted, reversed; posted and reversed entries can't
      change (C-02-T04) except Posted → Reversed;
    - ``source_type`` / ``source_id`` — the document that posted it (``sales.Invoice`` + public id);
    - ``narration`` — what the entry is for;
    - ``book_scope`` — the books its lines touch (``both`` when lines touch both books);
    - ``reversal_of`` — the entry this one reverses (a reversal has its own number);
    - ``auto_reverse_on`` — the date its reversal is posted by itself (C-03-T09);
    - ``posted_by`` / ``posted_at`` — set when posted (with ``created_by`` from ``OrgOwnedModel``).

    Lock dates (A-05-T06): posting an entry dated on or before the GL lock is refused
    (``LockedPeriod``, 409 ``lock.violation``) — checked when the entry **becomes** posted;
    drafts in a locked period may be kept and edited, and reversing a posted entry (status only;
    the reversal is a new entry, checked on its own date) is not a change in its period.
    """

    lock_module = "gl"
    lock_date_field = "date"

    number = models.PositiveBigIntegerField(_("journal number"), null=True, blank=True)
    date = models.DateField(_("date"))
    type = models.CharField(
        _("journal type"), max_length=32, choices=JournalType.choices, default=JournalType.MANUAL
    )
    journal_type = models.CharField(
        _("journal type"),
        max_length=20,
        choices=JournalCategory.choices,
        default=JournalCategory.GENERAL,
        db_default=JournalCategory.GENERAL,
    )
    status = models.CharField(
        _("status"), max_length=20, choices=JournalStatus.choices, default=JournalStatus.DRAFT
    )
    source_type = models.CharField(_("source document type"), max_length=60, blank=True)
    source_id = models.CharField(_("source document"), max_length=64, blank=True)
    narration = models.TextField(_("narration"), blank=True)
    book_scope = models.CharField(
        _("books"), max_length=16, choices=Book.choices, default=Book.BOTH
    )
    reversal_of = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_by",
        verbose_name=_("reverses"),
    )
    posted_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("posted by"),
    )
    posted_at = models.DateTimeField(_("posted at"), null=True, blank=True)
    auto_reverse_on = models.DateField(
        _("reverse automatically on"),
        null=True,
        blank=True,
        help_text=_("An accrual's reversal is posted by itself on this date."),
    )

    class Meta:
        ordering = ("-date", "-number", "-pk")
        verbose_name = _("journal entry")
        verbose_name_plural = _("journal entries")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(
                fields=("organisation", "number"),
                condition=models.Q(number__isnull=False),
                name="ledger_journal_number_unique_per_org",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=JournalStatus.values),
                name="ledger_journal_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(book_scope__in=Book.values),
                name="ledger_journal_book_scope_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(type=""), name="ledger_journal_type_required"
            ),
            models.CheckConstraint(
                condition=models.Q(journal_type__in=JournalCategory.values),
                name="ledger_journal_category_valid",
            ),
            # Posted and reversed entries have their number and posting time; drafts have neither.
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=sorted(LOCKED_STATUSES),
                        number__isnull=False,
                        posted_at__isnull=False,
                    )
                    | models.Q(
                        status__in=[JournalStatus.DRAFT, JournalStatus.AWAITING_APPROVAL],
                        number__isnull=True,
                    )
                ),
                name="ledger_journal_number_when_posted",
            ),
            models.CheckConstraint(
                condition=~models.Q(reversal_of=models.F("pk")),
                name="ledger_journal_not_own_reversal",
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            models.Index(fields=("organisation", "date"), name="ledger_journal_date_idx"),
            models.Index(
                fields=("organisation", "source_type", "source_id"),
                name="ledger_journal_source_idx",
            ),
            models.Index(
                fields=("organisation", "auto_reverse_on"),
                name="ledger_journal_autorev_idx",
                condition=models.Q(auto_reverse_on__isnull=False, status="posted"),
            ),
        ]

    def __str__(self) -> str:
        if self.number:
            return str(_("Journal %(number)s") % {"number": self.number})
        return str(_("Draft journal"))

    @property
    def is_locked(self) -> bool:
        return self.status in LOCKED_STATUSES

    def lock_applies(self, stored: dict[str, Any] | None) -> bool:
        """Lock dates apply when the entry is being posted (A-05-T06)."""
        was = stored["status"] if stored is not None else None
        return self.status == JournalStatus.POSTED and was != JournalStatus.POSTED

    # ---- append-only guard (C-02-T04) ----------------------------------------------------

    def _stored(self) -> dict[str, Any] | None:
        if self.pk is None:
            return None
        names = [field.attname for field in self._meta.concrete_fields]
        row: dict[str, Any] | None = (
            type(self)._base_manager.filter(pk=self.pk).values(*names).first()
        )
        return row

    def check_change_allowed(self) -> None:
        """Refuse any change to a posted/reversed entry except Posted → Reversed (status only)."""
        stored = self._stored()
        if stored is None or stored["status"] not in LOCKED_STATUSES:
            return
        changed = {name for name, value in stored.items() if getattr(self, name) != value} - {
            "updated_at"
        }
        if (
            stored["status"] == JournalStatus.POSTED
            and self.status == JournalStatus.REVERSED
            and changed <= _REVERSAL_CHANGES
        ):
            return
        # Even an unchanged save would rewrite the row (updated_at): refused like the database.
        raise _locked_error(self, stored["number"])

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.check_change_allowed()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        stored = self._stored()
        if stored is not None and stored["status"] in LOCKED_STATUSES:
            raise _locked_error(self, stored["number"])
        deleted: tuple[int, dict[str, int]] = super().delete(*args, **kwargs)
        return deleted


class JournalLine(OrgOwnedModel):
    """One debit or credit of an entry (C-02-T02).

    ``debit`` and ``credit`` are separate non-negative ``numeric(18, 2)`` columns and exactly one
    is greater than zero (database checks). ``book`` puts the line in both books or one of them.
    ``organisation`` repeats the entry's (the partition key of C-02-T03 and the RLS key); the
    primary key is ``(organisation, id)`` so the table can be hash-partitioned by organisation
    (ADR-0003 §5), ``id`` coming from the sequence ``ledger_journalline_id_seq``. Lines are written
    only by ``numo9.ledger.services`` (C-02-T08, T14) and are not audited one by one: the entry's
    posting event lists them.
    """

    pk = models.CompositePrimaryKey("organisation", "id")
    id = models.BigIntegerField(
        _("line ID"),
        editable=False,
        db_default=models.Func(models.Value("ledger_journalline_id_seq"), function="nextval"),
    )
    entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="lines",
        verbose_name=_("journal entry"),
    )
    line_no = models.PositiveSmallIntegerField(_("line"))
    account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name="journal_lines", verbose_name=_("account")
    )
    debit = models.DecimalField(
        _("debit"), max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES, default=Decimal("0")
    )
    credit = models.DecimalField(
        _("credit"), max_digits=MONEY_DIGITS, decimal_places=MONEY_PLACES, default=Decimal("0")
    )
    book = models.CharField(_("book"), max_length=16, choices=Book.choices, default=Book.BOTH)
    contact = models.ForeignKey(
        "contacts.Contact",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="journal_lines",
        verbose_name=_("contact"),
    )
    tracking = models.JSONField(_("tracking"), default=dict, blank=True)
    description = models.CharField(_("description"), max_length=500, blank=True)
    tax_code = models.CharField(_("tax code"), max_length=60, blank=True)

    # Lines have no public id of their own (the entry's is used), no creator (the entry's) and are
    # never soft-deleted (posted lines are append-only; draft lines are replaced).
    public_id = None  # type: ignore[assignment]
    created_by = None
    deleted_at = None

    class Meta:
        ordering = ("entry_id", "line_no")
        verbose_name = _("journal line")
        verbose_name_plural = _("journal lines")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.CheckConstraint(
                condition=models.Q(debit__gte=0), name="ledger_line_debit_not_negative"
            ),
            models.CheckConstraint(
                condition=models.Q(credit__gte=0), name="ledger_line_credit_not_negative"
            ),
            models.CheckConstraint(
                condition=(models.Q(debit__gt=0, credit=0) | models.Q(debit=0, credit__gt=0)),
                name="ledger_line_one_side",
            ),
            models.CheckConstraint(
                condition=models.Q(book__in=Book.values), name="ledger_line_book_valid"
            ),
            models.UniqueConstraint(
                fields=("organisation", "entry", "line_no"), name="ledger_line_no_unique"
            ),
        ]
        indexes: ClassVar[list[models.Index]] = [
            # Trial balance per book (C-02-T11): one partition, one index range per account.
            models.Index(
                fields=("organisation", "account", "book"), name="ledger_line_account_book_idx"
            ),
            models.Index(fields=("organisation", "entry"), name="ledger_line_entry_idx"),
            # A contact's lines (AR/AP sub-ledger views, C-03-T02).
            models.Index(
                fields=("organisation", "contact"),
                name="ledger_line_contact_idx",
                condition=models.Q(contact__isnull=False),
            ),
        ]

    def __str__(self) -> str:
        side = f"Dr {self.debit}" if self.debit else f"Cr {self.credit}"
        return f"{self.entry_id}/{self.line_no} {side}"

    @property
    def amount(self) -> Decimal:
        """Signed amount: debit positive, credit negative."""
        return self.debit - self.credit

    def _entries_touched(self) -> set[int]:
        """The entry the line is in, and the one it was in before (a draft line may move)."""
        touched = {self.entry_id} if self.entry_id is not None else set()
        if not self._state.adding:
            previous = (
                type(self)
                ._base_manager.filter(organisation_id=self.organisation_id, id=self.id)
                .values_list("entry_id", flat=True)
                .first()
            )
            if previous is not None:
                touched.add(previous)
        return touched

    def _refuse_if_locked(self) -> None:
        locked = (
            JournalEntry._base_manager.filter(
                pk__in=self._entries_touched(), status__in=LOCKED_STATUSES
            )
            .values_list("number", flat=True)
            .first()
        )
        if locked is not None:
            raise _locked_error(None, locked)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.entry_id is not None and not self.organisation_id:
            self.organisation_id = self.entry.organisation_id
        self._refuse_if_locked()
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        self._refuse_if_locked()
        return super().delete(*args, **kwargs)


class JournalSequence(OrgOwnedModel):
    """The organisation's journal numbers (C-02-T05, ADR-0003 §4): one row per organisation.

    ``next_number`` is taken with ``UPDATE … SET next_number = next_number + 1 … RETURNING`` inside
    the posting transaction (``numo9.ledger.sequence.allocate_journal_number``): the row lock
    serialises one organisation's postings for the few milliseconds until commit, other
    organisations never wait, and a rollback gives the number back — no gaps. ``prefix`` and
    ``padding`` only format the number for people (``JE-000042``); the entry stores the integer.
    Not audited (one update per posting); not sensitive.
    """

    next_number = models.PositiveBigIntegerField(_("next number"), default=1)
    prefix = models.CharField(_("prefix"), max_length=10, blank=True, default="JE-")
    padding = models.PositiveSmallIntegerField(_("digits"), default=6)

    class Meta:
        verbose_name = _("journal number sequence")
        verbose_name_plural = _("journal number sequences")
        constraints: ClassVar[list[models.BaseConstraint]] = [
            models.UniqueConstraint(fields=("organisation",), name="ledger_journalseq_one_per_org"),
            models.CheckConstraint(
                condition=models.Q(next_number__gte=1), name="ledger_journalseq_next_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(padding__lte=12), name="ledger_journalseq_padding_max"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.prefix}{str(self.next_number).zfill(self.padding)}"

    def format(self, number: int) -> str:
        return f"{self.prefix}{str(number).zfill(self.padding)}"


class JournalOverride(OrgOwnedModel):
    """An adviser's reason for posting a journal that drives a bank or cash account below zero
    (C-03-T08): the journal, who, when, why, and the shortfalls they were warned about
    (``[{account, lowest, lowest_on, message}…]``). Written by the posting service only."""

    entry = models.ForeignKey(
        JournalEntry,
        on_delete=models.PROTECT,
        related_name="overrides",
        verbose_name=_("journal entry"),
    )
    reason = models.TextField(_("reason"))
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("by"),
    )
    at = models.DateTimeField(_("at"), default=timezone.now)
    shortfalls = models.JSONField(_("shortfalls"), default=list)

    class Meta:
        ordering = ("-at", "-pk")
        verbose_name = _("journal override")
        verbose_name_plural = _("journal overrides")

    def __str__(self) -> str:
        return f"{self.entry} · {self.reason[:40]}"

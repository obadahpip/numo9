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
- ``default_tax_key`` — the default sales/purchase tax code key, resolved to a G-01 tax code in
  Phase 1 (``purchase.ON.standard``, ``purchase.exempt``… — see ``numo9.ledger.template``);
- ``status`` — active or archived (accounts are archived, never deleted: C-01-T08);
- ``template_ref`` — the template row the account was created from (``ca_v1:1100``): a stable key
  that survives renumbering, for code that must find "the template's payment fees account".
"""

from __future__ import annotations

import re
from typing import Any, ClassVar

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _

from numo9.audit.mixins import AuditedModel
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

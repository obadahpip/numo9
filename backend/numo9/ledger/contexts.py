"""Which accounts may be chosen where (account picker contexts, C-01-T10; gap-07 groundwork).

The design system's ``AccountPicker`` filters by context with the same rules
(``packages/ui/src/pickers/account-contexts.json``; a test keeps the two equal), and the server
checks them again when a document is saved (D-01-T06 and later validators call
``allowed_in_context``):

- **sales** — revenue, other income and current liabilities (customer deposits, deferred
  revenue); never an expense account;
- **purchase** — expenses (cost of sales, operating, other) and the assets a bill can buy
  (current assets, inventory, prepayments, fixed, non-current and intangible assets);
- **journal** — every postable sub-type except Current year earnings (computed by reports);
- **bank** — bank accounts only (bank, credit card, line of credit, loan).

Sales, purchase and bank pickers never offer the accounts the engine posts to by itself (AR, AP,
sales-tax controls, payroll liabilities, retained earnings…) or, for sales and purchase, bank
accounts. Archived accounts and accounts with sub-accounts are never offered anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Account, AccountSubtype, SystemRole

S, R = AccountSubtype, SystemRole

ENGINE_ROLES: tuple[str, ...] = (
    R.AR,
    R.AP,
    R.GST_HST_PAYABLE,
    R.ITC_RECEIVABLE,
    R.PST_PAYABLE,
    R.QST_PAYABLE,
    R.QST_ITR,
    R.RETAINED_EARNINGS,
    R.CURRENT_YEAR_EARNINGS,
    R.ROUNDING,
    R.SUSPENSE_CONVERSION,
    R.UNPAID_EXPENSE_CLAIMS,
    R.WAGES_PAYABLE,
    R.CPP_PAYABLE,
    R.QPP_PAYABLE,
    R.EI_PAYABLE,
    R.QPIP_PAYABLE,
    R.INCOME_TAX_WITHHELD,
    R.VACATION_PAYABLE,
    R.WORKERS_COMP_PAYABLE,
    R.EHT_PAYABLE,
    R.FX_GAIN_LOSS,
)


@dataclass(frozen=True)
class AccountContext:
    subtypes: tuple[str, ...]
    exclude_engine_roles: bool
    bank: str  # "any" | "exclude" | "only"


CONTEXTS: dict[str, AccountContext] = {
    "sales": AccountContext(
        subtypes=(S.REVENUE, S.OTHER_INCOME, S.CURRENT_LIABILITY),
        exclude_engine_roles=True,
        bank="exclude",
    ),
    "purchase": AccountContext(
        subtypes=(
            S.COST_OF_SALES,
            S.OPERATING_EXPENSE,
            S.OTHER_EXPENSE,
            S.CURRENT_ASSET,
            S.INVENTORY,
            S.PREPAYMENT,
            S.FIXED_ASSET,
            S.NON_CURRENT_ASSET,
            S.INTANGIBLE,
        ),
        exclude_engine_roles=True,
        bank="exclude",
    ),
    "journal": AccountContext(
        subtypes=tuple(s for s in AccountSubtype.values if s != S.CURRENT_YEAR_EARNINGS),
        exclude_engine_roles=False,
        bank="any",
    ),
    "bank": AccountContext(
        subtypes=(S.BANK, S.CURRENT_LIABILITY, S.NON_CURRENT_LIABILITY),
        exclude_engine_roles=True,
        bank="only",
    ),
}


def allowed_in_context(account: Account, context: str) -> bool:
    """Whether a document line of ``context`` may use ``account`` (sub-accounts aside: callers
    also run ``tree.assert_postable``)."""
    rules = CONTEXTS[context]
    if account.is_archived or account.deleted_at is not None:
        return False
    if account.subtype not in rules.subtypes:
        return False
    if rules.exclude_engine_roles and account.system_role in ENGINE_ROLES:
        return False
    if rules.bank == "only" and not account.is_bank:
        return False
    return not (rules.bank == "exclude" and account.is_bank)

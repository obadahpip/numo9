"""Chart-of-accounts template loader (C-01-T05).

``data/coa_ca_v1.json`` is the Canadian small-business template — the same rows the accountant
reviews in ``docs/accounting/coa_template_ca_v1.xlsx`` (C-01-T01, exported from this file by
``backend/tools/export_coa_template.py``). Each row has a 4-digit code, an English name, a
sub-type (which decides the type), a GIFI code, a tax-default kind, and optionally a system role,
the home provinces it is for, the require-contact flag and the bank flag.

``load_template(organisation, province)`` creates the organisation's accounts for its **home
province**: rows limited to other provinces are skipped (QST accounts only for Quebec, PST for
British Columbia, Manitoba and Saskatchewan, employer health tax for the provinces that levy one)
and each row's tax kind becomes a **tax-default key** for that province:

=================  ================================  ==================================
kind               key                               meaning (resolved by G-01, Phase 1)
=================  ================================  ==================================
``purchase``       ``purchase.<PROV>.standard``      the home province's purchase code
                                                     (e.g. ON → HST 13 % on purchases)
``purchase_itc50`` ``purchase.<PROV>.standard.itc50`` same, ITC/ITR restricted to 50 %
``sales``          ``sales.<PROV>.standard``         the home province's sales code
``exempt_purchase`` ``purchase.exempt``              exempt supply (bank charges, interest,
                                                     insurance)
``exempt_sales``   ``sales.exempt``                  exempt supply (interest income)
``none``           (empty)                           no tax on the account's lines (balance
                                                     sheet, wages, amortization…)
=================  ================================  ==================================

So expense accounts default to the home-province purchase rate, never "Exempt" (gap-45). Every
row has a GIFI code: a loaded chart has 0 unmapped accounts (gap-30). The load is one
transaction and one audit batch; every account's creation is attributed to the person (or job)
loading it (gap-44). A chart that already has accounts is never loaded over.

``ensure_system_account(organisation, role)`` creates a system account a chart lacks from its
template row (e.g. PST payable when an Ontario organisation registers for BC PST), at the
template code or the next free code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from numo9.audit.batch import audit_batch
from numo9.tenancy.context import current_org, org_context
from numo9.tenancy.models import Organisation

from .models import SUBTYPE_TYPE, Account, LedgerError, SystemRole
from .renumber import acting_as

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_TEMPLATE = "ca_v1"

#: Provinces and territories (postal abbreviations) a home province can be.
PROVINCES: tuple[str, ...] = (
    "AB",
    "BC",
    "MB",
    "NB",
    "NL",
    "NS",
    "NT",
    "NU",
    "ON",
    "PE",
    "QC",
    "SK",
    "YT",
)

TAX_KINDS: frozenset[str] = frozenset(
    {"purchase", "purchase_itc50", "sales", "exempt_purchase", "exempt_sales", "none"}
)


@dataclass(frozen=True)
class TemplateAccount:
    code: str
    name: str
    subtype: str
    gifi: str
    tax: str
    system_role: str = ""
    provinces: tuple[str, ...] = ()
    require_contact: bool = False
    is_bank: bool = False
    note: str = ""

    @property
    def type(self) -> str:
        return SUBTYPE_TYPE[self.subtype]

    def applies_to(self, province: str) -> bool:
        return not self.provinces or province in self.provinces


@dataclass(frozen=True)
class Template:
    key: str
    title: str
    version: str
    gifi_list: str
    status: str
    accounts: tuple[TemplateAccount, ...] = field(default_factory=tuple)

    def rows_for(self, province: str) -> list[TemplateAccount]:
        return [row for row in self.accounts if row.applies_to(province)]

    def row_for_role(self, role: str) -> TemplateAccount | None:
        return next((row for row in self.accounts if row.system_role == role), None)


@lru_cache(maxsize=4)
def get_template(key: str = DEFAULT_TEMPLATE) -> Template:
    path = DATA_DIR / f"coa_{key}.json"
    if not path.is_file():
        raise LookupError(f"No chart-of-accounts template {key!r}.")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    accounts = tuple(
        TemplateAccount(
            code=row["code"],
            name=row["name"],
            subtype=row["subtype"],
            gifi=row["gifi"],
            tax=row["tax"],
            system_role=row.get("system_role", ""),
            provinces=tuple(row.get("provinces", ())),
            require_contact=bool(row.get("require_contact", False)),
            is_bank=bool(row.get("is_bank", False)),
            note=row.get("note", ""),
        )
        for row in data["accounts"]
    )
    return Template(
        key=data["template"],
        title=data["title"],
        version=data["version"],
        gifi_list=data["gifi_list"],
        status=data["status"],
        accounts=accounts,
    )


def normalise_province(province: str) -> str:
    value = (province or "").strip().upper()
    if value not in PROVINCES:
        raise LedgerError(
            _("Choose the home province or territory (e.g. ON)."),
            code="ledger.template.province_invalid",
        )
    return value


def tax_key(kind: str, province: str) -> str:
    """The tax-default key of a template tax kind for a home province (table above)."""
    if kind not in TAX_KINDS:
        raise ValueError(f"Unknown tax kind {kind!r}.")
    return {
        "purchase": f"purchase.{province}.standard",
        "purchase_itc50": f"purchase.{province}.standard.itc50",
        "sales": f"sales.{province}.standard",
        "exempt_purchase": "purchase.exempt",
        "exempt_sales": "sales.exempt",
        "none": "",
    }[kind]


def _account_from_row(
    organisation: Organisation, row: TemplateAccount, template: Template, province: str, code: str
) -> Account:
    return Account(
        organisation=organisation,
        code=code,
        name_i18n={"en-ca": row.name},
        type=row.type,
        subtype=row.subtype,
        system_role=row.system_role,
        is_bank=row.is_bank,
        gifi_id=row.gifi,
        require_contact=row.require_contact,
        default_tax_key=tax_key(row.tax, province),
        template_ref=f"{template.key}:{row.code}",
    )


def _check_context(organisation: Organisation) -> None:
    active = current_org()
    if active is not None and active.pk != organisation.pk:
        raise ValueError("Load a template only for the active organisation.")


def load_template(
    organisation: Organisation,
    province: str,
    *,
    template: str = DEFAULT_TEMPLATE,
    actor: Any = None,
) -> list[Account]:
    """Create the organisation's chart from the template for its home province."""
    _check_context(organisation)
    home = normalise_province(province)
    definition = get_template(template)
    created: list[Account] = []
    with (
        org_context(organisation),
        acting_as(actor),
        transaction.atomic(),
        audit_batch(
            f"Chart of accounts loaded: {definition.title} ({home})",
            organisation=organisation,
            meta={"template": definition.key, "version": definition.version, "province": home},
        ),
    ):
        if Account._base_manager.filter(organisation=organisation).exists():
            raise LedgerError(
                _("This organisation already has accounts: a template loads into an empty chart."),
                code="ledger.template.chart_not_empty",
            )
        for row in definition.rows_for(home):
            account = _account_from_row(organisation, row, definition, home, row.code)
            account.created_by = actor if getattr(actor, "is_authenticated", False) else None
            account.save()
            created.append(account)
    return created


def ensure_system_account(
    organisation: Organisation,
    role: str,
    *,
    province: str,
    template: str = DEFAULT_TEMPLATE,
    actor: Any = None,
) -> Account:
    """The organisation's account for ``role``, created from the template row when missing."""
    _check_context(organisation)
    role = SystemRole(role).value
    home = normalise_province(province)
    definition = get_template(template)
    with org_context(organisation), acting_as(actor), transaction.atomic():
        existing = Account._base_manager.filter(organisation=organisation, system_role=role)
        account = existing.first()
        if account is not None:
            return account
        row = definition.row_for_role(role)
        if row is None:
            raise LedgerError(
                _("The template has no account for this system role."),
                code="ledger.template.role_missing",
            )
        taken = {
            code.lower()
            for code in Account._base_manager.filter(organisation=organisation).values_list(
                "code", flat=True
            )
        }
        code = row.code
        while code.lower() in taken:
            if not code.isdigit():
                raise LedgerError(
                    _("No free code for the account: renumber an account and try again."),
                    code="ledger.template.no_free_code",
                )
            code = str(int(code) + 1).zfill(len(code))
        account = _account_from_row(organisation, row, definition, home, code)
        account.created_by = actor if getattr(actor, "is_authenticated", False) else None
        account.save()
        return account


def unmapped_gifi_count(organisation: Organisation) -> int:
    """Active accounts without a GIFI code (gap-30 expects 0 for a loaded template)."""
    return (
        Account._base_manager.filter(
            organisation=organisation, gifi__isnull=True, deleted_at__isnull=True
        )
        .exclude(status="archived")
        .count()
    )

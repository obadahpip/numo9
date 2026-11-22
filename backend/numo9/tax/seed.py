"""The Canadian sales-tax table (G-01-T04): ``data/tax_ca.json`` installed per organisation.

The document holds the 5 authorities, every component version (GST 5 %, HST 13/14/15 %, QST
9.975 %, BC PST 7 %, MB RST 7 % and the historical NS HST 15 % to 31 Mar 2025 and MB RST 8 % to
30 Jun 2019, SK PST 6 %, a 0 % component for zero-rated supplies) and the codes for the 13
provinces and territories on both sides (``sales.<PROV>.standard``,
``purchase.<PROV>.standard`` and the 50 % ITC variant ``purchase.<PROV>.standard.itc50`` —
the keys the chart template gives its accounts), plus zero-rated, exempt and out-of-scope codes
on each side.

``install_tax_table(organisation)`` creates the organisation's copy — idempotent: an
organisation that already has authorities is left as it is (its own edits are never
overwritten). Each component's control accounts are the organisation's system accounts for its
kind (GST/HST payable and receivable, PST payable, QST payable and ITR) when the chart has them;
non-recoverable taxes (PST) have no purchase control account (the tax goes to the expense).
It runs when a chart template is loaded (so the control accounts exist), from migration
``tax.0003`` for organisations that already have a chart, and lazily (``ensure_tax_table``)
wherever codes are read.
"""

from __future__ import annotations

import datetime as dt
import json
from contextlib import nullcontext
from decimal import Decimal
from functools import cache
from pathlib import Path
from typing import Any

from django.db import transaction

SEED_PATH = Path(__file__).parent / "data" / "tax_ca.json"

#: Control-account system roles per component kind: (sales, purchase).
CONTROL_ROLES: dict[str, tuple[str, str]] = {
    "gst": ("gst_hst_payable", "itc_receivable"),
    "hst": ("gst_hst_payable", "itc_receivable"),
    "qst": ("qst_payable", "qst_itr"),
    "pst": ("pst_payable", ""),
}


@cache
def load_tax_seed() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    return data


def _day(value: str | None) -> dt.date | None:
    return dt.date.fromisoformat(value) if value else None


def install_tax_table(organisation: Any, *, models: Any = None) -> bool:
    """Install the Canadian table into ``organisation``; False when it already has one.

    ``models`` — an object with ``TaxAuthority``, ``TaxComponent``, ``TaxCode``,
    ``TaxCodeComponent`` and ``Account`` (historical models in a migration); default: the real
    ones (full model validation runs)."""
    real = models is None
    if models is None:
        from numo9.ledger.models import Account
        from numo9.tax import models as tax_models

        class Real:
            TaxAuthority = tax_models.TaxAuthority
            TaxComponent = tax_models.TaxComponent
            TaxCode = tax_models.TaxCode
            TaxCodeComponent = tax_models.TaxCodeComponent

        Real.Account = Account  # type: ignore[attr-defined]
        models = Real
    seed = load_tax_seed()
    org_id = organisation.pk
    batch: Any = nullcontext()
    if real:
        from numo9.audit.batch import audit_batch

        batch = audit_batch(
            f"Sales-tax table installed ({seed['version']})",
            organisation=organisation,
            meta={"tax_table": seed["version"]},
        )
    from numo9.tenancy.context import org_context

    # In the organisation's context: the tax tables have forced row-level security.
    with org_context(organisation), transaction.atomic(), batch:
        if models.TaxAuthority._base_manager.filter(organisation_id=org_id).exists():
            return False
        roles = {
            a.system_role: a
            for a in models.Account._base_manager.filter(organisation_id=org_id).exclude(
                system_role=""
            )
        }
        authorities = {}
        for row in seed["authorities"]:
            item = models.TaxAuthority(
                organisation_id=org_id, code=row["code"], name_i18n=row["name"]
            )
            item.save()
            authorities[row["code"]] = item
        components: dict[tuple[str, str], Any] = {}
        for row in seed["components"]:
            sales_role, purchase_role = CONTROL_ROLES[row["kind"]]
            item = models.TaxComponent(
                organisation_id=org_id,
                authority=authorities[row["authority"]],
                key=row["key"],
                kind=row["kind"],
                rate=Decimal(row["rate"]),
                effective_from=_day(row["from"]),
                effective_to=_day(row["to"]),
                recoverable=row["recoverable"],
                side=row["side"],
                name_i18n=row["name"],
                control_account_sales=roles.get(sales_role),
                control_account_purchase=roles.get(purchase_role) if row["recoverable"] else None,
            )
            item.save()
            components[(row["key"], row["from"])] = item
        code_fields = {f.name for f in models.TaxCode._meta.get_fields()}
        for row in seed["codes"]:
            restriction = row.get("itc_restriction_pct")
            # The code's claimable ITC % (G-01-T05); a table installed before that field existed
            # (migration tax.0003) carries it on the components instead — same result.
            on_code = restriction is not None and "itc_restriction_pct" in code_fields
            extra = {"itc_restriction_pct": Decimal(restriction)} if on_code else {}
            code = models.TaxCode(
                organisation_id=org_id,
                code=row["code"],
                version=row["version"],
                side=row["side"],
                type=row["type"],
                province=row["province"],
                effective_from=_day(row["from"]),
                effective_to=_day(row["to"]),
                name_i18n=row["name"],
                **extra,
            )
            code.save()
            for position, part in enumerate(row["components"], start=1):
                component = components[(part["key"], part["from"])]
                models.TaxCodeComponent(
                    organisation_id=org_id,
                    tax_code=code,
                    component=component,
                    position=position,
                    recoverable_pct=Decimal(restriction)
                    if restriction and component.recoverable and not on_code
                    else None,
                ).save()
    return True


def ensure_tax_table(organisation: Any) -> None:
    """Install the table if the organisation has none yet (codes are read lazily)."""
    install_tax_table(organisation)


def link_control_accounts(organisation: Any) -> int:
    """Fill missing control accounts from the organisation's system accounts (a chart loaded
    after the table was installed); returns how many components changed."""
    from numo9.ledger.models import Account
    from numo9.tenancy.context import org_context

    from .models import TaxComponent

    roles = {
        a.system_role: a
        for a in Account._base_manager.filter(organisation=organisation).exclude(system_role="")
    }
    changed = 0
    with org_context(organisation):
        components = list(TaxComponent._base_manager.filter(organisation=organisation))
    for component in components:
        sales_role, purchase_role = CONTROL_ROLES[component.kind]
        update = False
        if component.control_account_sales_id is None and roles.get(sales_role):
            component.control_account_sales = roles[sales_role]
            update = True
        if (
            component.recoverable
            and component.control_account_purchase_id is None
            and purchase_role
            and roles.get(purchase_role)
        ):
            component.control_account_purchase = roles[purchase_role]
            update = True
        if update:
            with org_context(organisation):
                component.save(
                    update_fields=[
                        "control_account_sales",
                        "control_account_purchase",
                        "updated_at",
                    ]
                )
            changed += 1
    return changed


def on_chart_loaded(organisation: Any) -> None:
    """Chart-template hook: install the table, or link a table installed before the chart."""
    if not install_tax_table(organisation):
        link_control_accounts(organisation)

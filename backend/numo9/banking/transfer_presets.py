"""Transfer presets (F-06-T05): "Fund petty cash" and "Pay credit card".

A preset pre-fills the two accounts of a transfer **by bank-account type**:

====================  ==================================  =====================
preset                from (first match, in this order)   to
====================  ==================================  =====================
``fund_petty_cash``   Chequing, then Savings              Cash / petty cash
``pay_credit_card``   Chequing, then Savings              Credit card
====================  ==================================  =====================

Within a type the accounts are taken in name order (the pickers' order), archived and deleted
accounts never. ``resolve_preset(key)`` returns the pair (either side ``None`` when the
organisation has no account of that type — the person picks it); the frontend applies the same
table to the accounts it already shows (``frontend/src/banking/transferPresets.ts``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.utils.translation import gettext_lazy as _

from .models import BankAccount, BankAccountType

T = BankAccountType


@dataclass(frozen=True)
class TransferPreset:
    key: str
    label: Any
    from_types: tuple[str, ...]
    to_types: tuple[str, ...]


PRESETS: dict[str, TransferPreset] = {
    preset.key: preset
    for preset in (
        TransferPreset("fund_petty_cash", _("Fund petty cash"), (T.CHEQUING, T.SAVINGS), (T.CASH,)),
        TransferPreset(
            "pay_credit_card", _("Pay credit card"), (T.CHEQUING, T.SAVINGS), (T.CREDIT_CARD,)
        ),
    )
}


@dataclass(frozen=True)
class PresetAccounts:
    preset: TransferPreset
    from_account: BankAccount | None
    to_account: BankAccount | None


def _first(types: tuple[str, ...], exclude: BankAccount | None = None) -> BankAccount | None:
    accounts = BankAccount.objects.pickable().select_related("gl_account")
    if exclude is not None:
        accounts = accounts.exclude(pk=exclude.pk)
    for kind in types:
        found: BankAccount | None = (
            accounts.filter(type=kind).order_by("display_name", "pk").first()
        )
        if found is not None:
            return found
    return None


def resolve_preset(key: str) -> PresetAccounts:
    """The preset's accounts in the active organisation (``KeyError`` for an unknown key)."""
    preset = PRESETS[key]
    source = _first(preset.from_types)
    return PresetAccounts(preset, source, _first(preset.to_types, exclude=source))

"""Saved statement mappings and the built-in Canadian bank layouts (F-02-T05).

``BUILTIN`` — the layouts of the statements Canadian banks export as CSV (or XLSX), as their
online banking gives them: RBC Royal Bank, TD Canada Trust, Scotiabank, BMO, CIBC, Desjardins,
National Bank, Tangerine, a generic credit union, and a generic "date, description, amount"
layout. Each has its header row (empty when the bank's file has none — TD, CIBC, Desjardins), the
role of each column, the date format, the sign convention and the rows to skip.

``ensure_builtin_mappings(organisation)`` seeds them as ``StatementMapping`` rows of the
organisation the first time it imports (idempotent; no audit noise — they are Numo9's, not the
organisation's edits). Built-in mappings are never edited: a person who changes the columns in
the wizard saves their own mapping (F-02-T06).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import translation
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation

from ..models import StatementMapping
from .layout import Layout, Role, Sign

D, DESC, AMT, DR, CR, BAL, REF, IGN = (
    Role.DATE,
    Role.DESCRIPTION,
    Role.AMOUNT,
    Role.DEBIT,
    Role.CREDIT,
    Role.BALANCE,
    Role.REFERENCE,
    Role.IGNORE,
)


@dataclass(frozen=True)
class Seed:
    key: str
    name: str | Promise
    institution: str
    headers: tuple[str, ...]
    layout: Layout


BUILTIN: tuple[Seed, ...] = (
    Seed(
        "rbc",
        "RBC Royal Bank",
        "RBC Royal Bank",
        (
            "Account Type",
            "Account Number",
            "Transaction Date",
            "Cheque Number",
            "Description 1",
            "Description 2",
            "CAD$",
            "USD$",
        ),
        Layout((IGN, IGN, D, REF, DESC, DESC, AMT, IGN), "MM/DD/YYYY", Sign.SIGNED),
    ),
    Seed(
        "td",
        "TD Canada Trust",
        "TD Canada Trust",
        (),
        Layout((D, DESC, DR, CR, BAL), "MM/DD/YYYY", Sign.DEBIT_CREDIT, has_header=False),
    ),
    Seed(
        "scotiabank",
        "Scotiabank",
        "Scotiabank",
        ("Date", "Description", "Sub-description", "Status", "Type of Transaction", "Amount"),
        Layout((D, DESC, DESC, IGN, IGN, AMT), "YYYY-MM-DD", Sign.SIGNED),
    ),
    Seed(
        "bmo",
        "BMO Bank of Montreal",
        "BMO Bank of Montreal",
        ("First Bank Card", "Transaction Type", "Date Posted", "Transaction Amount", "Description"),
        Layout((IGN, IGN, D, AMT, DESC), "YYYYMMDD", Sign.SIGNED, skip_rows=1),
    ),
    Seed(
        "cibc",
        "CIBC",
        "CIBC",
        (),
        Layout((D, DESC, DR, CR, IGN), "YYYY-MM-DD", Sign.DEBIT_CREDIT, has_header=False),
    ),
    Seed(
        "desjardins",
        "Desjardins",
        "Desjardins",
        (),
        Layout(
            (IGN, IGN, IGN, D, REF, DESC, IGN, DR, CR, BAL),
            "YYYY/MM/DD",
            Sign.DEBIT_CREDIT,
            has_header=False,
        ),
    ),
    Seed(
        "national_bank",
        "National Bank",
        "National Bank",
        ("Date", "Description", "Catégorie", "Débit", "Crédit", "Solde"),
        Layout((D, DESC, IGN, DR, CR, BAL), "YYYY-MM-DD", Sign.DEBIT_CREDIT, decimal_separator=","),
    ),
    Seed(
        "tangerine",
        "Tangerine",
        "Tangerine",
        ("Transaction date", "Transaction", "Name", "Memo", "Amount"),
        Layout((D, IGN, DESC, DESC, AMT), "MM/DD/YYYY", Sign.SIGNED),
    ),
    Seed(
        "credit_union",
        _("Credit union (generic)"),
        "",
        ("Date", "Description", "Withdrawals", "Deposits", "Balance"),
        Layout((D, DESC, DR, CR, BAL), "YYYY-MM-DD", Sign.DEBIT_CREDIT),
    ),
    Seed(
        "generic",
        _("Generic (date, description, amount)"),
        "",
        ("Date", "Description", "Amount"),
        Layout((D, DESC, AMT), "YYYY-MM-DD", Sign.SIGNED),
    ),
)
SEEDS: dict[str, Seed] = {seed.key: seed for seed in BUILTIN}
GENERIC = "generic"


def mapping_fields(layout: Layout) -> dict[str, Any]:
    """``StatementMapping`` field values of a layout."""
    data = layout.as_dict()
    return {
        "columns": data["columns"],
        "date_format": data["date_format"],
        "sign": data["sign"],
        "has_header": data["has_header"],
        "skip_rows": data["skip_rows"],
        "decimal_separator": data["decimal_separator"],
    }


def display_name(mapping: StatementMapping) -> str:
    """The mapping's name in the active language (built-in generic layouts are translated)."""
    seed = SEEDS.get(mapping.builtin_key)
    return str(seed.name) if seed is not None else mapping.name


def ensure_builtin_mappings(organisation: Organisation) -> list[StatementMapping]:
    """Seed the built-in layouts the organisation doesn't have yet; return all its mappings."""
    have = set(
        StatementMapping._base_manager.filter(
            organisation=organisation, deleted_at__isnull=True
        ).values_list("builtin_key", flat=True)
    )
    taken = {
        name.lower()
        for name in StatementMapping._base_manager.filter(
            organisation=organisation, deleted_at__isnull=True
        ).values_list("name", flat=True)
    }
    missing: list[StatementMapping] = []
    for seed in BUILTIN:
        if seed.key in have:
            continue
        with translation.override(None):
            name = str(seed.name)  # stored in English; ``display_name`` translates
        if name.lower() in taken:  # an organisation's own mapping already has the name
            name = f"{name} (Numo9)"
        missing.append(
            StatementMapping(
                organisation=organisation,
                name=name,
                institution=seed.institution,
                builtin_key=seed.key,
                headers=list(seed.headers),
                **mapping_fields(seed.layout),
            )
        )
    if missing:
        try:
            with transaction.atomic():
                StatementMapping._base_manager.bulk_create(missing)
        except IntegrityError:  # another request seeded them at the same moment
            pass
    return organisation_mappings(organisation)


def organisation_mappings(organisation: Organisation) -> list[StatementMapping]:
    return list(
        StatementMapping._base_manager.filter(
            organisation=organisation, deleted_at__isnull=True
        ).order_by("-use_count", "name", "pk")
    )


def builtin(mappings: Iterable[StatementMapping], key: str) -> StatementMapping | None:
    return next((m for m in mappings if m.builtin_key == key), None)

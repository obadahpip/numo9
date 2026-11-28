"""Saved statement mappings, the built-in Canadian bank layouts (F-02-T05) and auto-detection
(F-02-T06).

``BUILTIN`` — the layouts of the statements Canadian banks export as CSV (or XLSX), as their
online banking gives them: RBC Royal Bank, TD Canada Trust, Scotiabank, BMO, CIBC, Desjardins,
National Bank, Tangerine, a generic credit union, and a generic "date, description, amount"
layout. Each has its header row (empty when the bank's file has none — TD, CIBC, Desjardins), the
role of each column, the date format, the sign convention and the rows to skip.

``ensure_builtin_mappings(organisation)`` seeds them as ``StatementMapping`` rows of the
organisation the first time it imports (idempotent; no audit noise — they are Numo9's, not the
organisation's edits). Built-in mappings are never edited: a person who changes the columns in
the wizard saves their own mapping (F-02-T06).

**Auto-detection** — ``detect_mapping(table, mappings, preferred)`` scores every mapping against
the file: with a header row, 70 % header similarity (column by column, accents / case /
punctuation ignored) + 30 % the share of the first data rows the mapping reads without a problem;
without a header, only that share and the column count — a first row that isn't data (a header)
costs most of it — capped at 0.9 since nothing confirms it. The best mapping from ``MIN_SCORE``
(0.6) up is chosen; the bank account's own mapping (``BankAccount.statement_mapping``, the
person's last choice) wins while it fits the file and is within ``PREFERRED_MARGIN`` of the best.
Nothing fits → a layout guessed from the header words (``guess_layout``) that the person checks.
Dates are never guessed silently: the detection lists every date format the sampled dates fit, so
the wizard asks when they are ambiguous.

``remember_mapping`` saves the person's choice on the bank account when an import is committed:
the chosen mapping, or — when the columns were changed — the account's own "<account> (custom)"
mapping (built-in mappings are never edited).
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone, translation
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import Organisation

from ..models import BankAccount, StatementMapping
from .errors import StatementError
from .layout import Layout, Role, Sign, Table, TableRow, normalise_row, parse_date

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


# ---- auto-detection (F-02-T06) ------------------------------------------------------------------

#: A saved mapping is chosen by itself only from this score up; below, the wizard proposes a
#: layout guessed from the header and asks the person to check it.
MIN_SCORE = 0.6
#: The bank account's own mapping (the person's last choice) wins over a better-scoring one while
#: it fits the file this well and is within this distance of the best.
PREFERRED_MARGIN = 0.15
SAMPLE_ROWS = 10

#: Header words → the role a guessed layout gives the column (English and French exports).
KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (Role.BALANCE, ("balance", "solde")),
    (Role.DEBIT, ("debit", "withdrawal", "retrait", "paid out", "money out", "charge")),
    (Role.CREDIT, ("credit", "deposit", "depot", "paid in", "money in", "payment received")),
    (Role.AMOUNT, ("amount", "montant", "cad", "value", "valeur")),
    (Role.DATE, ("date", "posted", "jour")),
    (Role.FITID, ("transaction id", "fitid", "id de transaction")),
    (Role.REFERENCE, ("reference", "cheque", "check", "numero")),
    (Role.PAYEE, ("payee", "beneficiaire", "merchant", "marchand", "name", "nom")),
    (Role.DESCRIPTION, ("description", "details", "memo", "libelle", "narrative", "transaction")),
)
#: Order in which date formats are tried when guessing (the guess is shown, never silent).
GUESS_ORDER = (
    "YYYY-MM-DD",
    "YYYY/MM/DD",
    "YYYYMMDD",
    "DD/MM/YYYY",
    "MM/DD/YYYY",
    "DD-MM-YYYY",
    "MM-DD-YYYY",
    "DD.MM.YYYY",
    "DD MMM YYYY",
    "MMM DD, YYYY",
    "DD/MM/YY",
    "MM/DD/YY",
)


@dataclass(frozen=True)
class Candidate:
    mapping: StatementMapping
    score: float


@dataclass(frozen=True)
class Detection:
    """What the wizard proposes for a CSV / XLSX file.

    ``mapping`` — the saved mapping chosen (``None`` when none fits: ``layout`` is then guessed
    from the header and must be checked); ``score`` its fit (0–1); ``candidates`` every mapping
    with its score, best first; ``preferred`` — the bank account's own mapping was used;
    ``date_formats`` — the formats every sampled date fits (more than one: the dates are
    ambiguous, e.g. 03/04/2026, and the person confirms the format)."""

    mapping: StatementMapping | None
    layout: Layout
    score: float
    candidates: tuple[Candidate, ...]
    preferred: bool = False
    date_formats: tuple[str, ...] = ()

    @property
    def date_ambiguous(self) -> bool:
        return len(self.date_formats) > 1


def header_key(text: str) -> str:
    """``"Débit "`` → ``"debit"``: accents, case, spaces and punctuation ignored."""
    plain = unicodedata.normalize("NFKD", text or "")
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9$]+", "", plain.casefold())


def header_similarity(expected: Sequence[str], actual: Sequence[str]) -> float:
    """How alike two header rows are, column by column (0–1); widths that differ cost a bit."""
    if not expected or not actual:
        return 0.0
    wanted = [header_key(h) for h in expected]
    found = [header_key(h) for h in actual]
    ratios = [
        SequenceMatcher(None, w, found[i]).ratio() if i < len(found) else 0.0
        for i, w in enumerate(wanted)
    ]
    width = min(len(wanted), len(found)) / max(len(wanted), len(found))
    return (sum(ratios) / len(wanted)) * (0.8 + 0.2 * width)


def data_fit(rows: Sequence[TableRow], layout: Layout, *, iso_dates: bool = False) -> float:
    """The share of ``rows`` the layout reads without a problem."""
    if not rows:
        return 0.0
    good = sum(1 for row in rows if normalise_row(row, layout, iso_dates=iso_dates).ok)
    return good / len(rows)


def score(table: Table, mapping: StatementMapping) -> float:
    try:
        layout = mapping.layout()
    except StatementError:
        return 0.0
    header, data = table.header_and_data(layout)
    sample = data[:SAMPLE_ROWS]
    fit = data_fit(sample, layout, iso_dates=table.iso_dates)
    if layout.has_header:
        if header is None:
            return 0.0
        return 0.7 * header_similarity(mapping.headers, header.cells) + 0.3 * fit
    if not sample:
        return 0.0
    widths = {len(row.cells) for row in sample}
    width = 1.0 if widths == {len(layout.columns)} else 0.6
    # The file's first row must be data: a header row there means the file isn't this layout.
    first = 1.0 if normalise_row(sample[0], layout, iso_dates=table.iso_dates).ok else 0.4
    return 0.9 * fit * width * first  # no header to confirm it: never a perfect score


def _role_of(header: str, taken: set[str]) -> str:
    key = header_key(header)
    spaced = re.sub(r"\s+", " ", unicodedata.normalize("NFKD", header.casefold()))
    spaced = "".join(c for c in spaced if not unicodedata.combining(c))
    for role, words in KEYWORDS:
        if any(header_key(w) in key or w in spaced for w in words):
            if role in (Role.DATE, Role.AMOUNT, Role.DEBIT, Role.CREDIT, Role.BALANCE) and (
                role in taken
            ):
                continue  # only the first date / amount column
            return role
    return Role.IGNORE


def fitting_date_formats(values: Iterable[str], *, iso_dates: bool = False) -> tuple[str, ...]:
    """The date formats that read every one of ``values``."""
    sample = [v for v in values if v.strip()]
    if not sample:
        return ()
    return tuple(f for f in GUESS_ORDER if all(parse_date(v, f, iso_ok=iso_dates) for v in sample))


def guess_layout(table: Table) -> tuple[Layout, tuple[str, ...]]:
    """A layout from the header words (first row), and the date formats that fit its dates."""
    first = table.rows[0].cells if table.rows else ()
    roles: list[str] = []
    taken: set[str] = set()
    for header in first:
        role = _role_of(header, taken)
        taken.add(role)
        roles.append(role)
    if Role.DATE not in roles and roles:
        roles[0] = Role.DATE
    sign = Sign.DEBIT_CREDIT if {Role.DEBIT, Role.CREDIT} <= set(roles) else Sign.SIGNED
    if sign == Sign.SIGNED and Role.AMOUNT not in roles:
        for index in range(len(roles) - 1, -1, -1):  # the last column that looks like money
            if roles[index] in (Role.IGNORE, Role.DEBIT, Role.CREDIT):
                roles[index] = Role.AMOUNT
                break
    sample = table.rows[1 : 1 + SAMPLE_ROWS]
    position = roles.index(Role.DATE)
    formats = fitting_date_formats(
        (row.cells[position] if position < len(row.cells) else "" for row in sample),
        iso_dates=table.iso_dates,
    )
    return Layout(tuple(roles), formats[0] if formats else "YYYY-MM-DD", sign), formats


def detect_mapping(
    table: Table,
    mappings: Sequence[StatementMapping],
    preferred: StatementMapping | None = None,
) -> Detection:
    """The best saved mapping for ``table`` (see ``Detection``)."""
    ranked = sorted(
        (Candidate(m, round(score(table, m), 4)) for m in mappings),
        key=lambda c: (-c.score, not c.mapping.is_builtin, c.mapping.name),
    )
    candidates = tuple(ranked)
    best = candidates[0] if candidates else None
    chosen: Candidate | None = best if best is not None and best.score >= MIN_SCORE else None
    used_preferred = False
    if preferred is not None and best is not None:
        mine = next((c for c in candidates if c.mapping.pk == preferred.pk), None)
        if (
            mine is not None
            and mine.score >= MIN_SCORE
            and mine.score >= best.score - PREFERRED_MARGIN
        ):
            chosen, used_preferred = mine, True
    if chosen is None:
        layout, formats = guess_layout(table)
        return Detection(None, layout, best.score if best else 0.0, candidates, False, formats)
    layout = chosen.mapping.layout()
    _, data = table.header_and_data(layout)
    position = layout.positions(Role.DATE)[0]
    formats = fitting_date_formats(
        (row.cells[position] if position < len(row.cells) else "" for row in data[:SAMPLE_ROWS]),
        iso_dates=table.iso_dates,
    )
    return Detection(chosen.mapping, layout, chosen.score, candidates, used_preferred, formats)


# ---- the account's own mapping (F-02-T06) -------------------------------------------------------


def remember_mapping(
    bank: BankAccount,
    layout: Layout,
    mapping: StatementMapping | None,
    headers: Sequence[str] = (),
    *,
    user: Any = None,
) -> StatementMapping:
    """Save the person's choice for the bank account and return the mapping used.

    The layout of ``mapping`` unchanged → that mapping becomes the account's. Changed (or no
    mapping) → the account's own mapping "<account> (custom)" is created or updated with it —
    built-in mappings are never edited. Either way its use count goes up."""
    if mapping is not None and mapping.layout() == layout:
        chosen = mapping
    else:
        with translation.override(None):
            name = str(CUSTOM_NAME) % {"account": bank.display_name}
        chosen = StatementMapping.objects.filter(
            name__iexact=name, deleted_at__isnull=True
        ).first() or StatementMapping(
            organisation_id=bank.organisation_id, name=name, created_by=user
        )
        if chosen.is_builtin:  # pragma: no cover - names of seeds never end with "(custom)"
            chosen = StatementMapping(organisation_id=bank.organisation_id, name=f"{name} 2")
        for attribute, value in mapping_fields(layout).items():
            setattr(chosen, attribute, value)
        chosen.headers = list(headers) if layout.has_header else []
        chosen.institution = bank.institution
        chosen.save()
    StatementMapping.objects.filter(pk=chosen.pk).update(
        use_count=F("use_count") + 1, last_used_at=timezone.now()
    )
    if bank.statement_mapping_id != chosen.pk:
        bank.statement_mapping = chosen
        bank.save(update_fields=["statement_mapping", "updated_at"])
    return chosen


CUSTOM_NAME = _("%(account)s (custom)")

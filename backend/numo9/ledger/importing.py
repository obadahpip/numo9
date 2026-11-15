"""Chart-of-accounts import and export (C-01-T13), on the B-03 import framework.

**Export** — ``export_csv(org)`` / ``export_xlsx(org)``: every account (active and archived) in
code order, one column per field of the ``ledger.account`` import entity, headers = the field
labels, values as people read them (sub-type "Current asset", "Yes"/"No"). The file is the import
template: exporting and importing it again changes nothing (round trip = 0 changes).

**Import** — ``import_accounts(sheet, columns, apply=False)``: the rows of a parsed sheet
(``numo9.imports.parser``) with a column mapping (``numo9.imports.mapping``):

- rows match accounts by **code** (case-insensitive), the chart's stable key; never by name, so a
  renamed account is updated in place. A code that doesn't exist creates the account (name and
  sub-type then required). Renumbering is a separate action (C-01-T07), not an import;
- **non-destructive**: a blank cell leaves the field unchanged; ``__CLEAR__`` empties an optional
  field (French name, parent, GIFI, tax default, description); required fields can't be cleared;
- sub-type, type, system role and status accept the stored key or the English/French label; type,
  system role and status are **checked, not changed** (the type follows the sub-type; system roles
  are fixed by the platform; archiving has its own rules — C-01-T08);
- parents may be new rows of the same file: rows are processed parents first; a parent cycle in
  the file is an error on each row of the cycle; duplicate codes in the file are errors on every
  copy;
- each row is saved through ``Account.save()`` — every chart rule applies (code format, GIFI list
  and section, tree depth and types, system-role guard, unique code) and a refused row reports the
  rule's message; other rows go on (a savepoint per row);
- the whole import is one audit batch ("Chart of accounts import: <file>") attributed to the person
  importing;
- ``apply=False`` is the **dry run**: the same work inside a transaction that is rolled back, so
  the report (create / update with changes / unchanged / error per row) is exactly what applying
  will do, and the dry run writes no account and no audit event.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from functools import cache
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

from numo9.audit.batch import audit_batch
from numo9.imports.fields import ImportEntity, ImportField
from numo9.imports.mapping import check_mapping, normalise
from numo9.imports.parser import Sheet
from numo9.imports.report import CLEAR_TOKEN, Action, ImportReport, RowResult
from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation

from .models import (
    SUBTYPE_TYPE,
    Account,
    AccountStatus,
    AccountSubtype,
    AccountType,
    LedgerError,
    SystemRole,
)
from .renumber import acting_as

ENTITY_KEY = "ledger.account"

ACCOUNT = ImportEntity(
    ENTITY_KEY,
    _lazy("Chart of accounts"),
    (
        ImportField(
            "code",
            _lazy("Code"),
            ("account code", "account number", "account no", "number", "gl code"),
            ("code de compte", "numéro de compte", "no de compte", "numéro"),
            required=True,
            match_key=True,
        ),
        ImportField(
            "name",
            _lazy("Name"),
            ("account name", "account", "name (english)", "english name"),
            ("nom du compte", "nom (anglais)", "nom anglais"),
        ),
        ImportField(
            "name_fr",
            _lazy("Name (French)"),
            ("french name",),
            ("nom", "nom (français)", "nom français", "intitulé"),
        ),
        ImportField("type", _lazy("Type"), ("account type", "class"), ("type de compte", "classe")),
        ImportField(
            "subtype",
            _lazy("Sub-type"),
            ("subtype", "detail type", "account subtype"),
            ("sous-type", "sous type", "catégorie"),
        ),
        ImportField(
            "parent",
            _lazy("Parent code"),
            ("parent", "parent account", "parent account code"),
            ("compte parent", "code parent", "code du compte parent"),
        ),
        ImportField(
            "system_role", _lazy("System role"), ("role", "system account"), ("rôle système",)
        ),
        ImportField("is_bank", _lazy("Bank account"), ("bank",), ("compte bancaire", "banque")),
        ImportField(
            "gifi",
            _lazy("GIFI code"),
            ("gifi", "gifi mapping", "cra gifi"),
            ("code igrf", "igrf"),
        ),
        ImportField(
            "require_contact",
            _lazy("Require a contact"),
            ("contact required",),
            ("contact obligatoire",),
        ),
        ImportField(
            "require_tracking",
            _lazy("Require a tracking category"),
            ("tracking required",),
            ("suivi obligatoire",),
        ),
        ImportField(
            "require_attachment",
            _lazy("Require an attachment"),
            ("attachment required",),
            ("pièce jointe obligatoire",),
        ),
        ImportField(
            "default_tax_key",
            _lazy("Default tax code"),
            ("tax code", "default tax", "tax rate"),
            ("code de taxe", "taxe par défaut", "code de taxe par défaut"),
        ),
        ImportField("description", _lazy("Description"), ("notes",), ("description",)),
        ImportField("status", _lazy("Status"), ("state",), ("statut", "état")),
    ),
)

#: Optional fields ``__CLEAR__`` may empty.
CLEARABLE = frozenset({"name_fr", "parent", "gifi", "default_tax_key", "description"})
#: Columns checked against the account but never changed by an import.
CHECK_ONLY = frozenset({"type", "system_role", "status"})
BOOLEAN_FIELDS = ("is_bank", "require_contact", "require_tracking", "require_attachment")
TRUE_WORDS = frozenset({"yes", "y", "true", "1", "x", "oui", "o", "vrai"})
FALSE_WORDS = frozenset({"no", "n", "false", "0", "non", "faux"})
LANGUAGES = ("en-ca", "fr-ca")


# ---- values as text ----------------------------------------------------------------------------


def _choice_lookup(choices: type[Any]) -> dict[str, str]:
    """Normalised key and English/French labels → stored value."""
    lookup: dict[str, str] = {}
    for value, label in choices.choices:
        lookup[normalise(value)] = value
        for language in LANGUAGES:
            with translation.override(language):
                lookup[normalise(str(label))] = value
    return lookup


def _yes_no(value: bool) -> str:
    return str(_("Yes")) if value else str(_("No"))


def account_values(account: Account) -> dict[str, str]:
    """An account as the text of its export row (also the "before/after" of a change)."""
    names = account.name_i18n or {}
    parent = account.parent
    return {
        "code": account.code,
        "name": str(names.get("en-ca", "")),
        "name_fr": str(names.get("fr-ca", "")),
        "type": str(AccountType(account.type).label),
        "subtype": str(AccountSubtype(account.subtype).label),
        "parent": parent.code if parent is not None else "",
        "system_role": str(SystemRole(account.system_role).label) if account.system_role else "",
        "is_bank": _yes_no(account.is_bank),
        "gifi": account.gifi_id or "",
        "require_contact": _yes_no(account.require_contact),
        "require_tracking": _yes_no(account.require_tracking),
        "require_attachment": _yes_no(account.require_attachment),
        "default_tax_key": account.default_tax_key,
        "description": account.description,
        "status": str(AccountStatus(account.status).label),
    }


# ---- export ------------------------------------------------------------------------------------


def _organisation_accounts(organisation: Organisation) -> list[Account]:
    active = current_org()
    if active is None or active.pk != organisation.pk:
        raise ValueError("Export the chart only for the active organisation.")
    return list(
        Account.objects.filter(deleted_at__isnull=True)
        .select_related("parent")
        .order_by("code", "pk")
    )


def export_table(organisation: Organisation) -> tuple[list[str], list[list[str]]]:
    """Headers (the field labels, in the active language) and one row per account."""
    headers = [str(item.label) for item in ACCOUNT.fields]
    rows = []
    for account in _organisation_accounts(organisation):
        values = account_values(account)
        rows.append([values[key] for key in ACCOUNT.field_keys])
    return headers, rows


def export_csv(organisation: Organisation) -> bytes:
    """UTF-8 with a byte-order mark, so Excel opens accents correctly."""
    headers, rows = export_table(organisation)
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(headers)
    writer.writerows(rows)
    return ("﻿" + buffer.getvalue()).encode("utf-8")


def export_xlsx(organisation: Organisation) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    headers, rows = export_table(organisation)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = str(_("Chart of accounts"))[:31]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in rows:
        # Text cells: a code like 0100 or a GIFI code keeps its digits as typed.
        sheet.append(row)
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            cell.number_format = "@"
    sheet.freeze_panes = "A2"
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


# ---- import ------------------------------------------------------------------------------------


class _DryRun(Exception):
    """Raised at the end of a dry run to roll everything back."""


class _RowFailed(Exception):
    pass


def _messages(error: ValidationError) -> str:
    return " ".join(str(message) for message in error.messages)


def _error_code(error: ValidationError) -> str:
    code = getattr(error, "code", None)
    if code:
        return str(code)
    for item in getattr(error, "error_list", []):
        if item.code:
            return str(item.code)
    return "ledger.import.invalid"


def _cells(sheet: Sheet, columns: Mapping[str, str]) -> Iterator[tuple[int, dict[str, str]]]:
    index = {header: position for position, header in enumerate(sheet.headers)}
    mapped = [
        (index[header], field) for header, field in columns.items() if field and header in index
    ]
    for row in sheet.rows:
        yield row.number, {field: row.cells[position] for position, field in mapped}


def _order_parents_first(
    rows: list[tuple[int, dict[str, str]]], results: dict[int, RowResult]
) -> list[tuple[int, dict[str, str]]]:
    """Rows sorted so a row comes after the row of its parent code (when that is in the file)."""
    by_code = {cells["code"].casefold(): number for number, cells in rows if cells.get("code")}
    cells_of = dict(rows)
    ordered: list[int] = []
    state: dict[int, str] = {}  # "visiting" / "done"

    def visit(number: int, path: list[int]) -> None:
        if state.get(number) == "done":
            return
        if state.get(number) == "visiting":
            cycle = path[path.index(number) :]
            for member in cycle:
                results[member].fail(
                    "parent",
                    "ledger.import.parent_cycle",
                    _("The parent codes in the file form a loop (rows %(rows)s).")
                    % {"rows": ", ".join(str(n) for n in sorted(cycle))},
                )
            return
        state[number] = "visiting"
        parent = cells_of[number].get("parent", "").strip()
        if parent and parent != CLEAR_TOKEN and parent.casefold() in by_code:
            visit(by_code[parent.casefold()], [*path, number])
        state[number] = "done"
        ordered.append(number)

    for number, _cells_row in rows:
        visit(number, [])
    return [(number, cells_of[number]) for number in ordered]


@contextmanager
def _savepoint() -> Iterator[None]:
    try:
        with transaction.atomic():
            yield
    except _RowFailed:
        pass


def import_accounts(
    sheet: Sheet,
    columns: Mapping[str, str],
    *,
    apply: bool = False,
    actor: Any = None,
    filename: str = "",
) -> ImportReport:
    """Dry-run (default) or apply an accounts sheet; see the module docstring."""
    organisation = current_org()
    if organisation is None:
        raise ValueError("Import accounts only with an active organisation.")
    check_mapping(ENTITY_KEY, columns)
    report = ImportReport(ENTITY_KEY, applied=apply)
    rows = list(_cells(sheet, columns))
    results = {number: RowResult(number, cells.get("code", "")) for number, cells in rows}
    report.rows = [results[number] for number, _ in rows]

    _flag_duplicate_codes(rows, results)
    ordered = _order_parents_first(rows, results)
    label = _("Chart of accounts import: %(file)s") % {"file": filename or sheet.name}
    try:
        with (
            acting_as(actor),
            transaction.atomic(),
            audit_batch(
                label, organisation=organisation, meta={"file": filename, "rows": len(rows)}
            ),
        ):
            for number, cells in ordered:
                result = results[number]
                if result.action == Action.ERROR:
                    continue
                with _savepoint():
                    _import_row(organisation, cells, result, actor)
            if not apply:
                raise _DryRun
    except _DryRun:
        pass
    return report


def _flag_duplicate_codes(
    rows: list[tuple[int, dict[str, str]]], results: dict[int, RowResult]
) -> None:
    seen: dict[str, list[int]] = {}
    for number, cells in rows:
        code = cells.get("code", "").strip()
        if code:
            seen.setdefault(code.casefold(), []).append(number)
    for numbers in seen.values():
        if len(numbers) > 1:
            for number in numbers:
                results[number].fail(
                    "code",
                    "ledger.import.duplicate_code",
                    _("Code %(code)s appears more than once in the file (rows %(rows)s).")
                    % {"code": results[number].key, "rows": ", ".join(str(n) for n in numbers)},
                )


@cache
def _lookups() -> dict[str, dict[str, str]]:
    return {
        "subtype": _choice_lookup(AccountSubtype),
        "type": _choice_lookup(AccountType),
        "system_role": _choice_lookup(SystemRole),
        "status": _choice_lookup(AccountStatus),
    }


def _import_row(
    organisation: Organisation, cells: dict[str, str], result: RowResult, actor: Any
) -> None:
    code = cells.get("code", "").strip()
    if not code or code == CLEAR_TOKEN:
        result.fail("code", "ledger.import.code_required", _("Every row needs an account code."))
        return
    existing: Account | None = (
        Account.objects.filter(code__iexact=code, deleted_at__isnull=True)
        .select_related("parent")
        .first()
    )
    account = existing or Account(organisation=organisation, code=code)
    before = account_values(account) if existing else {}
    if existing is None:
        account.created_by = actor if getattr(actor, "is_authenticated", False) else None
    _apply_cells(account, cells, result, new=existing is None)
    if result.action == Action.ERROR:
        return
    try:
        account.clean()  # every chart rule, and the values the save will store
    except ValidationError as error:
        result.fail("", _error_code(error), _messages(error))
        return
    after = account_values(account)
    if existing is not None:
        changes = {key: [before[key], after[key]] for key in after if before[key] != after[key]}
        if not changes:
            result.action, result.label = Action.UNCHANGED, str(existing)
            return
    else:
        changes = {key: ["", value] for key, value in after.items() if value}
    try:
        with transaction.atomic():
            account.save()
    except ValidationError as error:
        result.fail("", _error_code(error), _messages(error))
        raise _RowFailed from error
    result.action = Action.UPDATE if existing else Action.CREATE
    result.changes = changes
    result.label = str(account)


def _text(cells: dict[str, str], key: str) -> str | None:
    """None = leave unchanged (blank cell or column not mapped); "" = clear; else the value."""
    value = cells.get(key, "").strip()
    if not value:
        return None
    if value == CLEAR_TOKEN:
        return ""
    return value


def _apply_cells(account: Account, cells: dict[str, str], result: RowResult, *, new: bool) -> None:
    for key in ("name", "subtype"):
        if _text(cells, key) == "":
            result.fail(
                key,
                "ledger.import.required_clear",
                _("%(field)s can't be cleared.") % {"field": ACCOUNT.field(key).label},
            )
    if new:
        for key in ("name", "subtype"):
            if not _text(cells, key):
                result.fail(
                    key,
                    "ledger.import.required_new",
                    _("A new account needs a %(field)s.")
                    % {"field": str(ACCOUNT.field(key).label).lower()},
                )
    if result.action == Action.ERROR:
        return

    name = _text(cells, "name")
    if name:
        account.set_name(name)
    name_fr = _text(cells, "name_fr")
    if name_fr is not None:
        names = dict(account.name_i18n or {})
        if name_fr:
            names["fr-ca"] = name_fr
        else:
            names.pop("fr-ca", None)
        account.name_i18n = names

    subtype = _text(cells, "subtype")
    if subtype:
        value = _lookups()["subtype"].get(normalise(subtype))
        if value is None:
            result.fail(
                "subtype",
                "ledger.import.subtype_unknown",
                _("“%(value)s” isn't an account sub-type.") % {"value": subtype},
            )
        else:
            account.subtype = value
            account.type = SUBTYPE_TYPE[value]
            if value == AccountSubtype.BANK:
                account.is_bank = True

    _check_only(account, cells, result, new=new)
    _apply_parent(account, cells, result)

    for key in BOOLEAN_FIELDS:
        raw = _text(cells, key)
        if raw is None:
            continue
        word = normalise(raw)
        if word in TRUE_WORDS:
            setattr(account, key, True)
        elif word in FALSE_WORDS or raw == "":
            if raw == "":
                result.fail(
                    key,
                    "ledger.import.boolean_clear",
                    _("%(field)s is Yes or No: it can't be cleared.")
                    % {"field": ACCOUNT.field(key).label},
                )
            else:
                setattr(account, key, False)
        else:
            result.fail(
                key,
                "ledger.import.boolean_invalid",
                _("%(field)s is Yes or No, not “%(value)s”.")
                % {"field": ACCOUNT.field(key).label, "value": raw},
            )

    gifi = _text(cells, "gifi")
    if gifi is not None:
        account.gifi_id = gifi or None
    tax_key = _text(cells, "default_tax_key")
    if tax_key is not None:
        account.default_tax_key = tax_key
    description = _text(cells, "description")
    if description is not None and description != (account.description or "").strip():
        account.description = description


def _check_only(account: Account, cells: dict[str, str], result: RowResult, *, new: bool) -> None:
    """Type, system role and status are compared with the account, never changed."""
    current = {
        "type": account.type,
        "system_role": account.system_role,
        "status": AccountStatus.ACTIVE if new else account.status,
    }
    for key, stored in current.items():
        raw = _text(cells, key)
        if raw is None:
            continue
        value = _lookups()[key].get(normalise(raw)) if raw else ""
        label = str(ACCOUNT.field(key).label).lower()
        if raw and value is None:
            result.fail(
                key,
                f"ledger.import.{key}_unknown",
                _("“%(value)s” isn't a valid %(field)s.") % {"value": raw, "field": label},
            )
        elif value != stored:
            result.fail(key, f"ledger.import.{key}_locked", _locked_message(key, account))


def _locked_message(key: str, account: Account) -> str:
    if key == "type":
        return _("The type follows the sub-type (%(type)s): change the sub-type instead.") % {
            "type": AccountType(account.type).label if account.type else "—"
        }
    if key == "system_role":
        return _("System roles are set by Numo9 and can't be changed by an import.")
    return _("Archive or restore accounts in the chart of accounts, not by an import.")


def _apply_parent(account: Account, cells: dict[str, str], result: RowResult) -> None:
    raw = _text(cells, "parent")
    if raw is None:
        return
    if raw == "":
        account.parent = None
        return
    if raw.casefold() == account.code.casefold():
        result.fail(
            "parent",
            "ledger.account.parent_cycle",
            _("An account can't be placed under itself or one of its own sub-accounts."),
        )
        return
    parent = Account.objects.filter(code__iexact=raw, deleted_at__isnull=True).first()
    if parent is None:
        result.fail(
            "parent",
            "ledger.import.parent_missing",
            _("No account has the code %(code)s (parent code).") % {"code": raw},
        )
        return
    account.parent = parent


def import_labels() -> dict[str, str]:
    """Field key → column label (for the errors CSV)."""
    return {item.key: str(item.label) for item in ACCOUNT.fields}


def run_import(
    data: bytes,
    filename: str,
    columns: Mapping[str, str] | None = None,
    *,
    apply: bool = False,
    actor: Any = None,
) -> ImportReport:
    """Parse ``data``, map its columns (given, saved for these headers, or auto-suggested) and
    dry-run or apply the first sheet — the whole B-03 pipeline for accounts in one call."""
    from numo9.imports.mapping import as_columns, resolve
    from numo9.imports.parser import parse_file

    sheet = parse_file(data, filename).sheet
    if columns is None:
        columns = as_columns(resolve(ENTITY_KEY, sheet.headers))
    return import_accounts(sheet, columns, apply=apply, actor=actor, filename=filename)


__all__ = [
    "ACCOUNT",
    "ENTITY_KEY",
    "LedgerError",
    "export_csv",
    "export_table",
    "export_xlsx",
    "import_accounts",
    "run_import",
]

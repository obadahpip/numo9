"""Trial balance import for the conversion (C-05-T08): a CSV or Excel trial balance from the old
system becomes the conversion's opening lines.

1. ``suggest_mapping(data, filename)`` — the file's columns, a few sample values, and the
   columns guessed for **account** (code or name), **debit** and **credit** — or a single signed
   **balance** column (positive = debit, negative or in brackets = credit).
2. ``import_tb(session, data, filename, mapping, dry_run=True)`` — reads every row and reports,
   **per row**, the account found, the amounts and every problem (``errors``: ``field``, ``code``,
   ``message``). A dry run writes nothing. A real run writes only when no row has a problem —
   all rows or none — replacing the session's lines for those accounts, in one transaction.

Row rules: an account is matched by code, then by name (case and accents ignored); unknown
accounts, accounts with sub-accounts, the same account twice, a row with both a debit and a
credit, or an amount that isn't a number are problems; a row with no account and no amount, the
file's own totals row (no account, a cell starting with "Total") and a zero balance are
skipped. Totals (debits, credits, difference) are reported so the import shows whether the
trial balance balances — it may not, and the difference meter (C-05-T04) says so later; nothing
is plugged.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from numo9.imports.parser import Sheet, parse_file
from numo9.tenancy.context import org_context

from .models import ConversionSession

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
FIELDS = ("account", "debit", "credit", "balance")
GUESSES: dict[str, tuple[str, ...]] = {
    "account": ("account code", "code", "account number", "acct", "gl code", "account", "compte"),
    "debit": ("debit", "debits", "dr", "débit"),
    "credit": ("credit", "credits", "cr", "crédit"),
    "balance": ("balance", "closing balance", "amount", "solde", "montant"),
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text).strip().lower()


def suggest_mapping(data: bytes, filename: str) -> dict[str, Any]:
    sheet = parse_file(data, filename).sheet
    folded = {_fold(h): h for h in sheet.headers}
    mapping: dict[str, str] = {}
    for name, guesses in GUESSES.items():
        for guess in guesses:
            if guess in folded and folded[guess] not in mapping.values():
                mapping[name] = folded[guess]
                break
    if "debit" in mapping or "credit" in mapping:
        mapping.pop("balance", None)
    return {
        "columns": [{"name": h, "samples": sheet.samples(h)} for h in sheet.headers],
        "mapping": mapping,
        "rows": len(sheet.rows),
    }


def _mapping_error(message: str, **params: Any) -> ValidationError:
    return ValidationError(
        {"mapping": ValidationError(message, code="conversion.import.mapping", params=params)}
    )


def check_mapping(sheet: Sheet, mapping: dict[str, str]) -> dict[str, str]:
    """The mapping kept to known fields, checked against the file's columns."""
    used = {k: v for k, v in (mapping or {}).items() if k in FIELDS and v}
    if "account" not in used:
        raise _mapping_error(_("Choose the column with the account code or name."))
    signed = "balance" in used
    sides = "debit" in used or "credit" in used
    if signed == sides:
        raise _mapping_error(
            _("Choose Debit and Credit columns, or one Balance column — not both.")
        )
    for column in used.values():
        if column not in sheet.headers:
            raise _mapping_error(_("The file has no column “%(column)s”."), column=column)
    return used


def parse_amount(text: str) -> Decimal | None:
    """An amount as trial balances write it: ``1,234.56``, ``$1,234.56``, ``(123.45)`` and
    ``-123.45`` (negative), ``123.45 CR`` (credit), ``123.45 DR``; empty → 0; anything else (or
    more than two decimals) → ``None``."""
    raw = (text or "").strip().replace("$", "").replace(" ", "").replace(" ", "")
    if not raw:
        return ZERO
    negative = False
    if raw.startswith("(") and raw.endswith(")"):
        negative, raw = True, raw[1:-1]
    upper = raw.upper()
    if upper.endswith("CR"):
        negative, raw = True, raw[:-2]
    elif upper.endswith("DR"):
        raw = raw[:-2]
    if raw.startswith("-"):
        negative, raw = not negative, raw[1:]
    if not re.fullmatch(r"\d{1,3}(,\d{3})*(\.\d+)?|\d+(\.\d+)?", raw):
        return None
    try:
        value = Decimal(raw.replace(",", ""))
    except InvalidOperation:
        return None
    if value != value.quantize(CENT):
        return None
    return -value if negative else value


@dataclass
class RowResult:
    row: int
    account: dict[str, str] | None = None
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    status: str = "ok"  # ok · error · skipped
    errors: list[dict[str, str]] = field(default_factory=list)
    account_obj: Any = None

    def problem(self, field_name: str, code: str, message: str) -> None:
        self.status = "error"
        self.errors.append({"field": field_name, "code": code, "message": message})

    def as_dict(self) -> dict[str, Any]:
        return {
            "row": self.row,
            "account": self.account,
            "debit": f"{self.debit:.2f}",
            "credit": f"{self.credit:.2f}",
            "status": self.status,
            "errors": self.errors,
        }


def _accounts(organisation: Any) -> tuple[dict[str, Any], dict[str, list[Any]], set[int]]:
    from numo9.ledger.models import Account

    by_code: dict[str, Any] = {}
    by_name: dict[str, list[Any]] = {}
    accounts = list(Account.objects.filter(organisation=organisation))
    parents = {a.parent_id for a in accounts if a.parent_id}
    for account in accounts:
        by_code[account.code.upper()] = account
        for name in (account.name_i18n or {}).values():
            if name:
                by_name.setdefault(_fold(str(name)), []).append(account)
    return by_code, by_name, parents


def import_tb(
    session: ConversionSession,
    data: bytes,
    filename: str,
    mapping: dict[str, str],
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Read (and, when every row is fine and ``dry_run`` is false, write) the trial balance."""
    from .services import set_line

    if session.is_finalised:
        raise ValidationError(
            _("The conversion is finalised: correct it with a correcting opening journal."),
            code="conversion.session.finalised",
        )
    sheet = parse_file(data, filename).sheet
    used = check_mapping(sheet, mapping)
    index = {name: sheet.headers.index(column) for name, column in used.items()}
    results: list[RowResult] = []
    seen: dict[int, int] = {}
    with org_context(session.organisation):
        by_code, by_name, parents = _accounts(session.organisation)
        for row in sheet.rows:
            cell = {name: row.cells[i].strip() for name, i in index.items()}
            result = RowResult(row=row.number)
            amounts: dict[str, Decimal | None] = {
                name: parse_amount(cell[name])
                for name in ("debit", "credit", "balance")
                if name in cell
            }
            totals_row = not cell["account"] and any(
                _fold(c).startswith(("total", "totaux")) for c in row.cells
            )
            if totals_row or (
                not cell["account"] and all(v in (ZERO, None) for v in amounts.values())
            ):
                result.status = "skipped"  # a blank row, or the file's own totals row
                results.append(result)
                continue
            for name, value in amounts.items():
                if value is None:
                    result.problem(
                        name,
                        "conversion.import.amount",
                        _("“%(value)s” isn't an amount.") % {"value": cell[name]},
                    )
            if "balance" in amounts and amounts["balance"] is not None:
                balance = amounts["balance"]
                result.debit, result.credit = (balance, ZERO) if balance >= 0 else (ZERO, -balance)
            elif result.status != "error":
                debit, credit = amounts.get("debit") or ZERO, amounts.get("credit") or ZERO
                if debit < 0 and credit == 0:  # a negative debit is a credit balance
                    debit, credit = ZERO, -debit
                if credit < 0 and debit == 0:
                    debit, credit = -credit, ZERO
                if debit > 0 and credit > 0:
                    result.problem(
                        "debit",
                        "conversion.import.both_sides",
                        _("The row has a debit and a credit: keep one."),
                    )
                result.debit, result.credit = debit, credit
            account = by_code.get(cell["account"].upper()) if cell["account"] else None
            if account is None and cell["account"]:
                named = by_name.get(_fold(cell["account"]), [])
                if len(named) == 1:
                    account = named[0]
                elif len(named) > 1:
                    result.problem(
                        "account",
                        "conversion.import.account_ambiguous",
                        _("More than one account is called “%(name)s”: use its code.")
                        % {"name": cell["account"]},
                    )
            if account is None:
                if not any(e["field"] == "account" for e in result.errors):
                    result.problem(
                        "account",
                        "conversion.import.account_unknown",
                        _("There's no account “%(account)s” in the chart of accounts.")
                        % {"account": cell["account"] or "—"},
                    )
            else:
                result.account_obj = account
                result.account = {
                    "id": str(account.public_id),
                    "code": account.code,
                    "name": account.name_in("en-ca"),
                }
                if account.pk in parents:
                    result.problem(
                        "account",
                        "conversion.import.account_not_postable",
                        _("%(code)s has sub-accounts: give the balances of its sub-accounts.")
                        % {"code": account.code},
                    )
                elif account.pk in seen:
                    result.problem(
                        "account",
                        "conversion.import.duplicate",
                        _("%(code)s is already on row %(row)d.")
                        % {"code": account.code, "row": seen[account.pk]},
                    )
                else:
                    seen[account.pk] = row.number
            if result.status == "ok" and result.debit == 0 and result.credit == 0:
                result.status = "skipped"  # a zero balance: nothing to open
            results.append(result)

    ok = [r for r in results if r.status == "ok"]
    errors = [r for r in results if r.status == "error"]
    debits = sum((r.debit for r in ok), ZERO)
    credits = sum((r.credit for r in ok), ZERO)
    written = 0
    if not dry_run and not errors:
        with transaction.atomic():
            for result in ok:
                set_line(session, result.account_obj, debit=result.debit, credit=result.credit)
                written += 1
    return {
        "dry_run": dry_run,
        "mapping": used,
        "rows": [r.as_dict() for r in results],
        "counts": {
            "ok": len(ok),
            "errors": len(errors),
            "skipped": sum(1 for r in results if r.status == "skipped"),
        },
        "totals": {
            "debit": f"{debits:.2f}",
            "credit": f"{credits:.2f}",
            "difference": f"{debits - credits:.2f}",
        },
        "written": written,
        "refused": bool(errors) and not dry_run,
    }

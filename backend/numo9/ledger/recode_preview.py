"""Find & recode — the preview (C-07-T04): what the recode would do, line by line, before it runs.

``preview(organisation, criteria, changes, user)`` → ``Preview``:

- ``lines`` — every found line that would change: the entry (number, date), the line, its book
  and **amounts — never changed** — and its coding ``before`` and ``after``
  (``{account, tax_code, tracking, contact}``, public ids; ``changed`` names what moves);
  and its ``fingerprint`` — the line as seen now: executing the chosen lines compares it again
  and reports a line changed meanwhile as a conflict (C-07-T06);
- ``excluded`` — the found lines left out, each with its reason (C-07-T03);
- ``unchanged`` — found lines already coded that way (nothing to do);
- ``totals_before`` / ``totals_after`` — debits and credits of the changed lines per book: the
  same, always (``totals_unchanged``; a difference raises ``RecodeTotalsChanged`` — the recode
  would no longer be a recode);
- ``accounts`` — the net movement per account before and after (what leaves one account arrives
  in another);
- ``tax_impact`` — for every line whose tax code changes, the tax the line's amount carries
  under the old and the new code on the line's date, per component, and the difference
  (``tax_delta``): a tax recode **recalculates the tax split** and asks for confirmation
  (``needs_confirmation``). Rates come from the tax app (``register_tax_rates``).

``changes`` — any of ``account`` (an active account's public id), ``tax_code`` (a code key, or
``""`` to clear), ``tracking`` (``{category: option}``, an option of ``None`` removes the
category), ``contact`` (a contact's public id, or ``None`` to clear). Anything else is refused
(``ValidationError``, code ``ledger.recode.changes_invalid``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from .models import Account, Book
from .recode_exclusions import Excluded, split
from .recode_query import find_lines

ZERO = Decimal("0.00")
FIELDS = ("account", "tax_code", "tracking", "contact")
#: ``rates(organisation, code, day, base) -> {component key: tax amount}`` (the tax app).
TaxRates = Callable[[Any, str, dt.date, Decimal], dict[str, Decimal]]
_rates: list[TaxRates] = []


def register_tax_rates(rates: TaxRates) -> None:
    if rates not in _rates:
        _rates.append(rates)


class RecodeTotalsChanged(AssertionError):
    """The recode would change debits or credits: it would no longer be a recode."""


def _invalid(message: str, name: str) -> ValidationError:
    return ValidationError(
        {
            "changes": ValidationError(
                message, code="ledger.recode.changes_invalid", params={"field": name}
            )
        }
    )


@dataclass(frozen=True)
class Changes:
    """The new coding, resolved: ``values`` for each field set."""

    values: dict[str, Any]
    account: Account | None = None
    contact: Any = None

    def apply(self, before: dict[str, Any]) -> dict[str, Any]:
        after = dict(before)
        for name, value in self.values.items():
            if name == "tracking":
                merged = dict(before.get("tracking") or {})
                for category, option in value.items():
                    if option is None:
                        merged.pop(category, None)
                    else:
                        merged[category] = option
                after["tracking"] = merged
            else:
                after[name] = value
        return after


def clean_changes(organisation: Any, changes: Any) -> Changes:
    from numo9.contacts.models import Contact

    if not isinstance(changes, dict) or not changes or set(changes) - set(FIELDS):
        raise _invalid(_("Choose the new account, tax code, tracking or contact."), "changes")
    values: dict[str, Any] = {}
    account = contact = None
    if "account" in changes:
        try:
            account = Account.objects.active().get(
                organisation=organisation, public_id=uuid.UUID(str(changes["account"]))
            )
        except (ValueError, Account.DoesNotExist):
            raise _invalid(
                _("The new account isn't an active account of this organisation."), "account"
            ) from None
        values["account"] = str(account.public_id)
    if "tax_code" in changes:
        code = changes["tax_code"] or ""
        if not isinstance(code, str):
            raise _invalid(_("The new tax code isn't a tax code."), "tax_code")
        values["tax_code"] = code
    if "tracking" in changes:
        tracking = changes["tracking"]
        if (
            not isinstance(tracking, dict)
            or not tracking
            or not all(
                isinstance(k, str) and (v is None or isinstance(v, str))
                for k, v in tracking.items()
            )
        ):
            raise _invalid(_("Tracking is a category and its option."), "tracking")
        values["tracking"] = dict(tracking)
    if "contact" in changes:
        if changes["contact"] in (None, ""):
            values["contact"] = None
        else:
            try:
                contact = Contact.objects.get(
                    organisation=organisation,
                    public_id=uuid.UUID(str(changes["contact"])),
                    deleted_at__isnull=True,
                )
            except (ValueError, Contact.DoesNotExist):
                raise _invalid(
                    _("The new contact isn't a contact of this organisation."), "contact"
                ) from None
            values["contact"] = str(contact.public_id)
    return Changes(values, account, contact)


def coding(line: Any) -> dict[str, Any]:
    return {
        "account": str(line.account.public_id),
        "tax_code": line.tax_code or "",
        "tracking": dict(line.tracking or {}),
        "contact": str(line.contact.public_id) if line.contact_id else None,
    }


def fingerprint(line: Any) -> str:
    """The line as the preview saw it: its entry's state and the line's coding and amounts. Any
    change between the preview and the run (another recode, a reversal, a void) changes it."""
    entry = line.entry
    payload = [
        entry.pk,
        entry.status,
        entry.reversal_of_id,
        line.line_no,
        line.account_id,
        f"{line.debit:.2f}",
        f"{line.credit:.2f}",
        line.book,
        line.tax_code or "",
        line.contact_id,
        sorted((line.tracking or {}).items()),
    ]
    return hashlib.sha256(json.dumps(payload, default=str).encode()).hexdigest()


@dataclass(frozen=True)
class PreviewLine:
    line: Any
    before: dict[str, Any]
    after: dict[str, Any]

    @property
    def changed(self) -> list[str]:
        return [name for name in FIELDS if self.before.get(name) != self.after.get(name)]

    def as_dict(self) -> dict[str, Any]:
        entry = self.line.entry
        return {
            "entry": str(entry.public_id),
            "number": entry.number,
            "date": entry.date.isoformat(),
            "line_no": self.line.line_no,
            "book": self.line.book,
            "debit": f"{self.line.debit:.2f}",
            "credit": f"{self.line.credit:.2f}",
            "before": self.before,
            "after": self.after,
            "changed": self.changed,
            "fingerprint": fingerprint(self.line),
        }


@dataclass
class Preview:
    lines: list[PreviewLine]
    excluded: list[Excluded]
    unchanged: int
    totals_before: dict[str, dict[str, Decimal]]
    totals_after: dict[str, dict[str, Decimal]]
    accounts: dict[str, dict[str, Decimal]]
    tax_impact: list[dict[str, Any]] = field(default_factory=list)

    @property
    def totals_unchanged(self) -> bool:
        return self.totals_before == self.totals_after

    @property
    def tax_delta(self) -> Decimal:
        return sum((Decimal(row["delta"]) for row in self.tax_impact), ZERO)

    @property
    def needs_confirmation(self) -> bool:
        return any(Decimal(row["delta"]) != 0 for row in self.tax_impact)

    def summary(self) -> dict[str, Any]:
        return {
            "lines": len(self.lines),
            "entries": len({p.line.entry_id for p in self.lines}),
            "accounts": len({p.before["account"] for p in self.lines}),
            "excluded": len(self.excluded),
            "unchanged": self.unchanged,
            "totals_unchanged": self.totals_unchanged,
            "tax_delta": f"{self.tax_delta:.2f}",
            "needs_confirmation": self.needs_confirmation,
        }


def _totals(rows: list[PreviewLine]) -> dict[str, dict[str, Decimal]]:
    """Debits and credits of the lines per book (``both`` lines count in each)."""
    out: dict[str, dict[str, Decimal]] = {}
    for book in (Book.ACCOUNTING, Book.TAX):
        mine = [r.line for r in rows if r.line.book in (book, Book.BOTH)]
        out[book] = {
            "debit": sum((line.debit for line in mine), ZERO),
            "credit": sum((line.credit for line in mine), ZERO),
        }
    return out


def _after_totals(rows: list[PreviewLine]) -> dict[str, dict[str, Decimal]]:
    """The same totals as the re-post would carry them: the amounts copied, the coding new."""
    reposted = [PreviewLine(_reposted(r), r.after, r.after) for r in rows]
    return _totals(reposted)


@dataclass(frozen=True)
class _Reposted:
    entry: Any
    line_no: int
    book: str
    debit: Decimal
    credit: Decimal


def _reposted(row: PreviewLine) -> Any:
    line = row.line
    return _Reposted(line.entry, line.line_no, line.book, line.debit, line.credit)


def _accounts(rows: list[PreviewLine]) -> dict[str, dict[str, Decimal]]:
    moves: dict[str, dict[str, Decimal]] = defaultdict(lambda: {"before": ZERO, "after": ZERO})
    for row in rows:
        net = row.line.debit - row.line.credit
        moves[row.before["account"]]["before"] += net
        moves[row.after["account"]]["after"] += net
    return dict(moves)


def _tax(organisation: Any, row: PreviewLine) -> dict[str, Any] | None:
    old, new = row.before["tax_code"], row.after["tax_code"]
    if old == new or not _rates:
        return None
    base = row.line.debit or row.line.credit
    day = row.line.entry.date
    rates = _rates[0]
    before = rates(organisation, old, day, base) if old else {}
    after = rates(organisation, new, day, base) if new else {}
    delta = sum(after.values(), ZERO) - sum(before.values(), ZERO)
    return {
        "entry": str(row.line.entry.public_id),
        "number": row.line.entry.number,
        "line_no": row.line.line_no,
        "base": f"{base:.2f}",
        "from": old,
        "to": new,
        "before": {k: f"{v:.2f}" for k, v in before.items()},
        "after": {k: f"{v:.2f}" for k, v in after.items()},
        "delta": f"{delta:.2f}",
    }


def build(
    organisation: Any, lines: list[Any], changes: Changes, excluded: list[Excluded]
) -> Preview:
    rows, unchanged = [], 0
    for line in lines:
        before = coding(line)
        row = PreviewLine(line, before, changes.apply(before))
        if row.changed:
            rows.append(row)
        else:
            unchanged += 1
    built = Preview(
        lines=rows,
        excluded=excluded,
        unchanged=unchanged,
        totals_before=_totals(rows),
        totals_after=_after_totals(rows),
        accounts=_accounts(rows),
        tax_impact=[t for t in (_tax(organisation, row) for row in rows) if t is not None],
    )
    moved_in = sum((v["before"] for v in built.accounts.values()), ZERO)
    moved_out = sum((v["after"] for v in built.accounts.values()), ZERO)
    if not built.totals_unchanged or moved_in != moved_out:
        raise RecodeTotalsChanged("A recode must leave debits and credits as they are.")
    return built


def preview(
    organisation: Any,
    criteria: Any,
    changes: Any,
    user: Any = None,
    *,
    keys: set[tuple[str, int]] | None = None,
) -> Preview:
    """The preview of the search; ``keys`` — ``{(entry public id, line no)}`` chosen in the
    results grid — narrows it to those lines (``None``: every line found)."""
    resolved = clean_changes(organisation, changes)
    found = list(find_lines(organisation, criteria))
    included, excluded = split(organisation, found, resolved.values, user)
    if keys is not None:
        included = [line for line in included if (str(line.entry.public_id), line.line_no) in keys]
    return build(organisation, included, resolved, excluded)

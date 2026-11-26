"""The conversion's difference (C-05-T04): does the opening trial balance balance, and do the
receivable and payable control lines equal the open documents?

``difference(session)`` reads the session's lines and opening documents and returns a
``Difference``:

- ``debits`` / ``credits`` / ``difference`` (debits − credits) of the lines — **nothing is
  plugged**: Xero pushes an unbalanced opening to "Historical adjustment"; Numo9 shows the
  difference and refuses to finalise (C-05-T05). A suspense line may be added explicitly (the
  *Conversion balances suspense* account) — visible, and flagged by the exceptions engine (K-09);
- ``controls`` — for Accounts receivable and Accounts payable (the ``ar`` / ``ap`` system
  accounts): the control line's balance on its normal side (AR a debit, AP a credit; a balance on
  the other side is negative), the sum of what the opening documents had outstanding, and the
  gap between them;
- ``accounts`` — the **unbalanced accounts**: each control account whose line doesn't equal its
  documents, with both figures (a document without a control line and a control line without
  documents are both listed);
- ``warnings`` — bank and cash accounts opening below zero (a credit balance on a bank asset:
  the C-03 cash guard's case, a warning here — the opening states what the old books said);
- ``opening_equity_missing`` — no line on any equity account (no share capital, retained
  earnings or shareholder equity): allowed, but suspicious — the REFINED case, registered for
  K-09 by ``numo9.conversion.exceptions`` (C-05-T14);
- ``reasons`` — why it can't be finalised, each a code and a message naming the figures
  (``conversion.unbalanced``, ``conversion.control_mismatch``, ``conversion.empty``,
  ``conversion.finalised``); ``can_finalise`` is true when there are none.

Amounts are ``Decimal`` to the cent; ``as_dict()`` is the API's shape (strings).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.models import AccountSubtype, AccountType, SystemRole
from numo9.ledger.validation import format_amount
from numo9.tenancy.context import org_context

from .models import ConversionLine, ConversionSession, OpeningDocument, OpeningDocumentKind

ZERO = Decimal("0.00")

#: (system role, opening-document kind, the control's normal side)
CONTROLS: tuple[tuple[str, str, str], ...] = (
    (SystemRole.AR, OpeningDocumentKind.INVOICE, "debit"),
    (SystemRole.AP, OpeningDocumentKind.BILL, "credit"),
)


def _account(account: Any) -> dict[str, str]:
    return {"id": str(account.public_id), "code": account.code, "name": account.name}


@dataclass(frozen=True)
class ControlCheck:
    role: str
    account: Any  # the control account (None when the chart has none)
    control: Decimal  # the line's balance on the normal side
    documents: Decimal  # Σ outstanding of the opening documents
    count: int  # how many opening documents

    @property
    def gap(self) -> Decimal:
        return self.control - self.documents

    @property
    def matches(self) -> bool:
        return self.gap == ZERO

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "label": str(SystemRole(self.role).label),
            "account": _account(self.account) if self.account is not None else None,
            "control": f"{self.control:.2f}",
            "documents": f"{self.documents:.2f}",
            "count": self.count,
            "gap": f"{self.gap:.2f}",
            "matches": self.matches,
        }


@dataclass(frozen=True)
class Reason:
    code: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass
class Difference:
    debits: Decimal = ZERO
    credits: Decimal = ZERO
    lines: int = 0
    controls: list[ControlCheck] = field(default_factory=list)
    warnings: list[Reason] = field(default_factory=list)
    opening_equity_missing: bool = True
    finalised: bool = False

    @property
    def difference(self) -> Decimal:
        return self.debits - self.credits

    @property
    def balanced(self) -> bool:
        return self.difference == ZERO

    @property
    def accounts(self) -> list[ControlCheck]:
        """The unbalanced accounts: controls that don't equal their documents."""
        return [c for c in self.controls if not c.matches]

    @property
    def reasons(self) -> list[Reason]:
        out: list[Reason] = []
        if self.finalised:
            out.append(
                Reason(
                    "conversion.finalised",
                    _("The conversion is finalised: correct it with a correcting opening journal."),
                )
            )
        if self.lines == 0:
            out.append(
                Reason("conversion.empty", _("Enter at least one opening balance to finalise."))
            )
        if not self.balanced:
            out.append(
                Reason(
                    "conversion.unbalanced",
                    _(
                        "Debits %(debits)s · Credits %(credits)s · Difference %(difference)s — "
                        "the opening balances must balance before they're finalised."
                    )
                    % {
                        "debits": format_amount(self.debits),
                        "credits": format_amount(self.credits),
                        "difference": format_amount(abs(self.difference)),
                    },
                )
            )
        for check in self.accounts:
            label = str(check.account) if check.account is not None else check.role
            out.append(
                Reason(
                    "conversion.control_mismatch",
                    _(
                        "%(account)s is %(control)s but its open documents add up to "
                        "%(documents)s (difference %(gap)s)."
                    )
                    % {
                        "account": label,
                        "control": format_amount(check.control),
                        "documents": format_amount(check.documents),
                        "gap": format_amount(check.gap),
                    },
                )
            )
        return out

    @property
    def can_finalise(self) -> bool:
        return not self.reasons

    def as_dict(self) -> dict[str, Any]:
        return {
            "debits": f"{self.debits:.2f}",
            "credits": f"{self.credits:.2f}",
            "difference": f"{self.difference:.2f}",
            "balanced": self.balanced,
            "lines": self.lines,
            "controls": [c.as_dict() for c in self.controls],
            "accounts": [c.as_dict() for c in self.accounts],
            "warnings": [w.as_dict() for w in self.warnings],
            "opening_equity_missing": self.opening_equity_missing,
            "reasons": [r.as_dict() for r in self.reasons],
            "can_finalise": self.can_finalise,
        }


def _documents(session: ConversionSession, kind: str) -> tuple[Decimal, int]:
    rows = OpeningDocument.objects.filter(session=session, kind=kind, deleted_at__isnull=True)
    amounts = list(rows.values_list("outstanding", flat=True))
    return sum(amounts, ZERO), len(amounts)


def difference(session: ConversionSession) -> Difference:
    """The session's difference (module docstring)."""
    from numo9.ledger.models import Account

    with org_context(session.organisation):
        lines = list(
            ConversionLine.objects.filter(session=session, deleted_at__isnull=True).select_related(
                "account"
            )
        )
        result = Difference(
            debits=sum((line.debit for line in lines), ZERO),
            credits=sum((line.credit for line in lines), ZERO),
            lines=len(lines),
            finalised=session.is_finalised,
            opening_equity_missing=not any(
                line.account.type == AccountType.EQUITY for line in lines
            ),
        )
        by_account = {line.account_id: line for line in lines}
        for role, kind, side in CONTROLS:
            account = Account.objects.filter(system_role=role).first()
            line = by_account.get(account.pk) if account is not None else None
            net = (line.debit - line.credit) if line is not None else ZERO
            documents, count = _documents(session, kind)
            if line is None and count == 0:
                continue
            control = net if side == "debit" else -net
            result.controls.append(ControlCheck(role, account, control, documents, count))
        for line in lines:
            account = line.account
            if (
                account.type == AccountType.ASSET
                and account.subtype == AccountSubtype.BANK
                and line.credit > ZERO
            ):
                result.warnings.append(
                    Reason(
                        "conversion.negative_cash",
                        _(
                            "%(account)s opens at −%(amount)s: check the bank statement at the "
                            "conversion date."
                        )
                        % {"account": account.name, "amount": format_amount(line.credit)},
                    )
                )
        return result

"""Exceptions hook of the conversion (C-05-T14): the conversion's findings, for the exceptions
engine (K-09) to register as rules — K-09 owns the rules, findings and their workflow; this
module only **answers** for the conversion and **announces** the case when it happens.

Providers — each ``(organisation) -> list[ConversionFinding]``, an empty list when there is
nothing to flag (no conversion, or the condition doesn't hold); read-only, safe to call from a
nightly or incremental run:

- ``opening_equity_missing(organisation)`` — code ``OPENING_EQUITY_MISSING``, severity
  ``warning``: the conversion (draft or finalised) has **no line on any equity account** — no
  share capital, retained earnings or other equity: an existing business whose balance sheet
  starts without equity (the REFINED case, teardown §6.11). The amount is the conversion's total
  debits;
- ``unbalanced_conversion(organisation)`` — code ``UNBALANCED_CONVERSION`` (K-09-T14), severity
  ``critical``: a draft conversion whose difference isn't 0.00 or whose AR/AP control lines
  don't equal the open documents (a finalised one is balanced by construction). The amount is
  the difference; ``details`` lists the reasons and the unbalanced accounts;
- ``conversion_suspense_used(organisation)`` — code ``CONVERSION_SUSPENSE_USED``, severity
  ``warning``: a line on the *Conversion balances suspense* account (system role
  ``suspense_conversion``) — the explicit plug a person may add instead of an automatic one,
  kept visible so it is cleared.

``PROVIDERS`` maps each code to its provider (what K-09's registry iterates).

Signal — ``numo9.conversion.signals.opening_equity_missing`` is **sent when a conversion is
finalised without any equity line** (``sender=ConversionSession``, ``organisation``,
``session``, ``finding``: the ``ConversionFinding``), after the finalise transaction commits
(``transaction.on_commit``, ``send_robust``: a receiver's error never undoes the finalise). K-09
connects to it to open the finding at once instead of waiting for its next run.

A ``ConversionFinding`` is plain data: ``code``, ``severity``, ``subject_type``
(``"conversion.ConversionSession"``), ``subject_id`` (the session's public id), ``fingerprint``
(``<code>:<subject_id>``: K-09 dedupes on it), ``amount`` (``Decimal``), ``message`` (in the
active language) and ``details`` (JSON-safe).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.models import SystemRole
from numo9.ledger.validation import format_amount
from numo9.tenancy.context import org_context

from .difference import difference
from .models import ConversionLine, ConversionSession

OPENING_EQUITY_MISSING = "OPENING_EQUITY_MISSING"
UNBALANCED_CONVERSION = "UNBALANCED_CONVERSION"
CONVERSION_SUSPENSE_USED = "CONVERSION_SUSPENSE_USED"
SUBJECT_TYPE = "conversion.ConversionSession"


@dataclass(frozen=True)
class ConversionFinding:
    code: str
    severity: str  # info · warning · critical (K-09's levels; K-09 settings may override)
    subject_id: str
    amount: Decimal
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    subject_type: str = SUBJECT_TYPE

    @property
    def fingerprint(self) -> str:
        return f"{self.code}:{self.subject_id}"


def _session(organisation: Any) -> ConversionSession | None:
    found: ConversionSession | None = ConversionSession.objects.filter(
        organisation=organisation, deleted_at__isnull=True
    ).first()
    return found


def _base(session: ConversionSession) -> dict[str, Any]:
    return {
        "conversion_date": session.conversion_date.isoformat(),
        "status": session.status,
        "opening_entry": session.opening_entry.number if session.opening_entry else None,
    }


def equity_finding(session: ConversionSession) -> ConversionFinding | None:
    """The OPENING_EQUITY_MISSING finding of one session, or None."""
    result = difference(session)
    if not result.lines or not result.opening_equity_missing:
        return None
    return ConversionFinding(
        code=OPENING_EQUITY_MISSING,
        severity="warning",
        subject_id=str(session.public_id),
        amount=result.debits,
        message=_(
            "The opening balances at %(date)s have no equity: no share capital, retained "
            "earnings or other equity was entered. Check the old balance sheet."
        )
        % {"date": session.conversion_date.isoformat()},
        details={**_base(session), "lines": result.lines, "debits": f"{result.debits:.2f}"},
    )


def opening_equity_missing(organisation: Any) -> list[ConversionFinding]:
    with org_context(organisation):
        session = _session(organisation)
        found = equity_finding(session) if session is not None else None
        return [found] if found is not None else []


def unbalanced_conversion(organisation: Any) -> list[ConversionFinding]:
    with org_context(organisation):
        session = _session(organisation)
        if session is None or session.is_finalised:
            return []
        result = difference(session)
        blocking = [
            r
            for r in result.reasons
            if r.code in ("conversion.unbalanced", "conversion.control_mismatch")
        ]
        if not blocking:
            return []
        return [
            ConversionFinding(
                code=UNBALANCED_CONVERSION,
                severity="critical",
                subject_id=str(session.public_id),
                amount=abs(result.difference),
                message=" ".join(r.message for r in blocking),
                details={
                    **_base(session),
                    "difference": f"{result.difference:.2f}",
                    "reasons": [r.as_dict() for r in blocking],
                    "accounts": [c.as_dict() for c in result.accounts],
                },
            )
        ]


def conversion_suspense_used(organisation: Any) -> list[ConversionFinding]:
    with org_context(organisation):
        session = _session(organisation)
        if session is None:
            return []
        line = (
            ConversionLine.objects.filter(
                session=session,
                deleted_at__isnull=True,
                account__system_role=SystemRole.SUSPENSE_CONVERSION,
            )
            .select_related("account")
            .first()
        )
        if line is None:
            return []
        amount = line.debit or line.credit
        return [
            ConversionFinding(
                code=CONVERSION_SUSPENSE_USED,
                severity="warning",
                subject_id=str(session.public_id),
                amount=amount,
                message=_(
                    "%(amount)s of the opening balances is on %(account)s: find what it is and "
                    "move it to the right account."
                )
                % {"amount": format_amount(amount), "account": str(line.account)},
                details={**_base(session), "account": line.account.code},
            )
        ]


#: K-09's registry: rule code → provider.
PROVIDERS: dict[str, Callable[[Any], list[ConversionFinding]]] = {
    OPENING_EQUITY_MISSING: opening_equity_missing,
    UNBALANCED_CONVERSION: unbalanced_conversion,
    CONVERSION_SUSPENSE_USED: conversion_suspense_used,
}


def announce_finalised(session: ConversionSession) -> None:
    """Called by ``finalise`` inside its transaction: once it commits, send
    ``signals.opening_equity_missing`` when the finalised conversion has no equity line."""
    from django.db import transaction

    from . import signals

    finding = equity_finding(session)
    if finding is None:
        return
    organisation = session.organisation

    def send() -> None:
        signals.opening_equity_missing.send_robust(
            sender=ConversionSession, organisation=organisation, session=session, finding=finding
        )

    transaction.on_commit(send)

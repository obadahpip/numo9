"""Spend money and receive money (F-01-T05): one balanced journal per bank transaction.

``record_bank_transaction(spec)`` writes, in **one transaction**, the ``BankTransaction`` header,
its lines and the journal it posts through the posting service (C-02) — type ``bank``, lock
module Bank, ``source_type`` ``banking.banktransaction`` and ``source_id`` the transaction's public
id. Nothing is half-written: a refused journal leaves no transaction either.

**Amounts.** Each line gives the ``amount`` as entered and its tax portions (``TaxPortion``: the
control account's system role, the amount, recoverable or not). The header's ``tax_mode`` says how
the amount is read:

- ``exclusive`` — the amount is before tax: net = amount, tax added on top;
- ``inclusive`` — the amount includes the tax: net = amount − tax;
- ``no_tax`` — no tax portions allowed.

The portions come from the tax engine (G-01 ``TaxCalculator``; the editors call it); this service
only checks they fit and posts them. ``total`` = Σ net + Σ tax is the money that left or reached
the bank and must be positive.

**Posting** (spend; receive is the mirror):

=====================================  =======================================
Dr each line's account                 net + its non-recoverable tax (PST in
                                       BC, the restricted part of an ITC)
Dr each recoverable portion's account  GST/HST receivable (ITC), QST ITR …
Cr the bank account's ledger account   total
=====================================  =======================================

A receipt credits each line's account with the net and every portion's control account (tax
collected is always owed: GST/HST payable, PST payable, QST payable), and debits the bank with the
total. Example: spend 113.00 tax inclusive with HST 13.00 → Dr Office supplies 100.00, Dr ITC
13.00, Cr Chequing 113.00.

Archived and deleted bank accounts can't be used (``banking.account.archived``); the contact,
attachment, journal-type and cash rules of C-03 apply as on any journal.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from numo9.contacts.models import Contact
from numo9.ledger.models import Account, JournalType, LedgerError, SystemRole
from numo9.ledger.services import ACTING, post_journal
from numo9.ledger.validation import JournalSpec, LineSpec, TaxPart
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import org_context

from .models import (
    BankAccount,
    BankTransaction,
    BankTransactionKind,
    BankTransactionLine,
    BankTransactionStatus,
    TaxMode,
)

ZERO = Decimal("0.00")
CENT = Decimal("0.01")
SOURCE_TYPE = "banking.banktransaction"
#: The system roles a tax portion may post to.
TAX_ROLES = frozenset(
    {
        SystemRole.GST_HST_PAYABLE,
        SystemRole.ITC_RECEIVABLE,
        SystemRole.PST_PAYABLE,
        SystemRole.QST_PAYABLE,
        SystemRole.QST_ITR,
    }
)


@dataclass(frozen=True)
class TaxPortion:
    """A line's tax for one component, posted to the account holding ``role``."""

    role: str
    amount: Decimal
    recoverable: bool = True


@dataclass(frozen=True)
class MoneyLine:
    account: Account | int
    amount: Decimal
    description: str = ""
    tax_code: str = ""
    taxes: Sequence[TaxPortion] = ()
    tracking: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MoneySpec:
    kind: str
    bank_account: BankAccount
    date: dt.date
    lines: Sequence[MoneyLine]
    contact: Contact | None = None
    reference: str = ""
    tax_mode: str = TaxMode.EXCLUSIVE


@dataclass(frozen=True)
class _Line:
    spec: MoneyLine
    account: Account
    net: Decimal
    tax: Decimal
    non_recoverable: Decimal


def _money(value: Any) -> Decimal:
    amount = Decimal(str(value))
    if amount != amount.quantize(CENT):
        raise LedgerError(
            _("Amounts have at most 2 decimals: %(amount)s."),
            code="banking.amount.precision",
            params={"amount": str(value)},
        )
    return amount.quantize(CENT)


def _account(value: Account | int) -> Account:
    if isinstance(value, Account):
        return value
    found = Account.objects.filter(pk=value).first()
    if found is None:
        raise LedgerError(_("That account doesn't exist."), code="banking.line.account_missing")
    return found


def _check_header(spec: MoneySpec) -> None:
    if spec.kind not in BankTransactionKind.values:
        raise LedgerError(_("Choose spend money or receive money."), code="banking.kind_invalid")
    if spec.tax_mode not in TaxMode.values:
        raise LedgerError(_("Unknown tax mode."), code="banking.tax_mode_invalid")
    bank = spec.bank_account
    if bank.archived_at is not None or bank.deleted_at is not None:
        raise LedgerError(
            _("%(name)s is archived: restore it or choose another account."),
            code="banking.account.archived",
            params={"name": bank.display_name},
        )
    if not spec.lines:
        raise LedgerError(_("Add at least one line."), code="banking.lines_required")


def _lines(spec: MoneySpec) -> list[_Line]:
    checked: list[_Line] = []
    for number, line in enumerate(spec.lines, start=1):
        amount = _money(line.amount)
        if amount <= ZERO:
            raise LedgerError(
                _("Line %(line)d: the amount must be more than 0.00."),
                code="banking.line.amount_positive",
                params={"line": number},
            )
        if spec.tax_mode == TaxMode.NO_TAX and line.taxes:
            raise LedgerError(
                _("Line %(line)d has tax, but the amounts have no tax."),
                code="banking.line.tax_not_allowed",
                params={"line": number},
            )
        tax, non_recoverable = ZERO, ZERO
        for portion in line.taxes:
            share = _money(portion.amount)
            if portion.role not in TAX_ROLES or share < ZERO:
                raise LedgerError(
                    _("Line %(line)d: a tax portion isn't valid."),
                    code="banking.line.tax_invalid",
                    params={"line": number},
                )
            tax += share
            if not portion.recoverable:
                non_recoverable += share
        net = amount - tax if spec.tax_mode == TaxMode.INCLUSIVE else amount
        if net < ZERO:
            raise LedgerError(
                _("Line %(line)d: the tax is more than the amount."),
                code="banking.line.tax_exceeds_amount",
                params={"line": number},
            )
        checked.append(_Line(line, _account(line.account), net, tax, non_recoverable))
    return checked


def _control_accounts(lines: list[_Line], *, spend: bool) -> dict[str, Account]:
    """The control account of every portion that posts to one (a spend's non-recoverable tax
    goes to the expense line instead)."""
    roles = {
        portion.role
        for line in lines
        for portion in line.spec.taxes
        if portion.recoverable or not spend
    }
    found = {a.system_role: a for a in Account.objects.filter(system_role__in=sorted(roles))}
    for role in sorted(roles - set(found)):
        raise LedgerError(
            _("The organisation has no %(role)s account: add it to the chart of accounts."),
            code="banking.tax.control_missing",
            params={"role": SystemRole(role).label},
        )
    return found


#: The tax kind of each control role (the tax lines of a bank transaction, G-05-T02).
ROLE_KINDS: dict[str, str] = {
    SystemRole.GST_HST_PAYABLE: "gst",
    SystemRole.ITC_RECEIVABLE: "gst",
    SystemRole.QST_PAYABLE: "qst",
    SystemRole.QST_ITR: "qst",
    SystemRole.PST_PAYABLE: "pst",
}


def _tax_parts(line: _Line, *, spend: bool) -> tuple[TaxPart, ...]:
    """The line's tax portions as tax lines: purchases when money is spent, sales when received."""
    out = []
    for portion in line.spec.taxes:
        amount = _money(portion.amount)
        recoverable = amount if spend and portion.recoverable else ZERO
        out.append(
            TaxPart(
                component=str(portion.role),
                kind=ROLE_KINDS.get(str(portion.role), "gst"),
                side="purchase" if spend else "sales",
                basis=line.net,
                tax=amount,
                recoverable=recoverable,
                non_recoverable=amount - recoverable if spend else ZERO,
                code=line.spec.tax_code,
            )
        )
    return tuple(out)


def journal_lines(spec: MoneySpec, lines: list[_Line], total: Decimal) -> list[LineSpec]:
    """The journal's lines (module docstring): line accounts, tax controls, then the bank."""
    spend = spec.kind == BankTransactionKind.SPEND
    controls = _control_accounts(lines, spend=spend)
    contact = spec.contact

    def side(amount: Decimal, *, money_in: bool) -> tuple[Decimal, Decimal]:
        return (amount, ZERO) if money_in else (ZERO, amount)

    result: list[LineSpec] = []
    taxes: dict[str, Decimal] = {}
    for line in lines:
        booked = line.net + (line.non_recoverable if spend else ZERO)
        result.append(
            LineSpec(
                line.account,
                *side(booked, money_in=spend),
                contact=contact,
                tracking=dict(line.spec.tracking),
                description=line.spec.description,
                tax_code=line.spec.tax_code,
                tax_parts=_tax_parts(line, spend=spend),
            )
        )
        for portion in line.spec.taxes:
            if spend and not portion.recoverable:
                continue
            taxes[portion.role] = taxes.get(portion.role, ZERO) + _money(portion.amount)
    for role, amount in taxes.items():
        if amount:
            result.append(LineSpec(controls[role], *side(amount, money_in=spend)))
    result.append(
        LineSpec(
            spec.bank_account.gl_account,
            *side(total, money_in=not spend),
            contact=contact,
            description=spec.reference,
        )
    )
    return [line for line in result if line.debit or line.credit]


def record_bank_transaction(
    spec: MoneySpec,
    *,
    user: Any = ACTING,
    attachments: Sequence[Any] = (),
    override_reason: str = "",
) -> BankTransaction:
    """Write and post a spend / receive (module docstring) — all or nothing."""
    organisation = spec.bank_account.organisation
    with org_context(organisation), transaction.atomic():
        _check_header(spec)
        lines = _lines(spec)
        subtotal = sum((line.net for line in lines), ZERO)
        tax_total = sum((line.tax for line in lines), ZERO)
        total = subtotal + tax_total
        if total <= ZERO:
            raise LedgerError(_("The total must be more than 0.00."), code="banking.total_positive")
        person = None if user is ACTING else user
        by = person if getattr(person, "is_authenticated", False) else None
        txn = BankTransaction(
            organisation=organisation,
            kind=spec.kind,
            bank_account=spec.bank_account,
            date=spec.date,
            contact=spec.contact,
            reference=spec.reference.strip(),
            tax_mode=spec.tax_mode,
            subtotal=subtotal,
            tax_total=tax_total,
            total=total,
            created_by=by,
        )
        txn.save()
        BankTransactionLine.objects.bulk_create(
            BankTransactionLine(
                organisation=organisation,
                transaction=txn,
                line_no=number,
                description=" ".join(line.spec.description.split())[:500],
                account=line.account,
                amount=_money(line.spec.amount),
                net=line.net,
                tax_amount=line.tax,
                tax_code=line.spec.tax_code,
                taxes=[
                    {
                        "role": p.role,
                        "amount": f"{_money(p.amount):.2f}",
                        "recoverable": p.recoverable,
                    }
                    for p in line.spec.taxes
                ],
            )
            for number, line in enumerate(lines, start=1)
        )
        label = BankTransactionKind(spec.kind).label
        entry = post_journal(
            JournalSpec(
                date=spec.date,
                lines=journal_lines(spec, lines, total),
                type=JournalType.BANK,
                narration=f"{label}: {txn.reference}" if txn.reference else str(label),
                source_type=SOURCE_TYPE,
                source_id=str(txn.public_id),
            ),
            organisation=organisation,
            user=user,
            module=LockModule.BANK,
            attachments=attachments,
            override_reason=override_reason,
        )
        txn.journal_entry = entry
        txn.save(update_fields=["journal_entry", "updated_at"])
        return txn


def void_bank_transaction(
    txn: BankTransaction, *, date: dt.date | None = None, user: Any = ACTING
) -> BankTransaction:
    """Void: reverse its journal (C-02 ``reverse``, lock module Bank) and mark it Voided.

    The journal is never edited; the reversal is dated ``date`` (the transaction's date by
    default). Voiding twice is refused (``banking.transaction.voided``)."""
    from django.utils import timezone

    from numo9.ledger.services import reverse

    with org_context(txn.organisation), transaction.atomic():
        locked = BankTransaction._base_manager.select_for_update().get(pk=txn.pk)
        if locked.status == BankTransactionStatus.VOIDED:
            raise LedgerError(
                _("This transaction is already voided."), code="banking.transaction.voided"
            )
        if locked.journal_entry is not None:
            reverse(
                locked.journal_entry,
                date=date or locked.date,
                narration=_("Void: %(label)s") % {"label": str(locked)},
                user=user,
                module=LockModule.BANK,
            )
        locked.status = BankTransactionStatus.VOIDED
        locked.voided_at = timezone.now()
        locked.save(update_fields=["status", "voided_at", "updated_at"])
        return locked

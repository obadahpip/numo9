"""Positive-pay export (E-06-T10): the cheques issued from a bank account, sent to the bank so it
pays only cheques it was told about (and refuses voided ones).

``export(bank_account, preset, date_from, date_to)`` → a ``PositivePayFile`` (file name, CSV
bytes, its rows) of every cheque in the register dated in the range — issued, printed, cleared
or stale-dated ones as **issues**, voided ones as **voids** — in cheque-number order. The rows
are the register's: same number, date, amount, payee and status (``register_rows``), so the
export always matches the register.

**Presets** (``PRESETS``) say how a bank wants the file: columns, a header row or not, the date
format, the amount in dollars or in cents, the issue / void codes. ``generic`` is a plain CSV with
a header any bank or reconciliation tool can map. The bank presets follow the layout each bank
asks for in its positive-pay set-up; banks change these and offer variants per service, so
check the preset against the bank's file specification when the service is set up (a wrong
layout is refused by the bank, never paid). Values are CSV-quoted; payee names are cut to the
preset's length.

The account number is the one printed on the cheques' MICR line (the bank account's cheque
settings, E-06-T07) with the transit and institution numbers.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from numo9.tenancy.context import org_context

from .cheques import ChequeRefused
from .models import Cheque, ChequeSequence, ChequeStatus

ISSUE = "issue"
VOID = "void"


@dataclass(frozen=True)
class Preset:
    key: str
    label: Any
    #: Column names, from: account, transit, institution, number, date, amount, payee, status.
    columns: tuple[str, ...]
    header: bool = True
    date_format: str = "%Y-%m-%d"
    cents: bool = False  # amount as whole cents ("123456") instead of "1234.56"
    issue_code: str = "I"
    void_code: str = "V"
    payee_length: int = 60
    pad_number: int = 0  # zero-pad the cheque number to this many digits (0: as is)


PRESETS: dict[str, Preset] = {
    p.key: p
    for p in (
        Preset(
            "generic",
            gettext_lazy("Generic CSV (with headers)"),
            ("account", "number", "date", "amount", "payee", "status"),
            issue_code="Issued",
            void_code="Void",
        ),
        Preset(
            "rbc",
            gettext_lazy("RBC Royal Bank"),
            ("account", "number", "amount", "date", "payee", "status"),
            header=False,
            date_format="%Y%m%d",
            pad_number=10,
            payee_length=50,
        ),
        Preset(
            "td",
            gettext_lazy("TD Canada Trust"),
            ("transit", "account", "number", "date", "amount", "status", "payee"),
            header=False,
            date_format="%m/%d/%Y",
            payee_length=40,
        ),
        Preset(
            "bmo",
            gettext_lazy("BMO Bank of Montreal"),
            ("account", "number", "date", "amount", "status", "payee"),
            header=False,
            date_format="%Y%m%d",
            cents=True,
            pad_number=8,
            payee_length=35,
        ),
        Preset(
            "scotiabank",
            gettext_lazy("Scotiabank"),
            ("transit", "account", "number", "amount", "date", "status"),
            header=False,
            date_format="%Y-%m-%d",
            issue_code="O",
            void_code="V",
        ),
        Preset(
            "cibc",
            gettext_lazy("CIBC"),
            ("account", "number", "amount", "date", "status", "payee"),
            header=True,
            date_format="%Y%m%d",
            cents=True,
            payee_length=35,
        ),
        Preset(
            "desjardins",
            gettext_lazy("Desjardins"),
            ("institution", "transit", "account", "number", "date", "amount", "status", "payee"),
            header=False,
            date_format="%Y%m%d",
            issue_code="E",  # émis
            void_code="A",  # annulé
            payee_length=40,
        ),
    )
}


@dataclass(frozen=True)
class RegisterRow:
    number: int
    date: dt.date
    amount: Decimal
    payee: str
    kind: str  # ISSUE or VOID


@dataclass(frozen=True)
class PositivePayFile:
    name: str
    content: bytes
    rows: tuple[RegisterRow, ...]


def register_rows(bank_account: Any, date_from: dt.date, date_to: dt.date) -> list[RegisterRow]:
    """The register's cheques of ``bank_account`` dated in the range, by number."""
    cheques = Cheque._base_manager.filter(
        organisation_id=bank_account.organisation_id,
        bank_account=bank_account,
        date__gte=date_from,
        date__lte=date_to,
    ).order_by("number")
    return [
        RegisterRow(
            number=c.number,
            date=c.date,
            amount=Decimal(c.amount),
            payee=c.payee_name,
            kind=VOID if c.status == ChequeStatus.VOID else ISSUE,
        )
        for c in cheques
    ]


def _digits(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def export(
    bank_account: Any,
    preset: str,
    date_from: dt.date,
    date_to: dt.date,
    *,
    user: Any = None,
) -> PositivePayFile:
    """The positive-pay file of ``bank_account`` for cheques dated ``date_from``–``date_to``."""
    with org_context(bank_account.organisation):
        return _export(bank_account, preset, date_from, date_to, user)


def _export(
    bank_account: Any, preset: str, date_from: dt.date, date_to: dt.date, user: Any
) -> PositivePayFile:
    from numo9.audit import service as audit

    chosen = PRESETS.get(preset)
    if chosen is None:
        raise ChequeRefused(
            _("Choose a positive-pay format from the list."),
            code="purchases.positive_pay.preset",
        )
    if date_to < date_from:
        raise ChequeRefused(
            _("The end date is before the start date."), code="purchases.positive_pay.dates"
        )
    settings = ChequeSequence._base_manager.filter(bank_account=bank_account).first()
    account = _digits(settings.account_number if settings else "")
    if not account:
        raise ChequeRefused(
            _("Enter the account number printed on the cheques of %(account)s first."),
            code="purchases.positive_pay.account_missing",
            params={"account": str(bank_account)},
        )
    values = {
        "account": account,
        "transit": _digits(bank_account.transit_number),
        "institution": _digits(bank_account.institution_number),
    }
    rows = register_rows(bank_account, date_from, date_to)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    if chosen.header:
        writer.writerow(chosen.columns)
    for row in rows:
        cells = {
            **values,
            "number": str(row.number).zfill(chosen.pad_number)
            if chosen.pad_number
            else str(row.number),
            "date": row.date.strftime(chosen.date_format),
            "amount": str(int(row.amount * 100)) if chosen.cents else f"{row.amount:.2f}",
            "payee": row.payee[: chosen.payee_length],
            "status": chosen.issue_code if row.kind == ISSUE else chosen.void_code,
        }
        writer.writerow([cells[column] for column in chosen.columns])
    content = buffer.getvalue().encode("utf-8")
    name = f"positive-pay-{chosen.key}-{account[-4:]}-{date_from:%Y%m%d}-{date_to:%Y%m%d}.csv"
    audit.record(
        "purchases.cheque.positive_pay_exported",
        obj=bank_account,
        meta={
            "preset": chosen.key,
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "cheques": len(rows),
            "issued": sum(1 for r in rows if r.kind == ISSUE),
            "voided": sum(1 for r in rows if r.kind == VOID),
        },
        actor=user if getattr(user, "is_authenticated", False) else None,
    )
    return PositivePayFile(name=name, content=content, rows=tuple(rows))

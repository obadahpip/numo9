"""Contact statements: the document and its PDF (B-02-T05).

A statement is what the statement engine (B-02-T04) produces from the sub-ledger sources —
``StatementDocument``: who issues it, who it is for, its kind and dates, its lines with running
balances, the aging buckets and the amount due, all in the contact's currency. This module turns
one into a PDF on the A-10 document baseline (``documents/base.html``: Letter 8.5 × 11 in, 1 in
margins, brand header with the issuer), in the contact's language (en-CA / fr-CA keys):

    pdf = render_statement_pdf(document, locale="fr-ca")

Two kinds (B-02 business rules):

- **outstanding** — the open items *as at* a date, each with its due date and balance, the aging
  buckets (Current, 1–30, 31–60, 61–90, over 90 days past due) and the amount due;
- **activity** — every document and payment in a date range, starting from the **opening
  balance** and ending with the closing balance (also the amount due).

``sample_statement()`` is the fixture shape used by the snapshot tests and the preview until the
engine lands.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any

from django.dispatch import Signal
from django.utils import translation

from numo9.documents.formatting import format_date, format_money
from numo9.documents.pdf import render_html, render_pdf

TEMPLATE = "contacts/statement.html"
ZERO = Decimal("0.00")


class StatementKind(StrEnum):
    OUTSTANDING = "outstanding"
    ACTIVITY = "activity"


#: Aging buckets, days past due (inclusive bounds; None = no upper bound).
AGING_BUCKETS: tuple[tuple[str, int, int | None], ...] = (
    ("current", -100_000, 0),
    ("days_1_30", 1, 30),
    ("days_31_60", 31, 60),
    ("days_61_90", 61, 90),
    ("over_90", 91, None),
)


@dataclass(frozen=True)
class Party:
    legal_name: str
    address_line: str = ""
    city: str = ""
    province: str = ""
    postal_code: str = ""
    business_number: str = ""
    phone: str = ""
    email: str = ""


@dataclass(frozen=True)
class StatementLine:
    date: dt.date
    document: str  # "INV-1043", "PMT-0042"
    description: str = ""
    due_date: dt.date | None = None
    amount: Decimal = ZERO  # positive: owed to the issuer; negative: payments, credits
    balance: Decimal = ZERO  # running balance after this line


@dataclass(frozen=True)
class StatementDocument:
    kind: StatementKind
    issuer: Party
    contact: Party
    contact_number: str
    currency: str
    issue_date: dt.date
    as_at: dt.date  # outstanding: as at; activity: period end
    lines: list[StatementLine]
    period_start: dt.date | None = None  # activity only
    opening_balance: Decimal = ZERO  # activity only
    aging: dict[str, Decimal] = field(default_factory=dict)

    @property
    def amount_due(self) -> Decimal:
        if self.lines:
            return self.lines[-1].balance
        return self.opening_balance

    def total(self) -> Decimal:
        return sum((line.amount for line in self.lines), ZERO)


def aging_of(lines: list[StatementLine], as_at: dt.date) -> dict[str, Decimal]:
    """Aging buckets of open items: days past due at ``as_at`` (no due date = current)."""
    buckets = {key: ZERO for key, _low, _high in AGING_BUCKETS}
    for line in lines:
        days = (as_at - line.due_date).days if line.due_date else 0
        for key, low, high in AGING_BUCKETS:
            if days >= low and (high is None or days <= high):
                buckets[key] += line.amount
                break
    return buckets


def statement_context(document: StatementDocument) -> dict[str, Any]:
    return {
        "statement": document,
        "issuer": document.issuer,
        "contact": document.contact,
        "lines": document.lines,
        "aging": [(key, document.aging.get(key, ZERO)) for key, _l, _h in AGING_BUCKETS],
        "amount_due": document.amount_due,
        "is_activity": document.kind == StatementKind.ACTIVITY,
    }


def render_statement_html(document: StatementDocument, *, locale: str | None = None) -> str:
    return render_html(TEMPLATE, statement_context(document), locale=locale)


def render_statement_pdf(document: StatementDocument, *, locale: str | None = None) -> bytes:
    return render_pdf(TEMPLATE, statement_context(document), locale=locale)


def sample_statement(kind: StatementKind = StatementKind.OUTSTANDING) -> StatementDocument:
    """A Canadian fixture (Ontario issuer and customer, CAD) in the engine's output shape."""
    issuer = Party(
        legal_name="Maple Leaf Supply Ltd.",
        address_line="120 King Street West",
        city="Toronto",
        province="ON",
        postal_code="M5V 2T6",
        business_number="123456782RT0001",
        email="ar@mapleleafsupply.example.ca",
    )
    contact = Party(
        legal_name="Cedar Roofing Co.",
        address_line="45 Elm Avenue",
        city="Ottawa",
        province="ON",
        postal_code="K1P 5G4",
    )
    as_at = dt.date(2026, 11, 30)
    if kind == StatementKind.OUTSTANDING:
        open_items = [
            (dt.date(2026, 8, 20), "INV-1012", dt.date(2026, 9, 19), Decimal("1130.00")),
            (dt.date(2026, 10, 2), "INV-1031", dt.date(2026, 11, 1), Decimal("565.00")),
            (dt.date(2026, 10, 28), "INV-1043", dt.date(2026, 11, 27), Decimal("2260.00")),
            (dt.date(2026, 11, 14), "CN-0007", None, Decimal("-226.00")),
        ]
        balance, lines = ZERO, []
        for date, number, due, amount in open_items:
            balance += amount
            lines.append(StatementLine(date, number, "", due, amount, balance))
        return StatementDocument(
            kind=kind,
            issuer=issuer,
            contact=contact,
            contact_number="C-0042",
            currency="CAD",
            issue_date=as_at,
            as_at=as_at,
            lines=lines,
            aging=aging_of(lines, as_at),
        )
    opening = Decimal("1695.00")
    activity = [
        (dt.date(2026, 11, 5), "INV-1051", "Invoice", Decimal("2260.00")),
        (dt.date(2026, 11, 14), "PMT-0042", "Payment — thank you", Decimal("-1695.00")),
        (dt.date(2026, 11, 20), "CN-0007", "Credit note", Decimal("-226.00")),
    ]
    balance, lines = opening, []
    for date, number, description, amount in activity:
        balance += amount
        lines.append(StatementLine(date, number, description, None, amount, balance))
    return StatementDocument(
        kind=kind,
        issuer=issuer,
        contact=contact,
        contact_number="C-0042",
        currency="CAD",
        issue_date=as_at,
        as_at=as_at,
        period_start=dt.date(2026, 11, 1),
        opening_balance=opening,
        lines=lines,
    )


# ---- sending (B-02-T06) ------------------------------------------------------------------------


class StatementError(ValueError):
    """A statement can't be sent (no recipient)."""


#: Sent after a statement went out: ``statement_sent.send(sender=StatementSend, send=row)`` —
#: the contact activity timeline (B-02-T02) records it from this signal.
statement_sent = Signal()


def statement_recipients(contact: Any) -> list[str]:
    """The contact's people marked "include in emails" that have an address (primary first)."""
    people = contact.people.filter(include_in_emails=True).exclude(email="")
    return list(dict.fromkeys(people.order_by("-is_primary", "pk").values_list("email", flat=True)))


def send_statement(
    contact: Any,
    document: StatementDocument,
    *,
    to: list[str] | None = None,
    language: str | None = None,
    user: Any = None,
) -> Any:
    """Email the statement as a PDF to the contact (A-07) and keep it in the history.

    The PDF is rendered in the contact's language (or ``language``), stored in the
    organisation's object storage and attached to one email per recipient; a ``StatementSend``
    row records what was sent, and ``statement_sent`` tells the activity timeline. Everything is
    in the caller's transaction: the emails leave only when it commits.
    """
    from numo9.audit.service import record
    from numo9.files.storage import new_key, put_bytes
    from numo9.notifications.mail import queue_email
    from numo9.notifications.templating import render_email

    from .models import StatementSend

    recipients = list(dict.fromkeys(e.strip() for e in (to or statement_recipients(contact))))
    recipients = [e for e in recipients if e]
    if not recipients:
        raise StatementError("The contact has no one to email statements to.")
    locale = (language or contact.language or "en-ca").lower()
    organisation = contact.organisation
    pdf = render_statement_pdf(document, locale=locale)
    file_name = (
        f"statement-{document.contact_number or contact.number}-{document.as_at:%Y-%m-%d}.pdf"
    )
    key = new_key(organisation, file_name)
    put_bytes(key, pdf, "application/pdf")
    with translation.override(locale):
        context = {
            "contact": document.contact.legal_name,
            "kind": document.kind.value,
            "as_at": format_date(document.as_at, locale),
            "period_start": format_date(document.period_start, locale)
            if document.period_start
            else "",
            "amount_due": f"{format_money(document.amount_due, locale)} {document.currency}",
        }
    email = render_email("statement", context, language=locale, organisation=organisation)
    attachment = {"key": key, "filename": file_name, "content_type": "application/pdf"}
    messages = [
        queue_email(
            address,
            email.subject,
            email.text,
            html=email.html,
            organisation=organisation,
            kind="contacts.statement",
            language=email.language,
            attachments=[attachment],
        )
        for address in recipients
    ]
    row = StatementSend.objects.create(
        organisation=organisation,
        contact=contact,
        kind=document.kind.value,
        as_at=document.as_at,
        period_start=document.period_start,
        amount_due=document.amount_due,
        currency=document.currency,
        language=email.language,
        recipients=recipients,
        subject=email.subject,
        file_key=key,
        file_name=file_name,
        email_messages=[str(message.public_id) for message in messages],
        sent_by=user if getattr(user, "is_authenticated", False) else None,
    )
    record(
        "contacts.statement.sent",
        obj=contact,
        meta={
            "kind": row.kind,
            "as_at": row.as_at.isoformat(),
            "amount_due": str(row.amount_due),
            "recipients": recipients,
        },
        actor=user,
    )
    statement_sent.send(sender=StatementSend, send=row)
    return row

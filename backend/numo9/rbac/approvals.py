"""Approval limits (A-03-T07): ``assert_can_approve(user, doc_type, amount)``.

An organisation sets, per document type (manual journal, bill, purchase order, pay run), the
highest amount a **user** — or everyone holding a **role** — may approve (``ApprovalLimit``,
A-03-T02). For a user in an organisation:

- the limits that apply are their own limit plus the limits of every role they hold there
  (membership system role, assigned organisation roles, system practice roles through a practice
  serving the organisation — ``resolver.organisation_roles``);
- the **effective limit is the lowest** of those (Phase 0 plan A-03: ``min(user limit, role
  limit)``) — a role limit can only tighten a user's own limit, never widen it;
- **no limit → no approval** (``approval.no_limit``); a user without access has no limits;
- amounts are compared in the organisation's base currency, CAD: callers convert a foreign
  amount first (edge case "limit in another currency");
- always read from the database, never cached — a limit or role changed while someone is
  approving applies when they commit (edge case "role edited mid-action").

Refusal raises ``ApprovalLimitExceeded`` — a ``403`` API error (``approval.limit_exceeded`` or
``approval.no_limit``) whose message names the next eligible approvers and whose body lists them
(``approvers``: people with access whose effective limit covers the amount, the refused user and
``exclude`` — e.g. the document's creator, A-03-T08 — left out).

Callers (bills D-03a, purchase orders E-01, pay runs N-02, journals C-02) check the approve
*permission* of their module themselves; this service only answers "is the amount within the
limit?".
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Q
from django.utils import translation
from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _

from numo9.documents.formatting import format_money
from numo9.i18n import errors
from numo9.i18n.errors import CatalogueError
from numo9.tenancy.access import can_access
from numo9.tenancy.context import acting_practice, current_org, org_context
from numo9.tenancy.models import Organisation, OrganisationMember, PracticeMember

from .models import ApprovalDocumentType, ApprovalLimit
from .resolver import organisation_roles

#: Most approvers named in the message (the body's ``approvers`` lists them all).
NAMED_APPROVERS = 3


@dataclass(frozen=True)
class Approver:
    """Someone who may approve the amount (``ApprovalLimitExceeded.next_approvers``)."""

    user_id: int
    public_id: str
    name: str
    email: str
    limit: Decimal


def _label(doc_type: str) -> str:
    text = str(ApprovalDocumentType(doc_type).label)
    return text[:1].lower() + text[1:]


_PLURALS: dict[str, Promise] = {
    ApprovalDocumentType.JOURNAL: _("manual journals"),
    ApprovalDocumentType.BILL: _("bills"),
    ApprovalDocumentType.PURCHASE_ORDER: _("purchase orders"),
    ApprovalDocumentType.PAY_RUN: _("pay runs"),
}


class ApprovalLimitExceeded(CatalogueError):
    """The amount is above the user's effective limit, or the user has no limit."""

    def __init__(
        self,
        *,
        doc_type: str,
        amount: Decimal,
        limit: Decimal | None,
        next_approvers: list[Approver],
    ) -> None:
        self.doc_type = doc_type
        self.amount = amount
        self.limit = limit
        self.next_approvers = next_approvers
        locale = translation.get_language()
        names = [a.name for a in next_approvers[:NAMED_APPROVERS]]
        next_step = (
            str(errors.APPROVAL_ASK) % {"names": ", ".join(names)}
            if names
            else str(errors.APPROVAL_NOBODY)
        )
        params = {"amount": format_money(amount, locale), "next_step": next_step}
        if limit is None:
            super().__init__(errors.APPROVAL_NO_LIMIT, documents=str(_PLURALS[doc_type]), **params)
        else:
            super().__init__(
                errors.APPROVAL_LIMIT_EXCEEDED,
                document=_label(doc_type),
                limit=format_money(limit, locale),
                **params,
            )
        self.extra = {
            "doc_type": doc_type,
            "amount": f"{amount:.2f}",
            "limit": None if limit is None else f"{limit:.2f}",
            "approvers": [
                {"id": a.public_id, "name": a.name, "limit": f"{a.limit:.2f}"}
                for a in next_approvers
            ],
        }


def _amount(amount: Decimal) -> Decimal:
    if isinstance(amount, bool) or not isinstance(amount, Decimal | int):
        raise TypeError("Approval amounts are Decimal (CAD), never float.")
    value = Decimal(amount)
    if not value.is_finite() or value < 0:
        raise ValueError("Approval amounts are finite and not negative.")
    return value


def _doc_type(doc_type: str) -> str:
    if doc_type not in ApprovalDocumentType.values:
        raise ValueError(f"Unknown approval document type {doc_type!r}.")
    return str(doc_type)


@contextmanager
def _in(organisation: Organisation | None) -> Iterator[Organisation]:
    """Run in the organisation's context (the active one by default; never another one)."""
    active = current_org()
    organisation = organisation or active
    if organisation is None:
        raise ValueError("No organisation: pass organisation= or run inside org_context().")
    if active is not None and active.pk != organisation.pk:
        raise ValueError("Approval limits are checked in the active organisation only.")
    if active is not None:
        yield organisation
        return
    with org_context(organisation, acting_practice()):
        yield organisation


def _effective(user: Any, organisation: Organisation, doc_type: str) -> Decimal | None:
    if not can_access(user, organisation):
        return None
    roles = organisation_roles(user, organisation)
    amounts = ApprovalLimit.objects.filter(
        Q(user=user) | Q(role__in=roles), doc_type=doc_type, deleted_at__isnull=True
    ).values_list("max_amount", flat=True)
    return min(amounts, default=None)


def effective_limit(
    user: Any, doc_type: str, *, organisation: Organisation | None = None
) -> Decimal | None:
    """The user's effective approval limit (CAD) for the document type; ``None`` = no limit."""
    doc_type = _doc_type(doc_type)
    with _in(organisation) as org:
        return _effective(user, org, doc_type)


def _candidates(organisation: Organisation) -> Iterable[Any]:
    """Members and the staff of practices serving the organisation (access checked per person)."""
    from numo9.accounts.models import User

    members = OrganisationMember.objects.filter(organisation=organisation).values("user_id")
    practice_staff = PracticeMember.objects.filter(
        practice__assignments__organisation=organisation, practice__assignments__active=True
    ).values("user_id")
    return (
        User.objects.filter(is_active=True)
        .filter(Q(pk__in=members) | Q(pk__in=practice_staff))
        .order_by("name", "pk")
    )


def eligible_approvers(
    doc_type: str,
    amount: Decimal,
    *,
    organisation: Organisation | None = None,
    exclude: Iterable[Any] = (),
) -> list[Approver]:
    """People with access whose effective limit covers ``amount``, by name."""
    doc_type, value = _doc_type(doc_type), _amount(amount)
    skip = {getattr(u, "pk", u) for u in exclude if u is not None}
    found: list[Approver] = []
    with _in(organisation) as org:
        for person in _candidates(org):
            if person.pk in skip:
                continue
            limit = _effective(person, org, doc_type)
            if limit is not None and value <= limit:
                found.append(
                    Approver(person.pk, str(person.public_id), person.name, person.email, limit)
                )
    return found


def can_approve(
    user: Any, doc_type: str, amount: Decimal, *, organisation: Organisation | None = None
) -> bool:
    limit = effective_limit(user, doc_type, organisation=organisation)
    return limit is not None and _amount(amount) <= limit


def assert_can_approve(
    user: Any,
    doc_type: str,
    amount: Decimal,
    *,
    organisation: Organisation | None = None,
    exclude: Iterable[Any] = (),
) -> Decimal:
    """Raise ``ApprovalLimitExceeded`` unless ``amount`` (CAD) is within the user's limit.

    Returns the effective limit. ``exclude``: people never suggested as next approvers (the
    document's creator when segregation of duties applies).
    """
    doc_type, value = _doc_type(doc_type), _amount(amount)
    with _in(organisation) as org:
        limit = _effective(user, org, doc_type)
        if limit is not None and value <= limit:
            return limit
        approvers = eligible_approvers(
            doc_type, value, organisation=org, exclude=[user, *list(exclude)]
        )
    raise ApprovalLimitExceeded(
        doc_type=doc_type, amount=value, limit=limit, next_approvers=approvers
    )

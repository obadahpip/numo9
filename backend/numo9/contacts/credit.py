"""Credit limit check (B-01-T13, gap-20): ``check_credit`` / ``assert_credit`` and overrides.

Xero has one checkbox — "Block new invoices when credit limit is reached" — and no way past it
but un-ticking it (teardown §3.2). Numo9 gives each contact a ``credit_limit`` and a
``credit_mode``:

- **no limit** (``credit_limit`` empty) — every document goes through;
- **warn** — a document that takes what the contact owes over the limit goes through with a
  warning (``CreditCheck.message``) the screen shows;
- **block** — the document is refused (``CreditLimitBlocked``, ``409
  contact.credit_limit_blocked``) unless an **approved override** covers it. The requester asks
  with ``request_override``; someone holding ``contacts.credit_limit.override`` — never the
  requester (segregation of duties, A-03-T08) — approves or declines it. An approval covers one
  document up to the amount asked, is used once, and expires after ``CREDIT_OVERRIDE_DAYS``.

What the contact **owes** (its exposure) comes from the modules that create receivables:
sales invoices (D-01), sales orders (E-02)… each registers a source with ``register_exposure``.
A source returns the open amount for the contact in the contact's currency, leaving out the
document being checked (``exclude``) so a revised document is not counted twice.

Callers (the documents of D and E) call ``assert_credit(contact, total, user=…, document_type=…,
document_ref=…)`` inside the transaction that saves the document; amounts are ``Decimal`` in the
contact's currency.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, Literal

from django.db import transaction
from django.utils import timezone

from numo9.documents.formatting import format_money
from numo9.i18n import errors
from numo9.i18n.errors import CatalogueError, api_error
from numo9.rbac.duties import assert_not_creator
from numo9.rbac.resolver import has_perm
from numo9.tenancy.access import can_access
from numo9.tenancy.context import acting_practice, current_org, org_context
from numo9.tenancy.models import OrganisationMember, PracticeMember

from .models import (
    CREDIT_OVERRIDE_DAYS,
    Contact,
    CreditMode,
    CreditOverride,
    CreditOverrideStatus,
)
from .permissions import CREDIT_OVERRIDE


def _in_organisation[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Run in the organisation of the first argument (a contact or an override), never another."""

    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        organisation = args[0].organisation  # type: ignore[attr-defined]
        active = current_org()
        if active is not None:
            if active.pk != organisation.pk:
                raise ValueError("Credit limits are checked in the active organisation only.")
            return func(*args, **kwargs)
        with org_context(organisation, acting_practice()):
            return func(*args, **kwargs)

    return wrapper


Outcome = Literal["no_limit", "within", "warn", "block", "override"]
ExposureSource = Callable[..., Decimal]

_sources: dict[str, ExposureSource] = {}


def register_exposure(key: str, source: ExposureSource) -> ExposureSource:
    """Register what a module adds to a contact's exposure: ``source(contact, *, exclude)``."""
    _sources[key] = source
    return source


def unregister_exposure(key: str) -> None:
    _sources.pop(key, None)


def _amount(value: Any) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal | int):
        raise TypeError("Credit amounts are Decimal, never float.")
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0:
        raise ValueError("Credit amounts are finite and not negative.")
    return amount


def exposure(contact: Contact, *, exclude: str = "") -> Decimal:
    """What the contact owes now, from every registered source (the contact's currency)."""
    total = Decimal("0")
    for source in _sources.values():
        total += Decimal(source(contact, exclude=exclude))
    return total


@dataclass(frozen=True)
class CreditCheck:
    contact: Contact
    amount: Decimal
    exposure: Decimal
    limit: Decimal | None
    mode: str
    outcome: Outcome
    override: CreditOverride | None = None
    params: dict[str, str] = field(default_factory=dict)

    @property
    def projected(self) -> Decimal:
        return self.exposure + self.amount

    @property
    def over_by(self) -> Decimal:
        if self.limit is None:
            return Decimal("0")
        return max(self.projected - self.limit, Decimal("0"))

    @property
    def allowed(self) -> bool:
        return self.outcome != "block"

    @property
    def message(self) -> str:
        """The warning people read (empty when within the limit)."""
        if self.outcome in ("warn", "block", "override"):
            return str(errors.CREDIT_LIMIT_WARNING) % self.params
        return ""


class CreditLimitBlocked(CatalogueError):
    """A block-mode contact would go over its limit and no approved override covers it."""

    def __init__(self, check: CreditCheck, approvers: list[dict[str, str]]) -> None:
        self.check = check
        super().__init__(errors.CREDIT_LIMIT_BLOCKED, **check.params)
        self.extra = {
            "contact": str(check.contact.public_id),
            "amount": f"{check.amount:.2f}",
            "exposure": f"{check.exposure:.2f}",
            "limit": f"{check.limit:.2f}",
            "over_by": f"{check.over_by:.2f}",
            "approvers": approvers,
        }


def _params(contact: Contact, limit: Decimal, projected: Decimal) -> dict[str, str]:
    return {
        "contact": contact.display_name,
        "projected": format_money(projected),
        "over": format_money(projected - limit),
        "limit": format_money(limit),
    }


def _matching_override(
    contact: Contact, amount: Decimal, document_type: str, document_ref: str
) -> CreditOverride | None:
    now = timezone.now()
    candidates = CreditOverride.objects.select_for_update().filter(
        contact=contact,
        status=CreditOverrideStatus.APPROVED,
        document_type=document_type,
        amount__gte=amount,
        expires_at__gt=now,
        deleted_at__isnull=True,
    )
    if document_ref:
        candidates = candidates.filter(document_ref__in=(document_ref, ""))
    return candidates.order_by("amount", "created_at").first()


@_in_organisation
def check_credit(
    contact: Contact,
    amount: Decimal,
    *,
    document_type: str = "",
    document_ref: str = "",
) -> CreditCheck:
    """Would a document of ``amount`` take the contact over its limit? Nothing is changed."""
    value = _amount(amount)
    owed = exposure(contact, exclude=document_ref)
    limit = contact.credit_limit
    mode = contact.credit_mode
    if limit is None:
        return CreditCheck(contact, value, owed, None, mode, "no_limit")
    projected = owed + value
    if projected <= limit:
        return CreditCheck(contact, value, owed, limit, mode, "within")
    params = _params(contact, limit, projected)
    if mode == CreditMode.WARN:
        return CreditCheck(contact, value, owed, limit, mode, "warn", params=params)
    override = (
        _matching_override(contact, value, document_type, document_ref) if document_type else None
    )
    if override is not None:
        return CreditCheck(contact, value, owed, limit, mode, "override", override, params)
    return CreditCheck(contact, value, owed, limit, mode, "block", params=params)


@_in_organisation
def approvers(contact: Contact, *, exclude: Iterable[Any] = ()) -> list[Any]:
    """People with access to the contact's organisation who may approve an override."""
    from numo9.accounts.models import User

    organisation = contact.organisation
    skip = {getattr(u, "pk", u) for u in exclude if u is not None}
    members = OrganisationMember.objects.filter(organisation=organisation).values("user_id")
    staff = PracticeMember.objects.filter(
        practice__assignments__organisation=organisation, practice__assignments__active=True
    ).values("user_id")
    people = (
        User.objects.filter(is_active=True)
        .filter(pk__in=members.union(staff))
        .exclude(pk__in=skip)
        .order_by("name", "pk")
    )
    return [
        p
        for p in people
        if can_access(p, organisation) and has_perm(p, organisation, CREDIT_OVERRIDE.key)
    ]


def _approver_list(people: Iterable[Any]) -> list[dict[str, str]]:
    return [{"id": str(p.public_id), "name": p.name} for p in people]


@_in_organisation
@transaction.atomic
def assert_credit(
    contact: Contact,
    amount: Decimal,
    *,
    user: Any = None,
    document_type: str,
    document_ref: str = "",
) -> CreditCheck:
    """Check and, for a block-mode contact over its limit, use the approved override.

    Returns the check (its ``message`` is the warning to show); raises ``CreditLimitBlocked``
    when the document may not be saved. Call it in the transaction that saves the document.
    """
    contact = Contact.objects.select_for_update().get(pk=contact.pk)
    check = check_credit(contact, amount, document_type=document_type, document_ref=document_ref)
    if check.outcome == "block":
        raise CreditLimitBlocked(check, _approver_list(approvers(contact, exclude=[user])))
    if check.override is not None:
        override = check.override
        override.status = CreditOverrideStatus.USED
        override.used_at = timezone.now()
        if not override.document_ref:
            override.document_ref = document_ref
        override.save(update_fields=["status", "used_at", "document_ref", "updated_at"])
    return check


def _link(contact: Contact) -> str:
    return f"/o/{contact.organisation.public_id}/contacts/{contact.public_id}"


@_in_organisation
@transaction.atomic
def request_override(
    contact: Contact,
    amount: Decimal,
    *,
    user: Any,
    reason: str,
    document_type: str,
    document_ref: str = "",
) -> CreditOverride:
    """Ask to go over the contact's limit for one document; the approvers are notified."""
    from numo9.notifications.services import notify

    reason = " ".join((reason or "").split())
    if not reason:
        raise api_error(errors.CREDIT_OVERRIDE_REASON)
    check = check_credit(contact, amount, document_ref=document_ref)
    if check.limit is None:
        raise ValueError("The contact has no credit limit: nothing to override.")
    people = approvers(contact, exclude=[user])
    if not people:
        raise api_error(errors.CREDIT_OVERRIDE_NO_APPROVER)
    override: CreditOverride = CreditOverride.objects.create(
        organisation=contact.organisation,
        contact=contact,
        amount=check.amount,
        exposure=check.exposure,
        limit=check.limit,
        currency=contact.currency,
        document_type=document_type,
        document_ref=document_ref,
        reason=reason,
        created_by=user,
        expires_at=timezone.now() + timedelta(days=CREDIT_OVERRIDE_DAYS),
    )
    notify(
        "contacts.credit_override_requested",
        people,
        organisation=contact.organisation,
        params={
            "contact": contact.display_name,
            "person": getattr(user, "name", "") or getattr(user, "email", ""),
            "over": format_money(check.over_by),
            "limit": format_money(check.limit),
            "reason": reason,
        },
        link=_link(contact),
    )
    return override


def _decide(
    override: CreditOverride, approver: Any, status: CreditOverrideStatus, note: str
) -> CreditOverride:
    from numo9.notifications.services import notify

    override = CreditOverride.objects.select_for_update().get(pk=override.pk)
    organisation = override.organisation
    if not (
        can_access(approver, organisation) and has_perm(approver, organisation, CREDIT_OVERRIDE.key)
    ):
        raise api_error(errors.PERMISSION_DENIED, action=str(errors.CREDIT_OVERRIDE_ACTION))
    assert_not_creator(approver, override)
    if override.status != CreditOverrideStatus.PENDING:
        raise api_error(
            errors.CREDIT_OVERRIDE_DECIDED,
            status=str(CreditOverrideStatus(override.status).label).lower(),
        )
    now = timezone.now()
    if override.expires_at <= now:
        raise api_error(
            errors.CREDIT_OVERRIDE_EXPIRED,
            date=timezone.localdate(override.expires_at).isoformat(),
        )
    override.status = status
    override.decided_by = approver
    override.decided_at = now
    override.decision_note = note
    if status == CreditOverrideStatus.APPROVED:
        override.expires_at = now + timedelta(days=CREDIT_OVERRIDE_DAYS)
    override.save()
    if override.created_by_id is not None:
        notify(
            f"contacts.credit_override_{status.value}",
            [override.created_by],
            organisation=organisation,
            params={
                "contact": override.contact.display_name,
                "person": getattr(approver, "name", "") or getattr(approver, "email", ""),
                "over": format_money(
                    max(override.exposure + override.amount - override.limit, Decimal("0"))
                ),
                "note": override.decision_note,
            },
            link=_link(override.contact),
        )
    return override


@_in_organisation
@transaction.atomic
def approve_override(override: CreditOverride, approver: Any, note: str = "") -> CreditOverride:
    return _decide(override, approver, CreditOverrideStatus.APPROVED, note)


@_in_organisation
@transaction.atomic
def reject_override(override: CreditOverride, approver: Any, note: str = "") -> CreditOverride:
    return _decide(override, approver, CreditOverrideStatus.REJECTED, note)

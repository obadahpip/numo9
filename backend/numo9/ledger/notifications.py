"""Journal approval notifications (C-04-T13, A-07).

- **Submitted** — everyone who may approve the journal hears about it (in the app and by email,
  per their preferences): people whose manual-journal approval limit covers its total, never its
  author or the person who submitted it (``ledger.journal_submitted``).
- **Approved** (and posted) / **sent back** — the author (and the submitter, when someone else)
  hears the decision, with the reason when it was sent back (``ledger.journal_approved``,
  ``ledger.journal_rejected``).

Notifications go out when the transaction commits — once: a rolled-back action sends nothing.
"""

from __future__ import annotations

from functools import partial
from typing import Any

from django.db import transaction
from django.utils.translation import gettext_lazy as _

from numo9.notifications.events import register_event
from numo9.notifications.models import NotificationCategory
from numo9.notifications.texts import register_text

SUBMITTED = "ledger.journal_submitted"
APPROVED = "ledger.journal_approved"
REJECTED = "ledger.journal_rejected"

register_event(
    SUBMITTED, NotificationCategory.APPROVALS, title_key="notifications.ledger.submitted"
)
register_event(APPROVED, NotificationCategory.APPROVALS, title_key="notifications.ledger.approved")
register_event(REJECTED, NotificationCategory.APPROVALS, title_key="notifications.ledger.rejected")
register_text(
    "notifications.ledger.submitted",
    _("%(journal)s is waiting for your approval"),
    _("%(person)s submitted a journal of %(total)s dated %(date)s: %(narration)s"),
)
register_text(
    "notifications.ledger.approved",
    _("%(journal)s was approved and posted"),
    _("%(person)s approved your journal of %(total)s."),
)
register_text(
    "notifications.ledger.rejected",
    _("%(journal)s was sent back"),
    _("%(person)s sent your journal back: %(reason)s"),
)


def _link(entry: Any) -> str:
    return f"/o/{entry.organisation.public_id}/accounting/journals/{entry.public_id}"


def _name(user: Any) -> str:
    return str(getattr(user, "name", "") or getattr(user, "email", "") or "")


def _params(entry: Any, person: Any, total: Any, **extra: Any) -> dict[str, Any]:
    from numo9.documents.formatting import format_money

    return {
        "journal": str(entry),
        "person": _name(person),
        "total": format_money(total),
        "date": entry.date.isoformat(),
        "narration": entry.narration or "",
        **extra,
    }


def _send(
    event: str, recipients: list[Any], organisation: Any, params: dict[str, Any], link: str
) -> None:
    from numo9.notifications.services import notify

    if recipients:
        notify(event, recipients, organisation=organisation, params=params, link=link)


def journal_submitted(entry: Any, submitter: Any) -> None:
    """The people who may approve ``entry`` hear about it (on commit)."""
    from numo9.accounts.models import User
    from numo9.rbac.approvals import eligible_approvers
    from numo9.rbac.models import ApprovalDocumentType

    from .approvals import journal_total

    total = journal_total(entry)
    approvers = eligible_approvers(
        ApprovalDocumentType.JOURNAL,
        total,
        organisation=entry.organisation,
        exclude=[entry.created_by, submitter],
    )
    people = list(User.objects.filter(pk__in=[a.user_id for a in approvers]))
    transaction.on_commit(
        partial(
            _send,
            SUBMITTED,
            people,
            entry.organisation,
            _params(entry, submitter, total),
            _link(entry),
        )
    )


def journal_decided(entry: Any, round_: Any) -> None:
    """The author (and the submitter) hear the decision on ``entry`` (on commit)."""
    from .models import ApprovalDecision

    if round_.decision not in (ApprovalDecision.APPROVED, ApprovalDecision.REJECTED):
        return
    people = []
    for person in (entry.created_by, round_.submitted_by):
        if person is not None and person not in people and person != round_.decided_by:
            people.append(person)
    event = APPROVED if round_.decision == ApprovalDecision.APPROVED else REJECTED
    transaction.on_commit(
        partial(
            _send,
            event,
            people,
            entry.organisation,
            _params(entry, round_.decided_by, round_.total, reason=round_.reason),
            _link(entry),
        )
    )

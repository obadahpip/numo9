"""Corrections after finalising (C-05-T07): a correcting opening journal, never an edit.

Once the conversion is finalised its lines, documents and opening journal don't change. A
balance found wrong later is corrected by an **adviser** (an accountant of the organisation's
practice, ``orgsettings.locks.is_adviser``) with ``correct(session, lines, reason, user)``:

- refused while the conversion is a draft (``conversion.correction.not_finalised`` — edit the
  draft instead), for anyone but an adviser (``conversion.correction.adviser_only``), and without
  a reason (``conversion.correction.reason_required``);
- ``lines`` — the correction itself (what to add to the opening balances): each a mapping with
  ``account`` (an ``Account``), ``debit`` or ``credit``, optional ``contact`` (required on
  Accounts receivable / payable) and ``description``; balanced, like any journal (the posting
  engine refuses it otherwise);
- posted through the posting engine as an opening journal (``JournalEntry.is_opening``, journal
  type Adjusting) dated the conversion date — the advisers-only "lock balances" lock (C-05-T06)
  is at the day before, so the adviser can post it; an *everyone* lock on the date refuses it;
- linked to the conversion by a ``ConversionCorrection`` (journal, reason, who and when) and
  audited; the original opening journal is untouched.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from django.db import transaction
from django.utils.translation import gettext as _

from numo9.ledger.validation import LineSpec
from numo9.orgsettings.locks import is_adviser
from numo9.tenancy.context import org_context

from .finalise import post_opening, refused
from .models import ConversionCorrection, ConversionSession


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def correct(
    session: ConversionSession,
    lines: Iterable[Mapping[str, Any]],
    reason: str,
    user: Any,
) -> ConversionCorrection:
    """Post a correcting opening journal (module docstring)."""
    from numo9.audit import service as audit
    from numo9.ledger.renumber import acting_as

    person = _person(user)
    reason = " ".join((reason or "").split())
    with org_context(session.organisation), transaction.atomic(), acting_as(person):
        locked = ConversionSession._base_manager.select_for_update().get(pk=session.pk)
        if not locked.is_finalised:
            raise refused(
                _("The conversion is still a draft: change its balances directly."),
                "conversion.correction.not_finalised",
            )
        if not is_adviser(person, locked.organisation):
            raise refused(
                _(
                    "Only an adviser (the organisation's accountant) can correct finalised opening "
                    "balances."
                ),
                "conversion.correction.adviser_only",
            )
        if not reason:
            raise refused(
                _("Say why the opening balances are corrected (kept with the journal)."),
                "conversion.correction.reason_required",
            )
        specs = [
            LineSpec(
                account=line["account"],
                debit=line.get("debit") or 0,
                credit=line.get("credit") or 0,
                contact=line.get("contact"),
                description=str(line.get("description") or reason),
            )
            for line in lines
        ]
        entry = post_opening(
            locked,
            specs,
            _("Correction of the opening balances at %(date)s — %(reason)s")
            % {"date": locked.conversion_date.isoformat(), "reason": reason},
            person,
        )
        correction = ConversionCorrection(
            organisation=locked.organisation,
            session=locked,
            entry=entry,
            reason=reason,
            created_by=person,
        )
        correction.save()
        audit.record(
            "conversion.session.corrected",
            obj=locked,
            meta={"journal": entry.number, "reason": reason},
            actor=person,
        )
        return correction

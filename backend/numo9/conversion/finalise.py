"""Finalising the conversion (C-05-T05): one opening journal, all or nothing.

``finalise(session, user)`` — in **one transaction**, under a row lock on the session:

1. refuses a conversion already finalised (``conversion.session.finalised``);
2. computes the difference (C-05-T04) and **refuses** while it can't be finalised — the
   difference isn't 0.00 (``conversion.unbalanced``, the message names debits, credits and the
   difference), a control line doesn't equal its open documents (``conversion.control_mismatch``,
   naming the account and both figures), or there is nothing to open (``conversion.empty``).
   Nothing is plugged: there is no automatic "historical adjustment";
3. posts **one** opening journal through the posting engine (C-02 ``post_journal``: the GL lock,
   closed periods, every journal rule) — type *Opening balance* (``JournalEntry.is_opening``),
   journal type Adjusting, dated the conversion date, source ``conversion.session``:

   - each line of the session as entered, except
   - the Accounts receivable and Accounts payable lines, split **per contact** of the open
     documents (the control accounts require a contact, and the ledger then shows each
     customer's and supplier's opening balance),
   - when the conversion date is the **first day of a fiscal year**, the revenue and expense lines
     (a closing trial balance of the old system) are rolled into Retained earnings: one line
     for their net, the year's income statement starting from zero. A mid-year conversion posts
     them to their accounts (the year-to-date comparatives);

4. marks the session finalised (by, at, ``opening_entry``) — its lines and documents can't
   change any more; corrections are correcting opening journals (C-05-T07);
5. **lock balances** (C-05-T06, optional: ``lock_balances``, the session's saved choice by
   default) — the GL, AR and AP lock dates for *everyone except advisers* move to the conversion
   date − 1 (never back: a later lock already set stays), each change audited by the lock date
   itself (``orgsettings.lockdate.*``) with the reason "Conversion balances finalised…", and the
   finalise event records which locks moved. Only advisers can then post before the conversion
   date — as in Xero, but for the three modules at once.

Any refusal (here or by the posting engine) leaves the session a draft and posts nothing.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from numo9.ledger.models import (
    Account,
    AccountType,
    JournalCategory,
    JournalEntry,
    JournalType,
    LedgerError,
    SystemRole,
)
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import LockModule
from numo9.tenancy.context import org_context

from .difference import CONTROLS, difference
from .models import ConversionLine, ConversionSession, ConversionStatus, OpeningDocument

ZERO = Decimal("0.00")
SOURCE_TYPE = "conversion.session"
#: ``caller`` of the opening journals for the posting rules: posted by the conversion itself
#: (the cash guard warns in the difference, C-05-T04, instead of blocking the opening).
CALLER = "conversion"
PL_TYPES = (AccountType.REVENUE, AccountType.EXPENSE)


class ConversionRefused(LedgerError):
    """A conversion action the rules refuse (``code`` names the rule)."""


def _person(user: Any) -> Any:
    return user if getattr(user, "is_authenticated", False) else None


def refused(message: str, code: str, **params: Any) -> ConversionRefused:
    return ConversionRefused(message, code=code, params=params or None)


def _side(amount: Decimal) -> tuple[Decimal, Decimal]:
    """A signed debit amount as (debit, credit)."""
    return (amount, ZERO) if amount > 0 else (ZERO, -amount)


def starts_fiscal_year(session: ConversionSession) -> bool:
    from numo9.ledger.period_close import fiscal_year_of

    start, _end = fiscal_year_of(session.organisation, session.conversion_date)
    return bool(start == session.conversion_date)


def _per_contact(session: ConversionSession, kind: str, side: str) -> list[tuple[Any, Decimal]]:
    """Σ outstanding of the open documents per contact, as a signed debit amount."""
    totals: dict[Any, Decimal] = defaultdict(lambda: ZERO)
    links = OpeningDocument.objects.filter(
        session=session, kind=kind, deleted_at__isnull=True
    ).select_related("invoice__contact", "bill__contact")
    for link in links:
        totals[link.document.contact] += link.outstanding
    sign = 1 if side == "debit" else -1
    return sorted(
        ((contact, sign * amount) for contact, amount in totals.items()),
        key=lambda pair: (pair[0].display_name.lower(), pair[0].pk),
    )


def opening_lines(session: ConversionSession) -> list[LineSpec]:
    """The opening journal's lines (module docstring, step 3)."""
    text = _("Opening balance at %(date)s") % {"date": session.conversion_date.isoformat()}
    lines = list(
        ConversionLine.objects.filter(session=session, deleted_at__isnull=True)
        .select_related("account", "contact")
        .order_by("account__code", "pk")
    )
    controls = {}
    for role, kind, side in CONTROLS:
        account = Account.objects.filter(system_role=role).first()
        if account is not None:
            controls[account.pk] = (kind, side)
    roll = starts_fiscal_year(session)
    specs: list[LineSpec] = []
    profit_and_loss = ZERO  # net debit of the revenue and expense lines rolled
    for line in lines:
        account = line.account
        net = line.debit - line.credit
        if roll and account.type in PL_TYPES:
            profit_and_loss += net
            continue
        if account.pk in controls:
            kind, side = controls[account.pk]
            split = _per_contact(session, kind, side)
            if split:  # the difference checked that they add up to the line
                for contact, amount in split:
                    debit, credit = _side(amount)
                    specs.append(
                        LineSpec(
                            account=account,
                            debit=debit,
                            credit=credit,
                            contact=contact,
                            description=line.description or text,
                        )
                    )
                continue
        specs.append(
            LineSpec(
                account=account,
                debit=line.debit,
                credit=line.credit,
                contact=line.contact,
                description=line.description or text,
            )
        )
    if profit_and_loss != ZERO:
        retained = Account.objects.filter(system_role=SystemRole.RETAINED_EARNINGS).first()
        if retained is None:
            raise refused(
                _("The chart has no Retained earnings account to open the year's result to."),
                "conversion.no_retained_earnings",
            )
        debit, credit = _side(profit_and_loss)
        specs.append(
            LineSpec(
                account=retained,
                debit=debit,
                credit=credit,
                description=_("Prior years' result (revenue and expenses at %(date)s)")
                % {"date": session.conversion_date.isoformat()},
            )
        )
    return specs


def post_opening(
    session: ConversionSession, lines: list[LineSpec], narration: str, person: Any
) -> JournalEntry:
    from numo9.ledger.services import post_journal

    return post_journal(
        JournalSpec(
            date=session.conversion_date,
            lines=lines,
            type=JournalType.OPENING,
            journal_type=JournalCategory.ADJUSTING,
            narration=narration,
            source_type=SOURCE_TYPE,
            source_id=str(session.public_id),
        ),
        organisation=session.organisation,
        user=person,
        module=LockModule.GL,
        caller=CALLER,
    )


LOCKED_MODULES = (LockModule.GL, LockModule.AR, LockModule.AP)


def lock_balances(session: ConversionSession) -> list[str]:
    """Step 5: move the advisers-only lock of the GL, AR and AP to the conversion date − 1;
    returns the modules whose lock moved."""
    import datetime as dt

    from numo9.orgsettings.models import LockDate, LockLevel

    day = session.conversion_date - dt.timedelta(days=1)
    reason = _("Conversion balances finalised at %(date)s: balances locked.") % {
        "date": session.conversion_date.isoformat()
    }
    moved: list[str] = []
    for module in LOCKED_MODULES:
        row = LockDate.objects.filter(
            module=module, level=LockLevel.ADVISERS_ONLY, deleted_at__isnull=True
        ).first() or LockDate(
            organisation=session.organisation, module=module, level=LockLevel.ADVISERS_ONLY
        )
        if row.date is not None and row.date >= day:
            continue
        row.set_lock(day, reason)
        row.full_clean()
        row.save()
        moved.append(str(module))
    return moved


def finalise(
    session: ConversionSession, user: Any, *, lock: bool | None = None
) -> ConversionSession:
    """Finalise the conversion (module docstring); returns the finalised session. ``lock``:
    lock the balances (step 5) — the session's ``lock_balances`` when not given."""
    from numo9.audit import service as audit
    from numo9.ledger.renumber import acting_as

    person = _person(user)
    with org_context(session.organisation), transaction.atomic(), acting_as(person):
        locked = ConversionSession._base_manager.select_for_update().get(pk=session.pk)
        if locked.is_finalised:
            raise refused(
                _("The conversion is finalised: correct it with a correcting opening journal."),
                "conversion.session.finalised",
            )
        result = difference(locked)
        if not result.can_finalise:
            first = result.reasons[0]
            raise refused(
                " ".join(r.message for r in result.reasons),
                first.code,
                difference=f"{result.difference:.2f}",
                debits=f"{result.debits:.2f}",
                credits=f"{result.credits:.2f}",
            )
        entry = post_opening(
            locked,
            opening_lines(locked),
            _("Opening balances at %(date)s") % {"date": locked.conversion_date.isoformat()},
            person,
        )
        locked.status = ConversionStatus.FINALISED
        locked.finalised_by = person
        locked.finalised_at = timezone.now()
        locked.opening_entry = entry
        if lock is not None:
            locked.lock_balances = lock
        locked.save()
        moved = lock_balances(locked) if locked.lock_balances else []
        audit.record(
            "conversion.session.finalised",
            obj=locked,
            meta={
                "conversion_date": locked.conversion_date.isoformat(),
                "journal": entry.number,
                "locked": moved,
            },
            actor=person,
        )
        session.refresh_from_db()
        return locked

from typing import Any

from django.apps import AppConfig
from django.db.models.signals import post_migrate


class LedgerConfig(AppConfig):
    """General ledger: chart of accounts and the GIFI list (C-01); posting engine (C-02)."""

    name = "numo9.ledger"
    label = "ledger"
    verbose_name = "General ledger"

    def ready(self) -> None:
        from numo9.imports.fields import register_entity

        from . import (
            cache,  # noqa: F401  (chart cache busting on account changes)
            notifications,  # noqa: F401  (journal approval events, C-04-T13)
        )
        from .importing import ACCOUNT

        # The chart of accounts can be imported and exported (C-01-T13, B-03 framework).
        register_entity(ACCOUNT)

        # The chart rules ask whether an account has transactions (C-01-T03/T08): posted lines.
        from .postings import register_posting_probe

        register_posting_probe(_has_posted_lines)

        # The GIFI list exists after every migrate and flush (test databases are flushed between
        # transactional tests): missing codes are created, existing rows are kept.
        post_migrate.connect(_seed_after_migrate, sender=self)

        # Tenant sweep (A-01-T09): the journals API needs a posted entry (C-02-T15).
        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["ledger.JournalEntry"] = _sweep_journal
        SWEEP_FACTORIES["ledger.Account"] = _sweep_account
        SWEEP_FACTORIES["ledger.RecurringJournalTemplate"] = _sweep_recurring

        from .approvables import register_journal_approvals

        register_journal_approvals()  # manual journals in the approvals inbox (C-04-T08)


def _seed_after_migrate(sender: AppConfig, **kwargs: Any) -> None:
    from django.apps import apps as global_apps

    from .gifi import seed_gifi

    seed_gifi(kwargs.get("apps") or global_apps, missing_only=True)


def _has_posted_lines(account: Any) -> bool:
    from .models import LOCKED_STATUSES, JournalLine

    return bool(
        JournalLine._base_manager.filter(
            organisation_id=account.organisation_id,
            account_id=account.pk,
            entry__status__in=LOCKED_STATUSES,
        ).exists()
    )


def _sweep_recurring(organisation: Any) -> Any:
    """A recurring journal of the organisation (C-04-T07), on the sweep journal's accounts."""
    import datetime as dt

    from numo9.tenancy.context import org_context

    from .models import JournalLine, RecurringJournalTemplate

    entry = _sweep_journal(organisation)
    with org_context(organisation):
        lines = list(JournalLine.objects.filter(entry=entry).select_related("account"))
        template = RecurringJournalTemplate(
            organisation=organisation,
            name="Sweep",
            rrule="FREQ=MONTHLY",
            start_date=dt.date(2026, 1, 1),
            lines=[
                {
                    "account": str(line.account.public_id),
                    "debit": f"{line.debit:.2f}",
                    "credit": f"{line.credit:.2f}",
                }
                for line in lines
            ],
        )
        template.full_clean()
        template.save()
        return template


def _sweep_journal(organisation: Any) -> Any:
    """A posted journal of the organisation, through the posting service."""
    from decimal import Decimal

    from django.utils import timezone

    from numo9.tenancy.context import org_context

    from .models import SUBTYPE_TYPE, Account
    from .services import post_journal
    from .validation import JournalSpec, LineSpec

    with org_context(organisation):
        accounts = []
        for code, subtype in (("1000", "bank"), ("4000", "revenue")):
            found = Account._base_manager.filter(organisation=organisation, code=code).first()
            if found is None:
                found = Account(
                    organisation=organisation,
                    code=code,
                    name_i18n={"en-ca": f"Sweep {code}"},
                    type=SUBTYPE_TYPE[subtype],
                    subtype=subtype,
                )
                found.save()
            accounts.append(found)
        return post_journal(
            JournalSpec(
                date=timezone.localdate(),
                narration="Sweep",
                lines=(
                    LineSpec(accounts[0], debit=Decimal("1.00")),
                    LineSpec(accounts[1], credit=Decimal("1.00")),
                ),
            ),
            user=None,
        )


def _sweep_account(organisation: Any) -> Any:
    """An account of the organisation (the chart of accounts API, C-01-T09)."""
    from numo9.tenancy.context import org_context

    from .models import Account

    with org_context(organisation):
        found = Account._base_manager.filter(organisation=organisation, code="6999").first()
        if found is not None:
            return found
        account = Account(
            organisation=organisation,
            code="6999",
            name_i18n={"en-ca": "Sweep expense"},
            type="expense",
            subtype="operating_expense",
        )
        account.save()
        return account

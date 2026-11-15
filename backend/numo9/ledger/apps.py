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

        from . import cache  # noqa: F401  (chart cache busting on account changes)
        from .importing import ACCOUNT

        # The chart of accounts can be imported and exported (C-01-T13, B-03 framework).
        register_entity(ACCOUNT)

        # The chart rules ask whether an account has transactions (C-01-T03/T08): posted lines.
        from .postings import register_posting_probe

        register_posting_probe(_has_posted_lines)

        # The GIFI list exists after every migrate and flush (test databases are flushed between
        # transactional tests): missing codes are created, existing rows are kept.
        post_migrate.connect(_seed_after_migrate, sender=self)


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

"""Saving a revision of a posted invoice (D-03b, ADR-0006).

Concurrency (D-03b-T06): ``lock_for_revision(invoice, version)`` — inside the saving
transaction, ``SELECT … FOR UPDATE`` on the invoice, then compare its ``version`` with the one the
editor opened (``RevisionDraft.base_version``). A mismatch is a ``RevisionConflict`` (HTTP 409,
``sales.revision.conflict``, carrying the invoice's current version): someone else saved first,
nothing is written, and the editor offers to reload. Two simultaneous saves of the same version
are serialised by the row lock: the first saves, the second sees the new version and is refused —
never a lost update.
"""

from __future__ import annotations

from typing import Any

from django.utils.translation import gettext as _

from numo9.ledger.models import LedgerError

from .models import Invoice


class RevisionConflict(LedgerError):
    """Someone else saved the invoice since it was opened (409)."""

    status_code = 409

    def __init__(self, invoice: Invoice, version: int) -> None:
        super().__init__(
            _(
                "Someone else revised %(invoice)s since you opened it: reload it to see their "
                "changes."
            )
            % {"invoice": invoice.number or str(invoice)},
            code="sales.revision.conflict",
            params={"version": str(invoice.version), "opened": str(version)},
        )
        self.current_version = invoice.version


def lock_for_revision(invoice: Invoice | Any, version: int) -> Invoice:
    """Lock the invoice row and check the version (module docstring); call inside the saving
    transaction. Returns the locked invoice."""
    locked: Invoice = Invoice._base_manager.select_for_update().get(pk=invoice.pk)
    if locked.version != version:
        raise RevisionConflict(locked, version)
    return locked

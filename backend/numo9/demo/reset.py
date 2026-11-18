"""Demo reset (U-07-T06): delete the demo's data in a foreign-key-safe order, re-clone the seed.

``reset_demo(organisation)``:

1. locks the organisation row (a second reset from another tab waits, then runs on the result
   of the first — never interleaved);
2. wipes the user-data tables (``reset_tables()``: what a visitor can add that is not part of the
   seed — activity, statements sent, imports, lock dates, documents, notifications…) and the
   seed tables, children first; the ledger's append-only triggers allow it for this demo only;
3. clones the template of the current seed version again (a demo built on an older seed moves to
   the new one);
4. returns the pristine hash of the result, which equals the template's (the acceptance check).

Phases 1–4 list their own user-data tables with ``register_reset_tables`` (seed contract,
docs/specs/demo-seed-contract.md). Members, the subscription, the audit trail and the demo
outbox (``DemoOutbox``) are kept: the visitor stays signed in and sees what they did before the
reset in the log.
"""

from __future__ import annotations

from collections.abc import Callable

from django.apps import apps
from django.db import models, transaction
from django.utils import timezone

from numo9.tenancy.models import Organisation

from .cloning import CloneError, clone, pristine_hash, template_for, wipe
from .seeders import SEED_VERSION, seed_models

# Parents before children, like the seeders' ``models``.
_reset_labels: list[str] = [
    "orgsettings.LockDate",
    "contacts.CustomFieldDefinition",
    "contacts.ExemptionCertificate",
    "contacts.CreditOverride",
    "contacts.StatementSend",
    "contacts.SupplierStatement",
    "contacts.SupplierStatementLine",
    "contacts.ActivityEvent",
    "imports.ImportMapping",
    "imports.ImportRun",
    "imports.ImportRunRow",
    "files.Document",
    "files.Attachment",
    "notifications.Notification",
]


def register_reset_tables(*labels: str) -> None:
    for label in labels:
        if label not in _reset_labels:
            _reset_labels.append(label)


def reset_tables() -> list[type[models.Model]]:
    return [apps.get_model(label) for label in _reset_labels]


def reset_demo(
    organisation: Organisation,
    *,
    version: int = SEED_VERSION,
    progress: Callable[[int, str], None] | None = None,
) -> str:
    """Return the demo to its seed; the pristine hash of the result."""
    if not organisation.is_demo:
        raise CloneError("Only a demo organisation can be reset.")
    step = progress or (lambda _percent, _label: None)
    step(5, "template")
    template = template_for(version)
    with transaction.atomic():
        locked = Organisation.objects.select_for_update().get(pk=organisation.pk)
        step(20, "wipe")
        wipe(locked, [*seed_models(), *reset_tables()])
        step(50, "clone")
        clone(template.organisation, locked)
        locked.demo_seed_version = template.seed_version
        locked.last_active_at = timezone.now()
        locked.save(update_fields=["demo_seed_version", "last_active_at", "updated_at"])
    step(90, "verify")
    result = pristine_hash(locked)
    step(100, "done")
    return result

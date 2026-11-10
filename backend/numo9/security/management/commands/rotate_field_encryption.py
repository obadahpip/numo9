"""``manage.py rotate_field_encryption [--dry-run | --check]`` (S-03-T04).

Re-wraps every ``EncryptedField`` value whose data key is wrapped by a key other than the active
one (``NUMO9_FIELD_ENCRYPTION_ACTIVE_KEY``), in batches, for every organisation. The plain value
never leaves memory and never changes.

    --dry-run   count what would be re-wrapped, change nothing
    --check     exit 1 if any value is not on the active key (CI / after a rotation)

Runbook: add the new key to the ring and make it active, deploy, run this command, then remove the
old key once it reports 0 values on it.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import models, transaction
from django.db.models.functions import Cast

from numo9.security import crypto
from numo9.security.fields import EncryptedField
from numo9.tenancy.managers import OrgScopedManager

REASON = "field-encryption key rotation (manage.py rotate_field_encryption)"


def encrypted_fields() -> list[tuple[type[models.Model], list[EncryptedField]]]:
    found = []
    for model in apps.get_models():
        fields = [f for f in model._meta.concrete_fields if isinstance(f, EncryptedField)]
        if fields:
            found.append((model, fields))
    return found


def all_rows(model: type[models.Model]) -> models.QuerySet[Any]:
    manager = model._default_manager
    if isinstance(manager, OrgScopedManager):
        return manager.unscoped(reason=REASON)
    return model._base_manager.all()


class Command(BaseCommand):
    help = "Re-wrap encrypted field values under the active field-encryption key."

    def add_arguments(self, parser: CommandParser) -> None:
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", help="Count only; change nothing")
        mode.add_argument(
            "--check", action="store_true", help="Fail if any value is not on the active key"
        )
        parser.add_argument("--batch-size", type=int, default=500)

    def handle(self, *args: Any, **options: Any) -> None:
        ring = crypto.key_ring()
        dry_run = options["dry_run"] or options["check"]
        batch_size = max(1, options["batch_size"])
        by_key: Counter[str] = Counter()
        rewrapped = 0

        for model, fields in encrypted_fields():
            raw = {
                f"_raw_{f.attname}": Cast(f.attname, output_field=models.TextField())
                for f in fields
            }
            rows = all_rows(model).annotate(**raw).values_list("pk", *raw.keys()).order_by("pk")
            pending: list[tuple[Any, dict[str, crypto.Ciphertext]]] = []
            for pk, *values in rows.iterator(chunk_size=batch_size):
                updates: dict[str, crypto.Ciphertext] = {}
                for field, value in zip(fields, values, strict=True):
                    if not value:
                        continue
                    key_id = crypto.key_id_of(value)
                    by_key[key_id] += 1
                    if key_id != ring.active:
                        updates[field.attname] = crypto.rewrap(value, field.context, ring)
                if updates:
                    pending.append((pk, updates))
                if len(pending) >= batch_size:
                    rewrapped += self._apply(model, pending, dry_run)
                    pending = []
            rewrapped += self._apply(model, pending, dry_run)
            self.stdout.write(f"{model._meta.label}: {', '.join(f.name for f in fields)}")

        summary = ", ".join(f"{k}={v}" for k, v in sorted(by_key.items())) or "no values"
        stale = sum(v for k, v in by_key.items() if k != ring.active)
        self.stdout.write(f"values by key: {summary}; active key: {ring.active}")
        if options["check"]:
            if stale:
                raise CommandError(f"{stale} value(s) are not on the active key {ring.active}.")
            self.stdout.write("check: every value is on the active key")
        elif dry_run:
            self.stdout.write(f"dry run: {stale} value(s) would be re-wrapped")
        else:
            self.stdout.write(f"re-wrapped {rewrapped} value(s) under {ring.active}")

    @staticmethod
    def _apply(
        model: type[models.Model],
        pending: list[tuple[Any, dict[str, crypto.Ciphertext]]],
        dry_run: bool,
    ) -> int:
        if dry_run or not pending:
            return sum(len(u) for _, u in pending)
        with transaction.atomic():
            for pk, updates in pending:
                all_rows(model).filter(pk=pk).update(**updates)
        return sum(len(u) for _, u in pending)

"""``AuditedModel``: every save of a model writes its field diff to the audit log (A-04-T03).

    class Contact(AuditedModel, OrgOwnedModel):      # AuditedModel first: it wraps save()
        audit_masked = frozenset({"bank_account"})   # never stored in clear (SIN, bank…)
        audit_exclude = frozenset({"search_vector"}) # not worth a history line
        ...

How it works:

- when a row is loaded (``from_db``) or reloaded (``refresh_from_db``) its audited fields are kept
  as the **pre** snapshot;
- ``save()`` runs the save and the audit write in **one transaction** — the change and its event
  commit or roll back together — and compares the **post** snapshot with the pre one:
  a new row → ``<app>.<model>.created`` with every non-empty field as ``[null, value]``;
  a changed row → ``…updated`` with ``{field: [old, new]}`` for the fields that changed (nothing
  changed → no event); ``deleted_at`` set by ``soft_delete()`` → ``…deleted``; cleared by
  ``restore()`` → ``…restored``;
- ``delete()`` (a real delete, rare: business records are soft-deleted) → ``…deleted`` with the
  last values;
- a row saved without having been loaded (built with an existing primary key) is read from the
  database first, so its diff is still right.

Audited fields are the concrete, non-relation-set fields minus the bookkeeping ones (``id``,
``public_id``, ``organisation``, ``created_at``, ``updated_at``, ``created_by``,
``deleted_at``) and ``audit_exclude``. Related records appear as ``{"id", "label"}`` (only the
ones that changed are loaded). Masked fields (``audit_masked``, encrypted fields, SIN/bank/secret
names — see ``service.is_masked_field``) are recorded as ``{"masked": true}`` — the field changed,
nothing more.

Bulk ``QuerySet.update()`` / ``bulk_create()`` bypass ``save()`` and are not captured: code that
changes many rows at once records them itself inside an audit batch (A-04-T06).
"""

from __future__ import annotations

from collections.abc import Collection
from typing import Any, ClassVar, Self

from django.db import models, router, transaction

from .service import MASKED, is_masked_field, plain, record, reference

#: Never part of a record's diff (bookkeeping; deleted_at is the deleted/restored action).
BOOKKEEPING_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "pk",
        "public_id",
        "organisation",
        "created_at",
        "updated_at",
        "created_by",
        "deleted_at",
    }
)


def audited_fields(model: type[models.Model]) -> list[models.Field[Any, Any]]:
    exclude = BOOKKEEPING_FIELDS | frozenset(getattr(model, "audit_exclude", frozenset()))
    return [
        f
        for f in model._meta.concrete_fields
        if f.name not in exclude and not f.primary_key and not isinstance(f, models.AutoField)
    ]


def raw_state(instance: models.Model) -> dict[str, Any]:
    """The audited fields' current values as stored (foreign keys as their id; masked marked)."""
    model = type(instance)
    masked = frozenset(getattr(model, "audit_masked", frozenset()))
    deferred = instance.get_deferred_fields()
    state: dict[str, Any] = {}
    for f in audited_fields(model):
        if f.attname in deferred:
            continue
        value = getattr(instance, f.attname)
        state[f.name] = ("masked", value) if is_masked_field(f, masked) else value
    if hasattr(instance, "deleted_at"):
        state["__deleted__"] = instance.deleted_at is not None
    return state


def _shown(instance: models.Model, name: str, value: Any, *, new: bool) -> Any:
    """A stored value as the log shows it (related records resolved, masked hidden)."""
    if isinstance(value, tuple) and len(value) == 2 and value[0] == "masked":
        return dict(MASKED)
    field = instance._meta.get_field(name)
    if isinstance(field, models.ForeignKey) and value is not None:
        related = getattr(instance, name, None) if new else None
        if related is None or related.pk != value:
            related = field.related_model._base_manager.filter(pk=value).first()
        return reference(related) if related is not None else {"id": str(value), "label": ""}
    return plain(value)


def state_diff(
    instance: models.Model, before: dict[str, Any] | None, after: dict[str, Any]
) -> dict[str, list[Any]]:
    """``{field: [old, new]}`` between two raw states (``before=None``: a new row)."""
    changes: dict[str, list[Any]] = {}
    for name, new_raw in after.items():
        if name == "__deleted__":
            continue
        old_raw = before.get(name) if before is not None else None
        if before is not None and name not in before:
            continue  # was deferred when loaded: unknown before value, not compared
        if before is None and new_raw in (None, "", ("masked", None), ("masked", "")):
            continue  # a new row lists the fields it was given
        if before is not None and old_raw == new_raw:
            continue
        old = _shown(instance, name, old_raw, new=False) if old_raw is not None else None
        new = _shown(instance, name, new_raw, new=True) if new_raw is not None else None
        if isinstance(old_raw, tuple) or isinstance(new_raw, tuple):
            old, new = dict(MASKED), dict(MASKED)  # masked: never the value, either side
        changes[name] = [old, new]
    return changes


class AuditedModel(models.Model):
    """Mixin: field diffs of every save, delete and restore go to the audit log."""

    audit_exclude: ClassVar[frozenset[str]] = frozenset()
    audit_masked: ClassVar[frozenset[str]] = frozenset()

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        adding = self._state.adding
        before = None if adding else self._audit_loaded_state()
        update_fields = kwargs.get("update_fields")
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            super().save(*args, **kwargs)
            after = raw_state(self)
            if update_fields is not None and before is not None:
                # Only the saved fields reached the database; compare those.
                names = {self._meta.get_field(n).name for n in update_fields} | {"__deleted__"}
                before = {k: v for k, v in before.items() if k in names}
                after = {k: v for k, v in after.items() if k in names}
            self._audit_write(adding, before, after)
        self._audit_before = raw_state(self)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            last = raw_state(self)
            changes = state_diff(self, last, {k: None for k in last if k != "__deleted__"})
            record(self.audit_action("deleted"), obj=self, changes=changes)
            return super().delete(*args, **kwargs)

    @classmethod
    def from_db(
        cls, db: str | None, field_names: Collection[str], values: Collection[Any], **kwargs: Any
    ) -> Self:
        instance = super().from_db(db, field_names, values, **kwargs)
        instance._audit_before = raw_state(instance)
        return instance

    def refresh_from_db(
        self, using: str | None = None, fields: Any = None, from_queryset: Any = None
    ) -> None:
        """Reloaded values become the pre snapshot, so the next save diffs from the database."""
        super().refresh_from_db(using=using, fields=fields, from_queryset=from_queryset)
        state = raw_state(self)
        before: dict[str, Any] | None = getattr(self, "_audit_before", None)
        if fields is None or before is None:
            self._audit_before = state
            return
        names = {self._meta.get_field(name).name for name in fields} | {"__deleted__"}
        self._audit_before = {**before, **{k: v for k, v in state.items() if k in names}}

    def audit_label(self) -> str:
        return str(self)

    def audit_action(self, verb: str) -> str:
        return f"{self._meta.app_label}.{self._meta.model_name}.{verb}"

    def _audit_loaded_state(self) -> dict[str, Any] | None:
        before: dict[str, Any] | None = getattr(self, "_audit_before", None)
        if before is None and not self._state.adding and self.pk is not None:
            stored = type(self)._base_manager.filter(pk=self.pk).first()
            before = raw_state(stored) if stored is not None else None
        return before

    def _audit_write(
        self, adding: bool, before: dict[str, Any] | None, after: dict[str, Any]
    ) -> None:
        was_deleted = bool(before and before.get("__deleted__"))
        is_deleted = bool(after.get("__deleted__"))
        changes = state_diff(self, None if adding else before, after)
        if adding:
            verb = "created"
        elif is_deleted and not was_deleted:
            verb = "deleted"
        elif was_deleted and not is_deleted:
            verb = "restored"
        elif changes:
            verb = "updated"
        else:
            return
        record(self.audit_action(verb), obj=self, changes=changes)

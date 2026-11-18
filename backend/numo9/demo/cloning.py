"""Template-org cloning (U-07-T05): a new demo in well under 10 s.

The seeders (U-07-T04) run once per seed version, into a hidden **template organisation**
(``is_demo``, status demo, no members — never in a directory, never in metrics). Every new demo
is then a bulk copy of the template's seed tables (``seeders.seed_models()``, parents first):

- rows are read under the template's tenant context and written under the new organisation's
  (RLS holds on both sides);
- primary keys and public ids are new; every foreign key into a seed table is remapped to the
  copy; a foreign key into another organisation-owned table that is not a seed table is refused
  (the seed contract would be broken — a seeder forgot to list a table);
- self references (an account's parent) are set in a second pass;
- posted journals are inserted as drafts with their lines, then posted with their original
  numbers — the path the append-only triggers allow.

The template is rebuilt when the seed version changes (``template_for`` builds the missing one,
serialised by an advisory lock). ``pristine_hash`` fingerprints the seed tables independently
of ids and timestamps, so a clone, a reset and the template can be compared exactly.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from django.db import connection, models, transaction
from django.utils import timezone

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationStatus

from .models import DemoTemplate
from .seeders import SEED_VERSION, load_seed, run_seed, seed_models

LOCK_KEY = 0x6E756D6F_0007  # pg_advisory_xact_lock key: one template build at a time
IGNORED_IN_HASH = {"id", "organisation_id", "created_at", "updated_at", "public_id"}


class CloneError(RuntimeError):
    """A seed table points at an organisation-owned row that is not part of the seed."""


def _org_owned(model: type[models.Model]) -> bool:
    return any(f.name == "organisation" for f in model._meta.concrete_fields)


def _fks(model: type[models.Model]) -> list[models.ForeignKey[Any, Any]]:
    return [
        f
        for f in model._meta.concrete_fields
        if isinstance(f, models.ForeignKey) and f.name != "organisation"
    ]


def _key(model: type[models.Model]) -> str:
    """The row id column: ``id`` for partitioned tables whose primary key is composite."""
    pk = model._meta.pk
    return "id" if pk is None or pk.attname == "pk" else pk.attname


def _rows(model: type[models.Model], organisation: Organisation) -> list[dict[str, Any]]:
    return list(model._base_manager.filter(organisation=organisation).order_by("pk").values())


def _auto_time(field: models.Field[Any, Any]) -> bool:
    return bool(getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False))


def wipe(organisation: Organisation, tables: list[type[models.Model]] | None = None) -> None:
    """Delete the organisation's rows of the seed tables (children first). Demo organisations
    only: the ledger's append-only triggers let the deletes through for this one demo."""
    if not organisation.is_demo:
        raise CloneError("Only a demo organisation can be wiped.")
    with org_context(organisation), transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT set_config('numo9.demo_wipe', %s, true)", [str(organisation.pk)])
        for model in reversed(tables if tables is not None else seed_models()):
            cursor.execute(
                f"DELETE FROM {connection.ops.quote_name(model._meta.db_table)} "  # noqa: S608
                "WHERE organisation_id = %s",
                [organisation.pk],
            )
        cursor.execute("SELECT set_config('numo9.demo_wipe', '', true)")


def clone(template: Organisation, target: Organisation) -> None:
    """Copy the template's seed tables into ``target`` (its own seed rows are wiped first)."""
    tables = seed_models()
    with org_context(template):
        snapshot = {model: _rows(model, template) for model in tables}
    wipe(target, tables)
    id_map: dict[type[models.Model], dict[Any, Any]] = {}
    with org_context(target), transaction.atomic():
        posted: list[tuple[Any, dict[str, Any]]] = []
        self_refs: list[tuple[type[models.Model], Any, str, Any]] = []
        for model in tables:
            mapping: dict[Any, Any] = {}
            id_map[model] = mapping
            fks = _fks(model)
            uuid_fields = [
                f.attname
                for f in model._meta.concrete_fields
                if isinstance(f, models.UUIDField) and f.unique
            ]
            journal = model._meta.label == "ledger.JournalEntry"
            olds: list[Any] = []
            objects: list[models.Model] = []
            pending_self: list[tuple[int, str, Any]] = []
            for row in snapshot[model]:
                data = dict(row)
                old_pk = data.pop(_key(model))
                data["organisation_id"] = target.pk
                for name in uuid_fields:
                    data[name] = uuid.uuid4()
                for fk in fks:
                    value = data.get(fk.attname)
                    if value is None:
                        continue
                    related = fk.related_model
                    if related is model:
                        pending_self.append((len(objects), fk.attname, value))
                        data[fk.attname] = None
                    elif related in id_map:
                        data[fk.attname] = id_map[related][value]
                    elif isinstance(related, type) and _org_owned(related):
                        raise CloneError(
                            f"{model._meta.label}.{fk.name} points at {related._meta.label}, "
                            "which is not a seed table: list it in the seeder's models."
                        )
                if journal and data["status"] in ("posted", "reversed"):
                    posted.append((len(objects), {k: data[k] for k in ("status", "number")}))
                    data.update(status="draft", number=None)
                olds.append(old_pk)
                objects.append(model(**data))
            created = model._base_manager.bulk_create(objects, batch_size=500)
            key = _key(model)
            for old_pk, obj in zip(olds, created, strict=True):
                mapping[old_pk] = getattr(obj, key)
            for index, attname, old_value in pending_self:
                self_refs.append((model, getattr(created[index], key), attname, old_value))
            if journal:
                id_map[model]["__posted__"] = [
                    (getattr(created[i], key), state) for i, state in posted
                ]
        for model, pk, attname, old_value in self_refs:
            model._base_manager.filter(**{_key(model): pk}).update(
                **{attname: id_map[model][old_value]}
            )
        for model in tables:
            for pk, state in id_map[model].pop("__posted__", []):
                model._base_manager.filter(**{_key(model): pk}).update(**state)


def pristine_hash(organisation: Organisation) -> str:
    """SHA-256 of the organisation's seed tables, ids and timestamps aside (foreign keys by the
    position of the row they point at), so two organisations with the same seed hash equal."""
    tables = seed_models()
    digest = hashlib.sha256()
    with org_context(organisation):
        positions: dict[type[models.Model], dict[Any, int]] = {}
        snapshot = {}
        for model in tables:
            rows = _rows(model, organisation)
            positions[model] = {row[_key(model)]: n for n, row in enumerate(rows)}
            snapshot[model] = rows
    for model in tables:
        fks = {f.attname: f.related_model for f in _fks(model)}
        auto = {f.attname for f in model._meta.concrete_fields if _auto_time(f)}
        uuids = {
            f.attname
            for f in model._meta.concrete_fields
            if isinstance(f, models.UUIDField) and f.unique
        }
        for row in snapshot[model]:
            clean: dict[str, Any] = {}
            for key, value in row.items():
                if key in IGNORED_IN_HASH or key in auto or key in uuids:
                    continue
                related = fks.get(key)
                if related is not None and value is not None and related in positions:
                    value = ("ref", positions[related][value])
                clean[key] = value
            digest.update(model._meta.label.encode())
            digest.update(json.dumps(clean, sort_keys=True, default=str).encode())
    return digest.hexdigest()


def _build_template(version: int) -> DemoTemplate:
    seed = load_seed(version)
    organisation = Organisation.objects.create(
        name=f"{seed['company']['name']} — demo template v{version}",
        status=OrganisationStatus.DEMO,
        is_demo=True,
        demo_seed_version=version,
    )
    run_seed(organisation, seed=seed)
    return DemoTemplate.objects.create(
        seed_version=version,
        organisation=organisation,
        pristine_hash=pristine_hash(organisation),
    )


def template_for(version: int = SEED_VERSION) -> DemoTemplate:
    """The template of ``version``, built (once, under a lock) when missing."""
    existing = DemoTemplate.objects.filter(seed_version=version).select_related("organisation")
    found = existing.first()
    if found is not None:
        return found
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])
        found = existing.first()
        return found if found is not None else _build_template(version)


def create_demo(*, name: str = "", version: int = SEED_VERSION) -> Organisation:
    """A new demo organisation cloned from the template of ``version`` (no members yet)."""
    template = template_for(version)
    seed = load_seed(version)
    with transaction.atomic():
        organisation = Organisation.objects.create(
            name=name or seed["company"]["name"],
            status=OrganisationStatus.DEMO,
            is_demo=True,
            demo_seed_version=version,
            last_active_at=timezone.now(),
            time_zone=seed["company"].get("time_zone", "America/Toronto"),
        )
        clone(template.organisation, organisation)
    return organisation

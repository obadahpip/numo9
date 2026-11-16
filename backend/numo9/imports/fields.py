"""What can be imported: entities and their fields (B-03-T03).

An **entity** is one kind of row a file can bring in (``contacts.contact``, ``contacts.person``,
``ledger.account``…). It lists its **fields** — the targets a column can map to — each with

- ``key`` — stable identifier stored in saved mappings (``email``, ``billing_postal_code``);
- ``label`` — the English name people read (also the template header, B-03-T13);
- ``names_en`` / ``names_fr`` — other headers that mean exactly this field in English and in
  French (``Courriel``, ``Adresse courriel`` → Email). The French names are recognised now, before
  the French interface (Phase 6), because Quebec files arrive with French headers;
- ``required`` — the mapping must include it (a contact needs a display name);
- ``match_key`` — the field can identify an existing record (External ID, contact number).

Apps register their entities in ``AppConfig.ready()`` with ``register_entity``; the registry is
the single source for the mapping step, auto-suggest, validation and the downloadable template.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.utils.functional import Promise


@dataclass(frozen=True)
class ImportField:
    key: str
    label: Promise | str
    names_en: tuple[str, ...] = ()
    names_fr: tuple[str, ...] = ()
    required: bool = False
    match_key: bool = False


@dataclass(frozen=True)
class ImportEntity:
    key: str
    label: Promise | str
    fields: tuple[ImportField, ...] = field(default_factory=tuple)

    def field(self, key: str) -> ImportField:
        for item in self.fields:
            if item.key == key:
                return item
        raise KeyError(key)

    @property
    def field_keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.fields)

    @property
    def required_keys(self) -> tuple[str, ...]:
        return tuple(item.key for item in self.fields if item.required)


class UnknownEntity(KeyError):
    pass


_entities: dict[str, ImportEntity] = {}


def register_entity(entity: ImportEntity) -> ImportEntity:
    """Register (or re-register, e.g. on autoreload) an entity; keys must be unique."""
    keys = [item.key for item in entity.fields]
    if len(keys) != len(set(keys)):
        raise ValueError(f"{entity.key}: duplicate field keys")
    _entities[entity.key] = entity
    return entity


def get_entity(key: str) -> ImportEntity:
    try:
        return _entities[key]
    except KeyError:
        raise UnknownEntity(key) from None


def entities() -> tuple[ImportEntity, ...]:
    return tuple(_entities.values())


def entity_choices() -> list[tuple[str, str]]:
    return [(key, str(entity.label)) for key, entity in sorted(_entities.items())]

"""Seed builder framework (U-07-T03): a registry of per-module seeders run through services.

Each module that owns sample data registers a ``Seeder``::

    register(Seeder("contacts", seed_contacts, after=("chart",),
                    models=("contacts.Contact", "contacts.ContactPerson", "contacts.Address")))

- ``run(ctx)`` builds its part of the seed **through the module's services and model saves**
  (never raw inserts), so every invariant holds — the ledger balances, numbers are allocated,
  validation runs. It reads the seed document (``ctx.seed``) and leaves references for later
  seeders in ``ctx.refs`` (contacts by key, accounts by code…).
- ``after`` names the seeders it needs first; ``order()`` resolves the dependencies (stable:
  registration order among independent seeders) and refuses an unknown dependency or a cycle.
- ``models`` lists, parents before children, the tables whose rows the seeder creates: the
  template cloner copies them (U-07-T05), reset wipes and re-clones them (U-07-T06), and the
  pristine hash covers them. A module's user-entered rows live in the same tables, so a reset
  returns them to the seed exactly.

``run_seed(organisation)`` runs every seeder in order in one transaction on the organisation.
Phases 1–4 add their seeders the same way (docs/specs/demo-seed-contract.md).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from django.apps import apps
from django.db import models, transaction

from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

SEED_VERSION = 1
SEED_DIR = Path(__file__).parent / "seed"


class SeedError(RuntimeError):
    """The registry can't be ordered (unknown dependency, cycle) or the seed is missing."""


@dataclass
class SeedContext:
    organisation: Organisation
    seed: dict[str, Any]
    refs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Seeder:
    key: str
    run: Callable[[SeedContext], None]
    after: tuple[str, ...] = ()
    models: tuple[str, ...] = ()


_registry: dict[str, Seeder] = {}


def register(seeder: Seeder) -> Seeder:
    if seeder.key in _registry and _registry[seeder.key] is not seeder:
        raise SeedError(f"A seeder named {seeder.key!r} is already registered.")
    _registry[seeder.key] = seeder
    return seeder


def unregister(key: str) -> None:
    _registry.pop(key, None)


def registered() -> list[Seeder]:
    return list(_registry.values())


def order(seeders: list[Seeder] | None = None) -> list[Seeder]:
    """Seeders with every dependency first (depth-first, registration order kept)."""
    items = {s.key: s for s in (seeders if seeders is not None else registered())}
    done: list[Seeder] = []
    state: dict[str, str] = {}

    def visit(key: str, path: tuple[str, ...]) -> None:
        if state.get(key) == "done":
            return
        if state.get(key) == "visiting":
            raise SeedError("Seeder dependency cycle: " + " → ".join((*path, key)))
        if key not in items:
            raise SeedError(f"Seeder {path[-1]!r} needs {key!r}, which is not registered.")
        state[key] = "visiting"
        for dependency in items[key].after:
            visit(dependency, (*path, key))
        state[key] = "done"
        done.append(items[key])

    for key in items:
        visit(key, ())
    return done


def seed_models(seeders: list[Seeder] | None = None) -> list[type[models.Model]]:
    """The seed tables, parents before children, each once."""
    out: list[type[models.Model]] = []
    for seeder in order(seeders):
        for label in seeder.models:
            model = apps.get_model(label)
            if model not in out:
                out.append(model)
    return out


@cache
def load_seed(version: int = SEED_VERSION) -> dict[str, Any]:
    path = SEED_DIR / f"demo_seed_v{version}.json"
    if not path.exists():
        raise SeedError(f"No demo seed version {version} ({path.name}).")
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def run_seed(
    organisation: Organisation,
    *,
    seed: dict[str, Any] | None = None,
    seeders: list[Seeder] | None = None,
) -> SeedContext:
    """Build the seed into ``organisation`` through the services, all or nothing."""
    ctx = SeedContext(organisation, seed if seed is not None else load_seed())
    with org_context(organisation), transaction.atomic():
        for seeder in order(seeders):
            seeder.run(ctx)
    return ctx

"""U-07-T03 — seed builder framework: registry, dependency order, seed tables, run_seed.

Acceptance: seeder order resolved by dependencies (stable among independent seeders); unknown
dependency and cycles refused; ``seed_models`` lists each table once, parents first; ``run_seed``
runs every seeder in order on the organisation, all or nothing.
"""

from __future__ import annotations

import pytest

from numo9.contacts.models import Contact
from numo9.demo import seeders
from numo9.demo.seeders import SeedContext, Seeder, SeedError, order, run_seed, seed_models
from numo9.tenancy.context import current_org
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


def noop(ctx: SeedContext) -> None:
    pass


def test_dependencies_first_and_stable() -> None:
    items = [
        Seeder("contacts", noop, after=("chart",)),
        Seeder("settings", noop),
        Seeder("opening", noop, after=("contacts", "chart")),
        Seeder("chart", noop, after=("settings",)),
    ]
    assert [s.key for s in order(items)] == ["settings", "chart", "contacts", "opening"]


def test_unknown_dependency_and_cycle_refused() -> None:
    with pytest.raises(SeedError, match="needs 'chart'"):
        order([Seeder("contacts", noop, after=("chart",))])
    with pytest.raises(SeedError, match="cycle: a → b → a"):
        order([Seeder("a", noop, after=("b",)), Seeder("b", noop, after=("a",))])


def test_seed_models_once_parents_first() -> None:
    items = [
        Seeder("people", noop, after=("contacts",), models=("contacts.ContactPerson",)),
        Seeder("contacts", noop, models=("contacts.Contact", "contacts.ContactPerson")),
    ]
    assert [m.__name__ for m in seed_models(items)] == ["Contact", "ContactPerson"]


def test_register_refuses_a_second_seeder_with_the_same_key() -> None:
    first = Seeder("test-dup", noop)
    seeders.register(first)
    try:
        seeders.register(first)  # the same object again is fine
        with pytest.raises(SeedError):
            seeders.register(Seeder("test-dup", noop))
    finally:
        seeders.unregister("test-dup")


def test_run_seed_in_order_on_the_organisation_all_or_nothing() -> None:
    org = Organisation.objects.create(name="Maple & Pine Supply Co.")
    ran: list[str] = []

    def make(ctx: SeedContext) -> None:
        assert current_org() == ctx.organisation
        ran.append("make")
        ctx.refs["c"] = Contact(
            organisation=ctx.organisation, display_name="Lakeshore Ltd.", roles=["customer"]
        )
        ctx.refs["c"].save()

    def use(ctx: SeedContext) -> None:
        ran.append("use")
        assert ctx.refs["c"].pk

    def boom(ctx: SeedContext) -> None:
        raise RuntimeError("seed failed")

    run_seed(org, seed={}, seeders=[Seeder("use", use, after=("make",)), Seeder("make", make)])
    assert ran == ["make", "use"]
    assert Contact._base_manager.filter(organisation=org).count() == 1
    with pytest.raises(RuntimeError):
        run_seed(
            org, seed={}, seeders=[Seeder("make", make), Seeder("boom", boom, after=("make",))]
        )
    assert Contact._base_manager.filter(organisation=org).count() == 1


def test_load_seed_v1() -> None:
    seed = seeders.load_seed(1)
    assert seed["version"] == 1 and len(seed["contacts"]) == 25
    with pytest.raises(SeedError):
        seeders.load_seed(99)

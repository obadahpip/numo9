"""C-01-T05 — template loader per home province, with GIFI and tax-default keys.

Acceptance: a loaded template has 0 unmapped GIFI accounts (gap-30). Also: every province and
territory loads; province-only rows (QST, PST, employer health tax) follow the home province;
tax kinds become the province's keys; system roles, bank and contact flags arrive; a chart that
has accounts is never loaded over; the load is one transaction and one audit batch attributed to
the person loading it; ``ensure_system_account`` adds a missing control account.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from numo9.accounts.models import User
from numo9.audit.batch import SUMMARY_ACTION
from numo9.audit.models import AuditEvent
from numo9.ledger.models import Account, LedgerError, SystemRole
from numo9.ledger.template import (
    PROVINCES,
    ensure_system_account,
    get_template,
    load_template,
    tax_key,
    unmapped_gifi_count,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


@pytest.fixture
def owner() -> User:
    return User.objects.create_user("owner@maple.example", name="Dana Owner")


def by_code(org: Organisation) -> dict[str, Account]:
    return {a.code: a for a in Account.objects.all()}


@pytest.mark.parametrize("province", PROVINCES)
def test_every_province_loads_with_zero_unmapped_gifi(province: str) -> None:
    org = Organisation.objects.create(name=f"Org {province}")
    with org_context(org):
        created = load_template(org, province)
        assert len(created) == Account.objects.count() == len(get_template().rows_for(province))
        assert unmapped_gifi_count(org) == 0
        assert not Account.objects.filter(gifi__isnull=True).exists()


def test_province_only_rows(org: Organisation) -> None:
    on = Organisation.objects.create(name="Ontario Ltd.")
    qc = Organisation.objects.create(name="Québec inc.")
    bc = Organisation.objects.create(name="BC Ltd.")
    ab = Organisation.objects.create(name="Alberta Ltd.")
    roles = {}
    for item, province in ((on, "ON"), (qc, "qc"), (bc, "BC"), (ab, "AB")):
        with org_context(item):
            load_template(item, province)
            roles[province.upper()] = set(
                Account.objects.exclude(system_role="").values_list("system_role", flat=True)
            )
    assert {"qst_payable", "qst_itr", "qpp_payable", "qpip_payable"} <= roles["QC"]
    assert not {"qst_payable", "qst_itr", "pst_payable"} & roles["ON"]
    assert "pst_payable" in roles["BC"] and "pst_payable" not in roles["QC"]
    assert "eht_payable" in roles["ON"] and "eht_payable" not in roles["AB"]
    for province_roles in roles.values():  # in every chart
        assert {"ar", "ap", "gst_hst_payable", "itc_receivable", "retained_earnings"} <= (
            province_roles
        )


def test_tax_default_keys_for_the_home_province(org: Organisation) -> None:
    load_template(org, "ON")
    accounts = by_code(org)
    assert accounts["6080"].default_tax_key == "purchase.ON.standard"  # office supplies
    assert accounts["6010"].default_tax_key == "purchase.ON.standard.itc50"  # meals
    assert accounts["4000"].default_tax_key == "sales.ON.standard"
    assert accounts["6030"].default_tax_key == "purchase.exempt"  # bank charges
    assert accounts["4500"].default_tax_key == "sales.exempt"  # interest income
    assert accounts["6300"].default_tax_key == ""  # wages: no tax
    assert accounts["1010"].default_tax_key == ""


def test_tax_key_table() -> None:
    assert tax_key("purchase", "QC") == "purchase.QC.standard"
    assert tax_key("sales", "NS") == "sales.NS.standard"
    assert tax_key("none", "ON") == ""
    with pytest.raises(ValueError):
        tax_key("zero", "ON")


def test_roles_flags_and_template_refs(org: Organisation) -> None:
    load_template(org, "ON")
    accounts = by_code(org)
    assert accounts["1100"].system_role == SystemRole.AR and accounts["1100"].require_contact
    assert accounts["2000"].system_role == SystemRole.AP and accounts["2000"].require_contact
    assert accounts["1010"].is_bank and accounts["1000"].is_bank
    assert accounts["2400"].is_bank and accounts["2400"].type == "liability"
    assert accounts["1200"].subtype == "inventory" and accounts["1200"].system_role == "inventory"
    assert accounts["6040"].template_ref == "ca_v1:6040"
    assert accounts["1010"].name == "Chequing account"
    assert all(len(code) == 4 and code.isdigit() for code in accounts)


def test_template_definition_is_consistent() -> None:
    template = get_template()
    codes = [row.code for row in template.accounts]
    assert len(codes) == len(set(codes)) and codes == sorted(codes)
    roles = [row.system_role for row in template.accounts if row.system_role]
    assert len(roles) == len(set(roles))
    assert set(roles) == set(SystemRole.values)  # every role has its template account
    for row in template.accounts:
        assert set(row.provinces) <= set(PROVINCES), row.code


def test_never_loads_over_an_existing_chart(org: Organisation) -> None:
    account(org, "6100", "Mine")
    with pytest.raises(LedgerError) as error:
        load_template(org, "ON")
    assert error.value.code == "ledger.template.chart_not_empty"
    assert Account.objects.count() == 1


def test_invalid_province(org: Organisation) -> None:
    with pytest.raises(LedgerError) as error:
        load_template(org, "XX")
    assert error.value.code == "ledger.template.province_invalid"


def test_only_for_the_active_organisation(org: Organisation) -> None:
    other = Organisation.objects.create(name="Other")
    with pytest.raises(ValueError):
        load_template(other, "ON")


def test_one_audit_batch_attributed_to_the_loader(org: Organisation, owner: User) -> None:
    created = load_template(org, "ON", actor=owner)
    events = AuditEvent.objects.filter(action="ledger.account.created")
    assert events.count() == len(created)
    assert set(events.values_list("actor_user", flat=True)) == {owner.pk}
    assert len(set(events.values_list("batch_id", flat=True))) == 1
    summary = AuditEvent.objects.get(action=SUMMARY_ACTION)
    assert summary.meta["template"] == "ca_v1" and summary.meta["province"] == "ON"
    assert summary.meta["events"] == len(created)
    assert {a.created_by_id for a in created} == {owner.pk}


def test_failed_load_leaves_nothing(org: Organisation, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}
    original = Account.save

    def flaky(self: Account, *args: object, **kwargs: object) -> None:
        calls["n"] += 1
        if calls["n"] == 50:
            raise RuntimeError("database went away")
        original(self, *args, **kwargs)

    monkeypatch.setattr(Account, "save", flaky)
    with pytest.raises(RuntimeError):
        load_template(org, "ON")
    assert Account.objects.count() == 0
    assert not AuditEvent.objects.filter(action="ledger.account.created").exists()


def test_ensure_system_account_adds_a_missing_control(org: Organisation) -> None:
    load_template(org, "ON")
    assert not Account.objects.filter(system_role="pst_payable").exists()
    pst = ensure_system_account(org, "pst_payable", province="ON")
    assert (pst.code, pst.subtype, pst.gifi_id) == ("2110", "sales_tax_control", "2680")
    assert ensure_system_account(org, "pst_payable", province="ON").pk == pst.pk  # idempotent


def test_ensure_system_account_takes_the_next_free_code(org: Organisation) -> None:
    load_template(org, "ON")
    account(org, "2120", "Something else", "current_liability")  # QST's template code
    qst = ensure_system_account(org, "qst_payable", province="ON")
    assert qst.code == "2121"

"""C-01-T02 — AccountType / sub-type enums and the Account model.

Acceptance: the account code is unique per organisation in the database. Also: codes compare
without case; the same code is fine in another organisation; the database refuses a sub-type
outside its type, an unknown role or a non-bank Bank account; names are per language with an
English fallback; GIFI codes are validated against the seeded list; every save is audited.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import IntegrityError, transaction
from django.utils import translation

from numo9.audit.models import AuditEvent
from numo9.ledger.models import (
    NORMAL_SIDE,
    ROLE_SUBTYPES,
    SUBTYPE_TYPE,
    Account,
    AccountStatus,
    AccountSubtype,
    AccountType,
    LedgerError,
    SystemRole,
)
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation
from tests.ledger_helpers import account

pytestmark = pytest.mark.django_db


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Bakery Inc.")


@pytest.fixture
def other_org() -> Organisation:
    return Organisation.objects.create(name="Northern Lights Ltd.")


@pytest.fixture(autouse=True)
def _active(org: Organisation) -> Iterator[None]:
    with org_context(org):
        yield


# ---- enums ------------------------------------------------------------------------------


def test_every_subtype_belongs_to_one_type_and_every_type_has_subtypes() -> None:
    assert set(SUBTYPE_TYPE) == set(AccountSubtype.values)
    assert set(SUBTYPE_TYPE.values()) == set(AccountType.values)
    assert set(NORMAL_SIDE) == set(AccountType.values)


def test_plan_subtypes_present() -> None:
    expected = {
        "asset": {
            "current_asset",
            "bank",
            "inventory",
            "prepayment",
            "fixed_asset",
            "accumulated_amortisation",
            "non_current_asset",
            "intangible",
        },
        "liability": {
            "current_liability",
            "sales_tax_control",
            "payroll_liability",
            "non_current_liability",
        },
        "equity": {
            "share_capital",
            "retained_earnings",
            "current_year_earnings",
            "dividends",
            "other_equity",
        },
        "revenue": {"revenue", "other_income"},
        "expense": {
            "cost_of_sales",
            "operating_expense",
            "amortisation",
            "income_tax",
            "other_expense",
        },
    }
    for type_, subtypes in expected.items():
        assert {s for s, t in SUBTYPE_TYPE.items() if t == type_} == subtypes


def test_every_system_role_has_allowed_subtypes() -> None:
    assert set(ROLE_SUBTYPES) == set(SystemRole.values)
    for subtypes in ROLE_SUBTYPES.values():
        assert subtypes and subtypes <= set(AccountSubtype.values)


# ---- code uniqueness (acceptance) ---------------------------------------------------------


def test_code_unique_per_org_in_the_database(org: Organisation) -> None:
    account(org, "6100", "Office supplies")
    duplicate = Account(
        organisation=org,
        code="6100",
        name_i18n={"en-ca": "Copy"},
        type="expense",
        subtype="operating_expense",
    )
    # Straight to the database, past every Python check: the constraint refuses it.
    with pytest.raises(IntegrityError), transaction.atomic():
        Account._base_manager.bulk_create([duplicate])


def test_code_unique_ignores_case(org: Organisation) -> None:
    account(org, "A-100", "Shop float")
    with pytest.raises(IntegrityError), transaction.atomic():
        Account._base_manager.bulk_create(
            [
                Account(
                    organisation=org,
                    code="a-100",
                    name_i18n={"en-ca": "x"},
                    type="asset",
                    subtype="current_asset",
                )
            ]
        )


def test_same_code_in_another_org(org: Organisation, other_org: Organisation) -> None:
    account(org, "6100")
    with org_context(other_org):
        other = account(other_org, "6100")
    assert other.pk


def test_code_format(org: Organisation) -> None:
    for bad in ("", " ", "-100", "12345678901", "61 00", "6100!"):
        with pytest.raises(LedgerError) as error:
            account(org, bad)
        assert error.value.code == "ledger.account.code_invalid"
    assert account(org, " 6110 ").code == "6110"  # trimmed


# ---- database constraints on type, role, bank ----------------------------------------------


@pytest.mark.parametrize(
    ("fields", "constraint"),
    [
        ({"type": "revenue", "subtype": "prepayment"}, "ledger_account_subtype_in_type"),
        (
            {"type": "asset", "subtype": "bank", "is_bank": False},
            "ledger_account_bank_subtype_is_bank",
        ),
        (
            {"type": "expense", "subtype": "operating_expense", "is_bank": True},
            "ledger_account_is_bank_subtype",
        ),
        (
            {"type": "expense", "subtype": "operating_expense", "system_role": "nope"},
            "ledger_account_system_role_valid",
        ),
        (
            {"type": "expense", "subtype": "operating_expense", "status": "gone"},
            "ledger_account_status_valid",
        ),
    ],
)
def test_database_refuses_inconsistent_rows(
    org: Organisation, fields: dict[str, object], constraint: str
) -> None:
    row = Account(organisation=org, code="9999", name_i18n={"en-ca": "x"}, **fields)
    with pytest.raises(IntegrityError) as error, transaction.atomic():
        Account._base_manager.bulk_create([row])
    assert constraint in str(error.value)


def test_one_account_per_system_role_in_the_database(org: Organisation) -> None:
    account(org, "1100", "Accounts receivable", "current_asset", system_role="ar")
    with pytest.raises(IntegrityError), transaction.atomic():
        Account._base_manager.bulk_create(
            [
                Account(
                    organisation=org,
                    code="1101",
                    name_i18n={"en-ca": "AR 2"},
                    type="asset",
                    subtype="current_asset",
                    system_role="ar",
                )
            ]
        )


# ---- model rules -------------------------------------------------------------------------


def test_type_follows_subtype_and_mismatch_refused(org: Organisation) -> None:
    item = Account(organisation=org, code="1010", name_i18n={"en-ca": "Chequing"}, subtype="bank")
    item.save()
    assert item.type == "asset"
    assert item.is_bank is True  # every Bank account is a bank account
    item.type = "expense"
    with pytest.raises(LedgerError) as error:
        item.save()
    assert error.value.code == "ledger.account.subtype_type_mismatch"


def test_liabilities_may_be_bank_accounts_expenses_may_not(org: Organisation) -> None:
    card = account(org, "2400", "Credit card", "current_liability", is_bank=True)
    assert card.is_bank
    with pytest.raises(LedgerError) as error:
        account(org, "6000", "Advertising", is_bank=True)
    assert error.value.code == "ledger.account.bank_subtype"


def test_name_per_language_with_english_fallback(org: Organisation) -> None:
    item = account(org, "1010", "Chequing account", "bank")
    assert item.name == "Chequing account"
    with translation.override("fr-ca"):
        assert item.name == "Chequing account"  # no French name yet: English
        item.set_name("Compte chèques", "fr-ca")
        item.save()
        assert item.name == "Compte chèques"
    assert item.name == "Chequing account"
    assert str(item) == "1010 · Chequing account"


def test_name_required_and_limited(org: Organisation) -> None:
    with pytest.raises(LedgerError) as error:
        account(org, "6100", " ")
    assert error.value.code == "ledger.account.name_required"
    with pytest.raises(LedgerError) as error:
        account(org, "6100", "x" * 151)
    assert error.value.code == "ledger.account.name_too_long"


def test_flags_and_defaults(org: Organisation) -> None:
    item = account(
        org,
        "6010",
        "Meals and entertainment",
        require_contact=True,
        require_tracking=True,
        require_attachment=True,
        default_tax_key="purchase.ON.standard.itc50",
    )
    item.refresh_from_db()
    assert (item.require_contact, item.require_tracking, item.require_attachment) == (
        True,
        True,
        True,
    )
    assert item.default_tax_key == "purchase.ON.standard.itc50"
    assert item.status == AccountStatus.ACTIVE
    assert item.normal_side == "debit"
    contra = account(org, "1611", "Accum. amortization", "accumulated_amortisation")
    assert contra.normal_side == "credit"


# ---- GIFI validation ---------------------------------------------------------------------


def test_gifi_must_be_on_the_list_not_a_total_and_fit_the_type(org: Organisation) -> None:
    mapped = account(org, "6080", "Office supplies", gifi_id="8811").gifi
    assert mapped is not None and mapped.description == "Office stationery and supplies"
    cases = [
        ("1234", "ledger.account.gifi_unknown"),
        ("9367", "ledger.account.gifi_total"),  # Total operating expenses
        ("1001", "ledger.account.gifi_section"),  # Cash: an asset code on an expense
    ]
    for index, (code, expected) in enumerate(cases):
        with pytest.raises(LedgerError) as error:
            account(org, f"61{index}0", gifi_id=code)
        assert error.value.code == expected, code


# ---- audit -------------------------------------------------------------------------------


def test_every_save_is_audited(org: Organisation) -> None:
    item = account(org, "6100", "Office supplies", gifi_id="8811")
    item.set_name("Office supplies and postage")
    item.save()
    actions = list(
        AuditEvent.objects.filter(object_type="ledger.Account").values_list("action", flat=True)
    )
    assert actions == ["ledger.account.created", "ledger.account.updated"]
    updated = AuditEvent.objects.get(action="ledger.account.updated")
    assert updated.changes["name_i18n"][1] == {"en-ca": "Office supplies and postage"}

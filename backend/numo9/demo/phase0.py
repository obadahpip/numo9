"""Phase 0 seeders (U-07-T04): organisation settings, the chart of accounts, contacts, opening
balances. Each builds its part of ``demo_seed_v1.json`` through the module's own services and
model saves, so the seeded organisation passes every rule a real one does — and its trial
balance is zero (checked by tests/test_demo_phase0_seed.py in CI).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal

from numo9.contacts.models import Address, Contact, ContactPerson
from numo9.ledger.models import Account
from numo9.ledger.services import post_journal
from numo9.ledger.template import load_template
from numo9.ledger.validation import JournalSpec, LineSpec
from numo9.orgsettings.models import RegistrationType, TaxRegistration
from numo9.orgsettings.service import get_settings

from .seeders import SeedContext, Seeder, register


def seed_settings(ctx: SeedContext) -> None:
    company = ctx.seed["company"]
    settings = get_settings(ctx.organisation)
    settings.display_name = company["name"]
    settings.legal_name = company["legal_name"]
    settings.industry = company["industry"]
    settings.structure = company["structure"]
    settings.mailing_line1 = company["line1"]
    settings.mailing_city = company["city"]
    settings.mailing_province = company["province"]
    settings.mailing_postal_code = company["postal_code"]
    settings.phone = company["phone"]
    settings.email = company["email"]
    settings.website = company["website"]
    settings.fye_month = company["fye_month"]
    settings.fye_day = company["fye_day"]
    settings.time_zone = company["time_zone"]
    settings.save()
    TaxRegistration(
        organisation=ctx.organisation, type=RegistrationType.BN, number=company["bn"]
    ).save()


def seed_chart(ctx: SeedContext) -> None:
    chart = ctx.seed["chart"]
    accounts = load_template(ctx.organisation, chart["province"], template=chart["template"])
    ctx.refs["accounts"] = {account.code: account for account in accounts}


def seed_contacts(ctx: SeedContext) -> None:
    made: dict[str, Contact] = {}
    for row in ctx.seed["contacts"]:
        contact = Contact(
            organisation=ctx.organisation,
            display_name=row["display_name"],
            roles=list(row["roles"]),
            bn=row["bn"],
            currency=row["currency"],
        )
        contact.save()
        address = row["address"]
        Address(
            organisation=ctx.organisation,
            contact=contact,
            kind=address["kind"],
            line1=address["line1"],
            city=address["city"],
            province=address["province"],
            postal_code=address["postal_code"],
            country=address["country"],
        ).save()
        person = row["person"]
        if any(person.values()):
            ContactPerson(
                organisation=ctx.organisation,
                contact=contact,
                first_name=person["first_name"],
                last_name=person["last_name"],
                email=person["email"],
                phone=person["phone"],
            ).save()
        made[row["key"]] = contact
    ctx.refs["contacts"] = made


def seed_opening_balances(ctx: SeedContext) -> None:
    opening = ctx.seed["opening_balances"]
    accounts: dict[str, Account] = ctx.refs["accounts"]
    contacts: dict[str, Contact] = ctx.refs["contacts"]
    lines = [
        LineSpec(
            account=accounts[row["account"]],
            debit=Decimal(row.get("debit", "0")),
            credit=Decimal(row.get("credit", "0")),
            contact=contacts[row["contact"]] if row.get("contact") else None,
        )
        for row in opening["lines"]
    ]
    post_journal(
        JournalSpec(
            date=dt.date.fromisoformat(opening["date"]),
            narration=opening["narration"],
            lines=lines,
        ),
        organisation=ctx.organisation,
        user=None,
    )


register(
    Seeder(
        "settings",
        seed_settings,
        models=(
            "orgsettings.OrganisationSettings",
            "orgsettings.TaxRegistration",
            "orgsettings.NumberingSequence",
        ),
    )
)
register(Seeder("chart", seed_chart, after=("settings",), models=("ledger.Account",)))
register(
    Seeder(
        "contacts",
        seed_contacts,
        after=("settings", "chart"),
        models=(
            "contacts.PaymentTerm",
            "contacts.Contact",
            "contacts.Address",
            "contacts.ContactPerson",
        ),
    )
)
register(
    Seeder(
        "opening_balances",
        seed_opening_balances,
        after=("chart", "contacts"),
        models=("ledger.JournalSequence", "ledger.JournalEntry", "ledger.JournalLine"),
    )
)

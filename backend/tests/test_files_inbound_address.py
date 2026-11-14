"""A-06-T06 — per-organisation inbound address (docs+<token>@in.<domain>), rotate.

Acceptance: unique per organisation. Also: format and alphabet; created once on first use; one
active address per organisation (database); rotating gives a new token and the old one keeps
routing for 7 days; routing is case-insensitive and refuses other domains, other local parts and
unknown tokens; API (view needs upload permission, rotate needs manage); audit.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.audit.models import AuditEvent
from numo9.files import inbound
from numo9.files.models import TOKEN_ALPHABET, InboundAddress, InboundAddressStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember, OrganisationRole
from tests.files_helpers import api, owner_of

pytestmark = pytest.mark.django_db

ADDRESS = re.compile(rf"^docs\+[{TOKEN_ALPHABET}]{{12}}@in\.numo9\.ca$")


@pytest.fixture
def org() -> Organisation:
    return Organisation.objects.create(name="Maple Leaf Supply Ltd.")


# ---- acceptance -------------------------------------------------------------------------------


def test_every_organisation_has_its_own_address() -> None:
    orgs = [Organisation.objects.create(name=f"Org {i}") for i in range(25)]
    addresses = [inbound.inbound_address(o).address for o in orgs]
    assert len(set(addresses)) == 25
    assert all(ADDRESS.match(a) for a in addresses)
    for address, organisation in zip(addresses, orgs, strict=True):
        routed = inbound.resolve(address)
        assert routed is not None and routed.organisation_id == organisation.pk


def test_the_address_is_created_once(org: Organisation) -> None:
    first = inbound.inbound_address(org)
    assert inbound.inbound_address(org).pk == first.pk
    assert InboundAddress._base_manager.filter(organisation=org).count() == 1


def test_one_active_address_per_organisation_and_unique_tokens(org: Organisation) -> None:
    first = inbound.inbound_address(org)
    with pytest.raises(IntegrityError), transaction.atomic():
        InboundAddress._base_manager.create(organisation=org, token=inbound.new_token())
    other = Organisation.objects.create(name="Northern Lights Ltd.")
    with pytest.raises(IntegrityError), transaction.atomic():
        InboundAddress._base_manager.create(organisation=other, token=first.token)


# ---- rotation and routing -----------------------------------------------------------------------


def test_rotating_retires_the_old_address_for_seven_days(org: Organisation) -> None:
    old = inbound.inbound_address(org)
    new = inbound.rotate(org)
    assert new.token != old.token and new.status == InboundAddressStatus.ACTIVE
    old.refresh_from_db()
    assert old.status == InboundAddressStatus.RETIRED and old.retired_at is not None
    assert inbound.resolve(old.address).pk == old.pk  # type: ignore[union-attr]
    later = timezone.now() + timedelta(days=7, minutes=1)
    with mock.patch("numo9.files.inbound.timezone.now", return_value=later):
        assert inbound.resolve(old.address) is None
        assert inbound.resolve(new.address).pk == new.pk  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "recipient",
    [
        "docs+{t}@in.numo9.ca.evil",
        "docs+{t}@numo9.ca",
        "bills+{t}@in.numo9.ca",
        "docs+zzzzzzzzzzzz@in.numo9.ca",
        "",
        "docs+@in.numo9.ca",
    ],
)
def test_routing_refuses_what_isnt_an_inbox_address(org: Organisation, recipient: str) -> None:
    token = inbound.inbound_address(org).token
    assert inbound.resolve(recipient.format(t=token)) is None


def test_routing_ignores_case_and_spaces(org: Organisation) -> None:
    address = inbound.inbound_address(org)
    assert inbound.resolve(f"  {address.address.upper()} ").pk == address.pk  # type: ignore[union-attr]


# ---- API ----------------------------------------------------------------------------------------


def test_api_shows_and_rotates_the_address(org: Organisation) -> None:
    client = api(owner_of(org))
    url = f"/api/v1/o/{org.public_id}/files/inbound-address"
    shown = client.get(url).json()
    assert ADDRESS.match(shown["address"]) and shown["previous"] is None
    rotated = client.post(url + "/rotate").json()
    assert rotated["address"] != shown["address"]
    assert rotated["previous"]["address"] == shown["address"]
    with org_context(org):
        actions = list(
            AuditEvent.objects.filter(object_type="files.InboundAddress")
            .order_by("id")
            .values_list("action", flat=True)
        )
    assert actions == [
        "files.inboundaddress.created",
        "files.inboundaddress.updated",
        "files.inboundaddress.created",
    ]


def test_rotating_needs_the_manage_permission(org: Organisation) -> None:
    from numo9.accounts.models import User

    sales = User.objects.create_user(email="sam@maple.ca", password="x" * 12, name="Sam")
    OrganisationMember.objects.create(organisation=org, user=sales, role=OrganisationRole.SALES)
    client: Any = api(sales)
    response = client.post(f"/api/v1/o/{org.public_id}/files/inbound-address/rotate")
    assert response.status_code == 403

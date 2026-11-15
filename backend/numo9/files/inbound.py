"""Per-organisation inbound email address (A-06-T06) and routing.

    address = inbound_address(org).address      # "docs+k7m3qv9p2xwa@in.numo9.ca"
    rotate(org)                                   # new address; the old one works 7 more days
    resolve("Docs+K7M3QV9P2XWA@in.numo9.ca")      # → the InboundAddress, or None

The address is ``docs+<token>@<NUMO9_INBOUND_DOMAIN>``: the provider receives every mail for the
domain (MX of ``in.``, S-02-T07) and the token after ``+`` routes it to one organisation. Tokens are
12 characters from an alphabet without look-alikes, random (``secrets``), unique across Numo9.
"""

from __future__ import annotations

import re
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from numo9.tenancy.models import Organisation

from .models import TOKEN_ALPHABET, TOKEN_LENGTH, InboundAddress, InboundAddressStatus

#: Mail to a rotated (retired) address is accepted this long after the rotation.
RETIRED_GRACE = timedelta(days=7)
LOCAL_PART = re.compile(r"^docs\+([a-z0-9]+)$")


def new_token() -> str:
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


def _active(organisation: Organisation) -> InboundAddress | None:
    found: InboundAddress | None = InboundAddress._base_manager.filter(
        organisation=organisation, status=InboundAddressStatus.ACTIVE
    ).first()
    return found


def _create(organisation: Organisation, user: Any = None) -> InboundAddress:
    for _attempt in range(5):
        address = InboundAddress(organisation=organisation, token=new_token(), created_by=user)
        try:
            with transaction.atomic():
                address.save()
        except IntegrityError:  # token taken (astronomically rare) or a concurrent first use
            existing = _active(organisation)
            if existing is not None:
                return existing
            continue
        return address
    raise RuntimeError("Could not create an inbound address.")  # pragma: no cover


def inbound_address(organisation: Organisation) -> InboundAddress:
    """The organisation's active address, created on first use."""
    return _active(organisation) or _create(organisation)


def rotate(organisation: Organisation, user: Any = None) -> InboundAddress:
    """Retire the active address (accepted 7 more days) and make a new one."""
    with transaction.atomic():
        current = (
            InboundAddress._base_manager.select_for_update()
            .filter(organisation=organisation, status=InboundAddressStatus.ACTIVE)
            .first()
        )
        if current is not None:
            current.status = InboundAddressStatus.RETIRED
            current.retired_at = timezone.now()
            current.save(update_fields=["status", "retired_at", "updated_at"])
        return _create(organisation, user)


def resolve(recipient: str) -> InboundAddress | None:
    """The address a recipient routes to: active, or retired less than 7 days ago."""
    local, _, domain = (recipient or "").strip().lower().rpartition("@")
    if domain != settings.NUMO9_INBOUND_DOMAIN.lower():
        return None
    match = LOCAL_PART.match(local)
    if match is None:
        return None
    address: InboundAddress | None = (
        InboundAddress._base_manager.select_related("organisation")
        .filter(token=match.group(1))
        .first()
    )
    if address is None:
        return None
    if address.status == InboundAddressStatus.RETIRED and (
        address.retired_at is None or timezone.now() - address.retired_at > RETIRED_GRACE
    ):
        return None
    return address

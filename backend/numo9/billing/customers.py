"""One Stripe customer per organisation (U-04-T04): ``ensure_customer(organisation)``.

The customer is the **organisation** — never a user or a practice (accountants are never
billed). Its id is kept on the organisation's current ``Subscription``
(``stripe_customer_id``); the customer's metadata name the organisation (``numo9_org``: its public
id) so a webhook can find it. ``ensure_customer``:

- returns the stored id when there is one (a second call never creates a second customer);
- otherwise creates the customer — name: the organisation's name, email: its owner's — with the
  idempotency key ``numo9-customer-<org public id>`` (a retried request returns the same customer
  at Stripe) and stores the id;
- runs under a row lock on the subscription, so two first calls at once create one customer.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction

from numo9.entitlements.models import Subscription, current_subscription
from numo9.i18n import errors
from numo9.i18n.errors import api_error
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation, OrganisationMember

from .gateway import BillingGateway, get_gateway

METADATA_KEY = "numo9_org"


def owner_email(organisation: Organisation) -> str:
    owner = (
        OrganisationMember.objects.filter(organisation=organisation, role="owner")
        .select_related("user")
        .order_by("pk")
        .first()
    )
    return owner.user.email if owner is not None else ""


def locked_subscription(organisation: Organisation) -> Subscription:
    """The organisation's current subscription under a row lock (in a transaction)."""
    current = current_subscription(organisation)
    if current is None:
        raise api_error(errors.BILLING_NO_SUBSCRIPTION)
    locked: Subscription = Subscription._base_manager.select_for_update().get(pk=current.pk)
    return locked


def ensure_customer(organisation: Organisation, gateway: BillingGateway | None = None) -> str:
    """The organisation's Stripe customer id, created once."""
    with org_context(organisation), transaction.atomic():
        subscription = locked_subscription(organisation)
        if subscription.stripe_customer_id:
            return subscription.stripe_customer_id
        gateway = gateway or get_gateway()
        customer = gateway.create_customer(
            name=organisation.name,
            email=owner_email(organisation),
            metadata={METADATA_KEY: str(organisation.public_id)},
            idempotency_key=f"numo9-customer-{organisation.public_id}",
        )
        subscription.stripe_customer_id = customer
        subscription.save(update_fields=["stripe_customer_id", "updated_at"])
        return customer


def organisation_of_customer(customer: str) -> Organisation | None:
    """The organisation whose subscription holds the Stripe customer id."""
    row: Any = (
        Subscription._base_manager.filter(stripe_customer_id=customer, deleted_at__isnull=True)
        .select_related("organisation")
        .order_by("-created_at")
        .first()
    )
    return row.organisation if row is not None else None

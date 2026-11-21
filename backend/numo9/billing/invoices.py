"""Invoice events → the platform invoice mirror and the receipt (U-04-T08).

Handlers of ``invoice.finalized``, ``invoice.paid`` and ``invoice.payment_failed``. Each upserts
the ``PlatformInvoice`` of the Stripe invoice (``stripe_invoice_id``) for the organisation of its
customer — number, status, amounts, period, issue and payment times, hosted page and PDF links,
attempts — so the local rows are exactly Stripe's invoices. An event older than the last one
applied to the invoice changes nothing (Stripe's ``created``; out of order, U-04-T15).

- ``invoice.paid`` — the organisation's owner gets a **receipt** (notification
  ``billing.receipt``, category Billing: in the app and by email), once per invoice; a renewal
  paid after a failure brings the subscription back to active (the dunning stops).
- ``invoice.paid`` with money paid (not a trial's $0 invoice) is also the organisation's **first
  successful payment** for the founding offer (U-08-T03): the slot is allocated in this event's
  transaction, so a rolled-back event takes it back and a replayed one finds the slot held.
- ``charge.refunded`` — a refunded first payment releases the founding slot when the refund came
  within the configured window (``FoundingCounter.refund_release_hours``, U-08-T06).
- ``invoice.payment_failed`` — the subscription goes past due with its 7-day grace (if the
  subscription event hasn't done it yet) and the dunning starts (U-04-T09).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from django.utils import timezone

from numo9.documents.formatting import format_money
from numo9.entitlements.models import Subscription, SubscriptionStatus
from numo9.founding.services import allocate_founding_slot
from numo9.tenancy.context import org_context
from numo9.tenancy.models import OrganisationMember

from .customers import METADATA_KEY
from .models import PlatformInvoice, PlatformInvoiceStatus, StripeEvent
from .processing import register_handler
from .subscriptions import apply_status, earlier_failure, find_subscription, is_newer, stamp


def _ts(value: Any) -> dt.datetime | None:
    if value in (None, "", 0):
        return None
    return dt.datetime.fromtimestamp(int(value), tz=dt.UTC)


def _period(obj: dict[str, Any]) -> tuple[dt.datetime | None, dt.datetime | None]:
    lines = ((obj.get("lines") or {}).get("data")) or []
    period = (lines[0].get("period") if lines else None) or {}
    start = _ts(period.get("start")) or _ts(obj.get("period_start"))
    end = _ts(period.get("end")) or _ts(obj.get("period_end"))
    return start, end


def _subscription_id(obj: dict[str, Any]) -> str:
    direct = obj.get("subscription")
    if isinstance(direct, str) and direct:
        return direct
    parent = ((obj.get("parent") or {}).get("subscription_details")) or {}
    return str(parent.get("subscription") or "")


def mirror(event: StripeEvent) -> tuple[PlatformInvoice, Subscription]:
    obj = event.data_object
    metadata = obj.get("metadata") or {}
    subscription = find_subscription(
        subscription_id=_subscription_id(obj),
        customer=str(obj.get("customer") or ""),
        organisation_id=str(metadata.get(METADATA_KEY, "")),
    )
    organisation = subscription.organisation
    with org_context(organisation):
        invoice = (
            PlatformInvoice.objects.select_for_update()
            .filter(stripe_invoice_id=str(obj["id"]))
            .first()
        ) or PlatformInvoice(organisation=organisation, stripe_invoice_id=str(obj["id"]))
        if invoice.stripe_event_created and invoice.stripe_event_created > event.stripe_created:
            return invoice, subscription
        start, end = _period(obj)
        status = str(obj.get("status") or "")
        invoice.number = str(obj.get("number") or invoice.number)
        if status in PlatformInvoiceStatus.values:
            invoice.status = status
        invoice.currency = str(obj.get("currency") or "cad").upper()
        invoice.subtotal_cents = int(obj.get("subtotal") or 0)
        invoice.total_cents = int(obj.get("total") or 0)
        invoice.tax_cents = invoice.total_cents - int(
            obj.get("total_excluding_tax") or invoice.subtotal_cents
        )
        invoice.amount_paid_cents = int(obj.get("amount_paid") or 0)
        invoice.amount_due_cents = int(obj.get("amount_due") or 0)
        invoice.period_start, invoice.period_end = start, end
        invoice.issued_at = _ts((obj.get("status_transitions") or {}).get("finalized_at")) or _ts(
            obj.get("created")
        )
        invoice.paid_at = _ts((obj.get("status_transitions") or {}).get("paid_at"))
        invoice.attempt_count = int(obj.get("attempt_count") or 0)
        invoice.next_attempt_at = _ts(obj.get("next_payment_attempt"))
        invoice.hosted_url = str(obj.get("hosted_invoice_url") or "")
        invoice.pdf_url = str(obj.get("invoice_pdf") or "")
        invoice.stripe_subscription_id = _subscription_id(obj)
        invoice.stripe_event_created = event.stripe_created
        invoice.save()
    StripeEvent.objects.filter(pk=event.pk).update(organisation_id=organisation.pk)
    return invoice, subscription


def _owners(subscription: Subscription) -> list[Any]:
    return [
        m.user
        for m in OrganisationMember.objects.filter(
            organisation_id=subscription.organisation_id, role="owner"
        ).select_related("user")
    ]


@register_handler("invoice.finalized")
def on_invoice_finalized(event: StripeEvent) -> PlatformInvoice:
    return mirror(event)[0]


@register_handler("invoice.paid")
def on_invoice_paid(event: StripeEvent) -> PlatformInvoice:
    from numo9.notifications.services import notify

    invoice, subscription = mirror(event)
    if invoice.status == PlatformInvoiceStatus.PAID and invoice.amount_paid_cents > 0:
        allocate_founding_slot(subscription.organisation, payment_ref=invoice.stripe_invoice_id)
    if is_newer(subscription, event.stripe_created, SubscriptionStatus.ACTIVE):
        # A paid invoice says "active" at that moment, even when nothing changes now.
        if subscription.status in (
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE,
            SubscriptionStatus.READ_ONLY,
        ):
            apply_status(subscription, "active", event.stripe_created)
        stamp(subscription, event.stripe_created)
        subscription.save()
    if invoice.receipt_sent_at is None and invoice.status == PlatformInvoiceStatus.PAID:
        organisation = subscription.organisation
        notify(
            "billing.receipt",
            _owners(subscription),
            organisation=organisation,
            params={
                "organisation": organisation.name,
                "number": invoice.number,
                "amount": format_money(Decimal(invoice.amount_paid_cents) / 100),
            },
            link=f"/o/{organisation.public_id}/settings/subscription",
        )
        with org_context(organisation):
            PlatformInvoice.objects.filter(pk=invoice.pk).update(receipt_sent_at=timezone.now())
    return invoice


@register_handler("invoice.payment_failed")
def on_invoice_payment_failed(event: StripeEvent) -> PlatformInvoice:
    from .dunning import start_dunning

    invoice, subscription = mirror(event)
    if is_newer(subscription, event.stripe_created, SubscriptionStatus.PAST_DUE):
        if subscription.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING):
            apply_status(subscription, "past_due", event.stripe_created)
        stamp(subscription, event.stripe_created)
        subscription.save()
    elif subscription.status == SubscriptionStatus.PAST_DUE:
        earlier_failure(subscription, event.stripe_created)
        subscription.save()
    start_dunning(subscription, invoice)
    return invoice


@register_handler("charge.refunded")
def on_charge_refunded(event: StripeEvent) -> Any:
    """A refunded first payment releases the founding slot within the release window (U-08)."""
    from numo9.founding.services import on_refund

    from .customers import organisation_of_customer

    obj = event.data_object
    organisation = organisation_of_customer(str(obj.get("customer") or ""))
    if organisation is None or not obj.get("refunded"):
        return None
    StripeEvent.objects.filter(pk=event.pk).update(organisation_id=organisation.pk)
    return on_refund(organisation, str(obj.get("invoice") or ""), event.stripe_created)

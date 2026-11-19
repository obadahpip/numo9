"""What a demo organisation is kept out of (U-07-T07).

- **Platform metrics** — ``numo9.platform.metrics`` leaves out organisations with status demo
  and demo subscriptions (U-06); demo organisations always have status demo.
- **The founding offer** — ``founding_eligible`` is the gate U-08 calls before allocating a slot.
- **Stripe** — ``billing.customers.ensure_customer`` refuses a demo (``billing.demo``, 409): no
  customer, no checkout, no invoice.
- **Real email** — ``notifications.mail.queue_email`` keeps a demo's emails in ``DemoOutbox``
  (shown in the demo bar's outbox) and queues no send task: no SMTP or provider call.
"""

from __future__ import annotations

from numo9.tenancy.models import Organisation, OrganisationStatus


def is_demo(organisation: Organisation) -> bool:
    return bool(organisation.is_demo or organisation.status == OrganisationStatus.DEMO)


def founding_eligible(organisation: Organisation) -> bool:
    """A demo (and its template) never takes a founding slot."""
    return not is_demo(organisation)

"""U-07-T07 — exclusions: metrics, founding, Stripe, real email.

Acceptance (integration): a demo organisation's email lands in its DemoOutbox and no SMTP /
provider call is made (the send task is never queued, the locmem outbox stays empty); a demo is
not founding-eligible; ensure_customer refuses a demo before calling the gateway; platform
metrics leave demos out.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core import mail
from django.test import override_settings

from numo9.billing.customers import ensure_customer
from numo9.demo.cloning import create_demo
from numo9.demo.exclusions import founding_eligible
from numo9.demo.models import DemoOutbox
from numo9.notifications.mail import queue_email
from numo9.notifications.models import EmailMessage, EmailStatus
from numo9.tenancy.context import org_context
from numo9.tenancy.models import Organisation

pytestmark = pytest.mark.django_db


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_demo_email_goes_to_the_outbox_never_out(
    django_capture_on_commit_callbacks: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    demo = create_demo()
    sent: list[Any] = []
    monkeypatch.setattr(
        "numo9.notifications.mail.send_email.apply_async", lambda *a, **k: sent.append(a)
    )
    with django_capture_on_commit_callbacks(execute=True), org_context(demo):
        message = queue_email(
            "priya@lakeshorehw.example",
            "Statement from Maple & Pine Supply Co.",
            "Your statement is attached.",
            organisation=demo,
            kind="statement",
        )
    assert sent == [] and mail.outbox == []
    assert message.status == EmailStatus.FAILED and "demo outbox" in message.error
    with org_context(demo):
        kept = DemoOutbox.objects.get()
        assert (kept.to_email, kept.kind) == ("priya@lakeshorehw.example", "statement")
        assert kept.subject == "Statement from Maple & Pine Supply Co."
        assert EmailMessage.objects.count() == 1


def test_real_organisation_email_is_queued(
    django_capture_on_commit_callbacks: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = Organisation.objects.create(name="Real Ltd.")
    sent: list[Any] = []
    monkeypatch.setattr(
        "numo9.notifications.mail.send_email.apply_async", lambda *a, **k: sent.append(a)
    )
    with django_capture_on_commit_callbacks(execute=True), org_context(real):
        queue_email("a@real.example", "Hello", "Hi", organisation=real)
    assert len(sent) == 1
    assert not DemoOutbox._base_manager.exists()


def test_demo_is_not_founding_eligible() -> None:
    assert not founding_eligible(create_demo())
    assert founding_eligible(Organisation.objects.create(name="Real Ltd."))


def test_no_stripe_customer_for_a_demo() -> None:
    class Gateway:
        def create_customer(self, **kwargs: Any) -> str:  # pragma: no cover — must not run
            raise AssertionError("Stripe called for a demo")

    demo = create_demo()
    with pytest.raises(Exception) as caught:
        ensure_customer(demo, Gateway())  # type: ignore[arg-type]
    assert "demo" in str(caught.value).lower()


def test_metrics_leave_demos_out() -> None:
    from numo9.platform import metrics

    create_demo()
    source = metrics.__doc__ or ""
    assert "leaves demo organisations out" in source

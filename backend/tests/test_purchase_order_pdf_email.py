"""E-01-T09 — PO PDF and email to the supplier: Letter pages; the buyer's GST/HST number, the
supplier, number, delivery block, lines and tax per component; the text matches the snapshot;
"Draft" before approval; emailing attaches the PDF (one email per recipient), keeps the first
sent time and is audited; a draft can't be sent.
"""

from __future__ import annotations

import datetime as dt
import io
import os
import re
from pathlib import Path
from typing import Any
from unittest import mock

import pypdf
import pytest
from django.core import mail

from numo9.audit.models import AuditEvent
from numo9.contacts.models import ContactPerson
from numo9.documents.pdf import LETTER_POINTS
from numo9.files.storage import open_object
from numo9.notifications import mail as outgoing
from numo9.notifications.models import EmailMessage
from numo9.orgsettings.models import TaxRegistration
from numo9.orgsettings.service import get_settings
from numo9.purchases.approvals import PurchaseOrderRefused, approve
from numo9.purchases.email import send_purchase_order
from numo9.purchases.pdf import purchase_order_context, render_purchase_order_pdf
from numo9.tenancy.context import org_context
from tests.purchase_helpers import po, purchase_books

pytestmark = pytest.mark.django_db
SNAPSHOT = Path(__file__).parent / "snapshots" / "purchase_order_pdf.txt"


@pytest.fixture
def books() -> dict[str, Any]:
    books = purchase_books()
    org = books["org"]
    with org_context(org):
        settings = get_settings(org)
        settings.legal_name = "Refined Interiors Inc."
        settings.mailing_line1 = "200 King Street West, Suite 1200"
        settings.mailing_city, settings.mailing_province = "Toronto", "ON"
        settings.mailing_postal_code = "M5V 2T6"
        settings.save()
        TaxRegistration(
            organisation=org,
            type="rt",
            number="123456782RT0001",
            effective_from=dt.date(2020, 1, 1),
        ).save()
        ContactPerson.objects.create(
            organisation=org,
            contact=books["supplier"],
            first_name="Ana",
            email="orders@cedar.ca",
            include_in_emails=True,
            is_primary=True,
        )
    return books


@pytest.fixture
def captured() -> Any:
    sent: list[Any] = []
    with mock.patch.object(
        outgoing.send_email, "apply_async", lambda args=None, **kw: sent.append(args)
    ):
        yield sent


def text_of(pdf: bytes) -> str:
    reader = pypdf.PdfReader(io.BytesIO(pdf))
    for page in reader.pages:
        assert (float(page.mediabox.width), float(page.mediabox.height)) == LETTER_POINTS
    raw = "\n".join(page.extract_text() for page in reader.pages)
    return "\n".join(
        line.rstrip() for line in re.sub(r"[ \t]+", " ", raw).splitlines() if line.strip()
    )


def squeezed(text: str) -> str:
    return re.sub(r"\s+", "", text.replace("\xa0", " "))


def approved(books: dict[str, Any]) -> Any:
    order = po(
        books,
        [("10", "25.00"), ("2", "80.00")],
        tax="purchase.ON.standard",
        delivery_address="200 King Street West, Loading dock B\nToronto ON M5V 2T6",
        delivery_attention="Receiving",
        delivery_date=dt.date(2026, 6, 29),
        delivery_instructions="Weekdays 8–4 only.",
        notes="Quote Q-1182 prices apply.",
    )
    return approve(order, books["owner"])


@pytest.mark.gap("gap-43")
def test_po_pdf_matches_the_snapshot(books: dict[str, Any]) -> None:
    text = text_of(render_purchase_order_pdf(approved(books)))
    for expected in (
        "Purchase order",
        "PO number PO-0001",
        "GST/HST registration: 123456782 RT 0001",
        "Cedar Supply Co.",
        "Deliver to",
        "Attention: Receiving",
        "Weekdays 8–4 only.",
        "Quote Q-1182 prices apply.",
    ):
        assert expected in text, expected
    assert re.search(r"HST.*\$53\.30", text)  # (250 + 160) × 13 %
    assert "$463.30" in text
    if os.environ.get("NUMO9_UPDATE_SNAPSHOTS") or not SNAPSHOT.exists():
        SNAPSHOT.write_text(text + "\n", encoding="utf-8")
    assert squeezed(text) == squeezed(SNAPSHOT.read_text(encoding="utf-8"))


def test_draft_says_draft(books: dict[str, Any]) -> None:
    assert purchase_order_context(po(books, [("1", "10.00")]))["document_number"] == "Draft"


def test_email_to_the_supplier(
    books: dict[str, Any], s3: str, captured: list[Any], django_capture_on_commit_callbacks: Any
) -> None:
    order = approved(books)
    with org_context(books["org"]), django_capture_on_commit_callbacks(execute=True):
        [message] = send_purchase_order(order, books["owner"])
    assert message.to_email == "orders@cedar.ca"
    assert message.subject == "Purchase order PO-0001 from Refined Interiors Inc."
    assert "Total: $463.30 CAD" in message.text_body
    with org_context(books["org"]):
        order.refresh_from_db()
        first = order.sent_at
        assert first is not None
        event = AuditEvent.objects.get(action="purchases.purchaseorder.sent")
        assert event.meta["recipients"] == ["orders@cedar.ca"]
        send_purchase_order(order, books["owner"], to=["boss@cedar.ca"])
        order.refresh_from_db()
        assert order.sent_at == first
    outgoing.send_email.apply(args=[message.pk])
    [email] = mail.outbox
    [(name, content, mime)] = email.attachments
    assert (name, mime) == ("purchase-order-PO-0001.pdf", "application/pdf")
    assert content == open_object(event.meta["file_key"]).read()
    assert EmailMessage.platform_messages.filter(kind="purchases.purchase_order").count() == 2


def test_draft_is_not_sent(books: dict[str, Any], s3: str) -> None:
    with org_context(books["org"]), pytest.raises(PurchaseOrderRefused) as refused:
        send_purchase_order(po(books, [("1", "10.00")]), books["owner"])
    assert refused.value.code == "purchases.po.not_sendable"

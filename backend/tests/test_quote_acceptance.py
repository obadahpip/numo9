"""D-02-T07 — acceptance evidence: typed name, signature PNG, IP, browser, the options chosen and
the SHA-256 of the PDF as accepted; the stored PDF matches the hash; typed name alone is enough
(accessible); accepting twice keeps the first; an expired quote can't be accepted."""

from __future__ import annotations

import datetime as dt
import hashlib
from decimal import Decimal
from typing import Any

import pytest

from numo9.files.storage import open_object
from numo9.sales import quotes as q
from numo9.sales.quote_links import AcceptanceRefused, accept_with_evidence
from numo9.tenancy.context import org_context
from tests.quote_helpers import quote, sales_books

pytestmark = pytest.mark.django_db
TODAY = dt.date.today()
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def sent(books: dict[str, Any], **fields: Any) -> Any:
    return q.send(
        quote(
            books,
            [("1", "1000", "sales.ON.standard"), {"price": "200", "is_optional": True}],
            date=TODAY,
            expiry=TODAY + dt.timedelta(days=10),
            **fields,
        )
    )


def test_evidence_stored_and_hash_matches_the_pdf(s3: str) -> None:
    books = sales_books()
    item = sent(books)
    with org_context(books["org"]):
        optional = item.lines.get(is_optional=True)
    evidence = accept_with_evidence(
        item,
        typed_name="  Jordan Smith ",
        signature_png=PNG,
        selections={str(optional.public_id): True},
        ip="203.0.113.7",
        user_agent="Mozilla/5.0 (iPhone)",
    )
    item.refresh_from_db()
    assert item.status == "accepted" and item.total == Decimal("1330.00")  # 1000 + 13 % + 200
    assert (evidence.typed_name, evidence.ip, evidence.user_agent) == (
        "Jordan Smith",
        "203.0.113.7",
        "Mozilla/5.0 (iPhone)",
    )
    assert evidence.selections[str(optional.public_id)] is True
    handle = open_object(evidence.pdf_key)
    try:
        assert hashlib.sha256(handle.read()).hexdigest() == evidence.pdf_sha256
    finally:
        handle.close()
    signature = open_object(evidence.signature_key)
    try:
        assert signature.read() == PNG
    finally:
        signature.close()
    again = accept_with_evidence(item, typed_name="Someone else")
    assert again.pk == evidence.pk and again.typed_name == "Jordan Smith"


def test_typed_name_alone_rules_and_expiry(s3: str) -> None:
    books = sales_books()
    item = sent(books)
    with pytest.raises(AcceptanceRefused) as err:
        accept_with_evidence(item, typed_name="  ")
    assert err.value.code == "sales.quote.name_required"
    with pytest.raises(AcceptanceRefused) as err:
        accept_with_evidence(item, typed_name="Jo", signature_png=b"GIF89a")
    assert err.value.code == "sales.quote.signature_invalid"
    evidence = accept_with_evidence(item, typed_name="Jo Lee")
    assert evidence.signature_key == "" and len(evidence.pdf_sha256) == 64
    late = sent(books)
    with pytest.raises(q.QuoteRefused) as refused:
        accept_with_evidence(
            late, typed_name="Jo", now=dt.datetime.now(dt.UTC) + dt.timedelta(days=20)
        )
    assert refused.value.code == "sales.quote.expired"

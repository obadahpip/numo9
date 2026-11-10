"""Canadian sample data for document previews and tests (A-10-T16, gap-43).

Fictional Ontario business and customer: Toronto addresses with Province and Postal code, a
Business Number with its GST/HST program account, 13 % HST (Ontario) and CAD amounts. Never
NZ/US/UK sample data in previews.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

HST_RATE = Decimal("0.13")  # Ontario HST


def _line(description: str, quantity: str, unit: str) -> dict[str, Any]:
    qty, price = Decimal(quantity), Decimal(unit)
    return {
        "description": description,
        "quantity": qty,
        "unit": price,
        "amount": (qty * price).quantize(Decimal("0.01")),
    }


def sample_context() -> dict[str, Any]:
    lines = [
        _line("Bookkeeping — October 2026", "1", "850.00"),
        _line("GST/HST return preparation", "1", "275.00"),
        _line("Payroll run (bi-weekly)", "2", "62.50"),
    ]
    subtotal: Decimal = sum((line["amount"] for line in lines), Decimal("0.00"))
    tax = (subtotal * HST_RATE).quantize(Decimal("0.01"))
    return {
        "document_title_key": "sample",
        "document_number": "SMP-000123",
        "issue_date": dt.date(2026, 10, 26),
        "due_date": dt.date(2026, 11, 25),
        "issuer": {
            "legal_name": "Refined Interiors Inc.",
            "address_line": "200 King Street West, Suite 1200",
            "city": "Toronto",
            "province": "ON",
            "postal_code": "M5V 2T6",
            "business_number": "123456789RT0001",
            "phone": "416-555-0142",
            "email": "accounts@refined-interiors.example.ca",
        },
        "customer": {
            "legal_name": "Maple Leaf Supply Ltd.",
            "address_line": "45 Sparks Street",
            "city": "Ottawa",
            "province": "ON",
            "postal_code": "K1P 5A9",
        },
        "lines": lines,
        "subtotal": subtotal,
        "tax_label": "HST 13 % (ON)",
        "tax": tax,
        "total": subtotal + tax,
    }

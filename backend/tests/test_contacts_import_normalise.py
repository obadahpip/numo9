"""B-03-T04 — contact import row normaliser and validators.

Acceptance: invalid rows are reported with a reason. Province by code or English/French name,
Canadian postal codes in any spacing (other countries free), email, currency, roles in English or
French, credit mode, language, yes/no and amounts in both locales; blank cells are absent (never a
deletion), ``__CLEAR__`` clears what may be empty and is refused on required columns; each
problem names its column and a code.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from numo9.contacts.import_normalise import CLEAR, normalise_row


def test_values_are_typed() -> None:
    row = normalise_row(
        {
            "display_name": "  Maple Leaf Supply Ltd. ",
            "email": "Dana@MapleLeaf.ca",
            "currency": "usd",
            "roles": "Client; Fournisseur",
            "credit_limit": "1 234,50 $",
            "credit_mode": "Bloquer",
            "language": "French",
            "t4a_flag": "oui",
            "billing_province": "Québec",
            "billing_postal_code": "h2x1y4",
            "shipping_country": "US",
            "shipping_postal_code": "98101",
            "bn": "123 456 782",
        }
    )
    assert row.errors == []
    assert row.values == {
        "display_name": "Maple Leaf Supply Ltd.",
        "email": "dana@mapleleaf.ca",
        "currency": "USD",
        "roles": ["customer", "supplier"],
        "credit_limit": Decimal("1234.50"),
        "credit_mode": "block",
        "language": "fr-ca",
        "t4a_flag": True,
        "billing_province": "QC",
        "billing_postal_code": "H2X 1Y4",
        "shipping_country": "US",
        "shipping_postal_code": "98101",
        "bn": "123456782",
    }


def test_blank_is_absent_and_clear_token_clears() -> None:
    row = normalise_row({"legal_name": "", "tax_id": "__CLEAR__", "billing_line2": "  "})
    assert row.values == {"tax_id": CLEAR}


@pytest.mark.parametrize(
    ("cells", "column", "code"),
    [
        ({"billing_province": "Ontar"}, "billing_province", "contacts.import.province"),
        ({"billing_postal_code": "12345"}, "billing_postal_code", "contacts.import.postal_code"),
        ({"email": "dana at maple"}, "email", "contacts.import.email"),
        ({"currency": "dollars"}, "currency", "contacts.import.currency"),
        ({"roles": "customer, wholesaler"}, "roles", "contacts.import.role"),
        ({"credit_limit": "lots"}, "credit_limit", "contacts.import.amount"),
        ({"credit_mode": "maybe"}, "credit_mode", "contacts.import.credit_mode"),
        ({"t4a_flag": "perhaps"}, "t4a_flag", "contacts.import.yes_no"),
        ({"display_name": "__CLEAR__"}, "display_name", "contacts.import.required"),
    ],
)
def test_invalid_cells_are_reported_with_the_reason(
    cells: dict[str, str], column: str, code: str
) -> None:
    row = normalise_row(cells)
    assert [(e.field, e.code) for e in row.errors] == [(column, code)]
    assert row.errors[0].message

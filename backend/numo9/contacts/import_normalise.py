"""Contact import: one row's cells → typed values and the reasons a row is refused (B-03-T04).

``normalise_row(cells)`` turns the mapped cells of a contacts sheet into values the diff engine
(T06) can apply, and lists every problem with its column, a code and a plain message:

- a **blank** cell is absent (the field stays as it is — never a deletion, gap-21);
- ``__CLEAR__`` empties a field that may be empty (``CLEAR``); on a required field it's an error;
- **province**: code (``ON``) or name in English or French (``Ontario``, ``Québec``);
- **postal code**: ``A1A 1A1`` for Canada (any spacing or case in the file);
- **email**: one address; **currency**: ISO 4217 (``CAD``); **roles**: words in English or French
  separated by ``,`` ``;`` ``/`` or ``|`` (``Customer; Fournisseur``);
- **credit mode** (warn/block, avertir/bloquer), **language** (English/French, en/fr),
  **yes/no** (yes, y, true, 1, x, oui, o, vrai / no, n, false, 0, non, faux), **amounts**
  (``1,234.50``, ``1 234,50``, ``$1,234.50``).

Values are only checked here; the model's own rules (BN check digit, unique number…) run when a
row is applied, and their refusals land on the row too.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils.translation import gettext as _

from numo9.imports.report import CLEAR_TOKEN, RowError
from numo9.orgsettings.validators import Province

from .models import ContactRole, CreditMode, StatementPreference


class _Clear:
    def __repr__(self) -> str:
        return "CLEAR"


#: The value of a cleared field (``__CLEAR__`` in the file).
CLEAR: Any = _Clear()

REQUIRED = frozenset({"display_name"})
TEXT = ("external_id", "number", "display_name", "legal_name", "tax_id")
ADDRESS_PARTS = ("line1", "line2", "city", "province", "postal_code", "country")
TRUE = frozenset({"yes", "y", "true", "1", "x", "oui", "o", "vrai"})
FALSE = frozenset({"no", "n", "false", "0", "non", "faux"})
POSTAL = re.compile(r"^([A-Z]\d[A-Z])\s*(\d[A-Z]\d)$")
EMAIL = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[^@\s,;]+$")
FRENCH_PROVINCES = {
    "colombie-britannique": "BC",
    "nouveau-brunswick": "NB",
    "terre-neuve-et-labrador": "NL",
    "nouvelle-ecosse": "NS",
    "territoires du nord-ouest": "NT",
    "ile-du-prince-edouard": "PE",
    "quebec": "QC",
}
ROLE_WORDS = {
    "customer": "customer",
    "customers": "customer",
    "client": "customer",
    "clients": "customer",
    "supplier": "supplier",
    "suppliers": "supplier",
    "vendor": "supplier",
    "fournisseur": "supplier",
    "fournisseurs": "supplier",
    "employee": "employee",
    "employe": "employee",
    "contractor": "contractor",
    "entrepreneur": "contractor",
    "sous-traitant": "contractor",
    "government agency": "government_agency",
    "government": "government_agency",
    "agency": "government_agency",
    "organisme gouvernemental": "government_agency",
}
CREDIT_WORDS = {"warn": "warn", "avertir": "warn", "block": "block", "bloquer": "block"}
LANGUAGE_WORDS = {
    "en": "en-ca",
    "en-ca": "en-ca",
    "english": "en-ca",
    "anglais": "en-ca",
    "fr": "fr-ca",
    "fr-ca": "fr-ca",
    "french": "fr-ca",
    "francais": "fr-ca",
}


def _plain(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text.strip().casefold())
    return "".join(c for c in folded if not unicodedata.combining(c))


def province_code(text: str) -> str | None:
    value = text.strip()
    if value.upper() in Province.values:
        return value.upper()
    plain = _plain(value)
    for code, label in Province.choices:
        if _plain(str(label)) == plain:
            return str(code)
    return FRENCH_PROVINCES.get(plain)


def amount(text: str) -> Decimal | None:
    value = text.strip().replace("$", "").replace(" ", " ").replace(" ", "")
    if "," in value and "." not in value and re.search(r",\d{1,2}$", value):
        value = value.replace(",", ".")  # 1234,50 (French decimal comma)
    value = value.replace(",", "")
    try:
        found = Decimal(value)
    except InvalidOperation:
        return None
    return found if found.is_finite() else None


@dataclass
class NormalisedRow:
    values: dict[str, Any] = field(default_factory=dict)
    errors: list[RowError] = field(default_factory=list)

    def fail(self, key: str, code: str, message: str) -> None:
        self.errors.append(RowError(key, code, message))


def normalise_row(cells: dict[str, str]) -> NormalisedRow:
    """Typed values (blank cells absent, ``CLEAR`` for ``__CLEAR__``) and the row's problems."""
    row = NormalisedRow()
    # Countries first: whether a postal code must look Canadian depends on its address's country.
    for key, raw in sorted(cells.items(), key=lambda item: not item[0].endswith("_country")):
        text = (raw or "").strip()
        if not text:
            continue
        if text == CLEAR_TOKEN:
            if key in REQUIRED or key in ("roles", "currency"):
                row.fail(key, "contacts.import.required", _("This column can't be cleared."))
            else:
                row.values[key] = CLEAR
            continue
        _one(row, key, text)
    return row


def _one(row: NormalisedRow, key: str, text: str) -> None:  # noqa: C901 — one branch per column type
    if key in TEXT:
        row.values[key] = text
    elif key in ("email",):
        if EMAIL.match(text):
            row.values[key] = text.lower()
        else:
            row.fail(
                key,
                "contacts.import.email",
                _("'%(value)s' isn't an email address.") % {"value": text},
            )
    elif key == "phone":
        row.values[key] = text
    elif key == "bn":
        row.values[key] = re.sub(r"\s", "", text)
    elif key == "currency":
        if re.fullmatch(r"[A-Za-z]{3}", text):
            row.values[key] = text.upper()
        else:
            row.fail(
                key, "contacts.import.currency", _("Use a 3-letter currency code like CAD or USD.")
            )
    elif key == "roles":
        roles: list[str] = []
        unknown: list[str] = []
        for word in re.split(r"[,;/|]", text):
            plain = _plain(word)
            if not plain:
                continue
            role = ROLE_WORDS.get(plain) or (plain if plain in ContactRole.values else None)
            (roles if role else unknown).append(role or word.strip())
        if unknown:
            row.fail(
                key,
                "contacts.import.role",
                _(
                    "Unknown role: %(words)s. Use Customer, Supplier, Employee, Contractor or "
                    "Government agency."
                )
                % {"words": ", ".join(unknown)},
            )
        elif roles:
            row.values[key] = [r for r in ContactRole.values if r in roles]
    elif key == "credit_limit":
        value = amount(text)
        if value is None or value < 0:
            row.fail(
                key, "contacts.import.amount", _("'%(value)s' isn't an amount.") % {"value": text}
            )
        else:
            row.values[key] = value.quantize(Decimal("0.01"))
    elif key == "credit_mode":
        mode = CREDIT_WORDS.get(_plain(text))
        if mode in CreditMode.values:
            row.values[key] = mode
        else:
            row.fail(key, "contacts.import.credit_mode", _("Use Warn or Block."))
    elif key == "language":
        language = LANGUAGE_WORDS.get(_plain(text))
        if language:
            row.values[key] = language
        else:
            row.fail(key, "contacts.import.language", _("Use English or French."))
    elif key == "statement_pref":
        plain = _plain(text).replace(" ", "_")
        if plain in StatementPreference.values:
            row.values[key] = plain
        else:
            row.fail(key, "contacts.import.statement_pref", _("Unknown statement preference."))
    elif key == "t4a_flag":
        plain = _plain(text)
        if plain in TRUE or plain in FALSE:
            row.values[key] = plain in TRUE
        else:
            row.fail(key, "contacts.import.yes_no", _("Use Yes or No."))
    elif key.startswith(("billing_", "shipping_")):
        _address_part(row, key, text)
    else:
        row.values[key] = text


def _address_part(row: NormalisedRow, key: str, text: str) -> None:
    part = key.split("_", 1)[1]
    kind = key.split("_", 1)[0]
    if part == "province":
        code = province_code(text)
        if code is None:
            row.fail(
                key,
                "contacts.import.province",
                _("'%(value)s' isn't a province or territory. Use its code, like ON, or its name.")
                % {"value": text},
            )
            return
        row.values[key] = code
    elif part == "postal_code":
        country = row.values.get(f"{kind}_country", "CA")
        match = POSTAL.match(text.upper().replace("-", ""))
        if country == "CA" and match is None:
            row.fail(
                key,
                "contacts.import.postal_code",
                _("Postal code should look like 'M5V 2T6'. '%(value)s' doesn't.") % {"value": text},
            )
            return
        row.values[key] = f"{match.group(1)} {match.group(2)}" if match else text
    elif part == "country":
        if re.fullmatch(r"[A-Za-z]{2}", text):
            row.values[key] = text.upper()
        elif _plain(text) in ("canada",):
            row.values[key] = "CA"
        else:
            row.fail(
                key, "contacts.import.country", _("Use a 2-letter country code like CA or US.")
            )
    else:
        row.values[key] = text

"""Validators for organisation settings (A-05-T02).

- **Legal name** — must contain letters: a name made only of digits, spaces and punctuation
  ("1001633222") is refused, so a statement header never prints a number (gap-55).
- **Postal code** — Canada Post format ``A1A 1A1``: letter-digit-letter, space, digit-letter-digit;
  D, F, I, O, Q and U never appear and W and Z never start a code. Input is forgiving (lower case,
  no space, extra spaces) and stored normalised (``M5X 1A9``). [EXTRA] The first letter must
  belong to the province: ``K/L/M/N/P`` Ontario, ``G/H/J`` Quebec, ``V`` British Columbia… (gap-39).
- **Telephone** — parsed with ``phonenumbers`` (Canada by default, so ``416 555 0123`` works; other
  countries with their ``+`` code), refused unless it is a valid number, stored as E.164
  (``+14165550123``).

Every error is a ``ValidationError`` with a stable ``code`` (``orgsettings.<field>.<problem>``) so
the API and the settings form can show it next to the field.
"""

from __future__ import annotations

import re

import phonenumbers
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _


class Province(models.TextChoices):
    """Canadian provinces and territories (Canada Post two-letter codes)."""

    AB = "AB", _("Alberta")
    BC = "BC", _("British Columbia")
    MB = "MB", _("Manitoba")
    NB = "NB", _("New Brunswick")
    NL = "NL", _("Newfoundland and Labrador")
    NS = "NS", _("Nova Scotia")
    NT = "NT", _("Northwest Territories")
    NU = "NU", _("Nunavut")
    ON = "ON", _("Ontario")
    PE = "PE", _("Prince Edward Island")
    QC = "QC", _("Quebec")
    SK = "SK", _("Saskatchewan")
    YT = "YT", _("Yukon")


#: The provinces each first letter of a postal code belongs to (X is shared by NT and NU).
POSTAL_PREFIX_PROVINCES: dict[str, frozenset[str]] = {
    "A": frozenset({Province.NL}),
    "B": frozenset({Province.NS}),
    "C": frozenset({Province.PE}),
    "E": frozenset({Province.NB}),
    "G": frozenset({Province.QC}),
    "H": frozenset({Province.QC}),
    "J": frozenset({Province.QC}),
    "K": frozenset({Province.ON}),
    "L": frozenset({Province.ON}),
    "M": frozenset({Province.ON}),
    "N": frozenset({Province.ON}),
    "P": frozenset({Province.ON}),
    "R": frozenset({Province.MB}),
    "S": frozenset({Province.SK}),
    "T": frozenset({Province.AB}),
    "V": frozenset({Province.BC}),
    "X": frozenset({Province.NT, Province.NU}),
    "Y": frozenset({Province.YT}),
}

_FIRST = "ABCEGHJKLMNPRSTVXY"  # letters a postal code may start with
_LETTER = "ABCEGHJKLMNPRSTVWXYZ"  # letters in the other positions
POSTAL_CODE = re.compile(rf"^[{_FIRST}][0-9][{_LETTER}] [0-9][{_LETTER}][0-9]$")
DEFAULT_PHONE_REGION = "CA"


# ---- legal name ------------------------------------------------------------------------------


def has_letters(value: str) -> bool:
    return any(character.isalpha() for character in value)


def validate_legal_name(value: str) -> None:
    """A legal name has letters: "1001633222" or "123-456" is a number, not a name (gap-55)."""
    if value and not has_letters(value):
        raise ValidationError(
            _("A legal name needs letters: %(value)s looks like a number."),
            code="orgsettings.legal_name.numeric",
            params={"value": value},
        )


# ---- postal code -----------------------------------------------------------------------------


def normalise_postal_code(value: str) -> str:
    """``m5x1a9``, `` M5X  1A9 `` → ``M5X 1A9`` (unchanged when it is not 6 letters/digits)."""
    compact = re.sub(r"[\s-]+", "", value or "").upper()
    if len(compact) == 6:
        return f"{compact[:3]} {compact[3:]}"
    return (value or "").strip().upper()


def validate_postal_code(value: str) -> None:
    """A Canada Post postal code, normalised (``A1A 1A1``)."""
    if value and not POSTAL_CODE.match(value):
        raise ValidationError(
            _("Enter a Canadian postal code like A1A 1A1."),
            code="orgsettings.postal_code.invalid",
        )


def validate_postal_code_province(postal_code: str, province: str) -> None:
    """[EXTRA] The postal code's first letter belongs to the province (M… is in Ontario)."""
    if not postal_code or not province or not POSTAL_CODE.match(postal_code):
        return
    provinces = POSTAL_PREFIX_PROVINCES.get(postal_code[0], frozenset())
    if province not in provinces:
        expected = ", ".join(sorted(str(Province(p).label) for p in provinces))
        raise ValidationError(
            _(
                "Postal codes starting with %(letter)s are in %(expected)s, not in "
                "%(province)s: check the postal code or the province."
            ),
            code="orgsettings.postal_code.province_mismatch",
            params={
                "letter": postal_code[0],
                "expected": expected,
                "province": Province(province).label,
            },
        )


def validate_province(value: str) -> None:
    if value and value not in Province.values:
        raise ValidationError(
            _("Choose a province or territory."), code="orgsettings.province.invalid"
        )


# ---- telephone -------------------------------------------------------------------------------


def normalise_phone(value: str, region: str = DEFAULT_PHONE_REGION) -> str:
    """A valid telephone number as E.164 (``+14165550123``); refused otherwise."""
    text = (value or "").strip()
    if not text:
        return ""
    try:
        number = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        number = None
    if number is None or not phonenumbers.is_valid_number(number):
        raise ValidationError(
            _("Enter a valid telephone number, e.g. 416 555 0123 or +44 20 7946 0958."),
            code="orgsettings.phone.invalid",
        )
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


# ---- tax registration numbers (A-05-T03) -----------------------------------------------------


def luhn_valid(digits: str) -> bool:
    """The Luhn (mod 10) check the CRA uses for the 9th digit of a Business Number."""
    if not digits.isdigit():
        return False
    total = 0
    for position, character in enumerate(reversed(digits)):
        value = int(character)
        if position % 2 == 1:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def validate_business_number(bn: str) -> None:
    """[EXTRA] A 9-digit Business Number whose check digit is right (Luhn)."""
    if not re.fullmatch(r"[0-9]{9}", bn):
        raise ValidationError(
            _("A Business Number has 9 digits, e.g. 123456782."),
            code="orgsettings.registration.bn_format",
        )
    if bn == "000000000" or not luhn_valid(bn):
        raise ValidationError(
            _(
                "%(bn)s is not a valid Business Number: check the digits (the last one is a "
                "check digit)."
            ),
            code="orgsettings.registration.bn_check_digit",
            params={"bn": bn},
        )


def _compact(value: str) -> str:
    return re.sub(r"[\s\-./]+", "", value or "").upper()


#: Program identifiers of the CRA program accounts (BN9 + 2 letters + 4-digit reference).
PROGRAM_TYPES: frozenset[str] = frozenset({"rt", "rp", "rc"})
_PROGRAM = re.compile(r"^([0-9]{9})([A-Z]{2})([0-9]{4})$")
_QST = re.compile(r"^([0-9]{10})TQ([0-9]{4})$")
_PST_BC = re.compile(r"^(?:PST)?([0-9]{8})$")
_DIGITS = re.compile(r"^[0-9]{6,10}$")


def normalise_registration_number(kind: str, value: str) -> str:
    """The canonical stored form of a registration number, or a ``ValidationError``.

    - ``bn``: ``123456782`` (9 digits, check digit verified);
    - ``rt`` / ``rp`` / ``rc``: ``123456782RT0001`` — the BN (check digit verified), the program
      letters of the registration's type and a reference other than 0000;
    - ``qst``: ``1234567890TQ0001`` (10 digits, TQ, a reference other than 0000);
    - ``pst_bc``: ``PST-1234-5678``;
    - ``pst_sk`` / ``rst_mb``: 6–10 digits (no published check digit).
    """
    compact = _compact(value)
    if not compact:
        raise ValidationError(_("Enter the number."), code="orgsettings.registration.required")
    if kind == "bn":
        validate_business_number(compact)
        return compact
    if kind in PROGRAM_TYPES:
        match = _PROGRAM.match(compact)
        program = kind.upper()
        if match is None:
            raise ValidationError(
                _("A program account looks like 123456782 %(program)s 0001."),
                code="orgsettings.registration.program_format",
                params={"program": program},
            )
        bn, letters, reference = match.groups()
        if letters != program:
            raise ValidationError(
                _("This is a %(letters)s number: a %(program)s registration needs %(program)s."),
                code="orgsettings.registration.program_mismatch",
                params={"letters": letters, "program": program},
            )
        validate_business_number(bn)
        if reference == "0000":
            raise ValidationError(
                _("The reference number after %(program)s starts at 0001."),
                code="orgsettings.registration.reference_zero",
                params={"program": program},
            )
        return compact
    if kind == "qst":
        match = _QST.match(compact)
        if match is None or match.group(2) == "0000":
            raise ValidationError(
                _("A QST number looks like 1234567890 TQ 0001."),
                code="orgsettings.registration.qst_format",
            )
        return compact
    if kind == "pst_bc":
        match = _PST_BC.match(compact)
        if match is None:
            raise ValidationError(
                _("A British Columbia PST number looks like PST-1234-5678."),
                code="orgsettings.registration.pst_bc_format",
            )
        digits = match.group(1)
        return f"PST-{digits[:4]}-{digits[4:]}"
    if kind in ("pst_sk", "rst_mb"):
        if not _DIGITS.match(compact):
            raise ValidationError(
                _("Enter the number's 6 to 10 digits."),
                code="orgsettings.registration.digits_format",
            )
        return compact
    raise ValidationError(
        _("Choose the type of registration."), code="orgsettings.registration.type_invalid"
    )


def display_registration_number(kind: str, number: str) -> str:
    """How a stored number reads: ``123456782 RT 0001``, ``1234567890 TQ 0001``…"""
    if kind in PROGRAM_TYPES and len(number) == 15:
        return f"{number[:9]} {number[9:11]} {number[11:]}"
    if kind == "qst" and len(number) == 16:
        return f"{number[:10]} {number[10:12]} {number[12:]}"
    return number

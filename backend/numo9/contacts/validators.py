"""Validators for contacts (B-01).

- **Currency** — an active ISO 4217 code (``CAD``, ``USD``, ``EUR``…); input is forgiving
  (``usd`` → ``USD``). Organisations keep CAD as their base currency (A-05); a contact's currency
  becomes the default currency of its documents (R-01, Phase 2).
- **Business Number** — the 9-digit CRA Business Number with its check digit, the same rule as the
  organisation's own BN (A-05-T03). A program account typed in full (``123456782 RT 0001``) is
  reduced to its BN.
- **Roles** — at least one, from the fixed list; stored once each, in the list's order.

Every error is a ``ValidationError`` with a stable ``code`` (``contacts.<field>.<problem>``).
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from numo9.orgsettings.validators import luhn_valid

#: Active ISO 4217 currency codes (funds, precious metals and testing codes excluded).
_ISO_4217_CODES = """
    AED AFN ALL AMD ANG AOA ARS AUD AWG AZN BAM BBD BDT BGN BHD BIF BMD BND BOB BRL BSD BTN
    BWP BYN BZD CAD CDF CHF CLP CNY COP CRC CUP CVE CZK DJF DKK DOP DZD EGP ERN ETB EUR FJD
    FKP GBP GEL GHS GIP GMD GNF GTQ GYD HKD HNL HTG HUF IDR ILS INR IQD IRR ISK JMD JOD JPY
    KES KGS KHR KMF KPW KRW KWD KYD KZT LAK LBP LKR LRD LSL LYD MAD MDL MGA MKD MMK MNT MOP
    MRU MUR MVR MWK MXN MYR MZN NAD NGN NIO NOK NPR NZD OMR PAB PEN PGK PHP PKR PLN PYG QAR
    RON RSD RUB RWF SAR SBD SCR SDG SEK SGD SHP SLE SOS SRD SSP STN SVC SYP SZL THB TJS TMT
    TND TOP TRY TTD TWD TZS UAH UGX USD UYU UZS VED VES VND VUV WST XAF XCD XCG XOF XPF YER
    ZAR ZMW ZWG
"""
ISO_4217: frozenset[str] = frozenset(_ISO_4217_CODES.split())

DEFAULT_CURRENCY = "CAD"


def normalise_currency(value: str) -> str:
    return (value or "").strip().upper()


def validate_currency(value: str) -> None:
    if value not in ISO_4217:
        raise ValidationError(
            _("Choose a currency by its three-letter code, e.g. CAD or USD."),
            code="contacts.currency.invalid",
        )


def normalise_bn(value: str) -> str:
    """``123 456 782``, ``123456782RT0001`` → ``123456782`` (unchanged when it isn't a BN)."""
    compact = re.sub(r"[\s\-./]+", "", value or "").upper()
    match = re.fullmatch(r"([0-9]{9})(?:[A-Z]{2}[0-9]{4})?", compact)
    return match.group(1) if match else compact


def validate_bn(value: str) -> None:
    """A Business Number: 9 digits whose last one is the Luhn check digit (empty is allowed)."""
    if not value:
        return
    if not re.fullmatch(r"[0-9]{9}", value):
        raise ValidationError(
            _("A Business Number has 9 digits, e.g. 123456782."), code="contacts.bn.format"
        )
    if value == "000000000" or not luhn_valid(value):
        raise ValidationError(
            _(
                "%(bn)s is not a valid Business Number: check the digits (the last one is a check "
                "digit)."
            ),
            code="contacts.bn.check_digit",
            params={"bn": value},
        )


def normalise_roles(roles: Iterable[str], order: Iterable[str]) -> list[str]:
    """Each role once, in the canonical order; unknown values are kept (validation names them)."""
    given = [str(r).strip().lower() for r in roles or [] if str(r).strip()]
    known = [r for r in order if r in given]
    unknown = sorted({r for r in given if r not in known})
    return known + unknown


def validate_roles(roles: list[str], allowed: Iterable[str]) -> None:
    if not roles:
        raise ValidationError(
            _(
                "Choose at least one role: customer, supplier, employee, contractor or government "
                "agency."
            ),
            code="contacts.roles.required",
        )
    unknown = [r for r in roles if r not in set(allowed)]
    if unknown:
        raise ValidationError(
            _("Unknown role: %(roles)s."),
            code="contacts.roles.invalid",
            params={"roles": ", ".join(unknown)},
        )

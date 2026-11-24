"""Business Number, program account and QST number validators (G-06-T03).

One place the tax settings page (G-06) and the registrations API (A-05) check a number:
``check_number(kind, value)`` → ``NumberCheck`` — the canonical form, how it reads, or the error
**with an example of the right format in the message** (an invalid RT names
``123456782 RT 0001``). Kinds: ``bn``, ``rt``, ``rp``, ``rc``, ``qst``, ``pst_bc``, ``pst_sk``,
``rst_mb``. The rules themselves (the BN check digit, program letters, the 0001 reference…) are
``numo9.orgsettings.validators.normalise_registration_number``.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from numo9.orgsettings.validators import (
    display_registration_number,
    normalise_registration_number,
)

#: A valid example of each kind (BN 123456782 passes the check digit).
EXAMPLES: dict[str, str] = {
    "bn": "123456782",
    "rt": "123456782 RT 0001",
    "rp": "123456782 RP 0001",
    "rc": "123456782 RC 0001",
    "qst": "1234567890 TQ 0001",
    "pst_bc": "PST-1234-5678",
    "pst_sk": "1234567",
    "rst_mb": "123456789",
}


@dataclass(frozen=True)
class NumberCheck:
    kind: str
    valid: bool
    number: str = ""
    display: str = ""
    code: str = ""
    message: str = ""
    example: str = ""

    def as_dict(self) -> dict[str, object]:
        return {
            "type": self.kind,
            "valid": self.valid,
            "number": self.number,
            "display": self.display,
            "code": self.code,
            "message": self.message,
            "example": self.example,
        }


def check_number(kind: str, value: str) -> NumberCheck:
    example = EXAMPLES.get(kind, "")
    if kind not in EXAMPLES:
        return NumberCheck(
            kind,
            False,
            code="orgsettings.registration.type_invalid",
            message=_("Choose the type of registration."),
        )
    try:
        number = normalise_registration_number(kind, value)
    except ValidationError as error:
        message = " ".join(str(m) for m in error.messages)
        if example.replace(" ", "") not in message.replace(" ", ""):
            message = _("%(message)s Example: %(example)s.") % {
                "message": message.rstrip(),
                "example": example,
            }
        return NumberCheck(
            kind,
            False,
            code=str(error.code or "invalid"),
            message=message,
            example=example,
        )
    return NumberCheck(
        kind, True, number, display_registration_number(kind, number), example=example
    )


def validate_number(kind: str, value: str) -> str:
    """The canonical number, or a ``ValidationError`` whose message carries the example."""
    result = check_number(kind, value)
    if not result.valid:
        raise ValidationError(result.message, code=result.code)
    return result.number

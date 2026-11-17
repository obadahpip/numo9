"""Free trial (U-05): normalisers, starting a trial, refusing a second one, reminders, expiry
and conversion. See ``docs/architecture/trial.md``.

**Normalisers** (U-05-T03) — what the trial registry stores and compares:

- ``normalise_bn("123 456 782 RT0001")`` → ``"123456782"``: the nine-digit Business Number
  whatever the spacing, dashes or program account suffix (RT/RP/RC/RZ… + 4 digits); anything that
  isn't nine digits (with a valid check digit) → ``""`` (no BN to compare);
- ``normalise_email("Dana+numo9@Refined.CA ")`` → ``"dana@refined.ca"``: trimmed, lower-case,
  plus-addressing stripped from the local part (``dana+trial2@`` is ``dana@``).
"""

from __future__ import annotations

import re

from numo9.orgsettings.validators import luhn_valid

_BN = re.compile(r"^(\d{9})(?:(?:RT|RP|RC|RZ|RR|RM|RN|RD|RG)\d{4})?$")


def normalise_bn(value: str | None) -> str:
    """The nine-digit BN of ``value``, or ``""`` when it doesn't hold a valid one."""
    compact = re.sub(r"[\s\-.]", "", (value or "").upper())
    match = _BN.match(compact)
    if match is None or not luhn_valid(match[1]):
        return ""
    return match[1]


def normalise_email(value: str | None) -> str:
    """Trimmed, lower-case, without plus-addressing; ``""`` when it isn't an address."""
    text = (value or "").strip().lower()
    if text.count("@") != 1:
        return ""
    local, domain = text.split("@")
    local = local.split("+", 1)[0]
    if not local or not domain or "." not in domain:
        return ""
    return f"{local}@{domain}"

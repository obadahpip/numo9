"""U-05-T03 — Normalisers for BN and email (tests incl. spaces, RT suffix, plus-addressing).

Acceptance: the table test passes.
"""

from __future__ import annotations

import pytest

from numo9.entitlements.trials import normalise_bn, normalise_email
from tests.workspace_helpers import valid_bn

BN = valid_bn(12345678)  # nine digits with a valid check digit


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (BN, BN),
        (f"{BN[:3]} {BN[3:6]} {BN[6:]}", BN),  # spaces
        (f"{BN[:3]}-{BN[3:6]}-{BN[6:]}", BN),  # dashes
        (f"{BN}RT0001", BN),  # GST/HST program account
        (f"{BN} rt 0001", BN),  # lower case, spaced suffix
        (f"{BN}RP0002", BN),  # payroll account
        (f"  {BN}RC0001  ", BN),
        (f"{BN}XX0001", ""),  # not a CRA program
        (BN[:8], ""),  # too short
        (BN + "0", ""),  # too long
        (BN[:8] + str((int(BN[8]) + 1) % 10), ""),  # wrong check digit
        ("", ""),
        (None, ""),
    ],
)
def test_bn(value: str | None, expected: str) -> None:
    assert normalise_bn(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("dana@refined.ca", "dana@refined.ca"),
        ("  Dana@Refined.CA ", "dana@refined.ca"),
        ("dana+numo9@refined.ca", "dana@refined.ca"),  # plus-addressing
        ("Dana+Trial+2@Refined.ca", "dana@refined.ca"),
        ("d.ana@refined.ca", "d.ana@refined.ca"),  # dots are kept (not every provider ignores them)
        ("+tag@refined.ca", ""),
        ("dana@localhost", ""),
        ("dana", ""),
        ("a@b@c.ca", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_email(value: str | None, expected: str) -> None:
    assert normalise_email(value) == expected

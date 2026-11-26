"""GST/HST return lines (G-03-T03, T04): the GST34 lines 101–115 of a filing period, from the
posted tax lines (G-05-T02) dated in the period on the organisation's basis (G-06; cash basis:
G-05-T03). The mapping is ``docs/specs/gst-hst-return-line-mapping.md``.

``regular_lines(period, entries=…)`` → ``{line: Decimal}``:

- **101** — the net amount of sales lines whose tax code is taxable or zero-rated (each line
  once, whatever its components; exempt and out-of-scope supplies have no GST/HST tax line);
- **103** — the GST + HST of sales lines (credit notes and reversals negative);
- **104 / 107** — the late adjustments carried into the period (G-03-T08) plus the amounts
  entered on the return (``entries``: ``104``, ``107``, ``110``, ``111``, ``113B``);
- **105** = 103 + 104 — equals the tax summary's GST/HST collected for the period (G-05);
- **106** — the claimable (recoverable) GST + HST of purchase lines;
- **108** = 106 + 107; **109** = 105 − 108; **112** = 110 + 111; **113A** = 109 − 112;
  **113C** = 113A + 113B; **114** = −113C when negative, else 0; **115** = 113C when positive.

``QST`` and ``PST`` never feed the GST34. ``as_text(lines)`` → the stored form (``"130.00"``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .cash_basis import RecognisedLine, recognised_lines

ZERO = Decimal("0.00")
LINES = (
    "101",
    "103",
    "104",
    "105",
    "106",
    "107",
    "108",
    "109",
    "110",
    "111",
    "112",
    "113A",
    "113B",
    "113C",
    "114",
    "115",
)
#: The lines entered on the return by hand (until G-09 brings instalments, Phase 4).
ENTRY_LINES = ("104", "107", "110", "111", "113B")
GST_KINDS = ("gst", "hst")


def _basis(period: Any) -> str:
    from .settings import report_basis

    return report_basis(period.organisation)[0]


def period_lines(period: Any, *, basis: str | None = None) -> list[RecognisedLine]:
    """The GST/HST tax lines the period's return reads."""
    return recognised_lines(
        period.organisation,
        period.start,
        period.end,
        basis=basis or _basis(period),
        kind="gst_hst",
    )


def _taxable_codes(organisation: Any, codes: set[str]) -> set[str]:
    from .models import TaxCode, TaxCodeType

    return set(
        TaxCode.objects.filter(
            organisation=organisation,
            code__in=codes,
            type__in=(TaxCodeType.TAXABLE, TaxCodeType.ZERO_RATED),
        ).values_list("code", flat=True)
    )


def line_101(organisation: Any, lines: list[RecognisedLine]) -> Decimal:
    sales = [r for r in lines if r.side == "sales" and r.source == "document"]
    taxable = _taxable_codes(organisation, {r.code for r in sales})
    seen: dict[tuple[int, int, int | None], Decimal] = {}
    for row in sales:
        if row.code in taxable:
            seen[(row.line.entry_id, row.line.line_no, row.line.reverses_id)] = row.basis
    return sum(seen.values(), ZERO)


def _d(value: Any) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(Decimal("0.01"))
    except ArithmeticError:
        return ZERO


def totals(lines: dict[str, Decimal]) -> dict[str, Decimal]:
    """Lines 105 to 115 from 101, 103, 104, 106, 107, 110, 111 and 113B."""
    out = dict(lines)
    out["105"] = out["103"] + out["104"]
    out["108"] = out["106"] + out["107"]
    out["109"] = out["105"] - out["108"]
    out["112"] = out["110"] + out["111"]
    out["113A"] = out["109"] - out["112"]
    out["113C"] = out["113A"] + out["113B"]
    out["114"] = -out["113C"] if out["113C"] < 0 else ZERO
    out["115"] = out["113C"] if out["113C"] > 0 else ZERO
    return {line: out[line] for line in LINES}


def regular_lines(
    period: Any, *, entries: dict[str, Any] | None = None, basis: str | None = None
) -> dict[str, Decimal]:
    """The regular method's lines (module docstring)."""
    from .returns import adjustment_lines

    entries = entries or {}
    lines = period_lines(period, basis=basis)
    sales = [r for r in lines if r.side == "sales"]
    purchases = [r for r in lines if r.side == "purchase"]
    adjustments = adjustment_lines(period)
    values = {
        "101": line_101(period.organisation, lines),
        "103": sum((r.tax for r in sales), ZERO),
        "104": _d(adjustments["104"]) + _d(entries.get("104")),
        "106": sum((r.recoverable for r in purchases), ZERO),
        "107": _d(adjustments["107"]) + _d(entries.get("107")),
        "110": _d(entries.get("110")),
        "111": _d(entries.get("111")),
        "113B": _d(entries.get("113B")),
    }
    return totals(values)


def as_text(lines: dict[str, Decimal]) -> dict[str, str]:
    return {line: f"{value:.2f}" for line, value in lines.items()}

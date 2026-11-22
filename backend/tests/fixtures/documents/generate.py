"""Reference sheet for the DocumentCalculator (D-01-T03…T05): regenerates the fixture JSON.

    python tests/fixtures/documents/generate.py

Independent of ``numo9.documents.calculator``: exact ``Fraction`` arithmetic and an explicit
half-up rounding. The backend tests and the client mirror's Vitest suite (D-01-T10) both read
the JSON this writes. A seeded random generator plus hand-picked edge cases (1/3 quantities,
100 % discounts, zero quantities, half-cent ties).
"""

from __future__ import annotations

import json
import random
from fractions import Fraction
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
REGIMES = {
    "ON": [("hst_on", "13")],
    "NS": [("hst_ns", "14")],
    "NB": [("hst_nb", "15")],
    "AB": [("gst", "5")],
    "QC": [("gst", "5"), ("qst", "9.975")],
    "BC": [("gst", "5"), ("pst_bc", "7")],
    "SK": [("gst", "5"), ("pst_sk", "6")],
    "MB": [("gst", "5"), ("rst_mb", "7")],
    "ZERO": [("gst_zero", "0")],
    "EXEMPT": [],
}


def half_up(value: Fraction) -> Fraction:
    """Round to the cent, half away from zero."""
    sign = -1 if value < 0 else 1
    cents = (abs(value) * 100 + Fraction(1, 2)).__floor__()
    return Fraction(sign * cents, 100)


def money(value: Fraction) -> str:
    cents = round(value * 100)
    sign = "-" if cents < 0 else ""
    return f"{sign}{abs(cents) // 100}.{abs(cents) % 100:02d}"


def frac(text: str) -> Fraction:
    return Fraction(text)


def reference(doc: dict[str, Any]) -> dict[str, Any]:
    mode = doc.get("tax_mode", "exclusive")
    rows = []
    for line in doc["lines"]:
        gross = half_up(frac(line.get("quantity", "1")) * frac(line.get("unit_price", "0")))
        kind, value = line.get("discount_type", "none"), frac(line.get("discount_value", "0"))
        discount = Fraction(0)
        if kind == "amount":
            discount = min(half_up(value), gross) if gross >= 0 else Fraction(0)
        elif kind == "percent":
            discount = half_up(gross * value / 100)
        rows.append((line, gross, discount, gross - discount))
    nets = [row[3] for row in rows]
    base = sum((n for n in nets if n > 0), Fraction(0))
    kind, value = doc.get("discount_type", "none"), frac(doc.get("discount_value", "0"))
    doc_discount = Fraction(0)
    if kind == "amount" and value:
        doc_discount = min(half_up(value), base)
    elif kind == "percent" and value:
        doc_discount = half_up(base * value / 100)
    shares = [Fraction(0)] * len(nets)
    if doc_discount and base:
        for i, net in enumerate(nets):
            if net > 0:
                shares[i] = min(half_up(doc_discount * net / base), net)
        left = round((doc_discount - sum(shares, Fraction(0))) * 100)
        order = sorted((i for i, n in enumerate(nets) if n > 0), key=lambda i: (-nets[i], i))
        cent = Fraction(1, 100) if left > 0 else Fraction(-1, 100)
        while left:
            for i in order:
                if left and 0 <= shares[i] + cent <= nets[i]:
                    shares[i] += cent
                    left -= 1 if cent > 0 else -1
    lines: list[dict[str, Any]] = []
    by: dict[str, Fraction] = {}
    for (line, gross, discount, net), share in zip(rows, shares, strict=True):
        taxable = net - share
        rates = [(c["key"], frac(c["rate"])) for c in line.get("components", [])]
        if mode == "no_tax":
            rates = []
        exclusive: Fraction = taxable
        taxes: dict[str, Fraction] = {}
        if mode == "inclusive" and rates:
            exclusive, taxes = back_out(taxable, rates)
        else:
            taxes = {key: half_up(taxable * rate / 100) for key, rate in rates}
        for key, amount in taxes.items():
            by[key] = by.get(key, Fraction(0)) + amount
        lines.append(
            {
                "gross": money(gross),
                "line_discount": money(discount),
                "net": money(net),
                "discount_share": money(share),
                "taxable": money(taxable),
                "exclusive": money(exclusive),
                "taxes": {k: money(v) for k, v in taxes.items()},
            }
        )
    subtotal = sum(nets, Fraction(0))
    tax_total = sum(by.values(), Fraction(0))
    after = subtotal - doc_discount
    total = after if mode == "inclusive" else after + tax_total
    return {
        "lines": lines,
        "subtotal": money(subtotal),
        "discount_total": money(doc_discount),
        "tax_total": money(tax_total),
        "total": money(total),
        "net_total": money(total - tax_total),
        "tax_by_component": {k: money(v) for k, v in sorted(by.items())},
    }


def back_out(
    gross: Fraction, rates: list[tuple[str, Fraction]]
) -> tuple[Fraction, dict[str, Fraction]]:
    """Inclusive: the exclusive amount whose taxes give back ``gross`` exactly, searched over
    every cent near gross / (1 + Σ rates); else the nearest one with the residual cent on the
    largest rate."""
    total_rate = sum((r for _, r in rates), Fraction(0))
    first = half_up(gross / (1 + total_rate / 100))
    step = Fraction(1, 100) if gross >= 0 else Fraction(-1, 100)
    for net in (first, first - step, first + step):
        taxes = {k: half_up(net * r / 100) for k, r in rates}
        if net + sum(taxes.values(), Fraction(0)) == gross:
            return net, taxes
    taxes = {k: half_up(first * r / 100) for k, r in rates}
    order = sorted(range(len(rates)), key=lambda i: (-rates[i][1], i))
    biggest = rates[order[0]][0]
    taxes[biggest] += gross - first - sum(taxes.values(), Fraction(0))
    return first, taxes


EDGE_INCLUSIVE = [
    {
        "name": "Ontario 113 inclusive",
        "lines": [
            {
                "quantity": "1",
                "unit_price": "113.00",
                "components": [{"key": "hst_on", "rate": "13"}],
            }
        ],
    },
    {
        "name": "Quebec 114.98 inclusive",
        "lines": [
            {
                "quantity": "1",
                "unit_price": "114.98",
                "components": [{"key": "gst", "rate": "5"}, {"key": "qst", "rate": "9.975"}],
            }
        ],
    },
    {
        "name": "Quebec small amount",
        "lines": [
            {
                "quantity": "1",
                "unit_price": "1.15",
                "components": [{"key": "gst", "rate": "5"}, {"key": "qst", "rate": "9.975"}],
            }
        ],
    },
    {
        "name": "Quebec residual cent",
        "lines": [
            {
                "quantity": "1",
                "unit_price": "1.03",
                "components": [{"key": "gst", "rate": "5"}, {"key": "qst", "rate": "9.975"}],
            }
        ],
    },
    {
        "name": "Inclusive one third",
        "lines": [
            {
                "quantity": "0.3333",
                "unit_price": "33.90",
                "components": [{"key": "hst_on", "rate": "13"}],
            }
        ],
    },
    {
        "name": "Inclusive 100 % discount",
        "lines": [
            {
                "quantity": "1",
                "unit_price": "56.50",
                "discount_type": "percent",
                "discount_value": "100",
                "components": [{"key": "hst_on", "rate": "13"}],
            }
        ],
    },
]


EDGE_DISCOUNT: list[dict[str, Any]] = [
    {
        "name": "10 % off three lines",
        "discount_type": "percent",
        "discount_value": "10",
        "lines": [
            {
                "quantity": "1",
                "unit_price": "100.00",
                "components": [{"key": "hst_on", "rate": "13"}],
            },
            {"quantity": "1", "unit_price": "50.00", "components": [{"key": "gst", "rate": "5"}]},
            {"quantity": "1", "unit_price": "0.01", "components": []},
        ],
    },
    {
        "name": "10.00 off three equal lines",
        "discount_type": "amount",
        "discount_value": "10.00",
        "lines": [{"quantity": "1", "unit_price": "10.00"}] * 3,
    },
    {
        "name": "100 % document discount",
        "discount_type": "percent",
        "discount_value": "100",
        "lines": [
            {
                "quantity": "2",
                "unit_price": "19.99",
                "components": [{"key": "hst_on", "rate": "13"}],
            },
            {
                "quantity": "1",
                "unit_price": "5.00",
                "components": [{"key": "hst_on", "rate": "13"}],
            },
        ],
    },
    {
        "name": "Discount larger than the lines",
        "discount_type": "amount",
        "discount_value": "500.00",
        "lines": [
            {
                "quantity": "1",
                "unit_price": "120.00",
                "components": [{"key": "hst_on", "rate": "13"}],
            }
        ],
    },
    {
        "name": "Inclusive with 25.00 off",
        "tax_mode": "inclusive",
        "discount_type": "amount",
        "discount_value": "25.00",
        "lines": [
            {
                "quantity": "1",
                "unit_price": "113.00",
                "components": [{"key": "hst_on", "rate": "13"}],
            },
            {
                "quantity": "1",
                "unit_price": "114.98",
                "components": [{"key": "gst", "rate": "5"}, {"key": "qst", "rate": "9.975"}],
            },
        ],
    },
    {
        "name": "Zero lines take no share",
        "discount_type": "amount",
        "discount_value": "3.00",
        "lines": [
            {"quantity": "0", "unit_price": "10.00"},
            {"quantity": "1", "unit_price": "7.00"},
        ],
    },
]


def components(regime: str) -> list[dict[str, Any]]:
    return [{"key": k, "rate": r} for k, r in REGIMES[regime]]


def random_line(rng: random.Random) -> dict[str, Any]:
    quantity = rng.choice(["1", "2", "3", "0.5", "0.3333", "1.25", "12", "0", "7.5", "100"])
    price = f"{rng.randint(0, 250000) / 100:.2f}"
    if rng.random() < 0.2:
        price = f"{rng.randint(0, 9999999) / 10000:.4f}"
    line = {
        "quantity": quantity,
        "unit_price": price,
        "components": components(rng.choice(list(REGIMES))),
    }
    roll = rng.random()
    if roll < 0.2:
        line |= {
            "discount_type": "percent",
            "discount_value": rng.choice(["10", "12.5", "33.33", "100", "2"]),
        }
    elif roll < 0.35:
        line |= {"discount_type": "amount", "discount_value": f"{rng.randint(0, 50000) / 100:.2f}"}
    return line


EDGE_EXCLUSIVE = [
    {
        "name": "Ontario single line",
        "lines": [{"quantity": "1", "unit_price": "100.00", "components": components("ON")}],
    },
    {
        "name": "Quebec GST+QST not compounded",
        "lines": [{"quantity": "1", "unit_price": "100.00", "components": components("QC")}],
    },
    {
        "name": "One third quantity",
        "lines": [{"quantity": "0.3333", "unit_price": "30.00", "components": components("ON")}],
    },
    {
        "name": "Three thirds",
        "lines": [{"quantity": "0.3333", "unit_price": "10.00", "components": components("AB")}]
        * 3,
    },
    {
        "name": "100 % line discount",
        "lines": [
            {
                "quantity": "2",
                "unit_price": "45.00",
                "discount_type": "percent",
                "discount_value": "100",
                "components": components("BC"),
            }
        ],
    },
    {
        "name": "Zero quantity",
        "lines": [{"quantity": "0", "unit_price": "99.99", "components": components("ON")}],
    },
    {
        "name": "Half-cent tie rounds up",
        "lines": [{"quantity": "1", "unit_price": "0.10", "components": components("AB")}],
    },
    {
        "name": "Amount discount larger than line",
        "lines": [
            {
                "quantity": "1",
                "unit_price": "20.00",
                "discount_type": "amount",
                "discount_value": "25.00",
                "components": components("ON"),
            }
        ],
    },
    {
        "name": "Exempt and zero-rated",
        "lines": [
            {"quantity": "1", "unit_price": "50.00", "components": components("EXEMPT")},
            {"quantity": "3", "unit_price": "4.99", "components": components("ZERO")},
        ],
    },
    {
        "name": "Mixed provinces",
        "lines": [
            {"quantity": "1", "unit_price": "10.00", "components": components("ON")},
            {"quantity": "1", "unit_price": "10.00", "components": components("QC")},
            {"quantity": "1", "unit_price": "10.00", "components": components("SK")},
        ],
    },
]


def build(seed: int, count: int, edges: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
    rng = random.Random(seed)  # noqa: S311 — reproducible test data, not security
    docs = [dict(edge) for edge in edges]
    while len(docs) < count:
        docs.append(
            {
                "name": f"{prefix} {len(docs) + 1}",
                "lines": [random_line(rng) for _ in range(rng.randint(1, 6))],
            }
        )
    return docs


def main() -> None:
    exclusive = build(20261, 50, EDGE_EXCLUSIVE, "Random exclusive")
    for doc in exclusive:
        doc["tax_mode"] = "exclusive"
        doc["expected"] = reference(doc)
    (HERE / "calculator_exclusive.json").write_text(json.dumps(exclusive, indent=1) + "\n")
    inclusive = build(20262, 30, EDGE_INCLUSIVE, "Random inclusive")
    no_tax = build(20263, 10, [], "Random no tax")
    for doc in inclusive:
        doc["tax_mode"] = "inclusive"
        doc["expected"] = reference(doc)
    for doc in no_tax:
        doc["tax_mode"] = "no_tax"
        doc["expected"] = reference(doc)
    discounted = build(20264, 20, EDGE_DISCOUNT, "Random document discount")
    rng = random.Random(20265)  # noqa: S311 — reproducible test data, not security
    for doc in discounted:
        if "discount_type" not in doc:
            doc["tax_mode"] = rng.choice(["exclusive", "exclusive", "inclusive", "no_tax"])
            if rng.random() < 0.5:
                doc |= {
                    "discount_type": "percent",
                    "discount_value": rng.choice(["5", "10", "15.5", "33.33", "100"]),
                }
            else:
                doc |= {
                    "discount_type": "amount",
                    "discount_value": f"{rng.randint(1, 100000) / 100:.2f}",
                }
        doc.setdefault("tax_mode", "exclusive")
        doc["expected"] = reference(doc)
    (HERE / "calculator_discount.json").write_text(json.dumps(discounted, indent=1) + "\n")
    (HERE / "calculator_inclusive.json").write_text(json.dumps(inclusive, indent=1) + "\n")
    (HERE / "calculator_no_tax.json").write_text(json.dumps(no_tax, indent=1) + "\n")


if __name__ == "__main__":
    main()

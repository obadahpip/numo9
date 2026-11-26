"""The amount of a cheque in words (E-06-T07), English and Canadian French.

    amount_in_words(Decimal("1234.56"), "en-ca")
    → "One thousand two hundred thirty-four and 56/100 dollars"
    amount_in_words(Decimal("1234.56"), "fr-ca")
    → "Mille deux cent trente-quatre et 56/100 dollars"

The cents are written as a fraction (``56/100``), as on Canadian cheques. French follows the
traditional spelling: *vingt et un*, *soixante et onze*, *quatre-vingts* / *quatre-vingt-un*,
*deux cents* / *deux cent un*, invariable *mille*, *millions*.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

EN_ONES = [
    "zero",
    "one",
    "two",
    "three",
    "four",
    "five",
    "six",
    "seven",
    "eight",
    "nine",
    "ten",
    "eleven",
    "twelve",
    "thirteen",
    "fourteen",
    "fifteen",
    "sixteen",
    "seventeen",
    "eighteen",
    "nineteen",
]
EN_TENS = ["_", "_", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
FR_ONES = [
    "zéro",
    "un",
    "deux",
    "trois",
    "quatre",
    "cinq",
    "six",
    "sept",
    "huit",
    "neuf",
    "dix",
    "onze",
    "douze",
    "treize",
    "quatorze",
    "quinze",
    "seize",
    "dix-sept",
    "dix-huit",
    "dix-neuf",
]
FR_TENS = ["_", "_", "vingt", "trente", "quarante", "cinquante", "soixante"]
MAX = Decimal("999999999.99")


def _en_below_1000(n: int) -> str:
    words: list[str] = []
    if n >= 100:
        words += [EN_ONES[n // 100], "hundred"]
        n %= 100
    if n >= 20:
        words.append(EN_TENS[n // 10] + (f"-{EN_ONES[n % 10]}" if n % 10 else ""))
    elif n or not words:
        words.append(EN_ONES[n])
    return " ".join(words)


def english(n: int) -> str:
    if n == 0:
        return "zero"
    parts: list[str] = []
    for size, name in ((1_000_000, "million"), (1_000, "thousand")):
        if n >= size:
            parts.append(f"{_en_below_1000(n // size)} {name}")
            n %= size
    if n:
        parts.append(_en_below_1000(n))
    return " ".join(parts)


def _fr_below_100(n: int) -> str:
    if n < 20:
        return FR_ONES[n]
    tens, unit = divmod(n, 10)
    if tens in (7, 9):  # soixante-dix…, quatre-vingt-dix…
        base = "soixante" if tens == 7 else "quatre-vingt"
        rest = n - (60 if tens == 7 else 80)
        joiner = " et " if (tens == 7 and rest == 11) else "-"
        return f"{base}{joiner}{FR_ONES[rest]}"
    if tens == 8:
        return "quatre-vingts" if unit == 0 else f"quatre-vingt-{FR_ONES[unit]}"
    word = FR_TENS[tens]
    if unit == 0:
        return word
    if unit == 1:
        return f"{word} et un"
    return f"{word}-{FR_ONES[unit]}"


def _fr_below_1000(n: int, *, before_mille: bool = False) -> str:
    hundreds, rest = divmod(n, 100)
    words: list[str] = []
    if hundreds:
        if hundreds == 1:
            words.append("cent")
        else:
            plural = rest == 0 and not before_mille
            words.append(f"{FR_ONES[hundreds]} {'cents' if plural else 'cent'}")
    if rest:
        tail = _fr_below_100(rest)
        if before_mille and tail.endswith("quatre-vingts"):
            tail = tail[:-1]  # quatre-vingt mille
        words.append(tail)
    return " ".join(words)


def french(n: int) -> str:
    if n == 0:
        return "zéro"
    parts: list[str] = []
    millions, n = divmod(n, 1_000_000)
    if millions:
        word = _fr_below_1000(millions)
        parts.append(f"{word} {'million' if millions == 1 else 'millions'}")
    thousands, n = divmod(n, 1_000)
    if thousands:
        parts.append(
            "mille" if thousands == 1 else f"{_fr_below_1000(thousands, before_mille=True)} mille"
        )
    if n:
        parts.append(_fr_below_1000(n))
    return " ".join(parts)


def amount_in_words(amount: Decimal, locale: str = "en-ca") -> str:
    """The amount in words with the cents as ``NN/100`` and the currency word, capitalised."""
    value = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if value < 0 or value > MAX:
        raise ValueError("A cheque amount is from 0 to 999,999,999.99.")
    dollars = int(value)
    cents = int((value - dollars) * 100)
    if (locale or "").lower().startswith("fr"):
        text = f"{french(dollars)} et {cents:02d}/100 dollars"
    else:
        text = f"{english(dollars)} and {cents:02d}/100 dollars"
    return text[0].upper() + text[1:]

"""Log and error-report scrubbing (S-03-T06): SIN, bank and card numbers, tokens and passwords
never reach logs or Sentry.

Two layers, applied to every structlog event, every standard-library log record and every
Sentry event:

1. **By name** — a value whose key names a secret (``password``, ``token``, ``sin``,
   ``bank_account``, ``card_number``, ``authorization``, ``cookie`` …) is replaced whole.
2. **By shape** — free text (messages, exception text, URLs) is searched for SINs (9 digits
   passing the Luhn check, or ``ddd-ddd-ddd``), card numbers (13–19 digits passing Luhn),
   Canadian bank accounts (transit-institution-account), bearer/API tokens, JWTs, Stripe keys,
   age private keys, ``password=…`` pairs and passwords in URLs.

Everything removed becomes ``[REDACTED]``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

# ---- By name ---------------------------------------------------------------------------------

SENSITIVE_WORDS = frozenset(
    {
        "password",
        "passwd",
        "pwd",
        "passphrase",
        "secret",
        "token",
        "apikey",
        "authorization",
        "auth",
        "cookie",
        "cookies",
        "csrftoken",
        "sessionid",
        "session",
        "sin",
        "nas",  # numéro d'assurance sociale
        "ssn",
        "card",
        "pan",
        "cvv",
        "cvc",
        "iban",
        "bank",
        "transit",
        "institution",
        "otp",
        "totp",
        "dsn",
        "signature",
        "credential",
        "credentials",
        "private",
    }
)
SENSITIVE_PAIRS = frozenset(
    {
        ("api", "key"),
        ("account", "number"),
        ("routing", "number"),
        ("social", "insurance"),
        ("secret", "key"),
        ("access", "key"),
    }
)
_HEADER_NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_WORD = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


def is_sensitive_key(key: object) -> bool:
    """``user_password``, ``X-Api-Key``, ``bankAccount``, ``sin`` → True; ``business``, ``since``,
    ``account_id``, ``company`` → False (whole words only)."""
    if not isinstance(key, str):
        return False
    words = [w.lower() for w in _WORD.findall(key)]
    if any(w in SENSITIVE_WORDS for w in words):
        return True
    return any(pair in SENSITIVE_PAIRS for pair in zip(words, words[1:], strict=False))


# ---- By shape --------------------------------------------------------------------------------


def _luhn(digits: str) -> bool:
    total = 0
    for index, char in enumerate(reversed(digits)):
        value = int(char)
        if index % 2:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


def _digits(text: str) -> str:
    return re.sub(r"\D", "", text)


_CARD = re.compile(r"(?<![\d.])(?:\d[ -]?){12,18}\d(?![\d.])")
_SIN_GROUPED = re.compile(r"(?<![\d-])\d{3}([- ])\d{3}\1\d{3}(?![\d-])")
_SIN_PLAIN = re.compile(r"(?<![\d.])\d{9}(?![\d.])")
_BANK = re.compile(r"(?<![\d-])\d{5}[- ]\d{3}[- ]\d{7,12}(?![\d-])")
_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    # "Authorization: Bearer abc…", "Token abc…"
    (re.compile(r"(?i)\b(bearer|token|basic)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 " + REDACTED),
    # JSON Web Tokens
    (re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}"), REDACTED),
    # Stripe secret, restricted and webhook keys
    (re.compile(r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{8,}|\bwhsec_[A-Za-z0-9]{8,}"), REDACTED),
    # age private keys (S-03-T03)
    (re.compile(r"AGE-SECRET-KEY-1[0-9A-Z]{20,}"), REDACTED),
    # password in a URL: scheme://user:password@host
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://[^:/\s@]+):[^@\s/]+@"), r"\1:" + REDACTED + "@"),
    # name=value / name: value / "name": "value" for secret-looking names
    (
        re.compile(
            r"""(?ix)
            (\b(?:password|passwd|pwd|passphrase|secret|token|api[_-]?key|access[_-]?key|
                 authorization|cookie|sessionid|csrftoken|sin|card[_-]?number|cvv|cvc|
                 account[_-]?number|bank[_-]?account|signature)
               ["']?\s*[:=]\s*["']?)
            ([^\s"'&,;}]+)
            """
        ),
        r"\1" + REDACTED,
    ),
)


def _scrub_numbers(text: str) -> str:
    text = _BANK.sub(REDACTED, text)
    text = _SIN_GROUPED.sub(REDACTED, text)
    text = _SIN_PLAIN.sub(lambda m: REDACTED if _luhn(m.group()) else m.group(), text)

    def card(match: re.Match[str]) -> str:
        digits = _digits(match.group())
        return REDACTED if 13 <= len(digits) <= 19 and _luhn(digits) else match.group()

    return _CARD.sub(card, text)


def scrub_text(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return _scrub_numbers(text)


def scrub(value: Any, *, depth: int = 0) -> Any:
    """Scrub a JSON-like structure: dict keys by name, strings by shape. Returns a copy."""
    if depth > 20:
        return REDACTED
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, Mapping):
        return {
            k: (
                REDACTED
                if is_sensitive_key(k) and v not in (None, "")
                else scrub(v, depth=depth + 1)
            )
            for k, v in value.items()
        }
    if isinstance(value, list | tuple):
        items = [scrub(v, depth=depth + 1) for v in value]
        # Sentry headers/cookies are lists of [name, value] pairs.
        if (
            len(items) == 2
            and isinstance(items[0], str)
            and _HEADER_NAME.match(items[0])
            and is_sensitive_key(items[0])
            and items[1] not in (None, "")
        ):
            items[1] = REDACTED
        return items if isinstance(value, list) else tuple(items)
    if isinstance(value, bytes):
        return scrub_text(value.decode("utf-8", "replace"))
    return value


# ---- structlog -------------------------------------------------------------------------------


def structlog_processor(
    logger: Any, method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    """structlog processor: put it after ``format_exc_info`` so tracebacks are scrubbed too."""
    scrubbed: dict[str, Any] = scrub(event_dict)
    return scrubbed


# ---- Sentry ----------------------------------------------------------------------------------


def sentry_before_send(event: dict[str, Any], hint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sentry ``before_send`` / ``before_send_transaction``: the whole event, scrubbed — request
    data, headers, cookies, query string, extra, contexts, breadcrumbs, exception values and
    stack-frame variables. The user is reduced to its id."""
    scrubbed: dict[str, Any] = scrub(event)
    user = scrubbed.get("user")
    if isinstance(user, dict):
        scrubbed["user"] = {"id": user["id"]} if "id" in user else {}
    return scrubbed


def sentry_before_breadcrumb(
    crumb: dict[str, Any], hint: dict[str, Any] | None = None
) -> dict[str, Any]:
    scrubbed: dict[str, Any] = scrub(crumb)
    return scrubbed

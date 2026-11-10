"""Brute-force protection for password login (S-03-T07).

- **Account lockout** — 10 failed logins for one email address within 15 minutes lock that
  address for **15 minutes**: every login for it is refused (429 with ``Retry-After``), even with
  the right password. The lock is per address, known or not, so it reveals nothing about which
  accounts exist. A successful login clears the failure count (not an active lock); a completed
  password reset clears both (the mailbox owner proved who they are).
- **CAPTCHA hook** — after ``NUMO9_LOGIN_CAPTCHA_AFTER`` failures (default 5) a login for that
  address must carry a ``captcha`` token, checked by the callable named in
  ``NUMO9_CAPTCHA_VERIFIER`` (``verify(token, remote_ip) -> bool``; the provider — Turnstile or
  hCaptcha, data-residency register SP-06 — is wired in Q-02-T03). With no verifier configured
  the hook is off and only the lockout applies.
- Per-IP limits on all and on failed attempts stay with allauth (``ACCOUNT_RATE_LIMITS``).

State lives in the shared cache (Redis in staging/prod). Keys hold a SHA-256 of the address,
never the address itself.
"""

from __future__ import annotations

import hashlib
import logging
import math
import time
from collections.abc import Callable

from django.conf import settings
from django.core.cache import cache
from django.utils.module_loading import import_string

logger = logging.getLogger("numo9.security.bruteforce")

LOCKOUT_THRESHOLD = 10
LOCKOUT_SECONDS = 15 * 60


def _now() -> float:
    return time.time()


def _digest(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _keys(email: str) -> tuple[str, str]:
    digest = _digest(email)
    return f"bruteforce:fail:{digest}", f"bruteforce:lock:{digest}"


def threshold() -> int:
    return int(getattr(settings, "NUMO9_LOGIN_LOCKOUT_THRESHOLD", LOCKOUT_THRESHOLD))


def lockout_seconds() -> int:
    return int(getattr(settings, "NUMO9_LOGIN_LOCKOUT_SECONDS", LOCKOUT_SECONDS))


def failures(email: str) -> int:
    fail_key, _ = _keys(email)
    entry = cache.get(fail_key)
    if not entry:
        return 0
    count, last = entry
    if _now() - last > lockout_seconds():  # older than the window: forgotten
        return 0
    return int(count)


def locked_for(email: str) -> int:
    """Seconds until the address unlocks; 0 when it is not locked."""
    _, lock_key = _keys(email)
    unlock_at = cache.get(lock_key)
    if unlock_at is None:
        return 0
    remaining = float(unlock_at) - _now()
    return max(0, math.ceil(remaining))


def record_failure(email: str) -> bool:
    """Count a failed login; returns True when this failure locks the address."""
    fail_key, lock_key = _keys(email)
    count = failures(email) + 1
    if count >= threshold():
        cache.set(lock_key, _now() + lockout_seconds(), timeout=lockout_seconds())
        cache.delete(fail_key)
        logger.warning(
            "login.locked",
            extra={"account_key": _digest(email)[:12], "minutes": lockout_seconds() // 60},
        )
        return True
    cache.set(fail_key, (count, _now()), timeout=lockout_seconds())
    return False


def record_success(email: str) -> None:
    fail_key, _ = _keys(email)
    cache.delete(fail_key)


def clear(email: str) -> None:
    """Forget failures and any lock (after a completed password reset)."""
    cache.delete_many(list(_keys(email)))


# ---- CAPTCHA hook -----------------------------------------------------------------------------


def captcha_verifier() -> Callable[[str, str | None], bool] | None:
    path = getattr(settings, "NUMO9_CAPTCHA_VERIFIER", "") or ""
    if not path:
        return None
    verifier: Callable[[str, str | None], bool] = import_string(path)
    return verifier


def captcha_required(email: str) -> bool:
    after = int(getattr(settings, "NUMO9_LOGIN_CAPTCHA_AFTER", 5))
    return captcha_verifier() is not None and failures(email) >= after


def captcha_ok(token: str | None, remote_ip: str | None) -> bool:
    verifier = captcha_verifier()
    if verifier is None:
        return True
    if not token:
        return False
    try:
        return bool(verifier(token, remote_ip))
    except Exception:  # a provider outage must not crash login; it counts as not verified
        logger.exception("captcha.verifier_failed")
        return False

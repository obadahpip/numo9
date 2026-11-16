"""Devices and sessions (A-02-T07): a readable name for a user agent, known devices, and the
new-device email.

**Sessions** are django-allauth's ``usersessions`` (one ``UserSession`` per signed-in browser:
IP, user agent, created, last seen — activity tracked), listed and ended through the headless
API: ``GET /_allauth/browser/v1/auth/sessions`` and ``DELETE`` with ``{"sessions": [ids]}``. An
ended session is deleted server-side, so that browser's next request is signed out (401).
Numo9's list view adds ``device`` ("Chrome on Windows") to each session.

**New device** — at each sign-in the browser and operating system family (``describe``) are
compared with the person's ``KnownDevice`` rows. A device not seen before is remembered and, if
the person had signed in before from another device, they get the ``new_device`` email (A-07-T11,
in their language; security email — always sent). The very first sign-in sends nothing.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from django.conf import settings
from django.utils import timezone, translation
from django.utils.formats import date_format

logger = logging.getLogger("numo9.accounts.devices")

_BROWSERS = (
    ("Edge", r"Edg(?:e|A|iOS)?/"),
    ("Opera", r"OPR/|Opera"),
    ("Samsung Internet", r"SamsungBrowser/"),
    ("Firefox", r"Firefox/|FxiOS/"),
    ("Chrome", r"Chrome/|CriOS/"),
    ("Safari", r"Safari/"),
)
_SYSTEMS = (
    ("iPhone", r"iPhone"),
    ("iPad", r"iPad"),
    ("Android", r"Android"),
    ("Windows", r"Windows"),
    ("macOS", r"Mac OS X|Macintosh"),
    ("ChromeOS", r"CrOS"),
    ("Linux", r"Linux"),
)


def describe(user_agent: str) -> tuple[str, str]:
    """(browser, system) families of a user agent; ``("", "")`` when unknown."""
    ua = user_agent or ""
    browser = next((name for name, pattern in _BROWSERS if re.search(pattern, ua)), "")
    system = next((name for name, pattern in _SYSTEMS if re.search(pattern, ua)), "")
    return browser, system


def device_name(user_agent: str) -> str:
    browser, system = describe(user_agent)
    if browser and system:
        with translation.override(translation.get_language()):
            return str(translation.gettext("%(browser)s on %(system)s")) % {
                "browser": browser,
                "system": system,
            }
    return browser or system or str(translation.gettext("Unknown device"))


def fingerprint(user: Any, user_agent: str) -> str:
    browser, system = describe(user_agent)
    return hashlib.sha256(f"{user.pk}|{browser}|{system}".encode()).hexdigest()


def remember_device(request: Any, user: Any) -> bool:
    """Record this sign-in's device; True when it is new for someone who signed in before."""
    from .models import KnownDevice

    agent = request.META.get("HTTP_USER_AGENT", "")
    key = fingerprint(user, agent)
    now = timezone.now()
    known = KnownDevice.objects.filter(user=user)
    had_devices = known.exists()
    row, created = KnownDevice.objects.get_or_create(
        user=user, fingerprint=key, defaults={"name": device_name(agent)[:120], "last_seen_at": now}
    )
    if not created:
        KnownDevice.objects.filter(pk=row.pk).update(last_seen_at=now)
    return created and had_devices


def send_new_device_email(request: Any, user: Any) -> None:
    from allauth.account.adapter import get_adapter

    from numo9.notifications.catalogue import render_system
    from numo9.notifications.mail import queue_email

    language = user.locale or settings.LANGUAGE_CODE
    with translation.override(language):
        when = date_format(timezone.localtime(), "DATETIME_FORMAT")
        email = render_system(
            "new_device",
            {
                "email": user.email,
                "device": device_name(request.META.get("HTTP_USER_AGENT", "")),
                "ip": get_adapter().get_client_ip(request) or "?",
                "when": when,
                "link": f"{settings.FRONTEND_URL}/account/security",
            },
            language=language,
        )
    queue_email(
        user.email,
        email.subject,
        email.text,
        html=email.html,
        recipient=user,
        kind="new_device",
        language=email.language,
    )


def on_logged_in(sender: Any, request: Any, user: Any, **kwargs: Any) -> None:
    if request is None:
        return
    try:
        if remember_device(request, user):
            send_new_device_email(request, user)
    except Exception:  # a sign-in never fails because the alert couldn't be prepared
        logger.exception("devices.new_device_failed")

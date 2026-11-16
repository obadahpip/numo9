"""System message catalogue (A-07-T11): the platform's own emails, EN and FR, with the context
each needs and a sample to render it — seeded as templates under ``templates/email/<name>/``.

- ``verify_email`` — sign-up, change of email (A-02): name, email, link;
- ``invitation`` — invitation created or resent (A-02-T09): inviter, target, role, email,
  expires, link;
- ``trial_reminder`` — 7, 3 and 1 days before the trial ends, and when it ended (U-05):
  organisation, days_left, ends_on, link;
- ``dunning`` — payment failed, day 0, 3, 5 and 7 (U-04-T09): organisation, amount, failed_on,
  grace_until, day, link;
- ``new_device`` — sign-in from a device not seen before (A-02-T07): email, device, ip, when,
  link.

``render_system(name, context, language, organisation)`` checks the context is complete
(``MissingContext`` names what is missing — never an email with a blank) and renders it with
``templating.render_email``. ``tests/test_notifications_catalogue.py`` renders every message in
both languages against snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from numo9.tenancy.models import Organisation

from .templating import RenderedEmail, render_email


@dataclass(frozen=True)
class SystemMessage:
    name: str
    purpose: str
    context: tuple[str, ...]
    sample: dict[str, Any] = field(default_factory=dict)


class MissingContext(KeyError):
    """A system message was rendered without a value it needs."""


LINK = "https://app.numo9.ca/"

SYSTEM_MESSAGES: dict[str, SystemMessage] = {
    m.name: m
    for m in (
        SystemMessage(
            "verify_email",
            "Verify the email address at sign-up",
            ("name", "email", "link"),
            {"name": "Dana Lee", "email": "dana@refined.ca", "link": f"{LINK}verify/Mg-abc123"},
        ),
        SystemMessage(
            "invitation",
            "Invitation to a practice or an organisation",
            ("inviter", "target", "role", "email", "expires", "link"),
            {
                "inviter": "Priya Shah",
                "target": "Refined Interiors Inc.",
                "role": "Accountant",
                "email": "sam@northstar.ca",
                "expires": "2026-11-23",
                "link": f"{LINK}invite/tok-123",
            },
        ),
        SystemMessage(
            "trial_reminder",
            "Trial ending (7, 3, 1 days) or ended",
            ("organisation", "days_left", "ends_on", "link"),
            {"days_left": 3, "ends_on": "2026-11-19", "link": f"{LINK}o/x/settings/subscription"},
        ),
        SystemMessage(
            "dunning",
            "Subscription payment failed (day 0, 3, 5, 7)",
            ("organisation", "amount", "failed_on", "grace_until", "day", "link"),
            {
                "amount": "$45.20",
                "failed_on": "2026-11-16",
                "grace_until": "2026-11-23",
                "day": 0,
                "link": f"{LINK}o/x/settings/subscription",
            },
        ),
        SystemMessage(
            "new_device",
            "Sign-in from a new device",
            ("email", "device", "ip", "when", "link"),
            {
                "email": "dana@refined.ca",
                "device": "Chrome on Windows",
                "ip": "203.0.113.24",
                "when": "2026-11-16 9:41 a.m.",
                "link": f"{LINK}account/security",
            },
        ),
    )
}


def render_system(
    name: str,
    context: dict[str, Any],
    *,
    language: str | None = None,
    organisation: Organisation | None = None,
) -> RenderedEmail:
    message = SYSTEM_MESSAGES[name]
    given = dict(context)
    if organisation is not None:
        given.setdefault("organisation", organisation.name)
    missing = [key for key in message.context if given.get(key) in (None, "")]
    if missing:
        raise MissingContext(f"{name}: {', '.join(missing)}")
    return render_email(name, given, language=language, organisation=organisation)

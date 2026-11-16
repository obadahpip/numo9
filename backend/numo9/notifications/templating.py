"""Email templates: MJML base layout, branding per practice/organisation, EN/FR variants
(A-07-T04).

An email template is a folder under ``templates/email/<name>/`` with one file per part and
language:

    subject.<language>.txt          one line
    body.html.<language>.mjml       extends ``email/base.mjml`` (MJML with Django template tags)
    body.<language>.txt             the plain-text part

``render_email(name, context, language=…, organisation=…)``

1. picks the **language variant**: the language asked (``fr-ca`` for a French reader); a template
   without that variant falls back to ``en-ca`` and says so (``fallback=True``, logged) — an email
   is never missing because a translation is;
2. resolves the **brand**: the organisation's own email branding, else the branding of the
   practice that serves it (its active full-service assignment, oldest first), else Numo9's.
   The accent colour is the brand's (buttons, top rule); the text on it is white or near-black,
   whichever has the higher contrast (WCAG 2.x relative luminance) — a pale brand colour never
   gives an unreadable button;
3. renders the Django templates with the context (+ ``brand``, ``language``, ``subject``,
   ``organisation``), then compiles the MJML to HTML (``mrml``, a Rust MJML engine — no Node.js
   at runtime). Compiled output is responsive, table-based HTML that email apps render.

Returns ``RenderedEmail(subject, text, html, language, fallback, brand)``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import mrml
from django.template import TemplateDoesNotExist
from django.template.loader import get_template, select_template
from django.utils import translation

from numo9.tenancy.context import org_context
from numo9.tenancy.models import AssignmentRole, Organisation, PracticeAssignment

from .models import OrganisationBranding, PracticeBranding

logger = logging.getLogger("numo9.notifications.email")

DEFAULT_LANGUAGE = "en-ca"
LANGUAGES = ("en-ca", "fr-ca")
NUMO9_COLOUR = "#1F4E79"
DARK_TEXT = "#1A1A1A"
LIGHT_TEXT = "#FFFFFF"


@dataclass(frozen=True)
class EmailBrand:
    name: str
    colour: str
    logo_url: str = ""
    source: str = "numo9"  # numo9 | practice | organisation

    @property
    def on_colour(self) -> str:
        """White or near-black text on the accent colour, whichever contrasts more."""
        return (
            LIGHT_TEXT
            if contrast(self.colour, LIGHT_TEXT) >= contrast(self.colour, DARK_TEXT)
            else DARK_TEXT
        )


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text: str
    html: str
    language: str
    fallback: bool
    brand: EmailBrand


def _luminance(colour: str) -> float:
    channels = [int(colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


NUMO9 = EmailBrand(name="Numo9", colour=NUMO9_COLOUR)


def _from_fields(row: Any, fallback_name: str, source: str) -> EmailBrand:
    return EmailBrand(
        name=row.display_name or fallback_name,
        colour=row.colour or NUMO9_COLOUR,
        logo_url=row.logo_url,
        source=source,
    )


def brand_for(organisation: Organisation | None) -> EmailBrand:
    """Organisation branding → its practice's branding → Numo9."""
    if organisation is None:
        return NUMO9
    with org_context(organisation):
        own = OrganisationBranding.objects.filter(deleted_at__isnull=True).first()
    if own is not None:
        return _from_fields(own, organisation.name, "organisation")
    assignment = (
        PracticeAssignment.objects.filter(
            organisation=organisation, active=True, role=AssignmentRole.FULL_SERVICE
        )
        .select_related("practice")
        .order_by("created_at", "pk")
        .first()
    )
    if assignment is not None:
        practice_brand = PracticeBranding.objects.filter(practice=assignment.practice).first()
        if practice_brand is not None:
            return _from_fields(practice_brand, assignment.practice.name, "practice")
    return EmailBrand(name=organisation.name, colour=NUMO9_COLOUR)


def normalise_language(language: str | None) -> str:
    value = (language or DEFAULT_LANGUAGE).lower().replace("_", "-")
    if value in LANGUAGES:
        return value
    return "fr-ca" if value.startswith("fr") else DEFAULT_LANGUAGE


def _variant(name: str, part: str, language: str) -> tuple[Any, str]:
    """The template of ``part`` in ``language`` or, failing that, in English."""
    candidates = [f"email/{name}/{part}.{language}.{_ext(part)}"]
    if language != DEFAULT_LANGUAGE:
        candidates.append(f"email/{name}/{part}.{DEFAULT_LANGUAGE}.{_ext(part)}")
    template = select_template(candidates)
    used = DEFAULT_LANGUAGE if template.template.name == candidates[-1] else language
    return template, used


def _ext(part: str) -> str:
    return "mjml" if part == "body.html" else "txt"


def template_exists(name: str) -> bool:
    try:
        get_template(f"email/{name}/subject.{DEFAULT_LANGUAGE}.txt")
    except TemplateDoesNotExist:
        return False
    return True


def render_email(
    name: str,
    context: dict[str, Any] | None = None,
    *,
    language: str | None = None,
    organisation: Organisation | None = None,
    brand: EmailBrand | None = None,
) -> RenderedEmail:
    wanted = normalise_language(language)
    brand = brand or brand_for(organisation)
    values: dict[str, Any] = {
        "organisation": organisation.name if organisation is not None else "",
        **(context or {}),
        "brand": brand,
    }
    with translation.override(wanted):
        subject_template, subject_lang = _variant(name, "subject", wanted)
        subject = " ".join(subject_template.render({**values, "language": wanted}).split())
        values = {**values, "subject": subject, "language": wanted}
        values.setdefault("preheader", values.get("body", "") or subject)
        text_template, text_lang = _variant(name, "body", wanted)
        html_template, html_lang = _variant(name, "body.html", wanted)
        text = text_template.render(values).strip() + "\n"
        mjml_source = html_template.render(values)
    output = mrml.to_html(mjml_source)
    fallback = any(used != wanted for used in (subject_lang, text_lang, html_lang))
    if fallback:
        logger.warning("email.template_fallback", extra={"template": name, "language": wanted})
    return RenderedEmail(subject, text, output.content, wanted, fallback, brand)

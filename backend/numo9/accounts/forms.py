"""Sign-up form (A-02-T02), used by django-allauth's headless sign-up endpoint.

Four fields for the person — path, name, email, password — plus the name of what they create:

- ``path = "accountant"`` → a free **practice** named ``practice_name``; the user is its
  practice admin (flow F1: then a demo organisation, U-07);
- ``path = "organisation"`` → a trial **organisation** named ``organisation_name``; the user is
  its owner (flow F4: subscribe later, U-04/U-05).

The user, the practice or organisation and the membership are created in one transaction with
the account; the email address must still be verified before the first login.
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from numo9.tenancy.models import (
    Organisation,
    OrganisationMember,
    OrganisationRole,
    OrganisationStatus,
    Practice,
    PracticeMember,
    PracticeRole,
)

from .models import Locale, User, default_time_format


class SignupPath:
    ACCOUNTANT = "accountant"
    ORGANISATION = "organisation"
    CHOICES = (
        (ACCOUNTANT, _("I'm an accountant")),
        (ORGANISATION, _("I run a business")),
    )


class SignupForm(forms.Form):
    path = forms.ChoiceField(label=_("Who are you?"), choices=SignupPath.CHOICES)
    name = forms.CharField(label=_("Your name"), max_length=150, strip=True)
    practice_name = forms.CharField(
        label=_("Practice name"), max_length=200, strip=True, required=False
    )
    organisation_name = forms.CharField(
        label=_("Business name"), max_length=200, strip=True, required=False
    )
    locale = forms.ChoiceField(label=_("Language"), choices=Locale.choices, required=False)

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        path = data.get("path")
        if path == SignupPath.ACCOUNTANT and not data.get("practice_name"):
            self.add_error(
                "practice_name",
                forms.ValidationError(
                    _("Enter your practice's name, e.g. 'Maple Leaf Accounting'."),
                    code="practice_name_required",
                ),
            )
        if path == SignupPath.ORGANISATION and not data.get("organisation_name"):
            self.add_error(
                "organisation_name",
                forms.ValidationError(
                    _("Enter your business name, e.g. 'Refined Interiors Inc.'."),
                    code="organisation_name_required",
                ),
            )
        return data

    def signup(self, request: HttpRequest, user: User) -> None:
        """Called by allauth inside the sign-up transaction, after the user is saved."""
        data = self.cleaned_data
        user.name = data["name"]
        user.locale = data.get("locale") or Locale.EN_CA
        user.time_format = default_time_format(user.locale)
        user.save(update_fields=["name", "locale", "time_format"])
        if data["path"] == SignupPath.ACCOUNTANT:
            practice = Practice.objects.create(name=data["practice_name"])
            PracticeMember.objects.create(
                practice=practice, user=user, role=PracticeRole.PRACTICE_ADMIN
            )
        else:
            organisation = Organisation.objects.create(
                name=data["organisation_name"],
                status=OrganisationStatus.TRIAL,
                locale=user.locale,
            )
            OrganisationMember.objects.create(
                organisation=organisation, user=user, role=OrganisationRole.OWNER
            )

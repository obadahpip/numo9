"""Serializers for the tenancy API (A-01-T13)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from numo9.accounts.models import Locale

from .models import (
    DEFAULT_TIME_ZONE,
    AssignmentRole,
    Organisation,
    OrganisationRole,
    OrganisationStatus,
    Practice,
    PracticeRole,
    validate_time_zone,
)


class MembershipSerializer(serializers.Serializer[Any]):
    role = serializers.ChoiceField(choices=OrganisationRole.choices)


class ViaPracticeSerializer(serializers.Serializer[Any]):
    """A practice through which the user reaches the organisation."""

    practice_id = serializers.UUIDField()
    practice_name = serializers.CharField()
    practice_role = serializers.ChoiceField(choices=PracticeRole.choices)
    assignment_role = serializers.ChoiceField(choices=AssignmentRole.choices)
    assigned_staff = serializers.BooleanField(help_text="The user is named in the assignment.")


class MyOrganisationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id")
    name = serializers.CharField()
    status = serializers.ChoiceField(choices=OrganisationStatus.choices)
    time_zone = serializers.CharField()
    locale = serializers.ChoiceField(
        choices=Locale.choices, help_text="Default language of the organisation's documents."
    )
    membership = MembershipSerializer(
        allow_null=True, help_text="The user's own role in the organisation, if a member."
    )
    via_practices = ViaPracticeSerializer(many=True)


class PracticeCreateSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200, trim_whitespace=True)


class PracticeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id")
    name = serializers.CharField()
    role = serializers.ChoiceField(choices=PracticeRole.choices)


class OrganisationCreateSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=200, trim_whitespace=True)
    time_zone = serializers.CharField(
        max_length=64, required=False, default=DEFAULT_TIME_ZONE, validators=[validate_time_zone]
    )
    locale = serializers.ChoiceField(choices=Locale.choices, required=False, default=Locale.EN_CA)
    practice = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text=(
            "Create the organisation for a client of this practice (the user must be a member). "
            "Without it, the user becomes the organisation's owner."
        ),
    )


__all__ = [
    "MyOrganisationSerializer",
    "Organisation",
    "OrganisationCreateSerializer",
    "Practice",
    "PracticeCreateSerializer",
    "PracticeSerializer",
]

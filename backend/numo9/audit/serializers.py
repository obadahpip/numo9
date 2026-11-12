"""OpenAPI shapes of the audit log API (A-04-T07). The data comes from ``presenter.event_data``."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import ActorKind


class AuditPersonSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    email = serializers.EmailField()


class AuditActorSerializer(serializers.Serializer[Any]):
    kind = serializers.ChoiceField(choices=ActorKind.choices)
    label = serializers.CharField(help_text="As shown in the log, e.g. 'System: Reprice invoices'")  # type: ignore[assignment]
    user = AuditPersonSerializer(allow_null=True)
    impersonator = AuditPersonSerializer(allow_null=True)


class AuditRecordSerializer(serializers.Serializer[Any]):
    type = serializers.CharField(help_text="Record type (model label)")
    type_label = serializers.CharField()
    id = serializers.CharField(help_text="The record's public id")
    label = serializers.CharField()  # type: ignore[assignment]  # field named label


class AuditChangeSerializer(serializers.Serializer[Any]):
    field = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]  # field named label
    old = serializers.JSONField(allow_null=True)
    new = serializers.JSONField(allow_null=True)
    masked = serializers.BooleanField(help_text="The value is hidden (SIN, bank details…)")


class AuditEventSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    at = serializers.DateTimeField()
    action = serializers.CharField()
    action_label = serializers.CharField()
    verb = serializers.ChoiceField(choices=["created", "updated", "deleted", "restored", "other"])
    actor = AuditActorSerializer()
    record = AuditRecordSerializer()
    changes = AuditChangeSerializer(many=True)
    meta = serializers.DictField(child=serializers.JSONField())
    ip = serializers.IPAddressField(allow_null=True)
    device = serializers.CharField()
    request_id = serializers.CharField()
    batch_id = serializers.UUIDField(allow_null=True)
    is_batch_summary = serializers.BooleanField()


class AuditEventDetailSerializer(AuditEventSerializer):
    hash = serializers.CharField()
    prev_hash = serializers.CharField()


class AuditRangeSerializer(serializers.Serializer[Any]):
    from_ = serializers.DateField()
    to = serializers.DateField()
    default = serializers.BooleanField(help_text="True when no dates were given: last 90 days")
    time_zone = serializers.CharField()

    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        fields = super().get_fields()
        fields["from"] = fields.pop("from_")
        return fields


class AuditViewerSerializer(serializers.Serializer[Any]):
    locale = serializers.CharField()
    time_format = serializers.ChoiceField(choices=["12h", "24h"])
    time_zone = serializers.CharField()


class AuditPageSerializer(serializers.Serializer[Any]):
    results = AuditEventSerializer(many=True)
    next = serializers.CharField(allow_null=True, help_text="Cursor of the next page")
    range = AuditRangeSerializer()
    viewer = AuditViewerSerializer()


class AuditHistorySerializer(serializers.Serializer[Any]):
    record = AuditRecordSerializer()
    results = AuditEventSerializer(many=True)
    next = serializers.CharField(allow_null=True)
    viewer = AuditViewerSerializer()


class AuditOptionSerializer(serializers.Serializer[Any]):
    value = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]  # field named label


class AuditFiltersSerializer(serializers.Serializer[Any]):
    users = AuditOptionSerializer(many=True)
    types = AuditOptionSerializer(many=True)
    actions = AuditOptionSerializer(many=True)

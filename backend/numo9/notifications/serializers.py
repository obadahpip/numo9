"""Notification API shapes (A-07-T01)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .models import Notification, NotificationCategory
from .texts import render


class NotificationSerializer(serializers.ModelSerializer[Notification]):
    id = serializers.UUIDField(source="public_id", read_only=True)
    category_label = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    params = serializers.JSONField(source="body_params", read_only=True)
    read = serializers.BooleanField(source="is_read", read_only=True)

    class Meta:
        model = Notification
        fields = (
            "id",
            "category",
            "category_label",
            "title",
            "body",
            "title_key",
            "params",
            "link",
            "read",
            "read_at",
            "created_at",
        )
        read_only_fields = fields

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._cache: dict[tuple[str, str], tuple[str, str]] = {}

    def _language(self) -> str | None:
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return getattr(user, "locale", None) or None

    def _rendered(self, notification: Notification) -> tuple[str, str]:
        key = (notification.title_key, repr(notification.body_params))
        if key not in self._cache:
            self._cache[key] = render(
                notification.title_key, notification.body_params, self._language()
            )
        return self._cache[key]

    def get_category_label(self, notification: Notification) -> str:
        return str(NotificationCategory(notification.category).label)

    def get_title(self, notification: Notification) -> str:
        return self._rendered(notification)[0]

    def get_body(self, notification: Notification) -> str:
        return self._rendered(notification)[1]


class NotificationPageSerializer(serializers.Serializer[Any]):
    results = NotificationSerializer(many=True)
    unread_count = serializers.IntegerField()
    next = serializers.UUIDField(allow_null=True, help_text="Pass as ?before= for the next page.")


class UnreadCountSerializer(serializers.Serializer[Any]):
    unread_count = serializers.IntegerField()


class ReadAllRequestSerializer(serializers.Serializer[Any]):
    category = serializers.ChoiceField(
        choices=NotificationCategory.choices, required=False, help_text="Only this category"
    )


class ReadAllResultSerializer(serializers.Serializer[Any]):
    marked = serializers.IntegerField()
    unread_count = serializers.IntegerField()

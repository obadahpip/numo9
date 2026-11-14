"""Serializers of the documents API (A-06)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from .listing import BULK_ACTION_CHOICES
from .models import MAX_FILE_SIZE, NAME_MAX, Document


class DocumentSerializer(serializers.Serializer[Document]):
    id = serializers.UUIDField(source="public_id", read_only=True)
    name = serializers.CharField(read_only=True)
    mime = serializers.CharField(read_only=True)
    size = serializers.IntegerField(read_only=True)
    sha256 = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    source = serializers.CharField(read_only=True)  # type: ignore[assignment]  # API field name
    sender = serializers.CharField(read_only=True)
    sender_known = serializers.BooleanField(read_only=True)
    period = serializers.CharField(read_only=True)
    tax_year = serializers.IntegerField(read_only=True, allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(), read_only=True)
    folder = serializers.CharField(read_only=True)
    preview_status = serializers.CharField(read_only=True)
    password_protected = serializers.BooleanField(read_only=True)
    uploaded_by = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)

    def get_uploaded_by(self, document: Document) -> str:
        user = document.created_by
        return (user.get_full_name() or user.email) if user is not None else ""


class UploadRequestSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=NAME_MAX)
    size = serializers.IntegerField(min_value=0, help_text=f"Bytes; at most {MAX_FILE_SIZE}")


class UploadFormSerializer(serializers.Serializer[Any]):
    url = serializers.URLField()
    fields = serializers.DictField(child=serializers.CharField())  # type: ignore[assignment]


class UploadResponseSerializer(serializers.Serializer[Any]):
    document = DocumentSerializer()
    upload = UploadFormSerializer()
    max_size = serializers.IntegerField()


class FinalizeResponseSerializer(DocumentSerializer):
    duplicate = serializers.BooleanField(read_only=True, default=False)


class SignedUrlSerializer(serializers.Serializer[Any]):
    url = serializers.URLField()
    expires_at = serializers.DateTimeField()


class PreviousAddressSerializer(serializers.Serializer[Any]):
    address = serializers.CharField()
    accepted_until = serializers.DateTimeField()


class InboundAddressSerializer(serializers.Serializer[Any]):
    address = serializers.CharField()
    created_at = serializers.DateTimeField()
    previous = PreviousAddressSerializer(allow_null=True)


class AttachmentSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id", read_only=True)
    record_type = serializers.CharField(read_only=True)
    record_id = serializers.UUIDField(source="object_public_id", read_only=True)
    document = DocumentSerializer(read_only=True)
    attached_at = serializers.DateTimeField(source="created_at", read_only=True)
    attached_by = serializers.SerializerMethodField()

    def get_attached_by(self, link: Any) -> str:
        user = link.created_by
        return (user.get_full_name() or user.email) if user is not None else ""


class AttachRequestSerializer(serializers.Serializer[Any]):
    document = serializers.UUIDField()
    record_type = serializers.CharField(max_length=100)
    record_id = serializers.UUIDField()


class AttachmentListSerializer(serializers.Serializer[Any]):
    results = AttachmentSerializer(many=True)


class DocumentPageSerializer(serializers.Serializer[Any]):
    results = DocumentSerializer(many=True)
    next = serializers.CharField(allow_null=True)
    total = serializers.IntegerField()


class DocumentUpdateSerializer(serializers.Serializer[Any]):
    name = serializers.CharField(max_length=NAME_MAX, required=False)
    period = serializers.CharField(max_length=7, required=False, allow_blank=True)
    tax_year = serializers.IntegerField(required=False, allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(max_length=40), required=False)
    folder = serializers.ChoiceField(choices=["inbox", "archived"], required=False)


class BulkRequestSerializer(serializers.Serializer[Any]):
    ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)
    action = serializers.ChoiceField(choices=BULK_ACTION_CHOICES)
    tags = serializers.ListField(child=serializers.CharField(max_length=40), required=False)
    period = serializers.CharField(max_length=7, required=False, allow_blank=True)
    tax_year = serializers.IntegerField(required=False, allow_null=True)


class BulkResultSerializer(serializers.Serializer[Any]):
    updated = serializers.IntegerField()


class TagCountSerializer(serializers.Serializer[Any]):
    tag = serializers.CharField()
    count = serializers.IntegerField()


class TagListSerializer(serializers.Serializer[Any]):
    results = TagCountSerializer(many=True)


class FileActionSerializer(serializers.Serializer[Any]):
    key = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]  # API field name
    module = serializers.CharField()
    available = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    url = serializers.CharField(allow_blank=True)


class FileActionListSerializer(serializers.Serializer[Any]):
    results = FileActionSerializer(many=True)

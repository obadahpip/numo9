"""Serializers of the accountant workspace API (V-01): the OpenAPI contract of the directory."""

from __future__ import annotations

import builtins
import re
from typing import Any

from rest_framework import serializers

from numo9.i18n import errors
from numo9.i18n.errors import error_detail

from .models import Density, DirectoryStatus, GstCycle


class DirectoryPracticeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()


class DirectoryRowSerializer(serializers.Serializer[Any]):
    """One organisation. Only ``id``, ``name`` and the requested columns' fields are present."""

    id = serializers.UUIDField(help_text="Organisation public id (``/o/<id>/…``).")
    name = serializers.CharField()
    legal_name = serializers.CharField(required=False)
    bn = serializers.CharField(required=False, help_text="Nine digits, empty when none.")
    owner_name = serializers.CharField(required=False)
    owner_email = serializers.CharField(required=False)
    industry = serializers.CharField(required=False)
    province = serializers.CharField(required=False, help_text="Two-letter code, may be empty.")
    package = serializers.CharField(required=False, help_text="Package code, may be empty.")
    package_name = serializers.CharField(required=False)
    status = serializers.ChoiceField(choices=DirectoryStatus.choices, required=False)
    trial_ends_at = serializers.DateTimeField(required=False, allow_null=True)
    trial_days_left = serializers.IntegerField(required=False, allow_null=True)
    fye_month = serializers.IntegerField(required=False)
    fye_day = serializers.IntegerField(required=False)
    gst_cycle = serializers.CharField(
        required=False, help_text=f"One of {', '.join(GstCycle.values)}; empty when unknown."
    )
    payroll_enabled = serializers.BooleanField(required=False)
    overdue_count = serializers.IntegerField(required=False)
    unfiled_count = serializers.IntegerField(required=False)
    tags = serializers.ListField(child=serializers.CharField(), required=False)
    groups = serializers.ListField(
        child=serializers.DictField(child=serializers.CharField()),
        required=False,
        help_text='Groups the organisation is filed in directly: [{"id", "name"}] (V-02-T08).',
    )


class FacetValueSerializer(serializers.Serializer[Any]):
    value = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]  # popped by the metaclass
    count = serializers.IntegerField(
        help_text="Organisations shown with this value added (every other filter applied)."
    )
    depth = serializers.IntegerField(
        required=False, help_text="Group facet only: the group's level (1 = top)."
    )


class DirectoryFacetsSerializer(serializers.Serializer[Any]):
    package = FacetValueSerializer(many=True)
    status = FacetValueSerializer(many=True)
    province = FacetValueSerializer(many=True)
    fye = FacetValueSerializer(many=True)
    gst_cycle = FacetValueSerializer(many=True)
    payroll = FacetValueSerializer(many=True)
    overdue = FacetValueSerializer(many=True)
    unfiled = FacetValueSerializer(many=True)
    # Practice dashboard drill-downs (V-04-T07).
    bn_missing = FacetValueSerializer(many=True)
    lock_missing = FacetValueSerializer(many=True)
    trial_ending = FacetValueSerializer(many=True)
    mine = FacetValueSerializer(many=True)
    tag = FacetValueSerializer(many=True)
    group = FacetValueSerializer(many=True)


class DirectoryGroupSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    name = serializers.CharField()
    depth = serializers.IntegerField()
    parent = serializers.UUIDField(allow_null=True)  # type: ignore[assignment]  # DRF Field.parent


class DirectoryGroupingSerializer(serializers.Serializer[Any]):
    group = DirectoryGroupSerializer(allow_null=True, help_text="null: organisations in no group.")
    count = serializers.IntegerField(help_text="Matching organisations filed in this group.")
    organisations = serializers.ListField(
        child=serializers.UUIDField(), help_text="Their ids, in the directory's order."
    )


class DirectoryPageSerializer(serializers.Serializer[Any]):
    practice = DirectoryPracticeSerializer()
    count = serializers.IntegerField(help_text="Organisations matching the search and filters.")
    total = serializers.IntegerField(help_text="Organisations in the directory (no search/filter).")
    page = serializers.IntegerField()
    page_size = serializers.IntegerField()
    pages = serializers.IntegerField()
    columns = serializers.ListField(child=serializers.CharField())
    results = DirectoryRowSerializer(many=True)
    facets = DirectoryFacetsSerializer(required=False)
    grouping = DirectoryGroupingSerializer(
        many=True, required=False, help_text="With group_by=group: the group headers (V-02-T08)."
    )


# ---- saved views (V-01-T08) --------------------------------------------------------------------

VIEW_FILTER_KEYS = ("q", "archived")  # besides the directory filters (search.FILTERS)


def _is_uuid(value: str) -> bool:
    import uuid

    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


class SavedViewSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id")
    practice = serializers.UUIDField(source="practice.public_id")
    name = serializers.CharField()
    filters = serializers.DictField(
        help_text='Search and filters: {"q": "maple", "province": ["ON"], "archived": "include"}.'
    )
    columns = serializers.ListField(child=serializers.CharField())
    sort = serializers.ListField(child=serializers.CharField())
    density = serializers.ChoiceField(choices=Density.choices)
    is_default = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class SavedViewWriteBase(serializers.Serializer[Any]):
    """The fields every saved view takes (directory and organisation lists, D-09-T03)."""

    name = serializers.CharField(max_length=80, trim_whitespace=True)
    filters = serializers.DictField(required=False)
    columns = serializers.ListField(child=serializers.CharField(), required=False, max_length=30)
    sort = serializers.ListField(child=serializers.CharField(), required=False, max_length=5)
    density = serializers.ChoiceField(choices=Density.choices, required=False)
    is_default = serializers.BooleanField(required=False)


class SavedViewWriteSerializer(SavedViewWriteBase):
    """Create (``practice`` and ``name`` required) or change a view (any field)."""

    practice = serializers.UUIDField(required=False, help_text="Default: the user's only practice.")

    def validate_filters(self, value: dict[str, Any]) -> dict[str, Any]:
        from .api import filter_choices
        from .search import FILTERS

        def bad(key: str, item: Any) -> serializers.ValidationError:
            detail = error_detail(errors.WORKSPACE_BAD_FILTER, name=key, value=str(item)[:100])
            return serializers.ValidationError([detail])

        clean: dict[str, Any] = {}
        for key, raw in value.items():
            if key == "q":
                if not isinstance(raw, str) or len(raw) > 200:
                    raise bad(key, raw)
                if raw.strip():
                    clean["q"] = raw.strip()
            elif key == "archived":
                if raw not in ("include", "exclude"):
                    raise bad(key, raw)
                clean["archived"] = raw
            elif key not in FILTERS:
                raise bad(key, raw)
            else:
                values = raw if isinstance(raw, list) else [raw]
                allowed = filter_choices(key)
                for item in values:
                    if not isinstance(item, str) or len(item) > 100:
                        raise bad(key, item)
                    if key == "group" and not _is_uuid(item):
                        raise bad(key, item)
                    if allowed is not None and item not in allowed:
                        raise bad(key, item)
                if values:
                    clean[key] = list(dict.fromkeys(values))
        return clean

    def validate_columns(self, value: list[str]) -> list[str]:
        from .api import COLUMNS

        for column in value:
            if column not in COLUMNS:
                detail = error_detail(errors.WORKSPACE_BAD_COLUMN, value=column[:100])
                raise serializers.ValidationError([detail])
        return list(dict.fromkeys(value))

    def validate_sort(self, value: list[str]) -> list[str]:
        from .search import SORTS

        for key in value:
            if key.lstrip("-") not in SORTS:
                detail = error_detail(errors.WORKSPACE_BAD_SORT, value=key[:100])
                raise serializers.ValidationError([detail])
        return value


# ---- saved list views inside an organisation (D-09-T03) ----------------------------------------

_KEY = re.compile(r"^[a-z][a-z0-9_]*$")


class SavedListViewSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(source="public_id")
    list = serializers.CharField(source="list_key", help_text="e.g. sales.invoices")
    name = serializers.CharField()
    filters = serializers.DictField(
        help_text='The list\'s query parameters: {"tab": "overdue", "q": "maple"}.'
    )
    columns = serializers.ListField(child=serializers.CharField())
    sort = serializers.ListField(child=serializers.CharField())
    density = serializers.ChoiceField(choices=Density.choices)
    is_default = serializers.BooleanField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class SavedListViewWriteSerializer(SavedViewWriteBase):
    """Create (``list`` and ``name`` required) or change a list view (any field but ``list``)."""

    list = serializers.CharField(
        required=False, max_length=60, help_text="The list's key, e.g. sales.invoices."
    )

    def validate_list(self, value: str) -> str:
        from .saved_views import LIST_KEYS

        if value not in LIST_KEYS:
            raise serializers.ValidationError(
                [error_detail(errors.WORKSPACE_UNKNOWN_LIST, value=value[:60])]
            )
        return value

    def validate_filters(self, value: dict[str, Any]) -> dict[str, Any]:
        from .saved_views import clean_list_filters

        try:
            return clean_list_filters(value)
        except ValueError as error:
            name, item = error.args
            detail = error_detail(errors.WORKSPACE_BAD_VIEW_VALUE, name=name, value=item)
            raise serializers.ValidationError([detail]) from None

    def _keys(self, value: builtins.list[str], field: str, *, signed: bool) -> builtins.list[str]:
        for key in value:
            bare = key[1:] if signed and key.startswith("-") else key
            if not _KEY.match(bare) or len(bare) > 60:
                detail = error_detail(errors.WORKSPACE_BAD_VIEW_VALUE, name=field, value=key[:60])
                raise serializers.ValidationError([detail])
        return list(dict.fromkeys(value))

    def validate_columns(self, value: builtins.list[str]) -> builtins.list[str]:
        return self._keys(value, "columns", signed=False)

    def validate_sort(self, value: builtins.list[str]) -> builtins.list[str]:
        return self._keys(value, "sort", signed=True)

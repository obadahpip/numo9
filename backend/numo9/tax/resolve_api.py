"""Tax resolve API (G-02-T06): ``POST /api/v1/o/<org>/tax/resolve`` — the default tax code of
many document lines at once, for the sales and purchase editors.

Request ``{side, date, contact, ship_to: {country, province} | null, lines: [{account, item,
override}]}`` — ``account`` / ``item`` public ids, ``override`` a code key the person chose on
the line (it wins, the "changed from default" dot). Response ``{lines: [{key, tax_code: {id,
code, name, version} | null, source, auto, explanation, params, province, flags, warnings}]}``
in the same order: the explanation **key** and its parameters are the "auto" chip's tooltip
(translated by the editor, G-02-T10); ``warnings`` are the inline ones (``tax.pos.
pst_unregistered``, ``tax.pos.registration_stopped``).

The header (home province, registrations with their not-registered gaps, the contact's
addresses, the tax setting) is read **once** per request, each line only adds its item and
account, and each code key is resolved to its version once: 50 lines well under 100 ms.
Reading needs ``tax.codes.view``.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import CORE, requires_feature
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .models import TaxCode
from .permissions import TAX_VIEW
from .place_of_supply import Resolution, resolve
from .supply_context import _account_key, _item_key, build_context

MAX_LINES = 500


class AddressSerializer(serializers.Serializer[Any]):
    country = serializers.CharField(max_length=2, required=False, default="CA")
    province = serializers.CharField(max_length=2, required=False, allow_blank=True, default="")


class LineSerializer(serializers.Serializer[Any]):
    account = serializers.UUIDField(required=False, allow_null=True, default=None)
    item = serializers.UUIDField(required=False, allow_null=True, default=None)
    override = serializers.CharField(required=False, allow_blank=True, default="")


class ResolveSerializer(serializers.Serializer[Any]):
    side = serializers.ChoiceField(choices=["sales", "purchase"])
    date = serializers.DateField()
    contact = serializers.UUIDField(required=False, allow_null=True, default=None)
    ship_to = AddressSerializer(required=False, allow_null=True, default=None)
    lines = LineSerializer(many=True)

    def validate_lines(self, value: list[Any]) -> list[Any]:
        if len(value) > MAX_LINES:
            raise serializers.ValidationError(f"At most {MAX_LINES} lines.")
        return value


def _by_id(model: Any, ids: set[Any]) -> dict[str, Any]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {str(row.public_id): row for row in model.objects.filter(public_id__in=ids)}


def resolution_dict(resolution: Resolution, code: TaxCode | None) -> dict[str, Any]:
    return {
        "key": resolution.code,
        "tax_code": (
            {
                "id": str(code.public_id),
                "code": code.code,
                "name": code.name,
                "version": code.version,
            }
            if code is not None
            else None
        ),
        "source": resolution.source,
        "auto": resolution.auto,
        "explanation": resolution.explanation,
        "params": resolution.params,
        "province": resolution.province,
        "flags": sorted(resolution.flags),
        "warnings": list(resolution.warnings),
    }


def resolve_lines(
    organisation: Any,
    side: str,
    date: dt.date,
    lines: list[dict[str, Any]],
    *,
    contact: Any = None,
    ship_to: Any = None,
) -> list[dict[str, Any]]:
    from numo9.items.models import Item
    from numo9.ledger.models import Account

    from .resolver import TaxCodeExpired, TaxCodeUnknown, code_for

    header = build_context(side, date, organisation, contact=contact, ship_to=ship_to)
    accounts = _by_id(Account, {line.get("account") for line in lines})
    items = _by_id(Item, {line.get("item") for line in lines})
    versions: dict[str, TaxCode | None] = {}
    out = []
    for line in lines:
        account = accounts.get(str(line.get("account"))) if line.get("account") else None
        item = items.get(str(line.get("item"))) if line.get("item") else None
        context = replace(
            header,
            line_override=line.get("override") or "",
            item_code=_item_key(item, side),
            account_default=_account_key(account, side, header.home_province),
            taxable=bool(getattr(item, "is_taxable", True)) if item is not None else True,
        )
        resolution = resolve(context)
        key = resolution.code
        if key and key not in versions:
            try:
                versions[key] = code_for(key, side, date, organisation)
            except (TaxCodeExpired, TaxCodeUnknown):
                versions[key] = None
        out.append(resolution_dict(resolution, versions.get(key) if key else None))
    return out


class TaxResolveView(APIView):
    @requires_permission(TAX_VIEW.key)
    @requires_feature(CORE)
    @extend_schema(operation_id="tax_resolve", request=ResolveSerializer, responses={200: dict})
    def post(self, request: Request, org: Any) -> Response:
        from numo9.contacts.models import Contact

        payload = ResolveSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        contact = None
        if data.get("contact"):
            contact = Contact.objects.filter(public_id=data["contact"]).first()
            if contact is None:
                raise serializers.ValidationError({"contact": ["There's no such contact."]})
        organisation = current_org()
        return Response(
            {
                "lines": resolve_lines(
                    organisation,
                    data["side"],
                    data["date"],
                    [dict(line) for line in data["lines"]],
                    contact=contact,
                    ship_to=dict(data["ship_to"]) if data.get("ship_to") else None,
                )
            }
        )

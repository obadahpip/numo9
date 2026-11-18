"""Contacts API (B-01-T11), under ``/api/v1/o/<org>/``.

- ``GET contacts`` — the organisation's contacts by name: number, names, roles, primary person,
  billing province, currency, status. Filters ``role`` (one of the roles; the list is titled per
  role in the UI), ``status`` (``active`` default, ``archived``, ``all``), ``q`` (name, number,
  email, BN); pages of ``limit`` (1–200, 50) from ``offset``.
- ``POST contacts`` — add a contact with its ``people`` and ``addresses`` (one transaction).
- ``GET`` / ``PATCH contacts/<id>`` — every field, people, addresses, defaults and custom fields;
  ``people``/``addresses`` in a PATCH replace the lists (rows with an ``id`` are updated, missing
  ones removed, new ones added). ``POST contacts/<id>/archive`` / ``…/restore``.
- ``GET contacts/duplicates`` ``?q=&email=&bn=&tax_id=&exclude=`` — possible duplicates while
  typing (B-01-T10): the contact, the reasons and the name similarity.

Rules are the model's (B-01-T02…T10); refusals keep DRF's ``{field: [messages]}`` shape with the
rule codes. Permissions ``contacts.contacts.view`` / ``.manage``; features
``accounting.contacts.read`` / ``.write``; tenant sweep factory ``contacts.Contact``.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Prefetch, Q, QuerySet
from django.utils.translation import gettext as _
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from numo9.catalogue.drf import requires_feature
from numo9.rbac.drf import requires_permission
from numo9.tenancy.context import current_org

from .duplicates import find_duplicates
from .models import (
    Address,
    AmountsAre,
    Contact,
    ContactPerson,
    ContactRole,
    ContactStatus,
    CreditMode,
    PaymentTerm,
    StatementPreference,
)
from .permissions import CONTACTS_MANAGE, CONTACTS_VIEW

READ = "accounting.contacts.read"
WRITE = "accounting.contacts.write"
MAX_LIMIT, DEFAULT_LIMIT = 200, 50

PERSON_FIELDS = (
    "first_name",
    "last_name",
    "email",
    "phone",
    "job_title",
    "is_primary",
    "include_in_emails",
)
ADDRESS_FIELDS = (
    "kind",
    "attention",
    "line1",
    "line2",
    "city",
    "province",
    "region",
    "postal_code",
    "country",
)
CONTACT_FIELDS = (
    "number",
    "display_name",
    "legal_name",
    "roles",
    "bn",
    "tax_id",
    "currency",
    "credit_limit",
    "credit_mode",
    "t4a_flag",
    "portal_enabled",
    "statement_pref",
    "language",
    "custom_fields",
    "sales_amounts_are",
    "purchase_amounts_are",
)
ACCOUNT_DEFAULTS = ("sales_account", "purchase_account")
TERM_DEFAULTS = ("sales_payment_term", "purchase_payment_term")


def drf_errors(error: DjangoValidationError, prefix: str = "") -> ValidationError:
    if hasattr(error, "error_dict"):
        body = {
            f"{prefix}{field}": [
                serializers.ErrorDetail(str(message), code=item.code or "invalid")
                for item in items
                for message in item.messages
            ]
            for field, items in error.error_dict.items()
        }
    else:
        body = {
            f"{prefix}non_field_errors": [
                serializers.ErrorDetail(str(m), code=getattr(error, "code", None) or "invalid")
                for m in error.messages
            ]
        }
    return ValidationError(body)


# ---- output --------------------------------------------------------------------------------------


def _person(person: ContactPerson) -> dict[str, Any]:
    return {"id": str(person.public_id), **{f: getattr(person, f) for f in PERSON_FIELDS}}


def _address(address: Address) -> dict[str, Any]:
    return {"id": str(address.public_id), **{f: getattr(address, f) for f in ADDRESS_FIELDS}}


def _ref(obj: Any, label: str) -> dict[str, str] | None:
    return None if obj is None else {"id": str(obj.public_id), "name": label}


def _people(contact: Contact) -> list[ContactPerson]:
    return [p for p in contact.people.all() if p.deleted_at is None]


def _addresses(contact: Contact) -> list[Address]:
    return [a for a in contact.addresses.all() if a.deleted_at is None]


def summary(contact: Contact) -> dict[str, Any]:
    people = _people(contact)
    primary = next((p for p in people if p.is_primary), people[0] if people else None)
    billing = next((a for a in _addresses(contact) if a.kind == "billing"), None)
    return {
        "id": str(contact.public_id),
        "number": contact.number,
        "display_name": contact.display_name,
        "legal_name": contact.legal_name,
        "roles": list(contact.roles),
        "email": primary.email if primary else "",
        "phone": primary.phone if primary else "",
        "person": " ".join(filter(None, [primary.first_name, primary.last_name]))
        if primary
        else "",
        "province": billing.province if billing else "",
        "city": billing.city if billing else "",
        "currency": contact.currency,
        "bn": contact.bn,
        "status": contact.status,
        "archived": contact.status == ContactStatus.ARCHIVED,
    }


def detail(contact: Contact) -> dict[str, Any]:
    body = {**summary(contact), **{f: getattr(contact, f) for f in CONTACT_FIELDS}}
    body["roles"] = list(contact.roles)
    body["credit_limit"] = None if contact.credit_limit is None else f"{contact.credit_limit:.2f}"
    for field in ACCOUNT_DEFAULTS:
        account = getattr(contact, field)
        body[field] = (
            None
            if account is None
            else {"id": str(account.public_id), "code": account.code, "name": account.name}
        )
    for field in TERM_DEFAULTS:
        term = getattr(contact, field)
        body[field] = _ref(term, str(term) if term else "")
    body["people"] = [_person(p) for p in _people(contact)]
    body["addresses"] = [_address(a) for a in _addresses(contact)]
    body["archived_at"] = contact.archived_at
    alias_of = contact.merged_into
    body["merged_into"] = _ref(alias_of, alias_of.display_name if alias_of else "")
    body["created_at"] = contact.created_at
    body["updated_at"] = contact.updated_at
    return body


def _queryset() -> QuerySet[Contact]:
    return Contact.objects.filter(deleted_at__isnull=True).prefetch_related(
        Prefetch("people", queryset=ContactPerson.objects.filter(deleted_at__isnull=True)),
        Prefetch("addresses", queryset=Address.objects.filter(deleted_at__isnull=True)),
    )


def _one(public_id: Any) -> Contact:
    found = (
        _queryset()
        .select_related(*ACCOUNT_DEFAULTS, *TERM_DEFAULTS, "merged_into")
        .filter(public_id=public_id)
        .first()
    )
    if found is None:
        raise NotFound
    return found


# ---- input ---------------------------------------------------------------------------------------


class PersonSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(required=False)
    first_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=100, allow_blank=True, required=False)
    email = serializers.CharField(max_length=254, allow_blank=True, required=False)
    phone = serializers.CharField(max_length=40, allow_blank=True, required=False)
    job_title = serializers.CharField(max_length=100, allow_blank=True, required=False)
    is_primary = serializers.BooleanField(required=False)
    include_in_emails = serializers.BooleanField(required=False)


class AddressSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(required=False)
    kind = serializers.ChoiceField(choices=[("billing", "billing"), ("shipping", "shipping")])
    attention = serializers.CharField(max_length=100, allow_blank=True, required=False)
    line1 = serializers.CharField(max_length=200, allow_blank=True, required=False)
    line2 = serializers.CharField(max_length=200, allow_blank=True, required=False)
    city = serializers.CharField(max_length=100, allow_blank=True, required=False)
    province = serializers.CharField(max_length=2, allow_blank=True, required=False)
    region = serializers.CharField(max_length=100, allow_blank=True, required=False)
    postal_code = serializers.CharField(max_length=16, allow_blank=True, required=False)
    country = serializers.CharField(max_length=2, required=False)


class ContactWriteSerializer(serializers.Serializer[Any]):
    number = serializers.CharField(max_length=40, allow_blank=True, required=False)
    display_name = serializers.CharField(max_length=200, required=False)
    legal_name = serializers.CharField(max_length=200, allow_blank=True, required=False)
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=ContactRole.choices), required=False
    )
    bn = serializers.CharField(max_length=40, allow_blank=True, required=False)
    tax_id = serializers.CharField(max_length=40, allow_blank=True, required=False)
    currency = serializers.CharField(max_length=3, required=False)
    credit_limit = serializers.DecimalField(
        max_digits=18, decimal_places=2, allow_null=True, required=False
    )
    credit_mode = serializers.ChoiceField(choices=CreditMode.choices, required=False)
    t4a_flag = serializers.BooleanField(required=False)
    portal_enabled = serializers.BooleanField(required=False)
    statement_pref = serializers.ChoiceField(choices=StatementPreference.choices, required=False)
    language = serializers.CharField(max_length=8, required=False)
    custom_fields = serializers.DictField(required=False)
    sales_amounts_are = serializers.ChoiceField(choices=AmountsAre.choices, required=False)
    purchase_amounts_are = serializers.ChoiceField(choices=AmountsAre.choices, required=False)
    sales_account = serializers.UUIDField(allow_null=True, required=False)
    purchase_account = serializers.UUIDField(allow_null=True, required=False)
    sales_payment_term = serializers.UUIDField(allow_null=True, required=False)
    purchase_payment_term = serializers.UUIDField(allow_null=True, required=False)
    people = PersonSerializer(many=True, required=False)
    addresses = AddressSerializer(many=True, required=False)


def _apply(contact: Contact, data: dict[str, Any]) -> None:
    from numo9.ledger.models import Account

    for field in CONTACT_FIELDS:
        if field in data:
            setattr(contact, field, data[field])
    for field, model in ((f, Account) for f in ACCOUNT_DEFAULTS):
        if field in data:
            ref = data[field]
            found = None if ref is None else model.objects.filter(public_id=ref).first()
            if ref is not None and found is None:
                raise ValidationError({field: [_("This account doesn't exist.")]})
            setattr(contact, field, found)
    for field in TERM_DEFAULTS:
        if field in data:
            ref = data[field]
            term = None if ref is None else PaymentTerm.objects.filter(public_id=ref).first()
            if ref is not None and term is None:
                raise ValidationError({field: [_("This payment term doesn't exist.")]})
            setattr(contact, field, term)


def _sync(
    contact: Contact, model: Any, rows: list[dict[str, Any]], fields: tuple[str, ...], key: str
) -> None:
    """Replace the contact's people or addresses with ``rows`` (ids update, others are new)."""
    existing = {
        item.public_id: item
        for item in model.objects.filter(contact=contact, deleted_at__isnull=True)
    }
    keep = set()
    for index, row in enumerate(rows):
        item = existing.get(row.get("id")) if row.get("id") else None
        if row.get("id") and item is None:
            raise ValidationError(
                {f"{key}[{index}]": [_("This row doesn't belong to the contact.")]}
            )
        if item is None:
            item = model(organisation=contact.organisation, contact=contact)
        for field in fields:
            if field in row:
                setattr(item, field, row[field])
        try:
            item.save()
        except DjangoValidationError as error:
            raise drf_errors(error, prefix=f"{key}[{index}].") from None
        keep.add(item.public_id)
    for public_id, item in existing.items():
        if public_id not in keep:
            item.soft_delete()


def _save(contact: Contact, data: dict[str, Any]) -> Contact:
    people = data.pop("people", None)
    addresses = data.pop("addresses", None)
    with transaction.atomic():
        _apply(contact, data)
        try:
            contact.save()
        except DjangoValidationError as error:
            raise drf_errors(error) from None
        if people is not None:
            _sync(contact, ContactPerson, people, PERSON_FIELDS, "people")
        if addresses is not None:
            _sync(contact, Address, addresses, ADDRESS_FIELDS, "addresses")
    return _one(contact.public_id)


# ---- views ---------------------------------------------------------------------------------------


def _int(params: Any, name: str, default: int, low: int, high: int) -> int:
    raw = params.get(name)
    if raw in (None, ""):
        return default
    try:
        return max(low, min(high, int(raw)))
    except ValueError:
        raise ValidationError({name: [_("Use a whole number.")]}) from None


class ContactListView(APIView):
    queryset = Contact._base_manager.none()  # tenant sweep: rows of Contact

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="contacts_list",
        summary="Contacts, filtered by role and status",
        parameters=[
            OpenApiParameter("role", str, enum=list(ContactRole.values)),
            OpenApiParameter("status", str, enum=["active", "archived", "all"]),
            OpenApiParameter("q", str),
            OpenApiParameter("limit", int),
            OpenApiParameter("offset", int),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        params = request.query_params
        contacts = _queryset().order_by("display_name", "number", "pk")
        role = params.get("role")
        if role:
            if role not in ContactRole.values:
                raise ValidationError({"role": [_("Unknown role.")]})
            contacts = contacts.filter(roles__contains=[role])
        wanted = params.get("status", "active")
        if wanted in (ContactStatus.ACTIVE, ContactStatus.ARCHIVED):
            contacts = contacts.filter(status=wanted)
        text = (params.get("q") or "").strip()
        if text:
            contacts = contacts.filter(
                Q(display_name__icontains=text)
                | Q(legal_name__icontains=text)
                | Q(number__iexact=text)
                | Q(bn__startswith=text.replace(" ", ""))
                | Q(people__email__icontains=text, people__deleted_at__isnull=True)
            ).distinct()
        limit = _int(params, "limit", DEFAULT_LIMIT, 1, MAX_LIMIT)
        offset = _int(params, "offset", 0, 0, 10**9)
        count = contacts.count()
        page = list(contacts[offset : offset + limit])
        counts = {
            r: Contact.objects.filter(
                deleted_at__isnull=True, status=ContactStatus.ACTIVE, roles__contains=[r]
            ).count()
            for r in ContactRole.values
        }
        return Response(
            {
                "results": [summary(c) for c in page],
                "count": count,
                "next_offset": offset + limit if offset + limit < count else None,
                "role_counts": counts,
            }
        )

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="contacts_create",
        summary="Add a contact with its people and addresses",
        request=ContactWriteSerializer,
        responses={201: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        incoming = ContactWriteSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        data = dict(incoming.validated_data)
        if not data.get("display_name"):
            raise ValidationError({"display_name": [_("Enter the contact's name.")]})
        contact = Contact(organisation=current_org())
        contact.created_by_id = request.user.pk
        return Response(detail(_save(contact, data)), status=201)


class ContactDetailView(APIView):
    queryset = Contact._base_manager.none()

    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(operation_id="contacts_get", responses={200: OpenApiTypes.OBJECT})
    def get(self, request: Request, org: Any, public_id: Any) -> Response:
        return Response(detail(_one(public_id)))

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="contacts_update",
        summary="Edit a contact (people and addresses replace the lists when given)",
        request=ContactWriteSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def patch(self, request: Request, org: Any, public_id: Any) -> Response:
        contact = _one(public_id)
        incoming = ContactWriteSerializer(data=request.data, partial=True)
        incoming.is_valid(raise_exception=True)
        return Response(detail(_save(contact, dict(incoming.validated_data))))


class ContactArchiveView(APIView):
    queryset = Contact._base_manager.none()
    restore = False

    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="contacts_archive",
        summary="Archive (history kept) or restore a contact",
        request=None,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any, public_id: Any) -> Response:
        contact = _one(public_id)
        if self.restore:
            contact.unarchive()
        else:
            contact.archive()
        return Response(detail(_one(public_id)))


class ContactDuplicatesView(APIView):
    @requires_permission(CONTACTS_VIEW.key)
    @requires_feature(READ)
    @extend_schema(
        operation_id="contacts_duplicates",
        summary="Possible duplicates of what's being typed (name, email, BN, tax ID)",
        parameters=[
            OpenApiParameter("q", str, description="Name"),
            OpenApiParameter("email", str),
            OpenApiParameter("bn", str),
            OpenApiParameter("tax_id", str),
            OpenApiParameter("exclude", OpenApiTypes.UUID, description="The contact being edited"),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        params = request.query_params
        exclude = None
        if params.get("exclude"):
            exclude = Contact.objects.filter(public_id=params["exclude"]).first()
        matches = find_duplicates(
            name=params.get("q", ""),
            email=params.get("email", ""),
            bn=params.get("bn", ""),
            tax_id=params.get("tax_id", ""),
            exclude=exclude,
        )
        return Response(
            {
                "results": [
                    {
                        "contact": summary(m.contact),
                        "reasons": list(m.reasons),
                        "similarity": m.similarity,
                        "exact": m.is_exact,
                    }
                    for m in matches
                ]
            }
        )


# ---- merge (B-01-T12) ----------------------------------------------------------------------------


class MergeSerializer(serializers.Serializer[Any]):
    survivor = serializers.UUIDField()
    merged = serializers.UUIDField()
    field_sources = serializers.DictField(
        child=serializers.ChoiceField(choices=[("survivor", "survivor"), ("merged", "merged")]),
        required=False,
    )


def _pair(survivor: Any, merged: Any) -> tuple[Contact, Contact]:
    return _one(survivor), _one(merged)


def _refused(error: Any) -> ValidationError:
    return ValidationError(
        {"non_field_errors": [serializers.ErrorDetail(str(error), code=error.code)]}
    )


class ContactMergePreviewView(APIView):
    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="contacts_merge_preview",
        summary="What merging two contacts would move (records per kind)",
        parameters=[
            OpenApiParameter("survivor", OpenApiTypes.UUID, required=True),
            OpenApiParameter("merged", OpenApiTypes.UUID, required=True),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request: Request, org: Any) -> Response:
        from .merge import MergeRefused, preview

        incoming = MergeSerializer(data=request.query_params)
        incoming.is_valid(raise_exception=True)
        survivor, merged = _pair(
            incoming.validated_data["survivor"], incoming.validated_data["merged"]
        )
        try:
            rows = preview(survivor, merged)
        except MergeRefused as error:
            raise _refused(error) from None
        return Response({"survivor": detail(survivor), "merged": detail(merged), "records": rows})


class ContactMergeView(APIView):
    @requires_permission(CONTACTS_MANAGE.key)
    @requires_feature(WRITE)
    @extend_schema(
        operation_id="contacts_merge",
        summary="Merge one contact into another (one transaction; the merged one stays an alias)",
        request=MergeSerializer,
        responses={200: OpenApiTypes.OBJECT},
    )
    def post(self, request: Request, org: Any) -> Response:
        from .merge import MergeRefused, merge_contacts

        incoming = MergeSerializer(data=request.data)
        incoming.is_valid(raise_exception=True)
        survivor, merged = _pair(
            incoming.validated_data["survivor"], incoming.validated_data["merged"]
        )
        try:
            outcome = merge_contacts(
                survivor, merged, fields=incoming.validated_data.get("field_sources") or {}
            )
        except MergeRefused as error:
            raise _refused(error) from None
        except DjangoValidationError as error:
            raise drf_errors(error) from None
        return Response(
            {
                "survivor": detail(_one(survivor.public_id)),
                "moved": outcome["moved"],
                "kept": outcome["kept"],
            }
        )

"""Merge two contacts (B-01-T12).

``merge_contacts(survivor, merged, fields=…)`` keeps ``survivor`` and folds ``merged`` into it, in
**one transaction** (a failure anywhere rolls everything back):

1. the fields chosen from ``merged`` (``fields={"legal_name": "merged", …}``) are copied to the
   survivor; roles are the union of both;
2. every record that refers to ``merged`` is re-pointed to the survivor through the **reference
   registry** — or, when it can't move, kept pointing at ``merged``, which stays as an alias:
   posted journal lines are append-only (C-02), so they keep their contact and reports resolve the
   alias (``resolve()``);
3. ``merged`` becomes an archived alias: ``merged_into`` = survivor, its number and name kept, so
   an import by its number (B-03) or a link to it still finds the survivor;
4. one audit event ``contacts.contact.merged`` on the survivor with what moved, next to each
   record's own history (which is never rewritten).

Refused: the same contact, a contact already merged, different currencies (amounts in two
currencies can't be one balance — gap-20). ``preview()`` counts what would move (the merge dialog).

**Registry.** Every foreign key to ``Contact`` must be registered (``register_reference``) with
``move`` or ``keep``; ``tests/test_contacts_merge.py`` introspects the models and fails when one
isn't, so a new module can't silently leave records on a merged contact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from django.apps import apps
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from numo9.audit.service import record

from .models import Contact, ContactStatus

Policy = Literal["move", "keep"]


@dataclass(frozen=True)
class Reference:
    model: str  # app_label.ModelName
    field: str
    policy: Policy
    label: Any  # what the dialog calls these records


REGISTRY: dict[tuple[str, str], Reference] = {}


def register_reference(model: str, field: str, policy: Policy, label: Any) -> None:
    REGISTRY[(model, field)] = Reference(model, field, policy, label)


register_reference("contacts.ContactPerson", "contact", "move", _("people"))
register_reference("contacts.Address", "contact", "move", _("addresses"))
register_reference("contacts.ExemptionCertificate", "contact", "move", _("exemption certificates"))
register_reference("contacts.CreditOverride", "contact", "move", _("credit limit overrides"))
register_reference("contacts.StatementSend", "contact", "move", _("statements sent"))
register_reference("contacts.SupplierStatement", "contact", "move", _("supplier statements"))
register_reference("contacts.ActivityEvent", "contact", "move", _("activity"))
# Posted journal lines are append-only (C-02-T04): they keep the merged contact (an alias).
register_reference("ledger.JournalLine", "contact", "keep", _("journal lines"))

#: Fields that may be taken from the merged contact.
CHOOSABLE = (
    "display_name",
    "legal_name",
    "bn",
    "tax_id",
    "credit_limit",
    "credit_mode",
    "t4a_flag",
    "portal_enabled",
    "reminders_opt_out",
    "statement_pref",
    "language",
    "sales_account",
    "sales_payment_term",
    "sales_amounts_are",
    "purchase_account",
    "purchase_payment_term",
    "purchase_amounts_are",
)

MERGED = "contacts.contact.merged"


class MergeRefused(Exception):
    def __init__(self, message: Any, code: str) -> None:
        super().__init__(str(message))
        self.code = code


def references_to_contact() -> set[tuple[str, str]]:
    """Every (model, field) foreign key to Contact in the installed apps (self-reference aside)."""
    found = set()
    for relation in Contact._meta.related_objects:
        label = relation.related_model._meta.label
        if label != "contacts.Contact":
            found.add((label, relation.field.name))
    return found


def _queryset(reference: Reference, contact: Contact) -> Any:
    model = apps.get_model(reference.model)
    return model._base_manager.filter(**{reference.field: contact})


def preview(survivor: Contact, merged: Contact) -> list[dict[str, Any]]:
    """What a merge would do with each kind of record: ``[{records, count, moves}]``."""
    check(survivor, merged)
    rows = []
    for reference in REGISTRY.values():
        count = _queryset(reference, merged).count()
        if count:
            rows.append(
                {
                    "records": str(reference.label),
                    "count": count,
                    "moves": reference.policy == "move",
                }
            )
    return rows


def check(survivor: Contact, merged: Contact) -> None:
    if survivor.pk == merged.pk:
        raise MergeRefused(_("Choose two different contacts."), "contacts.merge.same")
    for contact in (survivor, merged):
        if contact.merged_into_id is not None:
            raise MergeRefused(
                _("%(contact)s was already merged into another contact.") % {"contact": contact},
                "contacts.merge.already_merged",
            )
    if survivor.currency != merged.currency:
        raise MergeRefused(
            _(
                "%(a)s uses %(x)s and %(b)s uses %(y)s: contacts in different currencies can't be "
                "merged."
            )
            % {"a": survivor, "x": survivor.currency, "b": merged, "y": merged.currency},
            "contacts.merge.currency",
        )


def merge_contacts(
    survivor: Contact, merged: Contact, *, fields: dict[str, str] | None = None
) -> dict[str, Any]:
    """Fold ``merged`` into ``survivor`` (module docstring); returns what moved."""
    with transaction.atomic():
        locked = {
            c.pk: c
            for c in Contact._base_manager.select_for_update().filter(
                pk__in=[survivor.pk, merged.pk]
            )
        }
        survivor, merged = locked[survivor.pk], locked[merged.pk]
        check(survivor, merged)

        for field, side in (fields or {}).items():
            if field not in CHOOSABLE:
                raise MergeRefused(
                    _("%(field)s can't be taken from the merged contact.") % {"field": field},
                    "contacts.merge.field",
                )
            if side == "merged":
                setattr(survivor, field, getattr(merged, field))
        survivor.roles = sorted(set(survivor.roles) | set(merged.roles))
        survivor.save()

        moved: dict[str, int] = {}
        kept: dict[str, int] = {}
        for reference in REGISTRY.values():
            rows = _queryset(reference, merged)
            if reference.policy == "move":
                count = 0
                for row in rows:
                    setattr(row, reference.field, survivor)
                    if reference.model == "contacts.ContactPerson":
                        row.is_primary = False  # the survivor keeps its primary person
                    row.save()
                    count += 1
                if count:
                    moved[reference.model] = count
            else:
                count = rows.count()
                if count:
                    kept[reference.model] = count

        merged.merged_into = survivor
        merged.merged_at = timezone.now()
        merged.status = ContactStatus.ARCHIVED
        merged.archived_at = merged.archived_at or merged.merged_at
        merged.save()
        record(
            MERGED,
            obj=survivor,
            meta={
                "merged": {
                    "id": str(merged.public_id),
                    "number": merged.number,
                    "name": merged.display_name,
                },
                "moved": moved,
                "kept_on_alias": kept,
                "fields_from_merged": sorted(
                    f for f, side in (fields or {}).items() if side == "merged"
                ),
            },
        )
    return {"survivor": survivor, "merged": merged, "moved": moved, "kept": kept}


def resolve(contact: Contact) -> Contact:
    """The contact a merged alias points to (itself when it wasn't merged)."""
    seen = 0
    while contact.merged_into_id is not None and seen < 10:
        contact = Contact._base_manager.get(pk=contact.merged_into_id)
        seen += 1
    return contact

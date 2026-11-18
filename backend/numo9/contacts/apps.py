from typing import Any

from django.apps import AppConfig
from django.db.models.signals import post_save


class ContactsConfig(AppConfig):
    """Contacts: contact model, people, addresses, duplicate detection, payment terms (B-01)."""

    name = "numo9.contacts"
    label = "contacts"
    verbose_name = "Contacts"

    def ready(self) -> None:
        from numo9.imports.fields import register_entity
        from numo9.tenancy.models import Organisation

        from .importing import CONTACT, PERSON
        from .supplier_statements import SUPPLIER_STATEMENT_LINE

        # What a contacts file can map to (B-03-T03).
        register_entity(CONTACT)
        register_entity(PERSON)

        # Import runs (B-03-T07): the contacts importer behind the dry run and the apply job.
        from numo9.imports.runs import register_runner

        from .import_engine import import_contacts

        register_runner(CONTACT.key, import_contacts)
        # Supplier statement lines (B-02-T07).
        register_entity(SUPPLIER_STATEMENT_LINE)

        # Tenant sweep (A-01-T09): the contacts API needs a contact (B-01-T11).
        from numo9.tenancy.sweep import SWEEP_FACTORIES

        SWEEP_FACTORIES["contacts.Contact"] = _sweep_contact

        # Every new organisation starts with the default payment terms (B-01-T05).
        post_save.connect(
            _seed_new_organisation, sender=Organisation, dispatch_uid="contacts_seed_terms"
        )


def _seed_new_organisation(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    if created and not kwargs.get("raw"):
        from .models import seed_payment_terms

        seed_payment_terms(instance)


def _sweep_contact(organisation: Any) -> Any:
    from numo9.tenancy.context import org_context

    from .models import Contact

    with org_context(organisation):
        found = Contact._base_manager.filter(organisation=organisation, number="SWEEP-1").first()
        if found is not None:
            return found
        contact = Contact(
            organisation=organisation,
            number="SWEEP-1",
            display_name="Sweep Supply Ltd.",
            roles=["customer"],
        )
        contact.save()
        return contact

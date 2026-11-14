from typing import Any

from django.apps import AppConfig
from django.db.models.signals import post_save


class ContactsConfig(AppConfig):
    """Contacts: contact model, people, addresses, duplicate detection, payment terms (B-01)."""

    name = "numo9.contacts"
    label = "contacts"
    verbose_name = "Contacts"

    def ready(self) -> None:
        from numo9.tenancy.models import Organisation

        # Every new organisation starts with the default payment terms (B-01-T05).
        post_save.connect(
            _seed_new_organisation, sender=Organisation, dispatch_uid="contacts_seed_terms"
        )


def _seed_new_organisation(sender: Any, instance: Any, created: bool, **kwargs: Any) -> None:
    if created and not kwargs.get("raw"):
        from .models import seed_payment_terms

        seed_payment_terms(instance)

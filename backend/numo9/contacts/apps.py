from django.apps import AppConfig


class ContactsConfig(AppConfig):
    """Contacts: contact model, people, addresses, duplicate detection (B-01)."""

    name = "numo9.contacts"
    label = "contacts"
    verbose_name = "Contacts"

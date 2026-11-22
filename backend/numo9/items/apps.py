from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ItemsConfig(AppConfig):
    """Items (H-01): products and services picked on document lines. D-01-T02 adds the minimal
    stub the document grid needs; H-01 adds pricing, inventory tracking and the item UI."""

    name = "numo9.items"
    label = "items"
    verbose_name = _("Items")

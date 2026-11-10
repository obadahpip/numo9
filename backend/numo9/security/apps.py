from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class SecurityConfig(AppConfig):
    name = "numo9.security"
    label = "security"
    verbose_name = _("Security")

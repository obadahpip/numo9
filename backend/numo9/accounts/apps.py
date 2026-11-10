from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    name = "numo9.accounts"
    label = "accounts"
    verbose_name = _("Accounts")

    def ready(self) -> None:
        # Hashed, show-once recovery codes instead of allauth's seed-derived ones (A-02-T05).
        from . import mfa

        mfa.install()

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

        # Known devices and the new-device email at every sign-in (A-02-T07).
        from django.contrib.auth.signals import user_logged_in

        from .devices import on_logged_in

        user_logged_in.connect(on_logged_in, dispatch_uid="numo9.accounts.devices")

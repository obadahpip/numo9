from django.apps import AppConfig
from django.core import checks
from django.db.backends.signals import connection_created
from django.utils.translation import gettext_lazy as _


class TenancyConfig(AppConfig):
    name = "numo9.tenancy"
    label = "tenancy"
    verbose_name = _("Tenancy")

    def ready(self) -> None:
        from .checks import check_business_models_are_org_owned
        from .rls import install_guc_wrapper

        checks.register(check_business_models_are_org_owned, checks.Tags.models)
        # app.current_org on every PostgreSQL statement (A-01-T12).
        connection_created.connect(install_guc_wrapper, dispatch_uid="numo9.tenancy.rls")

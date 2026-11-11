"""CI canary URLconf (A-03-T06): the real project URLs plus one endpoint without a declaration.

``manage.py permission_check --urlconf tests.testapp.rbac_urls_ci_canary`` must fail; the CI
backend job runs it and goes red if it does not (the gate would be broken).
"""

from django.urls import path

from numo9.urls import urlpatterns as project

from . import rbac_api

urlpatterns = [
    *project,
    path("api/v1/ci-canary/", rbac_api.CanaryUndeclared.as_view()),
]

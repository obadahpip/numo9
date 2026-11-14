"""CI canary URLconf (U-01-T07): the real project URLs plus one business endpoint without a
feature key.

``manage.py check_feature_keys --urlconf tests.testapp.feature_urls_ci_canary`` must fail; the
CI backend job runs it and goes red if it does not (the gate would be broken).
"""

from django.urls import path

from numo9.urls import urlpatterns as project

from . import feature_api

urlpatterns = [
    *project,
    path("api/v1/o/<uuid:org>/ci-canary/", feature_api.CanaryUndeclared.as_view()),
]

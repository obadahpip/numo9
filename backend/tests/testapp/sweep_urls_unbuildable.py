from django.urls import re_path

from . import api
from .sweep_urls import urlpatterns as clean

urlpatterns = [*clean, re_path(r"^api/v1/o/[^/]+/widgets-by-regex/$", api.WidgetList.as_view())]

from django.urls import path

from . import api
from .sweep_urls import urlpatterns as clean

urlpatterns = [
    *clean,
    path("api/v1/o/<uuid:org>/leaky-widgets/<uuid:public_id>/", api.LeakyWidgetDetail.as_view()),
]

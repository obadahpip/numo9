from django.urls import path

from .sweep_urls import ping
from .sweep_urls import urlpatterns as clean

urlpatterns = [*clean, path("api/v1/widgets-everywhere/", ping)]

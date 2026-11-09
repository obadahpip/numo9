"""Test-only admin registration of an organisation-owned model (A-01-T15)."""

from django.contrib import admin

from numo9.tenancy.admin import OrgOwnedAdmin

from .models import Widget

admin.site.register(Widget, OrgOwnedAdmin)

"""Test settings plus a fixture app holding a plain model (used in a subprocess, A-01-T08)."""

from numo9.settings.test import *  # noqa: F403
from numo9.settings.test import INSTALLED_APPS

INSTALLED_APPS = [*INSTALLED_APPS, "tests.plain_model_app"]

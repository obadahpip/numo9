"""Migrations of django-waffle's own models (U-06-T12), in place of waffle's.

Numo9 swaps waffle's flag for ``platform.FeatureFlag`` (``WAFFLE_FLAG_MODEL``), but waffle's own
migrations create its ``waffle_flag`` tables regardless — rows nobody reads, with a foreign key to
users that breaks table flushes. ``MIGRATION_MODULES["waffle"]`` points here: only ``Switch`` and
``Sample`` are created. Regenerate with ``makemigrations waffle`` after upgrading django-waffle.
"""

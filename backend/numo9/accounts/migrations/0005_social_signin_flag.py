"""A-02-T16: the ``auth.social_signin`` feature flag, off for everyone (switched in the console)."""

from django.db import migrations

FLAG = "auth.social_signin"
NOTE = "Social sign-in (Google, Microsoft) on the sign-in page — A-02-T16. Off by default."


def create_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    FeatureFlag = apps.get_model("platform", "FeatureFlag")
    FeatureFlag.objects.get_or_create(name=FLAG, defaults={"everyone": False, "note": NOTE})


def remove_flag(apps, schema_editor):  # type: ignore[no-untyped-def]
    apps.get_model("platform", "FeatureFlag").objects.filter(name=FLAG).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_known_device"),
        ("platform", "0003_feature_flags"),
    ]

    operations = [migrations.RunPython(create_flag, remove_flag)]

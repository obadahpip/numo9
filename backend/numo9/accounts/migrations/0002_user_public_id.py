"""User.public_id (A-03-T07): a random id for APIs instead of the sequential primary key.

Three steps so existing rows each get their own UUID: add the column nullable, fill it row by
row, then make it required and unique.
"""

import uuid
from typing import Any

from django.db import migrations, models


def fill_public_ids(apps: Any, schema_editor: Any) -> None:
    User = apps.get_model("accounts", "User")
    for user in User.objects.filter(public_id__isnull=True).only("pk").iterator():
        User.objects.filter(pk=user.pk).update(public_id=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="public_id",
            field=models.UUIDField(editable=False, null=True, verbose_name="public ID"),
        ),
        migrations.RunPython(fill_public_ids, migrations.RunPython.noop, elidable=False),
        migrations.AlterField(
            model_name="user",
            name="public_id",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, unique=True, verbose_name="public ID"
            ),
        ),
    ]

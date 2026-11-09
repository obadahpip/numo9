from django.db import migrations

from numo9.tenancy.rls import EnableOrgRLS


class Migration(migrations.Migration):
    """Row-level security on the test Widget table (A-01-T12); Gadget stays without RLS."""

    dependencies = [("testapp", "0001_initial")]

    operations = [EnableOrgRLS("testapp_widget")]

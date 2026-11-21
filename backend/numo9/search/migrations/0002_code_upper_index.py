"""A-09-T10: code matches at a million documents — exact (``54`` → 54) and prefix (``54`` → 5400,
in code order) — read ``upper(code::text) COLLATE "C"`` from this index (a range scan in order)."""

from django.db import migrations

from numo9.audit.pg import PostgresOnly


class Migration(migrations.Migration):
    dependencies = [("search", "0001_search_document")]

    operations = [
        PostgresOnly(
            sql=(
                "CREATE INDEX search_doc_code_upper_idx ON search_searchdocument "
                '(organisation_id, (upper(code::text) COLLATE "C"))'
            ),
            reverse_sql="DROP INDEX IF EXISTS search_doc_code_upper_idx",
        ),
    ]

"""``audit_event`` is append-only at the database (A-04-T02).

1. Privileges: ``UPDATE``, ``DELETE`` and ``TRUNCATE`` are revoked from ``PUBLIC`` and from the
   role running the migrations (the table owner, which is the application role in staging and
   production). The application can only ``INSERT`` and ``SELECT``.
2. Trigger ``audit_event_append_only`` (``BEFORE UPDATE OR DELETE``, every row) raises
   ``insufficient_privilege`` — it holds even for roles that bypass privileges (superusers,
   a later ``GRANT ALL`` by mistake) and for every partition once S-06-T03 partitions the table
   (row triggers on a partitioned parent are created on each partition).

``TRUNCATE`` is not a row operation and is left to the privilege: only a superuser can still
empty the table (the test runner does, between transactional tests).
"""

from django.db import migrations

FORWARD = """
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_event FROM PUBLIC;
REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_event FROM CURRENT_USER;

CREATE FUNCTION audit_event_refuse_change() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_event is append-only: % is not allowed', TG_OP
        USING ERRCODE = 'insufficient_privilege',
              HINT = 'Audit events are never changed or removed (A-04).';
END;
$$;

CREATE TRIGGER audit_event_append_only
    BEFORE UPDATE OR DELETE ON audit_event
    FOR EACH ROW EXECUTE FUNCTION audit_event_refuse_change();
"""

BACKWARD = """
DROP TRIGGER IF EXISTS audit_event_append_only ON audit_event;
DROP FUNCTION IF EXISTS audit_event_refuse_change();
GRANT UPDATE, DELETE, TRUNCATE ON TABLE audit_event TO CURRENT_USER;
"""


class Migration(migrations.Migration):
    dependencies = [("audit", "0001_audit_event")]

    operations = [migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD)]

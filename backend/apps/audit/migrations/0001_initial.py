import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

CREATE_APPEND_ONLY_TRIGGER = """
CREATE OR REPLACE FUNCTION audit_reject_event_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit events are append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_event_append_only
BEFORE UPDATE OR DELETE ON audit_auditevent
FOR EACH ROW EXECUTE FUNCTION audit_reject_event_mutation();
"""

DROP_APPEND_ONLY_TRIGGER = """
DROP TRIGGER IF EXISTS audit_event_append_only ON audit_auditevent;
DROP FUNCTION IF EXISTS audit_reject_event_mutation();
"""


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("actor_display_name", models.CharField(max_length=255)),
                ("actor_email", models.EmailField(blank=True, max_length=254)),
                ("actor_role", models.CharField(max_length=32)),
                ("section", models.CharField(max_length=32)),
                ("action", models.CharField(max_length=100)),
                ("object_type", models.CharField(max_length=100)),
                ("object_id", models.CharField(max_length=64)),
                ("object_label", models.CharField(max_length=255)),
                ("result", models.CharField(default="success", max_length=32)),
                ("description", models.TextField(blank=True)),
                ("before", models.JSONField(default=dict)),
                ("after", models.JSONField(default=dict)),
                ("note", models.TextField(blank=True)),
                ("correlation_id", models.CharField(max_length=128)),
                ("occurred_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-occurred_at", "-id"),
                "indexes": [
                    models.Index(fields=["-occurred_at", "-id"], name="audit_occurred_id_idx"),
                    models.Index(fields=["section", "-occurred_at"], name="audit_section_time_idx"),
                    models.Index(fields=["actor", "-occurred_at"], name="audit_actor_time_idx"),
                    models.Index(fields=["action", "-occurred_at"], name="audit_action_time_idx"),
                ],
            },
        ),
        migrations.RunSQL(CREATE_APPEND_ONLY_TRIGGER, DROP_APPEND_ONLY_TRIGGER),
    ]

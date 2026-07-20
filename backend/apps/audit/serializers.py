from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.audit.models import AuditEvent
from apps.audit.registry import AuditSection


def snapshot_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for field in sorted(before.keys() | after.keys()):
        previous = before.get(field)
        current = after.get(field)
        if previous != current:
            changes.append({"field": field, "before": previous, "after": current})
    return changes


class AuditActorSerializer(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    display_name = serializers.CharField()
    email = serializers.EmailField(allow_blank=True)
    role = serializers.CharField()


class AuditObjectSerializer(serializers.Serializer):
    type = serializers.CharField()
    id = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]


class AuditChangeSerializer(serializers.Serializer):
    field = serializers.CharField()
    before = serializers.JSONField(allow_null=True)
    after = serializers.JSONField(allow_null=True)


class AuditEventListItemSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    object = serializers.SerializerMethodField()

    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "occurred_at",
            "actor",
            "section",
            "action",
            "object",
            "result",
            "description",
        )

    @extend_schema_field(AuditActorSerializer)
    def get_actor(self, event: AuditEvent) -> dict[str, Any]:
        return {
            "id": event.actor_id,
            "display_name": event.actor_display_name,
            "email": event.actor_email,
            "role": event.actor_role,
        }

    @extend_schema_field(AuditObjectSerializer)
    def get_object(self, event: AuditEvent) -> dict[str, str]:
        return {
            "type": event.object_type,
            "id": event.object_id,
            "label": event.object_label,
        }


class AuditEventDetailSerializer(AuditEventListItemSerializer):
    changes = serializers.SerializerMethodField()

    class Meta(AuditEventListItemSerializer.Meta):
        fields = AuditEventListItemSerializer.Meta.fields + (  # type: ignore[assignment]
            "before",
            "after",
            "changes",
            "note",
            "correlation_id",
        )

    @extend_schema_field(AuditChangeSerializer(many=True))
    def get_changes(self, event: AuditEvent) -> list[dict[str, Any]]:
        return snapshot_changes(event.before, event.after)


class AuditEventListResponseSerializer(serializers.Serializer):
    events = AuditEventListItemSerializer(many=True)
    next_cursor = serializers.UUIDField(allow_null=True)


class AuditEventFilterSerializer(serializers.Serializer):
    search = serializers.CharField(required=False, allow_blank=True, max_length=255)
    actor_id = serializers.IntegerField(required=False, min_value=1)
    section = serializers.ChoiceField(required=False, choices=[item.value for item in AuditSection])
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)
    cursor = serializers.UUIDField(required=False)

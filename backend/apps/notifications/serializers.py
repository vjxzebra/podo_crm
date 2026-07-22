from typing import Any

from rest_framework import serializers

from apps.notifications.models import NotificationKind, NotificationTone


class NotificationFilterSerializer(serializers.Serializer[Any]):
    status = serializers.ChoiceField(
        choices=("all", "unread"),
        default="all",
        required=False,
    )
    cursor = serializers.CharField(required=False, allow_blank=False, max_length=500)


class NotificationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=NotificationKind.choices)
    title = serializers.CharField()
    message = serializers.CharField()
    tone = serializers.ChoiceField(choices=NotificationTone.choices)
    is_important = serializers.BooleanField()
    deep_link = serializers.CharField()
    occurred_at = serializers.DateTimeField()
    created_at = serializers.DateTimeField()
    read_at = serializers.DateTimeField(allow_null=True)
    is_read = serializers.BooleanField()


class NotificationListResponseSerializer(serializers.Serializer[Any]):
    notifications = NotificationSerializer(many=True)
    total_count = serializers.IntegerField(min_value=0)
    unread_count = serializers.IntegerField(min_value=0)
    next_cursor = serializers.CharField(allow_null=True)


class NotificationMarkAllResponseSerializer(serializers.Serializer[Any]):
    marked_count = serializers.IntegerField(min_value=0)
    unread_count = serializers.IntegerField(min_value=0)

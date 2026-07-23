from typing import TypedDict

from django.db.models import Count, Q, QuerySet

from apps.accounts.models import User
from apps.notifications.models import Notification


class NotificationCounts(TypedDict):
    total_count: int
    unread_count: int


def notifications_visible_to(actor: User) -> QuerySet[Notification]:
    return Notification.objects.filter(recipient=actor).only(
        "id",
        "kind",
        "title",
        "message",
        "tone",
        "is_important",
        "deep_link",
        "occurred_at",
        "created_at",
        "read_at",
    )


def notification_counts(actor: User) -> NotificationCounts:
    counts = Notification.objects.filter(recipient=actor).aggregate(
        total_count=Count("id"),
        unread_count=Count("id", filter=Q(read_at__isnull=True)),
    )
    return {
        "total_count": int(counts["total_count"] or 0),
        "unread_count": int(counts["unread_count"] or 0),
    }

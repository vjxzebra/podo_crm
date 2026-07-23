from django.db.models import QuerySet

from apps.accounts.models import User, UserRole
from apps.work_items.models import WorkItem


def work_items_visible_to(actor: User) -> QuerySet[WorkItem]:
    queryset = WorkItem.objects.select_related(
        "assignee",
        "patient",
        "created_by",
        "completed_by",
    )
    if actor.role == UserRole.PODOLOGIST:
        return queryset.filter(assignee=actor)
    return queryset


def active_work_item_assignees() -> QuerySet[User]:
    return User.objects.filter(is_active=True).order_by("last_name", "first_name", "email", "pk")

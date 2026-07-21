from django.contrib import admin

from apps.work_items.models import WorkItem


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "kind",
        "assignee",
        "due_at",
        "is_important",
        "is_completed",
    )
    list_filter = ("kind", "is_important", "is_completed")
    search_fields = ("title", "comment", "patient__first_name", "patient__last_name")

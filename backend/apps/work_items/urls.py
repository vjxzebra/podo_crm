from django.urls import path

from apps.work_items.views import WorkItemDetailView, WorkItemListCreateView

urlpatterns = [
    path("work-items", WorkItemListCreateView.as_view(), name="work-item-list-create"),
    path(
        "work-items/<uuid:work_item_id>",
        WorkItemDetailView.as_view(),
        name="work-item-detail",
    ),
]

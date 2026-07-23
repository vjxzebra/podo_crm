from django.urls import path

from apps.audit.views import AuditEventDetailView, AuditEventExportView, AuditEventListView

urlpatterns = [
    path(
        "audit-events/export",
        AuditEventExportView.as_view(),
        name="audit-event-export",
    ),
    path("audit-events", AuditEventListView.as_view(), name="audit-event-list"),
    path(
        "audit-events/<uuid:event_id>",
        AuditEventDetailView.as_view(),
        name="audit-event-detail",
    ),
]

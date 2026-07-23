from django.urls import path

from apps.scheduling.views import (
    AppointmentAvailabilityView,
    AppointmentCancelView,
    AppointmentDetailView,
    AppointmentListCreateView,
    AppointmentStatusTransitionView,
    CalendarView,
)

urlpatterns = [
    path("calendar", CalendarView.as_view(), name="calendar"),
    path("appointments", AppointmentListCreateView.as_view(), name="appointment-list-create"),
    path(
        "appointments/availability",
        AppointmentAvailabilityView.as_view(),
        name="appointment-availability",
    ),
    path(
        "appointments/<uuid:appointment_id>",
        AppointmentDetailView.as_view(),
        name="appointment-detail",
    ),
    path(
        "appointments/<uuid:appointment_id>/status",
        AppointmentStatusTransitionView.as_view(),
        name="appointment-status-transition",
    ),
    path(
        "appointments/<uuid:appointment_id>/cancel",
        AppointmentCancelView.as_view(),
        name="appointment-cancel",
    ),
]

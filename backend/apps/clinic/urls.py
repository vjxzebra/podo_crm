from django.urls import path

from apps.clinic.views import (
    ClinicLogoView,
    ClinicProfileView,
    RoomDetailView,
    RoomListCreateView,
    ServiceDetailView,
    ServiceListCreateView,
)

urlpatterns = [
    path("clinic-profile", ClinicProfileView.as_view(), name="clinic-profile"),
    path("clinic-profile/logo", ClinicLogoView.as_view(), name="clinic-logo"),
    path("rooms", RoomListCreateView.as_view(), name="room-list-create"),
    path("rooms/<uuid:room_id>", RoomDetailView.as_view(), name="room-detail"),
    path("services", ServiceListCreateView.as_view(), name="service-list-create"),
    path("services/<uuid:service_id>", ServiceDetailView.as_view(), name="service-detail"),
]

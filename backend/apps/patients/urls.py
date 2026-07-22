from django.urls import path

from apps.patients.history_views import (
    PatientPhotoArchiveView,
    PatientRecommendationListView,
    PatientVisitHistoryView,
)
from apps.patients.views import PatientDetailView, PatientListCreateView

urlpatterns = [
    path("patients", PatientListCreateView.as_view(), name="patient-list-create"),
    path("patients/<uuid:patient_id>", PatientDetailView.as_view(), name="patient-detail"),
    path(
        "patients/<uuid:patient_id>/visits",
        PatientVisitHistoryView.as_view(),
        name="patient-visit-history",
    ),
    path(
        "patients/<uuid:patient_id>/photos",
        PatientPhotoArchiveView.as_view(),
        name="patient-photo-archive",
    ),
    path(
        "patients/<uuid:patient_id>/recommendations",
        PatientRecommendationListView.as_view(),
        name="patient-recommendation-list",
    ),
]

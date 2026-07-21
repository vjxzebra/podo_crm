from django.urls import path

from apps.patients.views import PatientDetailView, PatientListCreateView

urlpatterns = [
    path("patients", PatientListCreateView.as_view(), name="patient-list-create"),
    path("patients/<uuid:patient_id>", PatientDetailView.as_view(), name="patient-detail"),
]
